# app/services/chat_service.py
from typing import Dict, Any, Optional
import logging
from loguru import logger

from ..core.query_parser import SmartQueryParser
from ..core.query_builder import MongoQueryExecutor
from ..core.advisory_answer import IntelligentAdvisor
from ..services.schema_service import schema_service
from ..services.session_service import session_service
from ..models.query import QueryResult
from ..models.database import DatabaseResponse
from ..models.chat import ChatResponse
from ..config.settings import settings

# logger = logging.getLogger(__name__)

class ChatService:
    """
    Main chat service that orchestrates the complete pipeline:
    Natural Language → Parse → Execute → Advisory Response
    """
    
    def __init__(self):
        self.query_parser = SmartQueryParser()
        self.query_executor = MongoQueryExecutor()
        self.advisor = IntelligentAdvisor()
        
    async def process_chat_message(
        self,
        message: str,
        tenant_id: str,
        session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process complete chat pipeline
        
        Args:
            message: User's natural language query
            tenant_id: Tenant ID for context
            session_id: Optional session ID for conversation context
            
        Returns:
            ChatResponse with advisory insights
        """
        try:
            # Step 1: Parse natural language query
            logger.info(f"Parsing query for tenant {tenant_id}: {message[:50]}...")
            query_result = self.query_parser.parse(message, tenant_id)
            logger.info(f"results : {query_result}")
            
            # Step 2: Execute database query (if needed)
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
            
            # Step 3: Get tenant schema for advisory context
            logger.info("Fetching tenant schema")
            tenant_schema = await schema_service.get_tenant_schema(tenant_id)
            
            # Step 4: Generate advisory response
            logger.info("Generating advisory insights")
            try:
                logger.info(f"Query result type: {type(query_result)}")
                logger.info(f"DB response type: {type(db_response)}")
                logger.info(f"Tenant schema keys: {list(tenant_schema.keys())}")
                
                advisory_response = self.advisor.generate_advisory_response(
                    operation=query_result.operation,
                    query_result=query_result,
                    db_response=db_response,
                    tenant_schema=tenant_schema,
                    original_query=message,
                    session_id=session_id
                )
                logger.info(f"Advisory response generated: {type(advisory_response)}")
                
            except Exception as e:
                logger.error(f"Advisory generation failed with: {e}")
                logger.error(f"Error type: {type(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            advisory_response = self.advisor.generate_advisory_response(
                operation=query_result.operation,
                query_result=query_result,
                db_response=db_response,
                tenant_schema=tenant_schema,
                original_query=message,
                session_id=session_id
            )
            
            # Step 5: Store interaction in session (if session_id provided)
            if session_id:
                await session_service.store_interaction(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    message=message,
                    response=advisory_response
                )
            
            # Step 6: Create structured response
            response = ChatResponse(
                success=True,
                response=advisory_response["response"],
                suggested_questions=advisory_response["suggested_questions"],
                confidence=advisory_response["confidence"],
                operation=query_result.operation,
                session_id=session_id,
                data_summary=self._create_data_summary(db_response),
                db_response=db_response
            )
            
            logger.info(f"Chat processing completed successfully for tenant {tenant_id}")
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
    
    def _create_data_summary(self, db_response: DatabaseResponse) -> Optional[Dict[str, Any]]:
        """Create summary of database response for API"""
        if not db_response.success:
            return {"error": True, "message": db_response.error}
        
        if db_response.advisory_mode:
            return {"type": "advisory", "message": "No database query performed"}
        
        if db_response.operation == "list":
            return {
                "type": "content_list",
                "count": len(db_response.data) if db_response.data else 0,
                "total": db_response.total_count or 0,
                "has_more": db_response.has_next or False
            }
        elif db_response.operation == "distribution":
            return {
                "type": "distribution",
                "categories": len(db_response.data) if db_response.data else 0,
                "fields": db_response.distribution_fields or []
            }
        elif db_response.operation == "semantic":
            return {
                "type": "semantic_search",
                "matches": db_response.total_count or 0,
                "page": db_response.page or 1
            }
        else:
            return {"type": "unknown", "operation": db_response.operation}

# Global service instance
chat_service = ChatService()