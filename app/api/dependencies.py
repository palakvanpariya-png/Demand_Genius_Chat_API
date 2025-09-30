# app/api/dependencies.py
from fastapi import Header, HTTPException, Depends
from typing import Optional
from loguru import logger

from ..config.database import get_database, get_mongo_client
from ..services.schema_service import schema_service
from ..services.auth_validation_service import auth_validation_service
from ..middleware.jwt import JWTAccount , get_current_user 


async def validate_user_access(
    current_user: JWTAccount = Depends(get_current_user)  
) -> JWTAccount:
    """
    Comprehensive validation dependency
    """
    try:
        logger.info(f"Validating access for user={current_user.user_id}, tenant={current_user.tenant_id}")
        
        # Validate user-tenant relationship
        await auth_validation_service.validate_user_tenant_access(
            current_user.user_id,
            current_user.tenant_id
        )
        
        # Validate tenant has content
        await auth_validation_service.validate_tenant_has_content(
            current_user.tenant_id
        )
        
        logger.info(f"Access validation passed for user={current_user.user_id}")
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Access validation error: {e}")
        raise HTTPException(500, "Failed to validate access")


def get_db():
    """Database connection dependency"""
    return get_database()


def get_mongo():
    """MongoDB client dependency"""
    return get_mongo_client()