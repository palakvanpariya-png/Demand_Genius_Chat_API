# app/models/chat.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .database import DatabaseResponse


class MessageRequest(BaseModel):
    """Request model for chat message - only contains message and optional session_id"""
    message: str
    session_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User's natural language query")
    tenant_id: Optional[str] = Field(..., description="Tenant ID for the request")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation context")

class ChatResponse(BaseModel):
    """Internal response model - keep all fields for processing"""
    success: bool
    response: str  # This becomes the "message" in API response
    suggested_questions: List[str] = Field(default_factory=list)
    confidence: str = Field(default="medium")
    operation: str
    session_id: Optional[str] = None
    data_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    db_response: Optional[DatabaseResponse] = None

class APIResponse(BaseModel):
    """Clean API response format matching frontend expectations"""
    success: bool
    message: str  # This is our LLM response text
    data: Dict[str, Any]  # Contains sitemaps and columnConfig

class SessionCreateRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant ID for the session")

class SessionCreateResponse(BaseModel):
    session_id: str
    message: str = "Session created successfully"

class JWTAccount(BaseModel):
    user_id: str
    tenant_id: str