# app/config/settings/production.py
from app.config.settings.base import BackendBaseSettings
from app.config.settings.environment import Environment

class BackendProdSettings(BackendBaseSettings):
    """Production-specific settings"""
    DESCRIPTION: str | None = "Production Environment - Content Intelligence API"
    DEBUG: bool = False
    ENVIRONMENT: Environment = Environment.PRODUCTION
    
    # Production security
    LOG_LEVEL: str = "WARNING"
    
    # Stricter CORS for production
    # CORS_ORIGINS will be loaded from .env in production