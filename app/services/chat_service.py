# app/services/chat_service.py - Enhanced with context support
"""
Enhanced ChatService that supports contextual query parsing
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
from ..models.session import SessionInfo, InteractionRecord
from ..models.advisory import SessionStatsResponse
from ..config.settings import settings

class ChatService:
    """Enhanced chat service with contextual query parsing support"""
    
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
        """Enhanced chat processing with contextual query parsing"""
        try:
            # Step 1: Get previous query context if session exists
            previous_queries = []
            if session_id:
                previous_queries = self.advisor.session_handler.get_parsed_query_context(session_id, limit=3)
                logger.debug(f"Retrieved {len(previous_queries)} previous queries for context")
            
            # Step 2: Parse query WITH context
            logger.info(f"Parsing contextual query for tenant {tenant_id}: {message[:50]}...")
            query_result = self.query_parser.parse(message, tenant_id, previous_queries)
            logger.info(f"Parsed result: operation={query_result.operation}, confidence={query_result.confidence}, filters={query_result.filters}")
            
            # Step 3: Get tenant schema
            logger.info("Fetching tenant schema")
            tenant_schema = await schema_service.get_tenant_schema(tenant_id)
            
            # Step 4: Execute query if data needed
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
            
            # Step 5: Generate advisory response
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
            
            # Step 6: Store session interaction WITH parsed query context
            if session_id:
                # Convert query_result to dict for storage
                parsed_query_dict = self.query_parser.to_dict(query_result, message)
                
                # Store in in-memory session service
                await session_service.store_interaction(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    message=message,
                    response=advisory_response_dict
                )
                
                # Store in MongoDB with parsed query context
                self.advisor.session_handler.store_interaction(
                    session_id=session_id,
                    query=message,
                    response=advisory_response_dict,
                    operation=query_result.operation,
                    tenant_id=tenant_id,
                    parsed_query_dict=parsed_query_dict  # NEW: Store parsed query for context
                )
            
            # Step 7: Create response
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
            
            logger.info(f"Contextual chat processing completed successfully")
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

    def _create_data_summary(self, db_response: DatabaseResponse) -> DataSummary:
        """Create summary of database response - UNCHANGED"""
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
    
    # All existing methods remain the same
    async def get_session_history(self, session_id: str, tenant_id: str) -> Optional[SessionInfo]:
        """Get session history - UNCHANGED"""
        try:
            session_info = self.advisor.session_handler.get_session_info(session_id, tenant_id)
            return session_info
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return None
    
    async def cleanup_old_sessions(self, max_age_hours: int = 72) -> int:
        """Clean up old sessions - UNCHANGED"""
        try:
            return self.advisor.session_handler.cleanup_old_sessions(max_age_hours)
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0
    
    def get_session_stats(self) -> SessionStatsResponse:
        """Get session statistics - UNCHANGED"""
        try:
            stats_dict = self.advisor.get_session_stats()
            return SessionStatsResponse(
                total_sessions=stats_dict.get("total_sessions", 0),
                total_interactions=stats_dict.get("total_interactions", 0),
                active_sessions_24h=stats_dict.get("active_sessions_24h"),
                mongodb_sessions=True,
                dual_session_storage=True,
                storage_type=stats_dict.get("storage_type"),
                orchestrator_type="contextual_query_parsing"  # Updated to indicate enhancement
            )
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return SessionStatsResponse()

# Global service instance - UNCHANGED
chat_service = ChatService()