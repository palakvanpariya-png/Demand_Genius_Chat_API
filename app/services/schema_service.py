# app/services/schema_service.py
from typing import Dict, Any, Optional
import logging
from loguru import logger

from ..core.schema_extractor import SchemaExtractor
from ..config.setting import settings

# logger = logging.getLogger(__name__)

class SchemaService:
    """
    Service layer for schema operations with caching
    """
    
    def __init__(self):
        self.extractor = SchemaExtractor()
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600  # 1 hour cache
    
    async def get_tenant_schema(self, tenant_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get tenant schema with optional caching
        
        Args:
            tenant_id: Tenant ID
            use_cache: Whether to use cached schema
            
        Returns:
            Tenant schema dictionary
        """
        try:
            if use_cache and tenant_id in self._schema_cache:
                logger.debug(f"Using cached schema for tenant {tenant_id}")
                return self._schema_cache[tenant_id]
            
            logger.info(f"Extracting fresh schema for tenant {tenant_id}")
            schema = self.extractor.extract_tenant_schema(tenant_id)
            logger.debug(f"Extracted schema for tenant {tenant_id}: {schema}")
            if use_cache:
                self._schema_cache[tenant_id] = schema
                
            return schema
            
        except Exception as e:
            logger.error(f"Failed to get schema for tenant {tenant_id}: {e}")
            raise
    
    async def validate_tenant_exists(self, tenant_id: str) -> bool:
        """
        Check if tenant exists and has valid schema
        
        Args:
            tenant_id: Tenant ID to validate
            
        Returns:
            True if tenant exists and has content
        """
        try:
            schema = await self.get_tenant_schema(tenant_id)
            return schema.get("document_counts", {}).get("sitemaps", 0) > 0
        except Exception:
            return False
    
    async def get_tenant_categories(self, tenant_id: str) -> Dict[str, list]:
        """
        Get just the categories for a tenant
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Categories dictionary
        """
        schema = await self.get_tenant_schema(tenant_id)
        return schema.get("categories", {})
    
    async def clear_cache(self, tenant_id: Optional[str] = None):
        """
        Clear schema cache
        
        Args:
            tenant_id: Specific tenant to clear, or None for all
        """
        if tenant_id:
            self._schema_cache.pop(tenant_id, None)
            logger.info(f"Cleared cache for tenant {tenant_id}")
        else:
            self._schema_cache.clear()
            logger.info("Cleared all schema cache")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_tenants": list(self._schema_cache.keys()),
            "cache_size": len(self._schema_cache),
            "cache_ttl": self._cache_ttl
        }

# Global service instance
schema_service = SchemaService()