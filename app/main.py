
# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from .config.settings import settings, validate_settings
from .config.database import db_connection
from .api.routes import health, chat
from .utils.logger import setup_logger

# Setup logging
setup_logger()
# logger = logging.getLogger(__name__)

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
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Content Intelligence API",
        "version": settings.API_VERSION,
        "status": "running"
    }
