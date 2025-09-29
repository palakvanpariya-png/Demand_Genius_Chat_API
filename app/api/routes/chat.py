# app/api/routes/chat.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from loguru import logger

from ...models.chat import MessageRequest
from ...utilities.helpers.data_formatters import format_api_response, format_error_response
from ...services.chat_service import chat_service
from ...core.schema_extractor import get_tenant_schema
from ...config.setting import settings
from ...middleware.jwt import get_current_user, JWTAccount
from ...api.dependencies import validate_user_access  # NEW
from ...middleware.validation import ValidationMiddleware  # NEW

router = APIRouter()


@router.post("/ai-chat", response_model=Dict[str, Any])
async def send_message(
    request: MessageRequest, 
    current_user: JWTAccount = Depends(get_current_user),
    validated_user: JWTAccount = Depends(validate_user_access)  # NEW: Full validation
):
    """
    Process chat message with comprehensive validation
    """
    try:
        # Validate and sanitize message
        ValidationMiddleware.validate_message(request.message)
        request.message = ValidationMiddleware.sanitize_message(request.message)
        
        # Validate session_id format
        # ValidationMiddleware.validate_session_id(request.session_id)
        
        # Use validated tenant_id
        tenant_id = validated_user.tenant_id
        
        # Handle session_id
        session_id = request.session_id
        if not session_id:
            from ...services.session_service import session_service
            session_id = await session_service.create_session(tenant_id)
            logger.info(f"Auto-created session {session_id}")
        
        # Process chat message
        internal_response = await chat_service.process_chat_message(
            message=request.message,
            tenant_id=tenant_id,
            session_id=session_id
        )
        
        # Get tenant schema
        tenant_schema = None
        if internal_response.operation in ['list', 'semantic']:
            try:
                tenant_schema = get_tenant_schema(
                    settings.MONGODB_URI, 
                    settings.DATABASE_NAME, 
                    tenant_id
                )
            except Exception as e:
                logger.warning(f"Failed to get tenant schema: {e}")
        
        # Format response
        api_response = format_api_response(
            internal_response,
            tenant_schema=tenant_schema,
            tenant_id=tenant_id
        )
        
        # Include session_id
        if "data" in api_response:
            api_response["data"]["session_id"] = session_id
        else:
            api_response["data"] = {"session_id": session_id}
        
        logger.info(f"Chat processed: tenant={tenant_id}, user={validated_user.user_id}, session={session_id}")
        return api_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return format_error_response("Internal server error", "internal_error")