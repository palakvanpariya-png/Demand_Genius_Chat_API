# app/api/routes/health.py
from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging
from loguru import logger

from ...config.database import db_connection, vector_db_connection  # ✅ ADD
from ...services.vector_service import vector_service  # ✅ ADD
from ...models.database import HealthResponse
from ...config.setting import settings  # ✅ ADD

router = APIRouter()

@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check"""
    return HealthResponse(
        status="healthy",
        service="content-intelligence-api",
        timestamp=None,
        database_connected=True
    )

@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check with database connectivity"""
    try:
        # Check MongoDB
        db_healthy = db_connection.health_check()
        
        # ✅ Check PostgreSQL (pgvector)
        vector_db_healthy = True
        if settings.VECTOR_SEARCH_ENABLED:
            vector_db_healthy = vector_db_connection.health_check()
        
        if not db_healthy:
            return {
                "status": "not_ready",
                "database": "disconnected",
                "vector_database": "n/a" if not settings.VECTOR_SEARCH_ENABLED else ("connected" if vector_db_healthy else "disconnected"),
                "ready": False
            }
        
        return {
            "status": "ready",
            "database": "connected",
            "vector_database": "n/a" if not settings.VECTOR_SEARCH_ENABLED else ("connected" if vector_db_healthy else "disconnected"),
            "vector_search_enabled": settings.VECTOR_SEARCH_ENABLED,
            "ready": True
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "database": "error",
            "vector_database": "error",
            "ready": False,
            "error": str(e)
        }

@router.get("/status")
async def detailed_status() -> Dict[str, Any]:
    """Detailed system status"""
    try:
        # Check MongoDB
        db_status = "connected" if db_connection.health_check() else "disconnected"
        
        # ✅ Check PostgreSQL
        vector_db_status = "disabled"
        if settings.VECTOR_SEARCH_ENABLED:
            vector_db_status = "connected" if vector_db_connection.health_check() else "disconnected"
        
        # Get basic system info
        status_info = {
            "api": {
                "status": "running",
                "version": settings.API_VERSION,
                "debug_mode": settings.DEBUG
            },
            "database": {
                "mongodb": {
                    "status": db_status,
                    "uri": settings.MONGODB_URI.split('@')[1] if '@' in settings.MONGODB_URI else "local",
                    "database_name": settings.DATABASE_NAME
                },
                "postgresql": {
                    "status": vector_db_status,
                    "enabled": settings.VECTOR_SEARCH_ENABLED,
                    "host": settings.POSTGRES_HOST if settings.VECTOR_SEARCH_ENABLED else "n/a"
                }
            },
            "configuration": {
                "openai_configured": bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key"),
                "vector_search_enabled": settings.VECTOR_SEARCH_ENABLED,
                "embedding_model": settings.EMBEDDING_MODEL if settings.VECTOR_SEARCH_ENABLED else "n/a"
            }
        }
        
        return status_info
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "api": {"status": "error", "error": str(e)},
            "database": {"status": "unknown"},
            "configuration": {"status": "unknown"}
        }