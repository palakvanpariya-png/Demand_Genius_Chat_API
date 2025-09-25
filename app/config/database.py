# app/config/database.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging
from loguru import logger

from .settings import settings

class DatabaseConnection:
    """MongoDB connection manager"""
    
    def __init__(self):
        self._client = None
        self._db = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self._client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5
            )
            
            # Test connection
            self._client.admin.command('ping')
            self._db = self._client[settings.DATABASE_NAME]
            
            logger.info(f"Connected to MongoDB: {settings.DATABASE_NAME}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self._client is not None:  # ✅ FIXED: Use 'is not None'
            self._client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_client(self):
        """Get MongoDB client"""
        if self._client is None:  # ✅ FIXED: Use 'is None'
            self.connect()
        return self._client
    
    def get_database(self):
        """Get database instance"""
        if self._db is None:  # ✅ FIXED: Use 'is None'
            self.connect()
        return self._db
    
    def health_check(self) -> bool:
        """Check database health"""
        try:
            if self._client is None:  # ✅ FIXED: Use 'is None'
                return False
            self._client.admin.command('ping')
            return True
        except Exception:
            return False

# Global database connection
db_connection = DatabaseConnection()

def get_database():
    """Dependency to get database instance"""
    return db_connection.get_database()

def get_mongo_client():
    """Dependency to get MongoDB client"""
    return db_connection.get_client()