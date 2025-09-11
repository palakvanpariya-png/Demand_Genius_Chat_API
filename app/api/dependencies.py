# app/api/dependencies.py
from fastapi import Header, HTTPException, Depends
from typing import Optional
import logging
from loguru import logger

from ..config.database import get_database, get_mongo_client
from ..services.schema_service import schema_service

# logger = logging.getLogger(__name__)

async def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> str:
    """
    Extract and validate tenant ID from request headers
    
    Args:
        x_tenant_id: Tenant ID from X-Tenant-ID header
        
    Returns:
        Validated tenant ID
        
    Raises:
        HTTPException: If tenant ID is missing or invalid
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-ID header is required"
        )
    
    if not x_tenant_id.strip():
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-ID cannot be empty"
        )
    
    # Validate tenant exists and has content
    try:
        tenant_exists = await schema_service.validate_tenant_exists(x_tenant_id)
        if not tenant_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {x_tenant_id} not found or has no content"
            )
    except Exception as e:
        logger.error(f"Tenant validation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to validate tenant"
        )
    
    return x_tenant_id

def get_db():
    """Database connection dependency"""
    return get_database()

def get_mongo():
    """MongoDB client dependency"""
    return get_mongo_client()