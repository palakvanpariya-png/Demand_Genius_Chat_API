# app/config/settings/staging.py
from app.config.settings.base import BackendBaseSettings
from app.config.settings.environment import Environment

class BackendStageSettings(BackendBaseSettings):
    """Staging-specific settings"""
    DESCRIPTION: str | None = "Staging Environment - Content Intelligence API"
    DEBUG: bool = True
    ENVIRONMENT: Environment = Environment.STAGING
    
    # Staging might have specific test database
    # DATABASE_NAME: str = "demand-genius-staging"
