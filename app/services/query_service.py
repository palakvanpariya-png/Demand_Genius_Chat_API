# app/services/query_service.py  
from typing import Dict, Any, Optional
import logging
from loguru import logger

from ..core.query_parser import SmartQueryParser
from ..models.query import QueryResult
from ..config.settings import settings

# logger = logging.getLogger(__name__)

class QueryService:
    """
    Service layer for query parsing operations
    """
    
    def __init__(self):
        self.parser = SmartQueryParser()
        self._parse_cache: Dict[str, QueryResult] = {}
        self.cache_enabled = True
        
    async def parse_query(self, query_text: str, tenant_id: str, use_cache: bool = True) -> QueryResult:
        """
        Parse natural language query with optional caching
        
        Args:
            query_text: User's natural language query
            tenant_id: Tenant ID for context
            use_cache: Whether to use cached results
            
        Returns:
            QueryResult object
        """
        try:
            # Create cache key
            cache_key = f"{tenant_id}:{hash(query_text.lower().strip())}"
            
            if use_cache and self.cache_enabled and cache_key in self._parse_cache:
                logger.debug(f"Using cached parse result for query: {query_text[:50]}...")
                return self._parse_cache[cache_key]
            
            # Parse query
            result = self.parser.parse(query_text, tenant_id)
            
            # Cache result
            if use_cache and self.cache_enabled:
                self._parse_cache[cache_key] = result
                # Limit cache size
                if len(self._parse_cache) > 1000:
                    # Remove oldest entries
                    oldest_keys = list(self._parse_cache.keys())[:100]
                    for key in oldest_keys:
                        del self._parse_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse query '{query_text}' for tenant {tenant_id}: {e}")
            raise
    
    async def validate_query(self, query_text: str) -> bool:
        """
        Validate query text without parsing
        
        Args:
            query_text: Query to validate
            
        Returns:
            True if query is valid
        """
        if not query_text or not query_text.strip():
            return False
        if len(query_text) > settings.MAX_QUERY_LENGTH:
            return False
        return True
    
    async def clear_cache(self, tenant_id: Optional[str] = None):
        """
        Clear parse cache
        
        Args:
            tenant_id: Specific tenant to clear, or None for all
        """
        if tenant_id:
            keys_to_remove = [key for key in self._parse_cache.keys() if key.startswith(f"{tenant_id}:")]
            for key in keys_to_remove:
                del self._parse_cache[key]
            logger.info(f"Cleared parse cache for tenant {tenant_id}")
        else:
            self._parse_cache.clear()
            logger.info("Cleared all parse cache")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self._parse_cache),
            "cache_enabled": self.cache_enabled,
            "max_query_length": settings.MAX_QUERY_LENGTH
        }

# Global service instance
query_service = QueryService()