# app/api/routes/debug.py
"""
Debug endpoints for token usage and system monitoring
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
from loguru import logger

from ...utilities.token_calculator import token_calculator
from ...middleware.jwt import get_current_user, JWTAccount

router = APIRouter()

@router.get("/token-stats", response_model=Dict[str, Any])
async def get_token_statistics(current_user: JWTAccount = Depends(get_current_user)):
    """
    Get current session token usage statistics
    For debugging and monitoring purposes
    """
    try:
        stats = token_calculator.get_session_stats()
        
        # Add user context
        stats.update({
            "tenant_id": current_user.tenant_id,
            "user_id": current_user.user_id,
            "session_type": "debug_stats"
        })
        
        logger.info(f"Token stats requested by user {current_user.user_id} for tenant {current_user.tenant_id}")
        
        return {
            "success": True,
            "message": "Token usage statistics retrieved",
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get token stats: {e}")
        return {
            "success": False,
            "message": "Failed to retrieve token statistics",
            "data": {"error": str(e)}
        }

@router.post("/reset-token-stats", response_model=Dict[str, Any])
async def reset_token_statistics(current_user: JWTAccount = Depends(get_current_user)):
    """
    Reset token usage statistics
    Useful for debugging sessions
    """
    try:
        old_stats = token_calculator.get_session_stats()
        token_calculator.reset_stats()
        
        logger.info(f"Token stats reset by user {current_user.user_id} for tenant {current_user.tenant_id}")
        
        return {
            "success": True,
            "message": "Token statistics reset successfully",
            "data": {
                "previous_stats": old_stats,
                "tenant_id": current_user.tenant_id,
                "reset_by": current_user.user_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to reset token stats: {e}")
        return {
            "success": False,
            "message": "Failed to reset token statistics", 
            "data": {"error": str(e)}
        }

@router.get("/system-debug", response_model=Dict[str, Any])
async def get_system_debug_info(current_user: JWTAccount = Depends(get_current_user)):
    """
    Get comprehensive system debug information
    Includes token usage, session stats, and system health
    """
    try:
        from ...services.advisory_service import advisory_service
        from ...services.session_service import session_service
        
        debug_info = {
            "token_usage": token_calculator.get_session_stats(),
            "session_stats": session_service.get_session_stats(),
            "advisory_stats": advisory_service.get_session_stats(),
            "user_context": {
                "tenant_id": current_user.tenant_id,
                "user_id": current_user.user_id
            },
            "system_info": {
                "debug_mode": True,
                "token_tracking": "enabled"
            }
        }
        
        return {
            "success": True,
            "message": "System debug information retrieved",
            "data": debug_info
        }
        
    except Exception as e:
        logger.error(f"Failed to get system debug info: {e}")
        return {
            "success": False,
            "message": "Failed to retrieve system debug information",
            "data": {"error": str(e)}
        }