# app/core/advisory/session_handler.py
"""
OPTIONAL UPDATE: Enhanced session storage to include parsed results for context
Only the store_interaction method needs updating
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from pymongo import MongoClient
from bson import ObjectId

from ..models.session import SessionInfo, InteractionRecord
from ..config.setting import settings
from ..config.database import db_connection


class SessionHandler:
    """
    MongoDB-based session management with parsed result storage for context awareness
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None, max_memory_length: int = 3):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self.max_memory_length = max_memory_length
        self._client = None
        self._db = None
    
    def _get_db_connection(self):
        """Use centralized database connection"""
        return db_connection.get_database()

    def _close_connection(self):
        """No-op since we use centralized connection"""
        pass
    
    def store_interaction(
        self, 
        session_id: str, 
        query: str, 
        response: Dict, 
        operation: str, 
        tenant_id: str,
        parsed_result: Optional[Dict] = None  # NEW: Optional parsed result for context
    ):
        """
        Store interaction in MongoDB sessions collection with optional parsed result
        
        Args:
            session_id: Session ID
            query: User query
            response: Advisory response
            operation: Operation type
            tenant_id: Tenant ID
            parsed_result: Optional parsed query result for future context (NEW)
        """
        try:
            db = self._get_db_connection()
            
            # Create interaction record with parsed result
            interaction_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "message": query,
                "response_summary": response.get("response", "")[:200],
                "operation": operation,
                "confidence": response.get("confidence")
            }
            
            # NEW: Add parsed result if provided (for parser context)
            if parsed_result:
                # Store essential fields for context
                interaction_data["parsed_result"] = {
                    "operation": parsed_result.get("operation"),
                    "filters": parsed_result.get("filters", {}),
                    "description": parsed_result.get("description"),
                    "route": parsed_result.get("route"),
                    "confidence": parsed_result.get("confidence")
                }
            
            # Update or create session document
            result = db.sessions.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "interactions": {
                            "$each": [interaction_data],
                            "$slice": -self.max_memory_length
                        }
                    },
                    "$set": {
                        "updated_at": datetime.utcnow(),
                        "last_activity": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "session_id": session_id,
                        "created_at": datetime.utcnow(),
                        "tenant_id": tenant_id
                    }
                },
                upsert=True
            )
            
            logger.debug(f"Stored interaction for session {session_id} with context data")
            
        except Exception as e:
            logger.error(f"Failed to store interaction in MongoDB: {e}")
        finally:
            self._close_connection()
    
    def get_recent_context(self, session_id: str, limit: int = 2) -> List[Dict]:
        """
        Get recent conversation context for a session from MongoDB
        Returns last N interactions with parsed results for parser context
        
        Args:
            session_id: Session ID
            limit: Number of recent interactions to retrieve (default 2 for parser context)
            
        Returns:
            List of interaction dicts with query and parsed_result
        """
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one(
                {"session_id": session_id},
                {"interactions": {"$slice": -limit}}
            )
            
            if not session_doc or not session_doc.get("interactions"):
                return []
            
            return session_doc["interactions"]
            
        except Exception as e:
            logger.error(f"Failed to get session context from MongoDB: {e}")
            return []
        finally:
            self._close_connection()

    # ... rest of the methods remain unchanged ...
    
    def get_contextual_interactions(self, session_id: str, current_query: str, max_results: int = 3) -> List[Dict]:
        """Get contextually relevant interactions - UNCHANGED"""
        try:
            recent_interactions = self.get_recent_context(session_id, limit=max_results * 2)
            
            if not recent_interactions or len(recent_interactions) <= max_results:
                return recent_interactions
            
            return self._score_interactions_for_relevance(recent_interactions, current_query, max_results)
            
        except Exception as e:
            logger.error(f"Failed to get contextual interactions: {e}")
            return self.get_recent_context(session_id, limit=max_results)
    
    def _score_interactions_for_relevance(self, interactions: List[Dict], current_query: str, max_results: int) -> List[Dict]:
        """Score interactions for relevance - UNCHANGED"""
        if len(interactions) <= max_results:
            return interactions
        
        current_query_lower = current_query.lower()
        current_words = set(current_query_lower.split())
        
        scored_interactions = []
        
        for interaction in interactions:
            score = 0
            message = interaction.get("message", "").lower()
            message_words = set(message.split())
            operation = interaction.get("operation", "")
            
            shared_words = current_words & message_words
            score += len(shared_words) * 2
            
            if operation in ["distribution", "semantic", "list"] and any(word in current_query_lower for word in ["analyze", "show", "content"]):
                score += 1
            
            score += 0.1
            
            scored_interactions.append((score, interaction))
        
        scored_interactions.sort(key=lambda x: x[0], reverse=True)
        relevant_interactions = [interaction for _, interaction in scored_interactions[:max_results]]
        
        relevant_interactions.sort(key=lambda x: x.get("timestamp", ""))
        
        return relevant_interactions
    
    def has_history(self, session_id: str) -> bool:
        """Check if session has conversation history - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one(
                {"session_id": session_id},
                {"interactions": {"$slice": 1}}
            )
            
            return bool(session_doc and session_doc.get("interactions"))
            
        except Exception as e:
            logger.error(f"Failed to check session history: {e}")
            return False
        finally:
            self._close_connection()
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information about a session - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one({"session_id": session_id})
            
            if not session_doc:
                return None
            
            interactions = session_doc.get("interactions", [])
            if not interactions:
                return None
            
            operations_used = list(set(
                interaction.get("operation", "unknown") 
                for interaction in interactions
            ))
            
            return {
                "session_id": session_id,
                "total_interactions": len(interactions),
                "first_interaction": interactions[0].get("timestamp") if interactions else None,
                "last_interaction": interactions[-1].get("timestamp") if interactions else None,
                "operations_used": operations_used,
                "tenant_id": session_doc.get("tenant_id", ""),
                "created_at": session_doc.get("created_at", "").isoformat() if session_doc.get("created_at") else ""
            }
            
        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return None
        finally:
            self._close_connection()
    
    def get_session_info(self, session_id: str, tenant_id: str = None) -> Optional[SessionInfo]:
        """Get full session information - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            query = {"session_id": session_id}
            if tenant_id:
                query["tenant_id"] = tenant_id
            
            session_doc = db.sessions.find_one(query)
            
            if not session_doc:
                return None
            
            interactions = []
            for interaction_data in session_doc.get("interactions", []):
                interaction = InteractionRecord(
                    timestamp=interaction_data.get("timestamp", ""),
                    message=interaction_data.get("message", ""),
                    response_summary=interaction_data.get("response_summary", ""),
                    operation=interaction_data.get("operation", "unknown"),
                    confidence=interaction_data.get("confidence")
                )
                interactions.append(interaction)
            
            session_info = SessionInfo(
                session_id=session_id,
                tenant_id=session_doc.get("tenant_id", ""),
                created_at=session_doc.get("created_at", datetime.utcnow()).isoformat() if isinstance(session_doc.get("created_at"), datetime) else session_doc.get("created_at", ""),
                interactions=interactions
            )
            
            return session_info
            
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return None
        finally:
            self._close_connection()
    
    def update_session_tenant(self, session_id: str, tenant_id: str):
        """Update session with tenant information - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            db.sessions.update_one(
                {"session_id": session_id},
                {"$set": {"tenant_id": tenant_id}},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Failed to update session tenant: {e}")
        finally:
            self._close_connection()
    
    def clear_session(self, session_id: Optional[str] = None):
        """Clear session data - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            if session_id:
                result = db.sessions.delete_one({"session_id": session_id})
                if result.deleted_count > 0:
                    logger.info(f"Cleared session {session_id}")
            else:
                result = db.sessions.delete_many({})
                logger.info(f"Cleared all {result.deleted_count} sessions")
                
        except Exception as e:
            logger.error(f"Failed to clear session(s): {e}")
        finally:
            self._close_connection()
    
    def get_active_sessions(self, tenant_id: Optional[str] = None) -> List[str]:
        """Get list of active session IDs - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            query = {}
            if tenant_id:
                query["tenant_id"] = tenant_id
            
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            query["last_activity"] = {"$gte": cutoff_time}
            
            sessions = db.sessions.find(query, {"session_id": 1})
            return [session["session_id"] for session in sessions]
            
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
        finally:
            self._close_connection()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            total_sessions = db.sessions.count_documents({})
            
            pipeline = [
                {"$project": {"interaction_count": {"$size": "$interactions"}}},
                {"$group": {"_id": None, "total_interactions": {"$sum": "$interaction_count"}}}
            ]
            
            agg_result = list(db.sessions.aggregate(pipeline))
            total_interactions = agg_result[0]["total_interactions"] if agg_result else 0
            
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            active_sessions = db.sessions.count_documents({
                "last_activity": {"$gte": cutoff_time}
            })
            
            return {
                "total_sessions": total_sessions,
                "total_interactions": total_interactions,
                "active_sessions_24h": active_sessions,
                "max_memory_length": self.max_memory_length,
                "storage_type": "mongodb",
                "context_aware": True  # NEW: Indicates parsed results are stored
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "total_sessions": 0,
                "total_interactions": 0,
                "active_sessions_24h": 0,
                "error": str(e)
            }
        finally:
            self._close_connection()
    
    def cleanup_old_sessions(self, max_age_hours: int = 72) -> int:
        """Clean up old sessions - UNCHANGED"""
        try:
            db = self._get_db_connection()
            
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            result = db.sessions.delete_many({
                "last_activity": {"$lt": cutoff_time}
            })
            
            deleted_count = result.deleted_count
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old sessions")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0
        finally:
            self._close_connection()