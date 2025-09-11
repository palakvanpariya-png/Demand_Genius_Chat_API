# app/models/errors.py
from pydantic import BaseModel
from typing import Optional

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[str] = None
    suggested_questions: Optional[list] = None

class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    success: bool = False
    error: str = "Validation failed"
    validation_errors: list