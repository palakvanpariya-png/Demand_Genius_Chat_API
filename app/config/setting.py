# app/config/settings.py
"""
New settings manager - Backward compatible with your existing code
NO CHANGES needed in other files that import from here
"""
import os
from decouple import config
from app.config.settings.base import BackendBaseSettings
from app.config.settings.development import BackendDevSettings
from app.config.settings.staging import BackendStageSettings
from app.config.settings.production import BackendProdSettings

# Determine environment from .env file
ENV = config("ENVIRONMENT", default="DEV")

def get_settings() -> BackendBaseSettings:
    """
    Factory function to return appropriate settings based on environment
    """
    env_map = {
        "DEV": BackendDevSettings,
        "DEVELOPMENT": BackendDevSettings,
        "STAGE": BackendStageSettings,
        "STAGING": BackendStageSettings,
        "PROD": BackendProdSettings,
        "PRODUCTION": BackendProdSettings,
    }
    
    settings_class = env_map.get(ENV.upper(), BackendDevSettings)
    return settings_class()


# Create global settings instance - THIS IS WHAT YOUR CODE USES
settings = get_settings()


# Validation function (from your original settings.py)
def validate_settings():
    """Validate critical settings on startup"""
    errors = []
    
    if not settings.OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY must be set")
    
    if not settings.MONGODB_URI:
        errors.append("MONGODB_URI must be set")
        
    if not settings.DATABASE_NAME:
        errors.append("DATABASE_NAME must be set")
    
    if settings.SECRET_KEY == "your-secret-key-change-in-production":
        errors.append("SECRET_KEY should be changed from default value")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True


# Backward compatibility - expose Settings class
Settings = type(settings)

# You can also add helpful info
def get_current_environment():
    """Get current environment name"""
    return getattr(settings, 'ENVIRONMENT', 'DEV')