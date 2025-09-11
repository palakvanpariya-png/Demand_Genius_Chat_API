# app/core/query_builder.py
from pymongo import MongoClient
from bson import ObjectId
from typing import Dict, List, Any, Optional, Union
import re
from datetime import datetime
import logging
from loguru import logger

from ..config.settings import settings
from ..config.database import get_database, get_mongo_client
from ..models.query import QueryResult, FilterDict, DateFilter, Pagination
from ..models.database import DatabaseResponse
from ..models.content import DistributionItem, DistributionResult
from .schema_extractor import get_tenant_schema

# Import helper functions
from .helpers.date_utils import parse_date_string
from .helpers.data_formatters import (
    convert_objectids_to_strings, 
    format_sitemap_data, 
    build_pagination_response
)
from .helpers.database_helpers import (
    get_standardized_lookup_pipeline,
    get_category_attribute_ids,
    get_reference_ids,
    get_count
)
from .helpers.query_helpers import (
    build_base_match_query,
    apply_semantic_filters,
    apply_category_filters,
    build_category_condition
)

class MongoQueryExecutor:
    """
    MongoDB query executor that converts QueryResult objects into database operations
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self._schema_cache: Dict[str, Dict] = {}
        self._client = None
        self._db = None

    def _get_db_connection(self):
        """Get database connection with proper management"""
        if not self._client:
            self._client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=50
            )
            self._db = self._client[self.db_name]
        return self._db

    def _close_connection(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    def _get_schema(self, tenant_id: str) -> Dict:
        """Get cached schema for tenant"""
        if tenant_id not in self._schema_cache:
            schema = get_tenant_schema(self.mongo_uri, self.db_name, tenant_id)
            self._schema_cache[tenant_id] = schema
        return self._schema_cache[tenant_id]

    def execute_query_from_result(self, query_result: QueryResult) -> DatabaseResponse:
        """
        Main entry point - execute query from QueryResult object
        
        Args:
            query_result: Parsed query result object
            
        Returns:
            DatabaseResponse with results
        """
        try:
            operation = query_result.operation
            
            logger.info(f"Executing {operation} operation for tenant {query_result.tenant_id}")
            
            if operation == "list":
                result_dict = self._execute_data_query(query_result)
            elif operation == "distribution":
                result_dict = self._execute_distribution_query(query_result)
            elif operation == "semantic":
                result_dict = self._execute_data_query(query_result, is_semantic=True)
            else:
                # pure_advisory
                result_dict = {
                    "success": True,
                    "operation": operation,
                    "data": {"message": "Advisory operation - no database query executed"},
                    "advisory_mode": True
                }
            
            result_dict["operation"] = operation
            return DatabaseResponse(**result_dict)
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return DatabaseResponse(
                success=False,
                operation=operation,
                error=str(e),
                data=[]
            )
        finally:
            self._close_connection()

    def _execute_data_query(self, query_result: QueryResult, is_semantic: bool = False) -> Dict[str, Any]:
        """
        Unified method for executing list and semantic operations
        
        Args:
            query_result: Query parameters
            is_semantic: Whether this is a semantic search operation
            
        Returns:
            Formatted response dictionary
        """
        # Build match query using helper
        match_query = build_base_match_query(
            query_result.tenant_id,
            query_result.date_filter,
            query_result.marketing_filter
        )

        # Get database connection and schema
        db = self._get_db_connection()
        schema = self._get_schema(query_result.tenant_id)

        # Apply operation-specific filters
        if is_semantic:
            apply_semantic_filters(match_query, query_result.semantic_terms)
            # Apply additional filters without negation for semantic search
            apply_category_filters(
                match_query,
                query_result.filters,
                False,  # Semantic search doesn't use negation
                query_result.tenant_id,
                schema,
                db
            )
        else:
            # Apply category filters with potential negation for list operation
            apply_category_filters(
                match_query,
                query_result.filters,
                query_result.is_negation,
                query_result.tenant_id,
                schema,
                db
            )
        
        # Handle pagination
        skip = query_result.pagination.skip
        limit = query_result.pagination.limit
        
        # Count-only query
        if limit == 0:
            total_count = get_count(db, match_query)
            return build_pagination_response([], total_count, 1, 0)
        
        # Execute query with data
        total_count = get_count(db, match_query)
        
        # Build unified aggregation pipeline
        pipeline = [
            {"$match": match_query},
            {"$sort": {"createdAt": -1}},
            *get_standardized_lookup_pipeline(),
            {"$skip": skip},
            {"$limit": limit}
        ]
        
        raw_data = list(db.sitemaps.aggregate(pipeline))
        
        # Format data to match expected structure
        formatted_data = format_sitemap_data(raw_data)
        
        # Calculate pagination info
        page = (skip // limit) + 1 if limit > 0 else 1
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        
        return build_pagination_response(formatted_data, total_count, page, limit, total_pages)

    def _execute_distribution_query(self, query_result: QueryResult) -> Dict[str, Any]:
        """Execute distribution operation - handles multi-dimensional analysis"""
        if not query_result.distribution_fields:
            return {
                "success": False, 
                "error": "No distribution fields specified", 
                "data": []
            }
        
        # Build base match query using helper
        match_query = build_base_match_query(
            query_result.tenant_id,
            query_result.date_filter,
            query_result.marketing_filter
        )
        
        # Apply additional filters (excluding the distribution field itself)
        filtered_filters = {k: v for k, v in query_result.filters.items() 
                          if k not in query_result.distribution_fields}
        
        # Get database connection and schema
        db = self._get_db_connection()
        schema = self._get_schema(query_result.tenant_id)
        
        apply_category_filters(
            match_query,
            filtered_filters,
            query_result.is_negation,
            query_result.tenant_id,
            schema,
            db
        )
        
        # Handle single vs multi-dimensional distribution
        if len(query_result.distribution_fields) == 1:
            single_distribution = self._get_single_distribution(
                match_query, 
                query_result.distribution_fields[0],
                query_result.tenant_id
            )
            # Convert to DistributionResult for consistent API response
            result_data = [DistributionResult(
                field=query_result.distribution_fields[0],
                distribution=[DistributionItem(value=item["value"], count=item["count"]) for item in single_distribution],
                total_items=sum(item["count"] for item in single_distribution)
            )]
        else:
            result_data = self._get_multi_distribution(
                match_query,
                query_result.distribution_fields,
                query_result.tenant_id
            )
        
        return {
            "success": True,
            "data": result_data,
            "distribution_fields": query_result.distribution_fields
        }

    def _get_single_distribution(self, match_query: Dict, category: str, tenant_id: str) -> List[DistributionItem]:
        """Get distribution for single category"""
        db = self._get_db_connection()
        schema = self._get_schema(tenant_id)
        field_mappings = schema.get("field_mappings", {})
        mapping = field_mappings.get(category)
        
        if not mapping:
            return []
        
        pipeline = [{"$match": match_query}]
        
        field_name = mapping["field"]
        if mapping.get("requires_join"):
            if mapping.get("filter_by_category"):
                # Category attributes - need additional filtering
                pipeline.extend([
                    {"$unwind": f"${field_name}"},
                    {"$lookup": {
                        "from": "category_attributes",
                        "localField": field_name,
                        "foreignField": "_id",
                        "as": "attr_info"
                    }},
                    {"$unwind": "$attr_info"},
                    {"$lookup": {
                        "from": "categories",
                        "localField": "attr_info.category",
                        "foreignField": "_id",
                        "as": "cat_info"
                    }},
                    {"$unwind": "$cat_info"},
                    {"$match": {"cat_info.name": category}},
                    {"$group": {"_id": "$attr_info.name", "count": {"$sum": 1}}},
                    {"$project": {"value": "$_id", "count": "$count", "_id": 0}}
                ])
            else:
                # Standard reference collection
                ref_collection = mapping["reference_collection"]
                pipeline.extend([
                    {"$lookup": {
                        "from": ref_collection,
                        "localField": field_name,
                        "foreignField": "_id",
                        "as": "ref_info"
                    }},
                    {"$unwind": "$ref_info"},
                    {"$group": {"_id": "$ref_info.name", "count": {"$sum": 1}}},
                    {"$project": {"value": "$_id", "count": "$count", "_id": 0}}
                ])
        else:
            # Direct field (like geoFocus)
            pipeline.extend([
                {"$group": {"_id": f"${field_name}", "count": {"$sum": 1}}},
                {"$project": {"value": "$_id", "count": "$count", "_id": 0}}
            ])
        
        pipeline.append({"$sort": {"count": -1}})
        raw_results = list(db.sitemaps.aggregate(pipeline))
        
        # Convert to DistributionItem objects
        return [
            {"value": item["value"] or "Unknown", "count": item["count"]}
            for item in raw_results
        ]

    def _get_multi_distribution(self, match_query: Dict, categories: List[str], tenant_id: str) -> List[DistributionResult]:
        """Get multi-dimensional distribution"""
        results = []
        
        for category in categories:
            try:
                distribution = self._get_single_distribution(match_query, category, tenant_id)
                total_items = sum(item["count"] for item in distribution)
                
                results.append(DistributionResult(
                    field=category,
                    distribution=distribution,
                    total_items=total_items
                ))
            except Exception as e:
                logger.warning(f"Distribution failed for {category}: {e}")
                results.append(DistributionResult(
                    field=category,
                    distribution=[],
                    total_items=0,
                    error=str(e)
                ))
        
        return results

    def clear_cache(self):
        """Clear schema cache"""
        self._schema_cache.clear()
        logger.info("Query executor schema cache cleared")

# Factory function for dependency injection
def create_mongo_executor(mongo_uri: str = None, db_name: str = None) -> MongoQueryExecutor:
    """Create MongoQueryExecutor instance"""
    return MongoQueryExecutor(mongo_uri, db_name)

# Global executor instance for backward compatibility
_executor_instance = None

def get_query_executor() -> MongoQueryExecutor:
    """Get global query executor instance"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = MongoQueryExecutor()
    return _executor_instance