from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class InteractionRecord(BaseModel):
    """Single chat interaction record"""
    timestamp: str
    message: str
    response_summary: str = Field(..., max_length=200)
    operation: str
    confidence: Optional[str] = None

class SessionInfo(BaseModel):
    """Session information"""
    session_id: str
    tenant_id: str
    created_at: str
    interactions: List[InteractionRecord] = Field(default_factory=list)
    
    @property
    def interaction_count(self) -> int:
        return len(self.interactions)
    
    @property
    def last_interaction(self) -> Optional[InteractionRecord]:
        return self.interactions[-1] if self.interactions else None

class SessionHistory(BaseModel):
    """Session history response"""
    session_info: SessionInfo
    conversation_summary: str
    recent_topics: List[str] = Field(default_factory=list)
    has_history: bool = True