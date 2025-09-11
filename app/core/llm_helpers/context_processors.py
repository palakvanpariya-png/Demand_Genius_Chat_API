# app/core/llm_helpers/context_processors.py
from typing import Dict, List, Any, Optional
from .conversation_manager import get_conversation_context

def prepare_advisory_context(
    operation: str, 
    query_result: Dict, 
    db_response: Dict, 
    tenant_schema: Dict, 
    original_query: str, 
    conversation_cache: Dict,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Prepare structured context for LLM analysis with intelligent filtering"""
    
    # Extract data patterns for LLM analysis
    data_patterns = extract_data_patterns(operation, db_response)
    
    # Get tenant's actual categories
    available_categories = tenant_schema.get("categories", {})
    
    # Extract industry intelligence from categories (only if relevant)
    industry_context = extract_industry_context(available_categories) if available_categories else {}
    
    # Get conversation context if session_id provided
    conversation_context = {}
    if session_id:
        conversation_context = get_conversation_context(conversation_cache, session_id, original_query)
    
    # Build base context
    base_context = {
        "operation": operation,
        "original_query": original_query,
        "filters_applied": query_result.get("filters", {}),
        "data_patterns": data_patterns,
        "tenant_context": build_tenant_context(tenant_schema, available_categories),
        "conversation_context": conversation_context
    }
    
    # Add optional context only if it adds value
    if industry_context:
        base_context["industry_context"] = industry_context
    
    if available_categories:
        base_context["tenant_categories"] = available_categories
    
    return base_context

def build_tenant_context(tenant_schema: Dict, available_categories: Dict) -> Dict[str, Any]:
    """Build concise tenant context summary"""
    return {
        "total_content": tenant_schema.get("document_counts", {}).get("sitemaps", 0),
        "category_count": len(available_categories),
        "content_types": available_categories.get("Content Type", [])[:5],  # Limit for efficiency
        "topics": available_categories.get("Topics", [])[:5],  # Limit for efficiency
        "has_custom_categories": len([
            cat for cat in available_categories.keys() 
            if cat not in ["Content Type", "Topics", "Custom Tags", "Language"]
        ]) > 0
    }

def extract_data_patterns(operation: str, db_response: Dict) -> Dict[str, Any]:
    """Extract key patterns from database response for LLM analysis with enhanced details"""
    
    if operation == "list":
        total_count = db_response.get("total_count", 0)
        page_size = db_response.get("page_size", 0)
        data = db_response.get("data", [])
        
        return {
            "type": "content_list",
            "total_found": total_count,
            "page_size": page_size,
            "has_results": total_count > 0,
            "sample_data": data[:3] if data else [],
            "results_summary": get_list_results_summary(data, total_count),
            "showing_partial": page_size > 0 and total_count > page_size
        }
    
    elif operation == "distribution":
        distribution_data = db_response.get("data", [])
        
        # Handle both single and multi-distribution formats
        if distribution_data and isinstance(distribution_data[0], dict):
            if "field" in distribution_data[0]:
                # Multi-distribution format
                total_items = sum(result.get("total_items", 0) for result in distribution_data)
                categories_count = len(distribution_data)
            else:
                # Single distribution format
                total_items = sum(item.get("count", 0) for item in distribution_data)
                categories_count = len(distribution_data)
        else:
            total_items = 0
            categories_count = 0
        
        return {
            "type": "distribution_analysis",
            "categories_count": categories_count,
            "distribution_data": distribution_data,
            "total_items": total_items,
            "top_category": get_top_category(distribution_data),
            "has_empty_categories": any(item.get("count", 0) == 0 for item in distribution_data) if distribution_data else False,
            "concentration_ratio": calculate_concentration(distribution_data) if distribution_data else 0.0,
            "distribution_summary": get_distribution_summary(distribution_data, total_items)
        }
    
    elif operation == "semantic":
        total_count = db_response.get("total_count", 0)
        data = db_response.get("data", [])
        
        return {
            "type": "semantic_search",
            "total_found": total_count,
            "search_effective": total_count > 0,
            "sample_matches": data[:3] if data else [],
            "results_summary": get_semantic_results_summary(data, total_count)
        }
    
    else:  # pure_advisory
        return {
            "type": "advisory_only",
            "no_data_query": True
        }

def get_list_results_summary(data: List[Dict], total_count: int) -> str:
    """Create intelligent summary of list results for strategic context"""
    if total_count == 0:
        return "No content found with current filters"
    
    if total_count == 1:
        return "Single piece of content found"
    
    if total_count < 10:
        return f"Small focused set of {total_count} content pieces"
    
    if total_count < 50:
        return f"Moderate collection of {total_count} content pieces"
    
    if total_count < 200:
        return f"Substantial content set of {total_count} pieces"
    
    return f"Large content collection of {total_count} pieces"

def get_top_category(distribution_data: List[Dict]) -> Dict[str, Any]:
    """Get the top category from distribution data for strategic insights"""
    if not distribution_data:
        return None
    
    try:
        if isinstance(distribution_data[0], dict):
            if "field" in distribution_data[0]:
                # Multi-distribution format - get the field with highest total
                max_field = max(distribution_data, key=lambda x: x.get("total_items", 0))
                return {
                    "field": max_field.get("field", "Unknown"),
                    "count": max_field.get("total_items", 0)
                }
            else:
                # Single distribution format - get highest count item
                max_item = max(distribution_data, key=lambda x: x.get("count", 0))
                return {
                    "value": max_item.get("value", "Unknown"),
                    "count": max_item.get("count", 0)
                }
    except (ValueError, KeyError):
        pass
    
    return None

def get_distribution_summary(distribution_data: List[Dict], total_items: int) -> str:
    """Create intelligent summary of distribution data with strategic context"""
    if not distribution_data or total_items == 0:
        return "No distribution data available"
    
    categories_count = len(distribution_data)
    
    # Calculate concentration for strategic insight
    try:
        if isinstance(distribution_data[0], dict):
            if "field" in distribution_data[0]:
                # Multi-distribution format
                return f"{categories_count} distribution categories with {total_items} total items - multi-dimensional analysis available"
            else:
                # Single distribution format - calculate concentration
                max_count = max(item.get("count", 0) for item in distribution_data)
                concentration_pct = round((max_count / total_items) * 100, 1) if total_items > 0 else 0
                
                if concentration_pct > 70:
                    return f"{categories_count} categories, highly concentrated distribution ({concentration_pct}% in top category, {total_items} total items)"
                elif concentration_pct > 40:
                    return f"{categories_count} categories, moderately distributed ({concentration_pct}% in top category, {total_items} total items)"
                else:
                    return f"{categories_count} categories, evenly distributed (top category {concentration_pct}%, {total_items} total items)"
    except (ValueError, KeyError, TypeError):
        pass
    
    return f"{categories_count} categories with {total_items} total items"

def get_semantic_results_summary(data: List[Dict], total_count: int) -> str:
    """Create intelligent summary of semantic search results with strategic context"""
    if total_count == 0:
        return "No content matches the searched topics"
    
    if total_count == 1:
        return "Single content piece matches the topic search"
    
    if total_count < 5:
        return f"Limited matches found ({total_count} pieces) for the topic search"
    
    if total_count < 20:
        return f"Good topic coverage found ({total_count} pieces) for analysis"
    
    if total_count < 100:
        return f"Strong topic coverage found ({total_count} pieces) for comprehensive analysis"
    
    return f"Extensive topic coverage found ({total_count} pieces) for deep analysis"

def calculate_concentration(distribution_data: List[Dict]) -> float:
    """Calculate how concentrated the distribution is (Herfindahl index)"""
    if not distribution_data or len(distribution_data) <= 1:
        return 1.0
    
    # Handle both single and multi-distribution formats
    counts = []
    try:
        if "field" in str(distribution_data[0]):
            # Multi-distribution: flatten all counts
            for result in distribution_data:
                if "distribution" in result:
                    counts.extend([item.get("count", 0) for item in result["distribution"]])
        else:
            # Single distribution
            counts = [item.get("count", 0) for item in distribution_data]
        
        total = sum(counts)
        if total == 0:
            return 0.0
        
        # Calculate Herfindahl index
        squares_sum = sum((count / total) ** 2 for count in counts)
        return squares_sum
    except (KeyError, TypeError, ValueError):
        return 0.0

def extract_industry_context(categories: Dict[str, List[str]]) -> Dict[str, Any]:
    """Extract industry intelligence from tenant categories (only relevant info)"""
    industry_context = {}
    
    # Only add if they exist and are non-empty
    if categories.get("Industry"):
        industry_context["explicit_industry"] = categories["Industry"][:3]  # Limit for efficiency
    
    if categories.get("Primary Audience"):
        industry_context["primary_audiences"] = categories["Primary Audience"][:3]
    
    if categories.get("Topics"):
        industry_context["topics"] = categories["Topics"][:5]  # Limit for context
    
    if categories.get("Page Type"):
        industry_context["page_types"] = categories["Page Type"][:3]
    
    return industry_context

def is_context_relevant(query: str, context_type: str) -> bool:
    """Determine if specific context is relevant to the query"""
    query_lower = query.lower()
    
    if context_type == "industry":
        industry_keywords = ["industry", "sector", "market", "competition", "benchmark"]
        return any(keyword in query_lower for keyword in industry_keywords)
    
    elif context_type == "categories":
        category_keywords = ["category", "type", "distribution", "breakdown", "organize"]
        return any(keyword in query_lower for keyword in category_keywords)
    
    elif context_type == "conversation":
        follow_up_indicators = ["also", "additionally", "furthermore", "continue", "more about"]
        return any(indicator in query_lower for indicator in follow_up_indicators)
    
    return True  # Default to including context if unsure