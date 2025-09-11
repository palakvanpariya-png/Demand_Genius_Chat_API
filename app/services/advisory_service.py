# app/services/advisory_service.py
from typing import Dict, Any, Optional, Union
import logging
from loguru import logger

from ..core.advisory_answer import IntelligentAdvisor
from ..models.query import QueryResult
from ..models.database import DatabaseResponse
from ..models.session import SessionInfo, InteractionRecord
from ..config.settings import settings

# logger = logging.getLogger(__name__)

class AdvisoryService:
    """
    Service layer for advisory operations with session management
    """
    
    def __init__(self):
        self.advisor = IntelligentAdvisor()
        
    async def generate_advisory(
        self,
        operation: str,
        query_result: QueryResult,
        db_response: DatabaseResponse,
        tenant_schema: Dict,
        original_query: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate advisory response with proper type handling
        
        Args:
            operation: Query operation type
            query_result: Parsed query result
            db_response: Database response
            tenant_schema: Tenant schema information
            original_query: Original user query
            session_id: Optional session ID
            
        Returns:
            Advisory response dictionary
        """
        try:
            response = self.advisor.generate_advisory_response(
                operation=operation,
                query_result=query_result,
                db_response=db_response,
                tenant_schema=tenant_schema,
                original_query=original_query,
                session_id=session_id
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Advisory service error: {e}")
            return {
                "response": "I encountered an issue generating insights. Please try rephrasing your question.",
                "suggested_questions": [
                    "Show me my content overview",
                    "What content categories do I have?", 
                    "Help me understand my content distribution"
                ],
                "confidence": "low"
            }
    
    async def get_session_history(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session conversation history
        
        Args:
            session_id: Session ID
            
        Returns:
            SessionInfo if session exists, None otherwise
        """
        if session_id not in self.advisor.conversation_cache:
            return None
        
        interactions = self.advisor.conversation_cache[session_id]
        
        # Create SessionInfo (we don't have created_at, so use first interaction timestamp)
        created_at = interactions[0].timestamp if interactions else datetime.utcnow().isoformat()
        
        return SessionInfo(
            session_id=session_id,
            tenant_id="",  # We don't store this separately
            created_at=created_at,
            interactions=interactions
        )
    
    async def clear_session(self, session_id: str):
        """Clear specific session"""
        self.advisor.clear_conversation_cache(session_id)
    
    async def clear_all_sessions(self):
        """Clear all sessions"""
        self.advisor.clear_conversation_cache()
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.advisor.conversation_cache.keys())
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        total_sessions = len(self.advisor.conversation_cache)
        total_interactions = sum(len(interactions) for interactions in self.advisor.conversation_cache.values())
        
        return {
            "total_sessions": total_sessions,
            "total_interactions": total_interactions,
            "max_history_length": self.advisor.max_history_length,
            "active_sessions": list(self.advisor.conversation_cache.keys())
        }

# Global service instance
advisory_service = AdvisoryService()