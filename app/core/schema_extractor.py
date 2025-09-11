# app/core/schema_extractor.py
from pymongo import MongoClient
from bson import ObjectId
from typing import Dict, List, Any, Optional
import logging
from loguru import logger

from ..config.settings import settings

# logger = logging.getLogger(__name__)

class SchemaExtractor:
    """
    Extracts and caches tenant schema information from MongoDB
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self._client = None
        self._db = None
    
    def _get_db_connection(self):
        """Get database connection with proper error handling"""
        if not self._client:
            try:
                self._client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
                self._db = self._client[self.db_name]
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return self._db
    
    def _close_connection(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
    
    def extract_tenant_schema(self, tenant_id: str) -> Dict[str, Any]:
        """
        Extract complete schema information for a tenant
        
        Args:
            tenant_id: Tenant ID to extract schema for
        
        Returns:
            Dictionary containing categories, field_mappings, and collection_schemas
        """
        try:
            db = self._get_db_connection()
            tenant_obj_id = ObjectId(tenant_id) if isinstance(tenant_id, str) else tenant_id
            
            # Extract all schema components
            categories = self._extract_categories(db, tenant_obj_id)
            field_mappings = self._get_field_mappings(categories)
            collection_schemas = self._get_collection_schemas()
            doc_counts = self._get_document_counts(db, tenant_obj_id, collection_schemas.keys())
            
            return {
                "tenant_id": str(tenant_obj_id),
                "categories": categories,
                "field_mappings": field_mappings,
                "collection_schemas": collection_schemas,
                "document_counts": doc_counts,
                "summary": {
                    "total_categories": len(categories),
                    "total_values": sum(len(v) for v in categories.values()),
                    "collections": len(collection_schemas)
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting schema for tenant {tenant_id}: {e}")
            raise
        finally:
            self._close_connection()
    
    def _extract_categories(self, db, tenant_obj_id: ObjectId) -> Dict[str, List[str]]:
        """Extract all categories and their values for a tenant"""
        categories_data = {}
        
        try:
            # Get all categories for this tenant
            categories = {str(cat["_id"]): cat["name"] 
                         for cat in db.categories.find({"tenant": tenant_obj_id})}
            
            # Get category attributes mapping
            category_attrs = {}
            for attr in db.category_attributes.find({"tenant": tenant_obj_id}):
                category_id = str(attr["category"])
                category_name = categories.get(category_id)
                if category_name:
                    category_attrs[str(attr["_id"])] = {
                        "category_name": category_name,
                        "attribute_name": attr["name"]
                    }
            
            # Extract values from sitemaps
            for doc in db.sitemaps.find({"tenant": tenant_obj_id}):
                # Category attributes
                attr_ids = doc.get("categoryAttribute", [])
                for attr_id in attr_ids:
                    attr_info = category_attrs.get(str(attr_id))
                    if attr_info:
                        cat_name = attr_info["category_name"]
                        if cat_name not in categories_data:
                            categories_data[cat_name] = set()
                        categories_data[cat_name].add(attr_info["attribute_name"])
                
                # Language (geoFocus)
                geo_focus = doc.get("geoFocus")
                if geo_focus:
                    if "Language" not in categories_data:
                        categories_data["Language"] = set()
                    categories_data["Language"].add(geo_focus)
            
            # Content Types
            content_types = db.content_types.find({"tenant": tenant_obj_id})
            categories_data["Content Type"] = {ct["name"] for ct in content_types if ct.get("name")}
            
            # Topics
            topics = db.topics.find({"tenant": tenant_obj_id})
            categories_data["Topics"] = {topic["name"] for topic in topics if topic.get("name")}
            
            # Custom Tags
            custom_tags = db.custom_tags.find({"tenant": tenant_obj_id})
            categories_data["Custom Tags"] = {tag["name"] for tag in custom_tags if tag.get("name")}
            
            # Convert sets to sorted lists
            return {k: sorted(list(v)) for k, v in categories_data.items() if v}
            
        except Exception as e:
            logger.error(f"Error extracting categories: {e}")
            return {}
    
    def _get_field_mappings(self, categories: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        """Get field mappings for database queries"""
        field_mappings = {
            "Language": {
                "collection": "sitemaps",
                "field": "geoFocus",
                "requires_join": False,
                "field_type": "string"
            },
            "Content Type": {
                "collection": "sitemaps",
                "field": "contentType",
                "reference_collection": "content_types",
                "requires_join": True,
                "join_on": "_id",
                "display_field": "name"
            },
            "Topics": {
                "collection": "sitemaps",
                "field": "topic",
                "reference_collection": "topics",
                "requires_join": True,
                "join_on": "_id",
                "display_field": "name"
            },
            "Custom Tags": {
                "collection": "sitemaps",
                "field": "tag",
                "reference_collection": "custom_tags",
                "requires_join": True,
                "join_on": "_id",
                "display_field": "name",
                "is_array": True
            }
        }
        
        # Add dynamic category mappings
        for category_name in categories.keys():
            if category_name not in field_mappings:
                field_mappings[category_name] = {
                    "collection": "sitemaps",
                    "field": "categoryAttribute",
                    "reference_collection": "category_attributes",
                    "requires_join": True,
                    "join_on": "_id",
                    "display_field": "name",
                    "is_array": True,
                    "filter_by_category": True
                }
        
        return field_mappings
    
    def _get_collection_schemas(self) -> Dict[str, List[str]]:
        """Get static collection schemas"""
        return {
            "sitemaps": [
                "_id", "name", "fullUrl", "path", "domain", "hideForm",
                "contentType", "topic", "tag", "categoryAttribute", "tenant",
                "isMarketingContent", "wordCount", "geoFocus", "description",
                "summary", "readerBenefit", "confidence", "explanation",
                "datePublished", "dateModified", "createdAt", "updatedAt", "__v"
            ],
            "categories": [
                "_id", "name", "tenant", "providerId", "createdAt", 
                "updatedAt", "__v", "slug", "description"
            ],
            "category_attributes": [
                "_id", "category", "tenant", "__v", "createdAt", 
                "name", "updatedAt"
            ],
            "content_types": [
                "_id", "tenant", "__v", "createdAt", "name", "updatedAt"
            ],
            "topics": [
                "_id", "tenant", "__v", "createdAt", "name", "updatedAt"
            ],
            "custom_tags": [
                "_id", "name", "tenant", "providerId", "createdAt", 
                "updatedAt", "__v"
            ]
        }
    
    def _get_document_counts(self, db, tenant_obj_id: ObjectId, collection_names: List[str]) -> Dict[str, int]:
        """Get document counts for collections"""
        doc_counts = {}
        try:
            for collection_name in collection_names:
                count = db[collection_name].count_documents({"tenant": tenant_obj_id})
                doc_counts[collection_name] = count
        except Exception as e:
            logger.error(f"Error getting document counts: {e}")
        return doc_counts


# Global instance for backward compatibility and easy access
_schema_extractor = None

def get_schema_extractor() -> SchemaExtractor:
    """Get global schema extractor instance"""
    global _schema_extractor
    if _schema_extractor is None:
        _schema_extractor = SchemaExtractor()
    return _schema_extractor

def get_tenant_schema(mongo_uri: str, db_name: str, tenant_id: str) -> Dict[str, Any]:
    """
    Backward compatibility function - extract tenant schema
    
    Args:
        mongo_uri: MongoDB connection string  
        db_name: Database name
        tenant_id: Tenant ID to extract schema for
    
    Returns:
        Dictionary containing schema information
    """
    extractor = SchemaExtractor(mongo_uri, db_name)
    return extractor.extract_tenant_schema(tenant_id)