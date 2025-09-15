# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional
import os
import decouple
config = decouple.config

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
    
    # API_TOKEN: str = config("API_TOKEN", cast=str)
    # AUTH_TOKEN: str = config("AUTH_TOKEN", cast=str)
    # JWT_TOKEN_PREFIX: str = config("JWT_TOKEN_PREFIX", cast=str)
    JWT_SECRET_KEY: str = config("JWT_SECRET_KEY", cast=str)
    # JWT_SUBJECT: str = config("JWT_SUBJECT", cast=str)
    # JWT_MIN: int = config("JWT_MIN", cast=int)
    # JWT_HOUR: int = config("JWT_HOUR", cast=int)
    # JWT_DAY: int = config("JWT_DAY", cast=int)
    # JWT_ACCESS_TOKEN_EXPIRATION_TIME: int = JWT_MIN * JWT_HOUR * JWT_DAY

    # IS_ALLOWED_CREDENTIALS: bool = config("IS_ALLOWED_CREDENTIALS", cast=bool)
    # ALLOWED_ORIGINS: list[str] = [
    #     "http://localhost:3000",  # React default port
    #     "http://0.0.0.0:3000",
    #     "http://127.0.0.1:3000",  # React docker port
    #     "http://127.0.0.1:3001",
    #     "http://localhost:5173",  # Qwik default port
    #     "http://0.0.0.0:5173",
    #     "http://127.0.0.1:5173",  # Qwik docker port
    #     "http://127.0.0.1:5174",
    # ]
    # ALLOWED_METHODS: list[str] = ["*"]
    # ALLOWED_HEADERS: list[str] = ["*"]

    # LOGGING_LEVEL: int = logging.INFO
    # LOGGERS: tuple[str, str] = ("uvicorn.asgi", "uvicorn.access")

    # HASHING_ALGORITHM_LAYER_1: str = config("HASHING_ALGORITHM_LAYER_1", cast=str)
    # HASHING_ALGORITHM_LAYER_2: str = config("HASHING_ALGORITHM_LAYER_2", cast=str)
    # HASHING_SALT: str = config("HASHING_SALT", cast=str)
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", cast=str)

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

