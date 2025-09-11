# app/services/database_service.py
from typing import Dict, Any, List, Optional
import logging
from loguru import logger

from ..core.query_builder import MongoQueryExecutor
from ..models.query import QueryResult
from ..models.database import DatabaseResponse
from ..models.content import ContentItem, ContentSummary
from ..config.settings import settings

# logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Service layer for database operations with result transformation
    """
    
    def __init__(self):
        self.executor = MongoQueryExecutor()
        
    async def execute_query(self, query_result: QueryResult) -> DatabaseResponse:
        """
        Execute query and return typed response
        
        Args:
            query_result: Parsed query result
            
        Returns:
            DatabaseResponse with typed data
        """
        try:
            result = self.executor.execute_query_from_result(query_result)
            
            # Transform data if needed
            if result.success and result.data and query_result.operation == "list":
                result.data = await self._transform_content_data(result.data)
            
            return result
            
        except Exception as e:
            logger.error(f"Database service error: {e}")
            return DatabaseResponse(
                success=False,
                error=str(e),
                operation=query_result.operation
            )
    
    async def _transform_content_data(self, raw_data: List[Dict]) -> List[ContentSummary]:
        """Transform raw MongoDB data to ContentSummary objects"""
        transformed = []
        
        for item in raw_data:
            try:
                # Convert ObjectIds to strings and create summary
                summary = ContentSummary(
                    id=str(item.get("_id", "")),
                    name=item.get("name", ""),
                    content_type=item.get("content_type_info", [{}])[0].get("name") if item.get("content_type_info") else None,
                    topic=item.get("topic_info", [{}])[0].get("name") if item.get("topic_info") else None,
                    geo_focus=item.get("geoFocus"),
                    word_count=item.get("wordCount"),
                    is_marketing_content=item.get("isMarketingContent", False),
                    created_at=item.get("createdAt").isoformat() if item.get("createdAt") else None
                )
                transformed.append(summary)
            except Exception as e:
                logger.warning(f"Failed to transform content item: {e}")
                continue
        
        return transformed
    
    async def get_content_by_id(self, content_id: str, tenant_id: str) -> Optional[ContentItem]:
        """
        Get single content item by ID
        
        Args:
            content_id: Content item ID
            tenant_id: Tenant ID
            
        Returns:
            ContentItem if found, None otherwise
        """
        try:
            from bson import ObjectId
            db = self.executor._get_db_connection()
            
            result = db.sitemaps.find_one({
                "_id": ObjectId(content_id),
                "tenant": ObjectId(tenant_id)
            })
            
            if result:
                return ContentItem.from_mongo(result)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get content {content_id}: {e}")
            return None
        finally:
            self.executor._close_connection()
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get basic statistics for a tenant
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Statistics dictionary
        """
        try:
            from bson import ObjectId
            db = self.executor._get_db_connection()
            
            stats = {}
            
            # Total content count
            stats["total_content"] = db.sitemaps.count_documents({"tenant": ObjectId(tenant_id)})
            
            # Marketing vs non-marketing content
            marketing_count = db.sitemaps.count_documents({
                "tenant": ObjectId(tenant_id),
                "isMarketingContent": True
            })
            stats["marketing_content"] = marketing_count
            stats["non_marketing_content"] = stats["total_content"] - marketing_count
            
            # Content by language
            language_pipeline = [
                {"$match": {"tenant": ObjectId(tenant_id)}},
                {"$group": {"_id": "$geoFocus", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            stats["by_language"] = list(db.sitemaps.aggregate(language_pipeline))
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get tenant stats: {e}")
            return {}
        finally:
            self.executor._close_connection()

# Global service instance
database_service = DatabaseService()