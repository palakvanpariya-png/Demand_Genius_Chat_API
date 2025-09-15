# app/services/chat_service.py
"""
Updated ChatService with MongoDB Session Handler Integration
Minimal changes to integrate the new MongoDB-based advisory system
"""

from typing import Dict, Any, Optional
import logging
from loguru import logger

from ..core.query_parser import SmartQueryParser
from ..core.query_builder import MongoQueryExecutor
# CHANGE 1: Replace old import with new MongoDB-based system
# from ..core.advisory_answer import IntelligentAdvisor
from ..core.advisory.advisor_manager import AdvisorManager

from ..services.schema_service import schema_service
from ..services.session_service import session_service  # Keep your existing service
from ..models.query import QueryResult
from ..models.database import DatabaseResponse
from ..models.chat import ChatResponse
from ..config.settings import settings

class ChatService:
    """
    Main chat service with MongoDB session integration
    """
    
    def __init__(self):
        self.query_parser = SmartQueryParser()
        self.query_executor = MongoQueryExecutor()
        # CHANGE 2: Initialize AdvisorManager with MongoDB support
        self.advisor = AdvisorManager()
        
    async def process_chat_message(
        self,
        message: str,
        tenant_id: str,
        session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process complete chat pipeline with MongoDB session integration
        """
        try:
            # Step 1-3: Same as before (Parse, Execute, Schema)
            logger.info(f"Parsing query for tenant {tenant_id}: {message[:50]}...")
            query_result = self.query_parser.parse(message, tenant_id)
            logger.info(f"Parsed query result: {query_result}")
            
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
            
            logger.info("Fetching tenant schema")
            tenant_schema = await schema_service.get_tenant_schema(tenant_id)
            
            # Step 4: Generate advisory response using new MongoDB system
            logger.info("Generating advisory insights with MongoDB session support")
            advisory_response = self.advisor.generate_response(
            operation=query_result.operation,
            query_result=query_result,
            db_response=db_response,
            tenant_schema=tenant_schema,
            original_query=message,
            session_id=session_id,
            tenant_id=tenant_id  # ADD THIS
        )
            
            # Step 5: OPTIONAL - Keep existing session service for compatibility
            # The new system already stores in MongoDB, but you can keep both if needed
            if session_id:
                await session_service.store_interaction(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    message=message,
                    response=advisory_response
                )
            
            # Step 6: Create response (same as before)
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
            
            logger.info(f"Chat processing completed with MongoDB session storage")
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
        """Create summary of database response for API (unchanged)"""
        if not db_response.success:
            return {"error": True, "message": db_response.error}
        
        if getattr(db_response, 'advisory_mode', False):
            return {"type": "advisory", "message": "No database query performed"}
        
        if db_response.operation == "list":
            return {
                "type": "content_list",
                "count": len(db_response.data) if db_response.data else 0,
                "total": db_response.total_count or 0,
                "has_more": getattr(db_response, 'has_next', False)
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
    
    # NEW METHODS: Session management integration
    async def get_session_history(self, session_id: str, tenant_id: str) -> Optional[Dict]:
        """Get session history from MongoDB"""
        try:
            session_info = self.advisor.session_handler.get_session_info(session_id, tenant_id)
            if session_info:
                return {
                    "session_id": session_info.session_id,
                    "tenant_id": session_info.tenant_id,
                    "created_at": session_info.created_at,
                    "interaction_count": session_info.interaction_count,
                    "interactions": [
                        {
                            "timestamp": interaction.timestamp,
                            "message": interaction.message,
                            "operation": interaction.operation,
                            "confidence": interaction.confidence
                        }
                        for interaction in session_info.interactions[-5:]  # Last 5 interactions
                    ]
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return None
    
    async def cleanup_old_sessions(self, max_age_hours: int = 72) -> int:
        """Clean up old sessions from MongoDB"""
        try:
            return self.advisor.session_handler.cleanup_old_sessions(max_age_hours)
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics from MongoDB"""
        try:
            stats = self.advisor.get_session_stats()
            stats["mongodb_sessions"] = True
            stats["dual_session_storage"] = True  # If keeping both systems
            return stats
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {"error": str(e)}

# Global service instance
chat_service = ChatService()


# MIGRATION NOTES:
"""
MongoDB Collection Structure Created:
{
  "_id": ObjectId,
  "session_id": "uuid-string",
  "tenant_id": "tenant-id", 
  "created_at": datetime,
  "updated_at": datetime,
  "last_activity": datetime,
  "interactions": [
    {
      "timestamp": "iso-string",
      "message": "user query",
      "response_summary": "truncated response",
      "operation": "list|semantic|distribution|pure_advisory",
      "confidence": "high|medium|low"
    }
  ]
}

Indexes Created:
- session_id (unique)
- tenant_id  
- last_activity
- (tenant_id, last_activity) compound

Benefits:
- Sessions persist across server restarts
- Better performance with indexes
- Automatic cleanup of old sessions
- Compatible with existing models
- Can scale horizontally
"""