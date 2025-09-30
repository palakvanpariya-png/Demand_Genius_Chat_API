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
    
    # Add date filter
    if date_filter:
        date_conditions = {}
        try:
            if date_filter.start_date:
                start_dt = parse_date_string(date_filter.start_date)
                date_conditions["$gte"] = start_dt
                logger.debug(f"🔍 Start date filter: {start_dt}")
                
            if date_filter.end_date:
                end_dt = parse_date_string(date_filter.end_date)
                if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                date_conditions["$lte"] = end_dt
                logger.debug(f"🔍 End date filter: {end_dt}")
                
            if date_conditions:
                # 🔧 FIX: Ensure createdAt exists and is not null, then apply date filter
                match_query["$and"] = [
                    {"datePublished": {"$exists": True, "$ne": None, "$type": "date"}},  # Must be a date type
                    {"datePublished": date_conditions}  # Apply the date range filter
                ]
                logger.info(f"🔍 Date filter with existence check applied: {date_conditions}")
                
        except ValueError as e:
            logger.warning(f"Invalid date format: {e}")
    
    # Add marketing filter
    if marketing_filter is not None:
        match_query["isMarketingContent"] = marketing_filter
    
    return match_query


def apply_semantic_filters(match_query: Dict, semantic_terms: List[str]):
    """Apply semantic search conditions to match query - FIXED VERSION"""
    if not semantic_terms:
        return
        
    text_conditions = []
    for term_phrase in semantic_terms:
        # Split compound terms for better matching
        individual_terms = term_phrase.strip().split()
        
        for term in individual_terms:
            if len(term) > 2:  # Skip very short words
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                text_conditions.extend([
                    {"name": {"$regex": pattern}},
                    {"description": {"$regex": pattern}},
                    {"summary": {"$regex": pattern}}
                ])
    
    # CRITICAL FIX: Always apply semantic filter when terms exist
    if text_conditions:
        match_query["$or"] = text_conditions
    else:
        # If no valid terms, ensure no results (instead of all results)
        match_query["_id"] = {"$in": []}


def apply_category_filters(
    match_query: Dict,
    filters: Dict[str, FilterDict],
    is_negation: bool,
    tenant_id: str,
    schema: Dict,
    db
):
    """
    Apply category filters using schema mappings.

    Handles includes, excludes, negation, and edge case of empty filters with global negation.
    """
    field_mappings = schema.get("field_mappings", {})

    if not filters:
        if is_negation:
            # If global negation with no filters, block all documents
            match_query["__block_all__"] = True
        return

    for category, filter_dict in filters.items():
        include_values = filter_dict.include
        exclude_values = filter_dict.exclude

        # Skip empty categories unless global negation is True
        if not include_values and not exclude_values and not is_negation:
            continue

        condition = build_category_condition(
            category,
            include_values,
            field_mappings,
            tenant_id,
            exclude_values=exclude_values,
            negate=is_negation,
            db=db
        )

        if condition:
            match_query.update(condition)


def build_category_condition(
    category: str,
    include_values: List[str],
    field_mappings: Dict,
    tenant_id: str,
    exclude_values: List[str] = None,
    negate: bool = False,
    db=None
) -> Dict:
    """
    Build MongoDB condition for a single category.

    Handles includes, excludes, and negation. Works with direct fields and joins.
    """
    mapping = field_mappings.get(category)
    if not mapping:
        return {}

    field_name = mapping["field"]
    requires_join = mapping.get("requires_join", False)
    exclude_values = exclude_values or []

    # Resolve values to ObjectIds or strings
    if requires_join:
        if mapping.get("filter_by_category"):
            include_ids = get_category_attribute_ids(db, include_values, category, tenant_id)
            exclude_ids = get_category_attribute_ids(db, exclude_values, category, tenant_id)
        else:
            include_ids = get_reference_ids(db, mapping["reference_collection"], include_values, tenant_id)
            exclude_ids = get_reference_ids(db, mapping["reference_collection"], exclude_values, tenant_id)
    else:
        include_ids = include_values
        exclude_ids = exclude_values

    # Build MongoDB condition
    condition = {}

    if negate:
        # If negation is True and we have no filters, block everything
        if not include_ids and not exclude_ids:
            condition["__block_all__"] = True
        else:
            # Apply $nin to whatever values exist
            condition[field_name] = {"$nin": exclude_ids or include_ids}
    else:
        # Normal operation
        if include_ids and exclude_ids:
            condition[field_name] = {"$in": include_ids, "$nin": exclude_ids}
        elif include_ids:
            condition[field_name] = {"$in": include_ids}
        elif exclude_ids:
            condition[field_name] = {"$nin": exclude_ids}
        else:
            condition = {}

    return condition