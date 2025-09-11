# app/core/llm_helpers/data_normalizers.py
from typing import Dict, List, Any, Union
from datetime import datetime
from bson import ObjectId
from loguru import logger

from ...models.query import QueryResult
from ...models.database import DatabaseResponse
from ...models.content import DistributionItem, DistributionResult

def normalize_query_result(query_result: Union[QueryResult, Dict]) -> Dict:
    """Convert QueryResult to dict for processing"""
    if isinstance(query_result, QueryResult):
        return {
            "tenant_id": query_result.tenant_id,
            "filters": {k: {"include": v.include, "exclude": v.exclude} for k, v in query_result.filters.items()},
            "operation": query_result.operation,
            "distribution_fields": query_result.distribution_fields,
            "semantic_terms": query_result.semantic_terms,
            "is_negation": query_result.is_negation
        }
    return query_result

def normalize_db_response(db_response: Union[DatabaseResponse, Dict]) -> Dict:
    """Convert DatabaseResponse to dict for processing"""
    if isinstance(db_response, DatabaseResponse):
        # Handle typed distribution data
        data = db_response.data
        if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], (DistributionItem, DistributionResult)):
            if isinstance(data[0], DistributionItem):
                # Single distribution
                data = [{"value": item.value, "count": item.count} for item in data]
            else:
                # Multi-distribution
                data = [
                    {
                        "field": result.field,
                        "distribution": [{"value": item.value, "count": item.count} for item in result.distribution],
                        "total_items": result.total_items,
                        "error": result.error
                    }
                    for result in data
                ]
        
        return {
            "success": db_response.success,
            "data": data,
            "total_count": db_response.total_count,
            "page": db_response.page,
            "page_size": db_response.page_size,
            "error": db_response.error,
            "operation": db_response.operation,
            "distribution_fields": db_response.distribution_fields
        }
    return db_response

def clean_for_json(obj):
    """Recursively clean ObjectIds, datetime objects, and other non-JSON serializable objects"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: clean_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    else:
        return obj