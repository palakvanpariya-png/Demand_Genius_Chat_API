# app/config/database.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import execute_values
import logging
from loguru import logger

from .setting import settings

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
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5
            )
            
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
        if self._client is not None:  
            self._client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_client(self):
        """Get MongoDB client"""
        if self._client is None: 
            self.connect()
        return self._client
    
    def get_database(self):
        """Get database instance"""
        if self._db is None:  
            self.connect()
        return self._db
    
    def health_check(self) -> bool:
        """Check database health"""
        try:
            if self._client is None:  
                return False
            self._client.admin.command('ping')
            return True
        except Exception:
            return False


class VectorDatabaseConnection:
    """PostgreSQL + pgvector connection manager"""
    
    def __init__(self):
        self._pool = None
    
    def connect(self):
        """Establish connection pool"""
        try:
            self._pool = SimpleConnectionPool(
                minconn=2,
                maxconn=10,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD
            )
            
            # Test connection and ensure pgvector extension
            conn = self._pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    cur.execute("SELECT 1")
                    conn.commit()
                logger.info("Connected to PostgreSQL with pgvector")
            finally:
                self._pool.putconn(conn)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False
    
    def disconnect(self):
        """Close connection pool"""
        if self._pool is not None:
            self._pool.closeall()
            logger.info("Disconnected from PostgreSQL")
    
    def get_connection(self):
        """Get connection from pool"""
        if self._pool is None:
            self.connect()
        return self._pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        if self._pool is not None:
            self._pool.putconn(conn)
    
    def health_check(self) -> bool:
        """Check database health"""
        try:
            if self._pool is None:
                return False
            conn = self._pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                self._pool.putconn(conn)
        except Exception:
            return False


# Global connections
db_connection = DatabaseConnection()
vector_db_connection = VectorDatabaseConnection()

def get_database():
    """Dependency to get database instance"""
    return db_connection.get_database()

def get_mongo_client():
    """Dependency to get MongoDB client"""
    return db_connection.get_client()

def get_vector_connection():
    """Dependency to get PostgreSQL connection"""
    return vector_db_connection.get_connection()

def return_vector_connection(conn):
    """Return PostgreSQL connection"""
    vector_db_connection.return_connection(conn)