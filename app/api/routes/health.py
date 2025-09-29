# app/api/routes/health.py
from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging
from loguru import logger

from ...config.database import db_connection
from ...models.database import HealthResponse

router = APIRouter()
# logger = logging.getLogger(__name__)

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
        # Check database connection
        db_healthy = db_connection.health_check()
        
        if not db_healthy:
            return {
                "status": "not_ready",
                "database": "disconnected",
                "ready": False
            }
        
        return {
            "status": "ready",
            "database": "connected",
            "ready": True
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "database": "error",
            "ready": False,
            "error": str(e)
        }

@router.get("/status")
async def detailed_status() -> Dict[str, Any]:
    """Detailed system status"""
    try:
        from ...config.setting import settings
        
        # Check database
        db_status = "connected" if db_connection.health_check() else "disconnected"
        
        # Get basic system info
        status_info = {
            "api": {
                "status": "running",
                "version": settings.API_VERSION,
                "debug_mode": settings.DEBUG
            },
            "database": {
                "status": db_status,
                "uri": settings.MONGODB_URI.split('@')[1] if '@' in settings.MONGODB_URI else "local",
                "database_name": settings.DATABASE_NAME
            },
            "configuration": {
                "openai_configured": bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key"),
                "redis_configured": bool(settings.REDIS_URL)
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
