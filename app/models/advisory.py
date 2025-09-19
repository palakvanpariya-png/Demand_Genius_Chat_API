# app/models/advisory.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class AdvisoryResponse(BaseModel):
    """
    Standard advisory response model
    Replaces dict returns from generate_advisory method
    """
    response: str = Field(..., description="Advisory response text")
    suggested_questions: List[str] = Field(default_factory=list, description="Follow-up question suggestions")
    confidence: str = Field(default="medium", description="Confidence level: high, medium, low")
    operation: Optional[str] = Field(None, description="Operation type that generated this response")
    session_id: Optional[str] = Field(None, description="Session ID if applicable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "I found 150 content pieces matching your search criteria.",
                "suggested_questions": [
                    "How is this content distributed across categories?",
                    "What gaps exist in this content area?"
                ],
                "confidence": "high",
                "operation": "list",
                "session_id": "session-123"
            }
        }

class SessionStatsResponse(BaseModel):
    """
    Session statistics response model
    Replaces dict returns from get_session_stats method
    """
    total_sessions: int = Field(default=0, description="Total number of sessions")
    total_interactions: int = Field(default=0, description="Total number of interactions across all sessions")
    active_sessions_24h: Optional[int] = Field(None, description="Active sessions in last 24 hours")
    service_version: str = Field(default="streamlined_v1", description="Advisory service version")
    advisory_system: str = Field(default="4-file_architecture", description="Advisory system type")
    agents: List[str] = Field(
        default_factory=lambda: ["ContentResultsAgent", "DistributionAgent", "AdvisoryAgent"],
        description="List of available advisory agents"
    )
    storage_type: Optional[str] = Field(None, description="Session storage type (mongodb, memory)")
    max_memory_length: Optional[int] = Field(None, description="Maximum interactions stored per session")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_sessions": 25,
                "total_interactions": 150,
                "active_sessions_24h": 5,
                "service_version": "streamlined_v1",
                "advisory_system": "4-file_architecture",
                "agents": ["ContentResultsAgent", "DistributionAgent", "AdvisoryAgent"],
                "storage_type": "mongodb",
                "max_memory_length": 10
            }
        }

class PerformanceMetrics(BaseModel):
    """
    Performance metrics model
    Replaces dict returns from get_performance_metrics method
    """
    active_sessions: int = Field(default=0, description="Currently active sessions")
    total_interactions: int = Field(default=0, description="Total interactions processed")
    avg_interactions_per_session: float = Field(default=0.0, description="Average interactions per session")
    system_type: str = Field(default="streamlined_advisory", description="System architecture type")
    expected_performance: str = Field(
        default="4-6s per response (50% faster than previous)",
        description="Expected response time performance"
    )
    architecture: str = Field(default="operation_based_routing", description="Routing architecture")
    uptime_hours: Optional[float] = Field(None, description="System uptime in hours")
    response_time_avg: Optional[float] = Field(None, description="Average response time in seconds")
    success_rate: Optional[float] = Field(None, description="Success rate percentage")
    
    class Config:
        json_schema_extra = {
            "example": {
                "active_sessions": 12,
                "total_interactions": 350,
                "avg_interactions_per_session": 14.0,
                "system_type": "streamlined_advisory",
                "expected_performance": "4-6s per response (50% faster than previous)",
                "architecture": "operation_based_routing",
                "uptime_hours": 24.5,
                "response_time_avg": 4.2,
                "success_rate": 98.5
            }
        }

class AdvisoryHealthResponse(BaseModel):
    """
    Advisory-specific health check response model
    Replaces dict returns from health_check method
    """
    status: str = Field(default="healthy", description="Health status: healthy, degraded, error")
    active_sessions: int = Field(default=0, description="Number of active sessions")
    system: str = Field(default="streamlined_advisory_v1", description="Advisory system identifier")
    agents: int = Field(default=3, description="Number of available agents")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Health check timestamp")
    database_connected: Optional[bool] = Field(None, description="Database connection status")
    openai_configured: Optional[bool] = Field(None, description="OpenAI API configuration status")
    memory_usage: Optional[Dict[str, Any]] = Field(None, description="Memory usage statistics")
    error: Optional[str] = Field(None, description="Error message if status is error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "active_sessions": 8,
                "system": "streamlined_advisory_v1",
                "agents": 3,
                "timestamp": "2024-01-15T10:30:00Z",
                "database_connected": True,
                "openai_configured": True,
                "memory_usage": {
                    "sessions_cached": 25,
                    "schemas_cached": 5
                }
            }
        }

# Confidence level enum for better type safety
class ConfidenceLevel:
    """Advisory confidence levels"""
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"
    
    @classmethod
    def all(cls) -> List[str]:
        return [cls.HIGH, cls.MEDIUM, cls.LOW]

# Health status enum for better type safety
class HealthStatus:
    """Advisory health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    
    @classmethod
    def all(cls) -> List[str]:
        return [cls.HEALTHY, cls.DEGRADED, cls.ERROR]