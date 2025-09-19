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

class DataSummary(BaseModel):
    """
    Simple data summary for API responses
    Handles all _create_data_summary return types
    """
    type: str = Field(..., description="Summary type: error, advisory, content_list, distribution, unknown")
    message: Optional[str] = Field(None, description="Message for error or advisory types")
    count: Optional[int] = Field(None, description="Number of items shown (for content_list)")
    total: Optional[int] = Field(None, description="Total items available (for content_list)")
    has_more: Optional[bool] = Field(None, description="Whether more items available (for content_list)")
    categories: Optional[int] = Field(None, description="Number of categories (for distribution)")
    fields: Optional[List[str]] = Field(None, description="Distribution fields (for distribution)")
    operation: Optional[str] = Field(None, description="Operation name (for unknown type)")
    error: Optional[bool] = Field(None, description="Error flag")
    
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