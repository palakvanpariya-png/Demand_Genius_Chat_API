# app/api/middleware/validation.py
from fastapi import HTTPException
from typing import Optional
import re
from loguru import logger

from ..config.setting import settings


class ValidationMiddleware:
    """Request validation middleware"""
    
    @staticmethod
    def validate_session_id(session_id: Optional[str]) -> bool:
        """Validate session_id format (UUID)"""
        if not session_id:
            return True  # Optional field
        
        # UUID v4 format
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, session_id, re.IGNORECASE):
            raise HTTPException(400, "Invalid session_id format. Must be valid UUID v4.")
        
        return True
    
    @staticmethod
    def validate_message(message: str) -> bool:
        """Validate message content"""
        if not message or not message.strip():
            raise HTTPException(400, "Message cannot be empty")
        
        if len(message) > settings.MAX_QUERY_LENGTH:
            raise HTTPException(
                400, 
                f"Message too long. Maximum {settings.MAX_QUERY_LENGTH} characters allowed."
            )
        
        # Check for minimum length
        if len(message.strip()) < 2:
            raise HTTPException(400, "Message too short. Minimum 2 characters required.")
        
        # Check for suspicious patterns (NoSQL injection, XSS)
        suspicious_patterns = [
            r'\$where',
            r'\$ne',
            r'<script',
            r'javascript:',
            r'onerror=',
            r'onclick=',
        ]
        
        message_lower = message.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, message_lower):
                logger.warning(f"Suspicious pattern detected: {pattern}")
                raise HTTPException(400, "Message contains invalid characters")
        
        return True
    
    @staticmethod
    def sanitize_message(message: str) -> str:
        """Sanitize message input"""
        # Remove leading/trailing whitespace
        message = message.strip()
        
        # Remove null bytes
        message = message.replace('\x00', '')
        
        # Normalize whitespace
        message = ' '.join(message.split())
        
        # Limit consecutive special characters
        message = re.sub(r'([^\w\s])\1{3,}', r'\1\1', message)
        
        return message