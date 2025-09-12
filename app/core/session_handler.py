# app/core/advisory/session_handler.py
"""
MongoDB Session Handler - Replaces memory-based session management
Integrates with your existing session models and MongoDB infrastructure
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from pymongo import MongoClient
from bson import ObjectId

from ..models.session import SessionInfo, InteractionRecord
from ..config.settings import settings


class SessionHandler:
    """
    MongoDB-based session management for advisory interactions
    Uses your existing session models and integrates with your MongoDB infrastructure
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None, max_memory_length: int = 3):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self.max_memory_length = max_memory_length
        self._client = None
        self._db = None
    
    def _get_db_connection(self):
        """Get database connection with proper error handling"""
        if not self._client:
            try:
                self._client = MongoClient(
                    self.mongo_uri,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000
                )
                self._db = self._client[self.db_name]
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return self._db
    
    def _close_connection(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
    
    def store_interaction(self, session_id: str, query: str, response: Dict, operation: str):
        """
        Store interaction in MongoDB sessions collection
        Uses your existing InteractionRecord model structure
        """
        try:
            db = self._get_db_connection()
            
            # Create interaction record using your existing model
            interaction_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "message": query,
                "response_summary": response.get("response", "")[:200],  # Limit as per your model
                "operation": operation,
                "confidence": response.get("confidence")
            }
            
            # Update or create session document
            result = db.sessions.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "interactions": {
                            "$each": [interaction_data],
                            "$slice": -self.max_memory_length  # Keep only recent interactions
                        }
                    },
                    "$set": {
                        "updated_at": datetime.utcnow(),
                        "last_activity": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "session_id": session_id,
                        "created_at": datetime.utcnow(),
                        "tenant_id": "",  # Will be updated when we have tenant context
                        "interactions": []
                    }
                },
                upsert=True
            )
            
            logger.debug(f"Stored interaction for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store interaction in MongoDB: {e}")
            # Don't fail the whole request for session storage issues
        finally:
            self._close_connection()
    
    def get_recent_context(self, session_id: str, limit: int = 2) -> List[Dict]:
        """
        Get recent conversation context for a session from MongoDB
        Returns last N interactions for context
        """
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one(
                {"session_id": session_id},
                {"interactions": {"$slice": -limit}}  # Get last N interactions
            )
            
            if not session_doc or not session_doc.get("interactions"):
                return []
            
            return session_doc["interactions"]
            
        except Exception as e:
            logger.error(f"Failed to get session context from MongoDB: {e}")
            return []
        finally:
            self._close_connection()
    
    def has_history(self, session_id: str) -> bool:
        """Check if session has conversation history in MongoDB"""
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one(
                {"session_id": session_id},
                {"interactions": {"$slice": 1}}  # Just check if any interactions exist
            )
            
            return bool(session_doc and session_doc.get("interactions"))
            
        except Exception as e:
            logger.error(f"Failed to check session history: {e}")
            return False
        finally:
            self._close_connection()
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information about a session from MongoDB"""
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one({"session_id": session_id})
            
            if not session_doc:
                return None
            
            interactions = session_doc.get("interactions", [])
            if not interactions:
                return None
            
            # Extract unique operations used
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
        """
        Get full session information using your SessionInfo model
        Compatible with your existing session_service pattern
        """
        try:
            db = self._get_db_connection()
            
            query = {"session_id": session_id}
            if tenant_id:
                query["tenant_id"] = tenant_id
            
            session_doc = db.sessions.find_one(query)
            
            if not session_doc:
                return None
            
            # Convert MongoDB document to your SessionInfo model
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
        """Update session with tenant information"""
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
        """
        Clear session data from MongoDB
        If session_id is None, clears all sessions (use with caution)
        """
        try:
            db = self._get_db_connection()
            
            if session_id:
                result = db.sessions.delete_one({"session_id": session_id})
                if result.deleted_count > 0:
                    logger.info(f"Cleared session {session_id}")
            else:
                # Clear all sessions - use with extreme caution
                result = db.sessions.delete_many({})
                logger.info(f"Cleared all {result.deleted_count} sessions")
                
        except Exception as e:
            logger.error(f"Failed to clear session(s): {e}")
        finally:
            self._close_connection()
    
    def get_active_sessions(self, tenant_id: Optional[str] = None) -> List[str]:
        """Get list of active session IDs"""
        try:
            db = self._get_db_connection()
            
            query = {}
            if tenant_id:
                query["tenant_id"] = tenant_id
            
            # Get sessions active in last 24 hours
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
        """
        Get session statistics from MongoDB
        Compatible with your advisory_service pattern
        """
        try:
            db = self._get_db_connection()
            
            # Get basic counts
            total_sessions = db.sessions.count_documents({})
            
            # Get total interactions using aggregation
            pipeline = [
                {"$project": {"interaction_count": {"$size": "$interactions"}}},
                {"$group": {"_id": None, "total_interactions": {"$sum": "$interaction_count"}}}
            ]
            
            agg_result = list(db.sessions.aggregate(pipeline))
            total_interactions = agg_result[0]["total_interactions"] if agg_result else 0
            
            # Get active sessions (last 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            active_sessions = db.sessions.count_documents({
                "last_activity": {"$gte": cutoff_time}
            })
            
            return {
                "total_sessions": total_sessions,
                "total_interactions": total_interactions,
                "active_sessions_24h": active_sessions,
                "max_memory_length": self.max_memory_length,
                "storage_type": "mongodb"
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
        """
        Clean up old sessions from MongoDB based on last activity
        More conservative default (72 hours) for database storage
        """
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
   