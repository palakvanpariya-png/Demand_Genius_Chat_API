# app/services/chat_service.py
"""
OPTIONAL UPDATE: How to pass conversation context to parser
You can implement this later when ready to enable context awareness
"""

from typing import Dict, Any, Optional, List
from loguru import logger

from ..core.query_parser import SmartQueryParser
from ..core.query_builder import MongoQueryExecutor
from ..core.advisory.advisor_manager import AdvisoryOrchestrator
from ..services.schema_service import schema_service
from ..services.session_service import session_service
from ..models.query import QueryResult
from ..models.database import DatabaseResponse
from ..models.chat import ChatResponse, DataSummary
from ..config.setting import settings


class ChatService:
    """
    Main chat service with optional context-aware parsing
    """
    
    def __init__(self):
        self.query_parser = SmartQueryParser()
        self.query_executor = MongoQueryExecutor()
        self.advisor = AdvisoryOrchestrator()
        
    async def process_chat_message(
        self,
        message: str,
        tenant_id: str,
        session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process complete chat pipeline with optional context awareness
        """
        try:
            # OPTIONAL: Get conversation context for parser
            conversation_history = None
            if session_id:
                conversation_history = await self._get_parsing_context(session_id)
            
            # Step 1: Parse query WITH CONTEXT (if available)
            logger.info(f"Parsing query for tenant {tenant_id}: {message[:50]}...")
            query_result = self.query_parser.parse(
                message, 
                tenant_id,
                conversation_history  # NEW: Pass context to parser
            )
            logger.info(f"Parsed query result: {query_result}")
            
            # Log the generated description
            if query_result.description:
                logger.info(f"Query description: {query_result.description}")
            
            # Step 2: Get tenant schema (UNCHANGED)
            logger.info("Fetching tenant schema")
            tenant_schema = await schema_service.get_tenant_schema(tenant_id)
            
            # Step 3: Execute query if data needed (UNCHANGED)
            if query_result.needs_data or query_result.operation != "pure_advisory":
                logger.info(f"Executing {query_result.operation} query")
                db_response = self.query_executor.execute_query_from_result(query_result)
            else:
                logger.info("Skipping database query for pure advisory")
                db_response = DatabaseResponse(
                    success=True,
                    data={"message": "Advisory operation - no database query executed"},
                    advisory_mode=True,
                    operation=query_result.operation
                )
            
            # Step 4: Generate advisory response (UNCHANGED)
            logger.info("Generating advisory insights")
            advisory_response_dict = self.advisor.generate_response(
                operation=query_result.operation,
                query_result=query_result,
                db_response=db_response,
                tenant_schema=tenant_schema,
                original_query=message,
                session_id=session_id,
                tenant_id=tenant_id
            )
            
            # Step 5: Store interaction WITH PARSED RESULT for future context
            if session_id:
                await self._store_interaction_with_context(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    message=message,
                    response=advisory_response_dict,
                    query_result=query_result  # NEW: Store parsed result
                )
            
            # Step 6: Create response (UNCHANGED)
            response = ChatResponse(
                success=True,
                response=advisory_response_dict["response"],
                suggested_questions=advisory_response_dict["suggested_questions"],
                confidence=advisory_response_dict["confidence"],
                operation=query_result.operation,
                session_id=session_id,
                data_summary=self._create_data_summary(db_response).dict(),
                db_response=db_response
            )
            
            logger.info(f"Chat processing completed")
            return response
            
        except Exception as e:
            logger.error(f"Chat processing failed for tenant {tenant_id}: {e}")
            return ChatResponse(
                success=False,
                error=str(e),
                response="I encountered an issue processing your request. Please try rephrasing your question.",
                suggested_questions=[
                    "Show me my content overview",
                    "What content categories do I have?",
                    "Help me understand my content distribution"
                ],
                confidence="low",
                operation="error",
                session_id=session_id
            )
    
    async def _get_parsing_context(self, session_id: str) -> List[Dict]:
        """Get last 2 queries and their parsed results for context"""
        try:
            recent_interactions = self.advisor.session_handler.get_recent_context(
                session_id, 
                limit=2
            )
            
            if not recent_interactions:
                logger.debug(f"No context found for session {session_id}")
                return None
            
            # Format for parser
            context = []
            for interaction in recent_interactions:
                parsed_result = interaction.get("parsed_result")
                if parsed_result:
                    context.append({
                        "query": interaction.get("message", ""),
                        "parsed_result": parsed_result
                    })
            
            if context:
                logger.info(f"Using context from {len(context)} previous interactions")  # ✅ ADD THIS LOG
            
            return context if context else None
            
        except Exception as e:
            logger.error(f"Failed to get parsing context: {e}")
            return None
    
    async def _store_interaction_with_context(
    self,
    session_id: str,
    tenant_id: str,
    message: str,
    response: Dict[str, Any],
    query_result: QueryResult
):
        """
        Store interaction with full parsed result for future context
        """
        try:
            # Convert QueryResult to dict matching session_handler expected structure
            parsed_result_dict = {
                "operation": query_result.operation,
                "filters": {
                    k: {
                        "include": v.include, 
                        "exclude": v.exclude
                    } 
                    for k, v in query_result.filters.items()
                },
                "description": query_result.description,
                "route": query_result.route,
                "confidence": query_result.confidence,
                "semantic_terms": query_result.semantic_terms or []
            }
            
            # Store in session handler WITH parsed result
            self.advisor.session_handler.store_interaction(
                session_id=session_id,
                query=message,
                response=response,
                operation=query_result.operation,
                tenant_id=tenant_id,
                parsed_result=parsed_result_dict  # ✅ NOW PASSING IT
            )
            
            logger.debug(f"Stored interaction with parsed result for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store interaction with context: {e}")
    
    def _create_data_summary(self, db_response: DatabaseResponse) -> DataSummary:
        """Create summary of database response using model - UNCHANGED"""
        if not db_response.success:
            return DataSummary(
                type="error",
                error=True,
                message=db_response.error
            )
        
        if getattr(db_response, 'advisory_mode', False):
            return DataSummary(
                type="advisory",
                message="No database query performed"
            )
        
        if db_response.operation in ["list", "semantic"]:
            return DataSummary(
                type="content_list",
                count=len(db_response.data) if db_response.data else 0,
                total=db_response.total_count or 0,
                has_more=getattr(db_response, 'has_next', False)
            )
        elif db_response.operation == "distribution":
            return DataSummary(
                type="distribution",
                categories=len(db_response.data) if db_response.data else 0,
                fields=db_response.distribution_fields or []
            )
        else:
            return DataSummary(
                type="unknown",
                operation=db_response.operation
            )

# Global service instance
chat_service = ChatService()