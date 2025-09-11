# app/models/database.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from .content import DistributionResult

class DatabaseResponse(BaseModel):
    """Standard database query response"""
    success: bool
    data: Union[List[Dict[str, Any]], List[DistributionResult], Dict[str, Any]] = Field(default_factory=list)
    total_count: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None
    has_next: Optional[bool] = None
    has_prev: Optional[bool] = None
    operation: str = "unknown"
    distribution_fields: Optional[List[str]] = None
    error: Optional[str] = None
    advisory_mode: bool = False

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str = "content-intelligence-api"
    timestamp: Optional[str] = None
    database_connected: bool = True