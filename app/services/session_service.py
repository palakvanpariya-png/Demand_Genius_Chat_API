# app/services/session_service.py
import uuid
from typing import Dict, Optional, Any
from datetime import datetime
import logging
from loguru import logger

from ..models.session import SessionInfo, InteractionRecord
from ..config.settings import settings

# logger = logging.getLogger(__name__)

class SessionService:
    """
    Session management service with in-memory storage
    TODO: Replace with Redis for production
    """
    
    def __init__(self):
        # Simple in-memory storage - replace with Redis in production
        self.sessions: Dict[str, SessionInfo] = {}
        self.max_sessions = 1000  # Prevent memory bloat
        
    async def create_session(self, tenant_id: str) -> str:
        """
        Create new chat session
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            New session ID
        """
        session_id = str(uuid.uuid4())
        
        session_info = SessionInfo(
            session_id=session_id,
            tenant_id=tenant_id,
            created_at=datetime.utcnow().isoformat(),
            interactions=[]
        )
        
        self.sessions[session_id] = session_info
        
        # Cleanup old sessions if too many
        if len(self.sessions) > self.max_sessions:
            # Remove oldest sessions
            oldest_sessions = sorted(
                self.sessions.items(),
                key=lambda x: x[1].created_at
            )[:100]
            
            for old_session_id, _ in oldest_sessions:
                del self.sessions[old_session_id]
            
            logger.info(f"Cleaned up {len(oldest_sessions)} old sessions")
        
        logger.info(f"Created session {session_id} for tenant {tenant_id}")
        return session_id
    
    async def store_interaction(
        self,
        session_id: str,
        tenant_id: str,
        message: str,
        response: Dict[str, Any]
    ):
        """
        Store chat interaction in session
        
        Args:
            session_id: Session ID
            tenant_id: Tenant ID
            message: User message
            response: Advisory response
        """
        if session_id not in self.sessions:
            # Create session if it doesn't exist
            await self.create_session(tenant_id)
            return
        
        session = self.sessions[session_id]
        
        # Verify tenant matches
        if session.tenant_id != tenant_id:
            logger.warning(f"Tenant mismatch for session {session_id}")
            return
        
        interaction = InteractionRecord(
            timestamp=datetime.utcnow().isoformat(),
            message=message,
            response_summary=response.get("response", "")[:200],
            operation=response.get("operation", "unknown"),
            confidence=response.get("confidence")
        )
        
        session.interactions.append(interaction)
        
        # Keep only recent interactions
        max_interactions = settings.MAX_SESSION_INTERACTIONS
        if len(session.interactions) > max_interactions:
            session.interactions = session.interactions[-max_interactions:]
    
    async def get_session(self, session_id: str, tenant_id: str) -> Optional[SessionInfo]:
        """
        Get session information
        
        Args:
            session_id: Session ID
            tenant_id: Tenant ID
            
        Returns:
            SessionInfo if found and belongs to tenant
        """
        session = self.sessions.get(session_id)
        
        if not session:
            return None
        
        if session.tenant_id != tenant_id:
            logger.warning(f"Tenant {tenant_id} attempted to access session {session_id} owned by {session.tenant_id}")
            return None
        
        return session
    
    async def delete_session(self, session_id: str, tenant_id: str):
        """
        Delete session
        
        Args:
            session_id: Session ID to delete
            tenant_id: Tenant ID for verification
        """
        session = self.sessions.get(session_id)
        
        if not session:
            return
        
        if session.tenant_id != tenant_id:
            logger.warning(f"Tenant {tenant_id} attempted to delete session {session_id} owned by {session.tenant_id}")
            return
        
        del self.sessions[session_id]
        logger.info(f"Deleted session {session_id} for tenant {tenant_id}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        total_sessions = len(self.sessions)
        total_interactions = sum(len(session.interactions) for session in self.sessions.values())
        
        return {
            "total_sessions": total_sessions,
            "total_interactions": total_interactions,
            "max_sessions": self.max_sessions,
            "max_interactions_per_session": settings.MAX_SESSION_INTERACTIONS
        }

# Global service instance
session_service = SessionService()