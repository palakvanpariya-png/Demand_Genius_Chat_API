# app/core/advisory/session_handler.py - Enhanced for storing parsed queries
"""
Enhanced MongoDB Session Handler that stores parsed query information for context
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from pymongo import MongoClient
from bson import ObjectId

from ..models.session import SessionInfo, InteractionRecord
from ..config.settings import settings
from ..config.database import db_connection

class SessionHandler:
    """Enhanced MongoDB session handler with parsed query storage for context"""
    
    def __init__(self, mongo_uri: str = None, db_name: str = None, max_memory_length: int = 5):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self.max_memory_length = max_memory_length  # Increased for better context
        self._client = None
        self._db = None
    
    def _get_db_connection(self):
        """Use centralized database connection"""
        return db_connection.get_database()

    def _close_connection(self):
        """No-op since we use centralized connection"""
        pass
    
    def store_interaction(self, session_id: str, query: str, response: Dict, operation: str, 
                         tenant_id: str, parsed_query_dict: Dict = None):
        """
        Enhanced: Store interaction WITH parsed query information for context
        
        Args:
            session_id: Session ID
            query: Original user query
            response: Advisory response
            operation: Operation type
            tenant_id: Tenant ID
            parsed_query_dict: Parsed query information (NEW)
        """
        try:
            db = self._get_db_connection()
            
            # Create interaction record
            interaction_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "message": query,
                "response_summary": response.get("response", "")[:200],
                "operation": operation,
                "confidence": response.get("confidence")
            }
            
            # NEW: Store parsed query information for context
            if parsed_query_dict:
                interaction_data["parsed_query"] = parsed_query_dict
            
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
            
            if result.upserted_id:
                logger.info(f"Created NEW MongoDB session: {session_id}")
            else:
                logger.debug(f"Updated session: {session_id} with parsed query context")
            
        except Exception as e:
            logger.error(f"Failed to store interaction with context: {e}")
        finally:
            self._close_connection()
    
    def get_parsed_query_context(self, session_id: str, limit: int = 3) -> List[Dict]:
        """
        NEW: Get recent parsed queries for context
        
        Args:
            session_id: Session ID
            limit: Number of recent queries to retrieve
            
        Returns:
            List of parsed query dicts for context
        """
        try:
            db = self._get_db_connection()
            
            session_doc = db.sessions.find_one(
                {"session_id": session_id},
                {"interactions": {"$slice": -limit}}
            )
            
            if not session_doc or not session_doc.get("interactions"):
                return []
            
            # Extract parsed queries from interactions
            parsed_queries = []
            for interaction in session_doc["interactions"]:
                if "parsed_query" in interaction:
                    parsed_queries.append(interaction["parsed_query"])
            
            logger.debug(f"Retrieved {len(parsed_queries)} parsed queries for context")
            return parsed_queries
            
        except Exception as e:
            logger.error(f"Failed to get parsed query context: {e}")
            return []
        finally:
            self._close_connection()
    
    # All existing methods remain the same
    def get_recent_context(self, session_id: str, limit: int = 2) -> List[Dict]:
        """Get recent conversation context - UNCHANGED"""
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
            logger.error(f"Failed to get session context: {e}")
            return []
        finally:
            self._close_connection()

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
                "context_enhanced": True  # NEW: Indicates context support
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {"error": str(e)}
        finally:
            self._close_connection()