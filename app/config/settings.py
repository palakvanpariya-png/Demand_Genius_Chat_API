# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database Configuration
    MONGODB_URI: str = "mongodb+srv://openxcelldev:VDevkdbh8RM0RXDl@clusterox.a54ut1v.mongodb.net/demand-genius"
    DATABASE_NAME: str = "demand-genius"
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = "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"
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.0
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    API_TITLE: str = "Content Intelligence API"
    API_DESCRIPTION: str = "Natural language content analysis chatbot"
    API_VERSION: str = "1.0.0"
    
    # Security Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis Configuration (Optional - for session management)
    REDIS_URL: Optional[str] = None
    REDIS_TTL_HOURS: int = 24
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS Configuration
    CORS_ORIGINS: list = ["*"]  # Configure properly for production
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # Rate Limiting (requests per minute)
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Query Processing Configuration
    MAX_QUERY_LENGTH: int = 1000
    MAX_SCHEMA_VALUES: int = 5000  # Threshold for large schema handling
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 200
    
    # Session Configuration
    MAX_SESSION_INTERACTIONS: int = 10
    SESSION_CLEANUP_INTERVAL: int = 3600  # seconds
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# Global settings instance
settings = Settings()

# Validation function
def validate_settings():
    """Validate critical settings on startup"""
    errors = []
    
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key":
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

