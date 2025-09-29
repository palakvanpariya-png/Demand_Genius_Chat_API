# app/api/routes/chat.py - Updated with LangChain integration and streaming support
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
import logging
import json
from loguru import logger

from ...models.chat import MessageRequest, APIResponse, SessionCreateResponse
from ...utilities.helpers.data_formatters import format_api_response, format_error_response
from ...services.chat_service import chat_service
from ...services.session_service import session_service
from ...core.schema_extractor import get_tenant_schema
from ...config.setting import settings
from ...securities.jwt import get_current_user, JWTAccount

router = APIRouter()

@router.post("/message", response_model=Dict[str, Any])
async def send_message(
    request: MessageRequest, 
    current_user: JWTAccount = Depends(get_current_user)
):
    """Process chat message and return advisory response in API format"""
    try:
        # Validate message length
        if len(request.message) > 1000:
            return format_error_response(
                "Message too long. Maximum 1000 characters allowed.",
                "validation_error"
            )
        
        # Use tenant_id from JWT payload
        tenant_id = current_user.tenant_id
        
        # Handle session_id from frontend
        session_id = request.session_id
        if not session_id:
            # Frontend didn't provide session_id, create new one
            session_id = await session_service.create_session(tenant_id)
            logger.info(f"Auto-created session {session_id} for tenant {tenant_id}")
        # ✅ REMOVED: No need to check if session exists
        # MongoDB upsert will handle session creation on first interaction
        
        # Process the chat message using context-aware parser
        internal_response = await chat_service.process_chat_message(
            message=request.message,
            tenant_id=tenant_id,
            session_id=session_id  # Use frontend's ID or backend-generated
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
        
        # Always include session_id in response
        if "data" in api_response:
            api_response["data"]["session_id"] = session_id
        else:
            api_response["data"] = {"session_id": session_id}
        
        logger.info(f"Chat message processed for tenant {tenant_id}, session {session_id}, operation: {internal_response.operation}")
        return api_response
        
    except HTTPException as e:
        return format_error_response(e.detail, "http_error")
    except Exception as e:
        logger.error(f"Chat endpoint error for tenant {current_user.tenant_id}: {e}")
        return format_error_response(
            "Internal server error occurred while processing your request",
            "internal_error"
        )

@router.post("/message/stream")
async def send_message_streaming(
    request: MessageRequest,
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    NEW: Process chat message with streaming response
    Provides real-time token streaming using LangChain
    """
    async def generate_stream():
        try:
            # Validate message length
            if len(request.message) > 1000:
                yield f"data: {json.dumps({'type': 'error', 'data': {'error': 'Message too long. Maximum 1000 characters allowed.'}})}\n\n"
                return
            
            # Use tenant_id from JWT payload
            tenant_id = current_user.tenant_id
            
            # Auto-handle session creation (same logic as non-streaming)
            session_id = request.session_id
            if not session_id:
                session_id = await session_service.create_session(tenant_id)
                logger.info(f"Auto-created session {session_id} for streaming")
            else:
                existing_session = await session_service.get_session(session_id, tenant_id)
                if not existing_session:
                    session_id = await session_service.create_session(tenant_id)
            
            # Process the streaming chat message
            async for chunk in chat_service.process_chat_message_streaming(
                message=request.message,
                tenant_id=tenant_id,
                session_id=session_id
            ):
                # Send each chunk as Server-Sent Events
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Send final completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming chat endpoint error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

# EXISTING ENDPOINTS - UNCHANGED for backward compatibility
@router.post("/session/new", response_model=SessionCreateResponse)
async def create_new_session(current_user: JWTAccount = Depends(get_current_user)):
    """Create new chat session - UNCHANGED"""
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
    """Get session information and history - UNCHANGED"""
    try:
        tenant_id = current_user.tenant_id
        
        session_info = await session_service.get_session(session_id, tenant_id)
        
        if not session_info:
            return {
                "success": False,
                "message": "Session not found",
                "data": {"session_id": session_id}
            }
        
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
    """Delete chat session - UNCHANGED"""
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
    """Health check endpoint - UNCHANGED"""
    from datetime import datetime
    return {
        "success": True,
        "message": "Chat service is healthy",
        "data": {
            "service": "chat",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "langchain_enabled": True  # NEW: indicate LangChain integration
        }
    }

@router.get("/capabilities", response_model=Dict[str, Any])
async def get_capabilities(current_user: JWTAccount = Depends(get_current_user)):
    """Get chat service capabilities - ENHANCED with streaming"""
    try:
        tenant_id = current_user.tenant_id
        
        capabilities = {
            "operations": ["list", "semantic", "distribution", "advisory", "clarification"],
            "features": [
                "conversation_memory", 
                "strategic_insights", 
                "content_analysis",
                "langchain_orchestration",  # NEW
                "streaming_responses"       # NEW
            ],
            "max_message_length": 1000,
            "supported_languages": ["en"],
            "streaming_supported": True,    # NEW
            "langchain_version": "0.1.0",   # NEW
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