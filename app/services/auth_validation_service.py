# app/services/auth_validation_service.py
from typing import Optional
from fastapi import HTTPException
from bson import ObjectId
from loguru import logger

from ..config.database import db_connection


class AuthValidationService:
    """Validates user and tenant relationships"""
    
    @staticmethod
    async def validate_user_tenant_access(user_id: str, tenant_id: str) -> bool:
        """
        Comprehensive validation:
        1. User exists and is verified
        2. Tenant exists and is active
        3. User belongs to tenant
        4. UserTenant relationship is active
        """
        try:
            db = db_connection.get_database()
            
            # Step 1: Validate User
            user = db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                logger.warning(f"User {user_id} not found")
                raise HTTPException(401, "User not found")
            
            if not user.get("isEmailVerified", False):
                logger.warning(f"User {user_id} Email not verified")
                raise HTTPException(403, "User account Email not verified")
            
            # if not user.get("isActive", False):
            #     logger.warning(f"User {user_id} is inactive")
            #     raise HTTPException(403, "User account is inactive")
            
            
            # Step 2: Validate Tenant
            tenant = db.tenants.find_one({"_id": ObjectId(tenant_id)})
            if not tenant:
                logger.warning(f"Tenant {tenant_id} not found")
                raise HTTPException(404, "Tenant not found")
            
            if not tenant.get("isActive", False):
                logger.warning(f"Tenant {tenant_id} is inactive")
                raise HTTPException(403, "Tenant is inactive")
            
            if not tenant.get("isVerified", False):
                logger.warning(f"Tenant {tenant_id} not verified")
                raise HTTPException(403, "Tenant not verified")
            
            # Step 3: Validate User-Tenant Relationship
            user_tenant = db["user-tenants"].find_one({
                "user": ObjectId(user_id),
                "tenant": ObjectId(tenant_id)
            })
            
            if not user_tenant:
                logger.warning(f"User {user_id} not associated with tenant {tenant_id}")
                raise HTTPException(403, "User not authorized for this tenant")
            
            if not user_tenant.get("isActive", False):
                logger.warning(f"User-Tenant relationship inactive for {user_id} - {tenant_id}")
                raise HTTPException(403, "User access to tenant is inactive")
            
            logger.info(f"Validation passed for user {user_id} and tenant {tenant_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(500, "Failed to validate user access")
    
    @staticmethod
    async def validate_tenant_has_content(tenant_id: str) -> bool:
        """Validate tenant has sitemaps (content)"""
        try:
            db = db_connection.get_database()
            
            count = db.sitemaps.count_documents({"tenant": ObjectId(tenant_id)})
            
            if count == 0:
                logger.warning(f"Tenant {tenant_id} has no content")
                raise HTTPException(404, "Tenant has no content")
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Content validation error: {e}")
            raise HTTPException(500, "Failed to validate tenant content")


# Global instance
auth_validation_service = AuthValidationService()