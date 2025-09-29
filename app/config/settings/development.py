# app/config/settings/development.py
from app.config.settings.base import BackendBaseSettings
from app.config.settings.environment import Environment

class BackendDevSettings(BackendBaseSettings):
    """Development-specific settings"""
    DESCRIPTION: str | None = "Development Environment - Content Intelligence API"
    DEBUG: bool = True
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    
    # Override logging for development
    LOG_LEVEL: str = "DEBUG"
    
    # More permissive CORS for local development
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]