# app/config/settings/base.py
import logging
import pathlib
from decouple import config
from pydantic_settings import BaseSettings
from typing import Optional

ROOT_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent.parent.parent.resolve()

class BackendBaseSettings(BaseSettings):
    """
    Base settings - contains ALL configurations from your working settings.py
    This is the single source of truth that can be overridden by environment-specific configs
    """
    
    # Application Metadata
    TITLE: str = "Content Intelligence API"
    VERSION: str = "1.0.0"
    TIMEZONE: str = "UTC"
    DESCRIPTION: Optional[str] = "Natural language content analysis chatbot"
    DEBUG: bool = config("DEBUG", default=False, cast=bool)
    
    # Server Configuration
    SERVER_HOST: str = config("API_HOST", default="0.0.0.0", cast=str)
    SERVER_PORT: int = config("API_PORT", default=8000, cast=int)
    API_PREFIX: str = "/api"
    DOCS_URL: str = "/docs"
    OPENAPI_URL: str = "/openapi.json"
    REDOC_URL: str = "/redoc"
    
    # MongoDB Configuration (Your current setup)
    MONGODB_URI: str = config("MONGODB_URI", default="mongodb+srv://openxcelldev:VDevkdbh8RM0RXDl@clusterox.a54ut1v.mongodb.net/demand-genius")
    DATABASE_NAME: str = config("DATABASE_NAME", default="demand-genius")
    
    # OpenAI Configuration (Your current setup)
    OPENAI_API_KEY: str = config("OPENAI_API_KEY", default="")
    OPENAI_MODEL: str = config("OPENAI_MODEL", default="gpt-4o")
    OPENAI_TEMPERATURE: float = config("OPENAI_TEMPERATURE", default=0.0, cast=float)
    
    # JWT Configuration (Your current setup)
    JWT_SECRET_KEY: str = config("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
    SECRET_KEY: str = config("SECRET_KEY", default="your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int)
    
    # # Redis Configuration (Your current setup)
    REDIS_URL: Optional[str] = config("REDIS_URL", default=None)
    REDIS_TTL_HOURS: int = config("REDIS_TTL_HOURS", default=24, cast=int)
    
    # CORS Configuration (Your current setup)
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # Logging Configuration
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOGGING_LEVEL: int = logging.INFO
    
    # Rate Limiting (Your current setup)
    RATE_LIMIT_REQUESTS: int = config("RATE_LIMIT_REQUESTS", default=60, cast=int)
    RATE_LIMIT_WINDOW: int = config("RATE_LIMIT_WINDOW", default=60, cast=int)
    
    # Query Processing Configuration (Your current setup)
    MAX_QUERY_LENGTH: int = config("MAX_QUERY_LENGTH", default=1000, cast=int)
    MAX_SCHEMA_VALUES: int = config("MAX_SCHEMA_VALUES", default=5000, cast=int)
    DEFAULT_PAGE_SIZE: int = config("DEFAULT_PAGE_SIZE", default=50, cast=int)
    MAX_PAGE_SIZE: int = config("MAX_PAGE_SIZE", default=200, cast=int)
    
    # Session Configuration (Your current setup) ---- not being used currently
    MAX_SESSION_INTERACTIONS: int = config("MAX_SESSION_INTERACTIONS", default=10, cast=int)
    SESSION_CLEANUP_INTERVAL: int = config("SESSION_CLEANUP_INTERVAL", default=3600, cast=int)
    
    # API Configuration
    API_TITLE: str = TITLE
    API_DESCRIPTION: str = DESCRIPTION or "Natural language content analysis chatbot"
    API_VERSION: str = VERSION
    API_HOST: str = SERVER_HOST
    API_PORT: int = SERVER_PORT
    
    class Config:
        case_sensitive: bool = True
        env_file: str = f"{str(ROOT_DIR)}/.env"
        env_file_encoding: str = "utf-8"
        validate_assignment: bool = True
    
    @property
    def set_backend_app_attributes(self) -> dict[str, str | bool | None]:
        """
        FastAPI application attributes
        """
        return {
            "title": self.TITLE,
            "version": self.VERSION,
            "debug": self.DEBUG,
            "description": self.DESCRIPTION,
            "docs_url": self.DOCS_URL,
            "openapi_url": self.OPENAPI_URL,
            "redoc_url": self.REDOC_URL,
            "api_prefix": self.API_PREFIX,
        }