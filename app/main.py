# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from .config.setting import settings, validate_settings
from .config.database import db_connection, vector_db_connection  # ✅ ADD
from .api.routes import health, chat, sync  # ✅ ADD sync
from .utilities.logger import setup_logger
from .config.logging_config import setup_logging
from .services.vector_service import vector_service  # ✅ ADD

if settings.DEBUG:
    from .api.routes import debug

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
    
    # Connect to MongoDB
    if not db_connection.connect():
        logger.error("Failed to connect to MongoDB")
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    # ✅ Connect to PostgreSQL (pgvector)
    if settings.VECTOR_SEARCH_ENABLED:
        if vector_db_connection.connect():
            logger.info("✅ Vector database connected")
            # Ensure table exists
            try:
                vector_service._ensure_table_exists()
                logger.info("✅ Vector tables initialized")
            except Exception as e:
                logger.error(f"Failed to initialize vector tables: {e}")
                logger.warning("⚠️ Vector search will be disabled")
                settings.VECTOR_SEARCH_ENABLED = False
        else:
            logger.warning("⚠️ Failed to connect to vector database, disabling vector search")
            settings.VECTOR_SEARCH_ENABLED = False
    else:
        logger.info("Vector search is disabled in configuration")
    
    logger.info("Application startup complete")
    
    # Log token tracking status
    if settings.DEBUG:
        logger.info("Token tracking enabled for debugging")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Content Intelligence API...")
    db_connection.disconnect()
    
    # ✅ Disconnect from PostgreSQL
    if settings.VECTOR_SEARCH_ENABLED:
        vector_db_connection.disconnect()
        logger.info("Vector database disconnected")
    
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
app.include_router(sync.router, prefix="/api/v1/sync", tags=["sync"])  # ✅ ADD

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
        "token_tracking": settings.DEBUG,
        "vector_search": settings.VECTOR_SEARCH_ENABLED  # ✅ ADD
    }