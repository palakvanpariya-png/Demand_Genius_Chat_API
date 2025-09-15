# app/api/routes/chat.py - Updated to use JWT authentication
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, Dict, Any
import logging
from loguru import logger

from ...models.chat import MessageRequest, APIResponse, SessionCreateResponse
from ...core.helpers.data_formatters import format_api_response, format_error_response
from ...services.chat_service import chat_service
from ...services.session_service import session_service
from ...core.schema_extractor import get_tenant_schema
from ...config.settings import settings
from ...middleware.jwt_middleware import get_current_user, JWTAccount

router = APIRouter()

@router.post("/message", response_model=Dict[str, Any])
async def send_message(
    request: MessageRequest, 
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    Process chat message and return advisory response in API format
    
    Args:
        request: Message request with message content and optional session_id
        current_user: Authenticated user from JWT token (contains tenant_id and user_id)
        
    Returns:
        API response with success, message, data structure, and session_id
    """
    try:
        # Validate message length
        if len(request.message) > 1000:
            return format_error_response(
                "Message too long. Maximum 1000 characters allowed.",
                "validation_error"
            )
        
        # Use tenant_id from JWT payload
        tenant_id = current_user.tenant_id
        
        # Auto-handle session creation
        session_id = request.session_id
        if not session_id:
            # Create new session automatically if none provided
            session_id = await session_service.create_session(tenant_id)
            logger.info(f"Auto-created session {session_id} for tenant {tenant_id}, user {current_user.user_id}")
        else:
            # Verify session exists and belongs to this tenant
            existing_session = await session_service.get_session(session_id, tenant_id)
            if not existing_session:
                logger.warning(f"Session {session_id} not found for tenant {tenant_id}, creating new session")
                session_id = await session_service.create_session(tenant_id)
        
        # Process the chat message (returns InternalChatResponse)
        internal_response = await chat_service.process_chat_message(
            message=request.message,
            tenant_id=tenant_id,
            session_id=session_id  # Always have a session_id now
        )
        
        # Get tenant schema for column config (only for list/semantic operations)
        tenant_schema = None
        if internal_response.operation in ['list', 'semantic']:
            try:
                tenant_schema = get_tenant_schema(
                    settings.MONGODB_URI, 
                    settings.DATABASE_NAME, 
                    tenant_id
                )
            except Exception as e:
                logger.warning(f"Failed to get tenant schema for {tenant_id}: {e}")
        
        # Convert to API format
        api_response = format_api_response(
            internal_response,
            tenant_schema=tenant_schema,
            tenant_id=tenant_id
        )
        
        # Always include session_id in response so client can use it for next message
        if "data" in api_response:
            api_response["data"]["session_id"] = session_id
        else:
            api_response["data"] = {"session_id": session_id}
        
        logger.info(f"Chat message processed for tenant {tenant_id}, user {current_user.user_id}, session {session_id}, operation: {internal_response.operation}")
        return api_response
        
    except HTTPException as e:
        return format_error_response(
            e.detail,
            "http_error"
        )
    except Exception as e:
        logger.error(f"Chat endpoint error for tenant {current_user.tenant_id}: {e}")
        return format_error_response(
            "Internal server error occurred while processing your request",
            "internal_error"
        )

@router.post("/session/new", response_model=SessionCreateResponse)
async def create_new_session(current_user: JWTAccount = Depends(get_current_user)):
    """
    Create new chat session
    
    Args:
        current_user: Authenticated user from JWT token (contains tenant_id)
        
    Returns:
        New session ID
    """
    try:
        tenant_id = current_user.tenant_id
        
        session_id = await session_service.create_session(tenant_id)
        
        logger.info(f"New session created for tenant {tenant_id}, user {current_user.user_id}: {session_id}")
        return SessionCreateResponse(
            session_id=session_id,
            message="Session created successfully"
        )
        
    except Exception as e:
        logger.error(f"Session creation error for tenant {current_user.tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.get("/session/{session_id}", response_model=Dict[str, Any])
async def get_session_info(
    session_id: str, 
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    Get session information and history
    
    Args:
        session_id: Session ID to retrieve
        current_user: Authenticated user from JWT token (contains tenant_id)
        
    Returns:
        Session information in API format
    """
    try:
        tenant_id = current_user.tenant_id
        
        session_info = await session_service.get_session(session_id, tenant_id)
        
        if not session_info:
            return {
                "success": False,
                "message": "Session not found",
                "data": {"session_id": session_id}
            }
        
        # Return in API format
        return {
            "success": True,
            "message": "Session retrieved successfully",
            "data": session_info
        }
        
    except Exception as e:
        logger.error(f"Session retrieval error for tenant {current_user.tenant_id}: {e}")
        return {
            "success": False,
            "message": "Failed to retrieve session",
            "data": {"error": str(e)}
        }

@router.delete("/session/{session_id}", response_model=Dict[str, Any])
async def delete_session(
    session_id: str, 
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    Delete chat session
    
    Args:
        session_id: Session ID to delete
        current_user: Authenticated user from JWT token (contains tenant_id)
        
    Returns:
        Deletion confirmation in API format
    """
    try:
        tenant_id = current_user.tenant_id
        
        await session_service.delete_session(session_id, tenant_id)
        
        logger.info(f"Session deleted for tenant {tenant_id}, user {current_user.user_id}: {session_id}")
        return {
            "success": True,
            "message": "Session deleted successfully",
            "data": {"session_id": session_id}
        }
        
    except Exception as e:
        logger.error(f"Session deletion error for tenant {current_user.tenant_id}: {e}")
        return {
            "success": False,
            "message": "Failed to delete session",
            "data": {"error": str(e), "session_id": session_id}
        }

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint (no authentication required)"""
    from datetime import datetime
    return {
        "success": True,
        "message": "Chat service is healthy",
        "data": {
            "service": "chat",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
    }

@router.get("/capabilities", response_model=Dict[str, Any])
async def get_capabilities(current_user: JWTAccount = Depends(get_current_user)):
    """
    Get chat service capabilities for this tenant
    
    Args:
        current_user: Authenticated user from JWT token (contains tenant_id)
    
    Returns:
        Available operations and features
    """
    try:
        tenant_id = current_user.tenant_id
        
        # You could get actual tenant-specific capabilities here
        capabilities = {
            "operations": ["list", "semantic", "distribution", "advisory"],
            "features": ["conversation_memory", "strategic_insights", "content_analysis"],
            "max_message_length": 1000,
            "supported_languages": ["en"],
            "tenant_id": tenant_id,
            "user_id": current_user.user_id
        }
        
        return {
            "success": True,
            "message": "Chat capabilities retrieved",
            "data": capabilities
        }
        
    except Exception as e:
        logger.error(f"Capabilities retrieval error for tenant {current_user.tenant_id}: {e}")
        return {
            "success": False,
            "message": "Failed to retrieve capabilities",
            "data": {"error": str(e)}
        }

