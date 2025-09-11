# app/api/routes/chat.py - Updated to use tenant_id from request body
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
import logging
from loguru import logger

from ...models.chat import ChatRequest, APIResponse, SessionCreateRequest, SessionCreateResponse
from ...core.helpers.data_formatters import format_api_response, format_error_response
from ...services.chat_service import chat_service
from ...services.session_service import session_service
from ...core.schema_extractor import get_tenant_schema
from ...config.settings import settings

router = APIRouter()

@router.post("/message", response_model=Dict[str, Any])
async def send_message(request: ChatRequest):
    """
    Process chat message and return advisory response in API format
    
    Args:
        request: Chat request with message, tenant_id, and optional session_id
        
    Returns:
        API response with success, message, and data structure
    """
    try:
        # Validate message length
        if len(request.message) > 1000:
            return format_error_response(
                "Message too long. Maximum 1000 characters allowed.",
                "validation_error"
            )
        
        # Validate tenant_id format (basic validation)
        if not request.tenant_id or len(request.tenant_id) < 10:
            return format_error_response(
                "Invalid tenant ID provided.",
                "validation_error"
            )
        
        # Process the chat message (returns InternalChatResponse)
        internal_response = await chat_service.process_chat_message(
            message=request.message,
            tenant_id=request.tenant_id,
            session_id=request.session_id
        )
        
        # Get tenant schema for column config (only for list/semantic operations)
        tenant_schema = None
        if internal_response.operation in ['list', 'semantic']:
            try:
                tenant_schema = get_tenant_schema(
                    settings.MONGODB_URI, 
                    settings.DATABASE_NAME, 
                    request.tenant_id
                )
            except Exception as e:
                logger.warning(f"Failed to get tenant schema for {request.tenant_id}: {e}")
        
        # Convert to API format
        api_response = format_api_response(
            internal_response,
            tenant_schema=tenant_schema,
            tenant_id=request.tenant_id
        )
        
        logger.info(f"Chat message processed for tenant {request.tenant_id}, operation: {internal_response.operation}")
        return api_response
        
    except HTTPException as e:
        return format_error_response(
            e.detail,
            "http_error"
        )
    except Exception as e:
        logger.error(f"Chat endpoint error for tenant {request.tenant_id}: {e}")
        return format_error_response(
            "Internal server error occurred while processing your request",
            "internal_error"
        )

@router.post("/session/new", response_model=SessionCreateResponse)
async def create_new_session(request: SessionCreateRequest):
    """
    Create new chat session
    
    Args:
        request: Session creation request with tenant_id
        
    Returns:
        New session ID
    """
    try:
        # Validate tenant_id
        if not request.tenant_id or len(request.tenant_id) < 10:
            raise HTTPException(status_code=400, detail="Invalid tenant ID provided")
        
        session_id = await session_service.create_session(request.tenant_id)
        
        logger.info(f"New session created for tenant {request.tenant_id}: {session_id}")
        return SessionCreateResponse(
            session_id=session_id,
            message="Session created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session creation error for tenant {request.tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.get("/session/{session_id}", response_model=Dict[str, Any])
async def get_session_info(session_id: str, tenant_id: str):
    """
    Get session information and history
    
    Args:
        session_id: Session ID to retrieve
        tenant_id: Tenant ID (can be passed as query parameter)
        
    Returns:
        Session information in API format
    """
    try:
        # Validate tenant_id
        if not tenant_id or len(tenant_id) < 10:
            return {
                "success": False,
                "message": "Invalid tenant ID provided",
                "data": {"session_id": session_id}
            }
        
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
        logger.error(f"Session retrieval error for tenant {tenant_id}: {e}")
        return {
            "success": False,
            "message": "Failed to retrieve session",
            "data": {"error": str(e)}
        }

@router.delete("/session/{session_id}", response_model=Dict[str, Any])
async def delete_session(session_id: str, tenant_id: str):
    """
    Delete chat session
    
    Args:
        session_id: Session ID to delete
        tenant_id: Tenant ID (can be passed as query parameter)
        
    Returns:
        Deletion confirmation in API format
    """
    try:
        # Validate tenant_id
        if not tenant_id or len(tenant_id) < 10:
            return {
                "success": False,
                "message": "Invalid tenant ID provided",
                "data": {"session_id": session_id}
            }
        
        await session_service.delete_session(session_id, tenant_id)
        
        logger.info(f"Session deleted for tenant {tenant_id}: {session_id}")
        return {
            "success": True,
            "message": "Session deleted successfully",
            "data": {"session_id": session_id}
        }
        
    except Exception as e:
        logger.error(f"Session deletion error for tenant {tenant_id}: {e}")
        return {
            "success": False,
            "message": "Failed to delete session",
            "data": {"error": str(e), "session_id": session_id}
        }

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint"""
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
async def get_capabilities(tenant_id: str):
    """
    Get chat service capabilities for this tenant
    
    Args:
        tenant_id: Tenant ID (query parameter)
    
    Returns:
        Available operations and features
    """
    try:
        # Validate tenant_id
        if not tenant_id or len(tenant_id) < 10:
            return {
                "success": False,
                "message": "Invalid tenant ID provided",
                "data": {"error": "Invalid tenant ID"}
            }
        
        # You could get actual tenant-specific capabilities here
        capabilities = {
            "operations": ["list", "semantic", "distribution", "advisory"],
            "features": ["conversation_memory", "strategic_insights", "content_analysis"],
            "max_message_length": 1000,
            "supported_languages": ["en"],
            "tenant_id": tenant_id
        }
        
        return {
            "success": True,
            "message": "Chat capabilities retrieved",
            "data": capabilities
        }
        
    except Exception as e:
        logger.error(f"Capabilities retrieval error for tenant {tenant_id}: {e}")
        return {
            "success": False,
            "message": "Failed to retrieve capabilities",
            "data": {"error": str(e)}
        }