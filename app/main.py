# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from .config.setting import settings, validate_settings
from .config.database import db_connection
from .api.routes import health, chat
# Import debug routes only in debug mode
from .utilities.logger import setup_logger
from app.config.logging_config import setup_logging


# Import debug routes conditionally
if settings.DEBUG:
    from .api.routes import debug

# Setup logging 
setup_logger()
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Content Intelligence API...")
    
    # Validate configuration
    try:
        validate_settings()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    
    # Connect to database
    if not db_connection.connect():
        logger.error("Failed to connect to database")
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    logger.info("Application startup complete")
    
    # Log token tracking status
    if settings.DEBUG:
        logger.info("Token tracking enabled for debugging")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Content Intelligence API...")
    db_connection.disconnect()
    logger.info("Application shutdown complete")

# Create FastAPI application
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(chat.router, prefix="/api/v1/tenant", tags=["chat"])

# Include debug routes only in debug mode
if settings.DEBUG:
    app.include_router(debug.router, prefix="/api/v1/debug", tags=["debug"])
    logger.info("Debug endpoints enabled at /api/v1/debug/")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Content Intelligence API",
        "version": settings.API_VERSION,
        "status": "running",
        "debug_mode": settings.DEBUG,
        "token_tracking": settings.DEBUG
    }