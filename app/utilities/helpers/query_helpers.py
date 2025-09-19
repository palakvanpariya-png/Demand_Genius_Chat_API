# app/core/helpers/query_helpers.py
from typing import Dict, List, Optional
from bson import ObjectId
import re
from loguru import logger

from ...models.query import DateFilter, FilterDict
from .date_utils import parse_date_string
from .database_helpers import get_category_attribute_ids, get_reference_ids

def build_base_match_query(tenant_id: str, date_filter: Optional[DateFilter], 
                          marketing_filter: Optional[bool]) -> Dict:
    """Build base query with tenant, date, and marketing filters"""
    match_query = {"tenant": ObjectId(tenant_id)}
    
    # Add date filter with improved parsing
    if date_filter:
        date_conditions = {}
        try:
            if date_filter.start_date:
                date_conditions["$gte"] = parse_date_string(date_filter.start_date)
            if date_filter.end_date:
                # For end date, set to end of day to include the entire day
                end_date = parse_date_string(date_filter.end_date)
                # If no time component, set to end of day
                if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                date_conditions["$lte"] = end_date
                
            if date_conditions:
                match_query["createdAt"] = date_conditions
        except ValueError as e:
            logger.warning(f"Invalid date format: {e}")
    
    # Add marketing filter
    if marketing_filter is not None:
        match_query["isMarketingContent"] = marketing_filter
    
    return match_query

def apply_semantic_filters(match_query: Dict, semantic_terms: List[str]):
    """Apply semantic search conditions to match query"""
    if not semantic_terms:
        return
        
    text_conditions = []
    for term in semantic_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        text_conditions.extend([
            {"name": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
            {"summary": {"$regex": pattern}}
        ])
    
    if text_conditions:
        match_query["$or"] = text_conditions

def apply_category_filters(match_query: Dict, filters: Dict[str, FilterDict], 
                          is_negation: bool, tenant_id: str, schema: Dict, db):
    """Apply category filters using schema mappings"""
    if not filters:
        return
    
    field_mappings = schema.get("field_mappings", {})
    
    for category, filter_dict in filters.items():
        include_values = filter_dict.include
        exclude_values = filter_dict.exclude
        
        if include_values or exclude_values:
            condition = build_category_condition(
                category, include_values, field_mappings, tenant_id, 
                exclude_values=exclude_values, negate=is_negation, db=db
            )
            if condition:
                match_query.update(condition)

def build_category_condition(category: str, include_values: List[str], 
                            field_mappings: Dict, tenant_id: str,
                            exclude_values: List[str] = None, negate: bool = False, db=None) -> Dict:
    """Build MongoDB condition for a single category"""
    mapping = field_mappings.get(category)
    if not mapping:
        return {}
    
    field_name = mapping["field"]
    requires_join = mapping.get("requires_join", False)
    
    # Get values (ObjectIds or strings)
    if requires_join:
        if mapping.get("filter_by_category"):
            include_ids = get_category_attribute_ids(db, include_values, category, tenant_id)
            exclude_ids = get_category_attribute_ids(db, exclude_values or [], category, tenant_id)
        else:
            include_ids = get_reference_ids(db, mapping["reference_collection"], include_values, tenant_id)
            exclude_ids = get_reference_ids(db, mapping["reference_collection"], exclude_values or [], tenant_id)
    else:
        include_ids = include_values
        exclude_ids = exclude_values or []
    
    # Build condition
    if negate:
        return {field_name: {"$not": {"$in": exclude_ids}}} if include_ids else {}
    
    condition = {}
    if include_ids and exclude_ids:
        condition[field_name] = {"$in": include_ids, "$not": {"$in": exclude_ids}}
    elif include_ids:
        condition[field_name] = {"$in": include_ids}
    elif exclude_ids:
        condition[field_name] = {"$not": {"$in": exclude_ids}}
        
    return condition