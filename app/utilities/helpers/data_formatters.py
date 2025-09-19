# app/core/helpers/data_formatters.py
from typing import Dict, List, Any
from bson import ObjectId


def convert_objectids_to_strings(data):
    """Convert ObjectIds to strings in the data"""
    if isinstance(data, list):
        return [convert_objectids_to_strings(item) for item in data]
    elif isinstance(data, dict):
        converted = {}
        for key, value in data.items():
            if isinstance(value, ObjectId):
                converted[key] = str(value)
            elif isinstance(value, list):
                converted[key] = [str(item) if isinstance(item, ObjectId) else convert_objectids_to_strings(item) for item in value]
            elif isinstance(value, dict):
                converted[key] = convert_objectids_to_strings(value)
            else:
                converted[key] = value
        return converted
    else:
        return data

def format_sitemap_data(raw_data: List[Dict]) -> List[Dict]:
    """
    Format raw aggregation data to match expected structure
    Converts categoryAttribute array to customCategory structure
    """
    formatted_data = []
    
    for sitemap in raw_data:
        # Transform categoryAttribute to customCategory structure
        # This matches the logic from the reference getAllSitemap function
        category_attributes = sitemap.get('categoryAttribute', [])
        
        # Group category attributes by category
        categories_dict = {}
        for attr in category_attributes:
            if 'category' in attr and attr['category']:
                category_id = str(attr['category']['_id'])
                
                if category_id not in categories_dict:
                    categories_dict[category_id] = {
                        '_id': category_id,
                        'name': attr['category']['name'],
                        'slug': attr['category']['slug'],
                        'categoryAttribute': []
                    }
                
                categories_dict[category_id]['categoryAttribute'].append({
                    '_id': str(attr['_id']),
                    'name': attr['name']
                })
        
        # Convert to list and add to sitemap
        custom_category = list(categories_dict.values())
        
        # Create formatted sitemap object
        formatted_sitemap = {
            **sitemap,
            'customCategory': custom_category
        }
        
        # Remove the original categoryAttribute field
        if 'categoryAttribute' in formatted_sitemap:
            del formatted_sitemap['categoryAttribute']
        
        # Convert ObjectIds to strings
        formatted_sitemap = convert_objectids_to_strings(formatted_sitemap)
        formatted_data.append(formatted_sitemap)
    
    return formatted_data

def build_pagination_response(data: List[Dict], total_count: int, 
                             page: int, page_size: int, total_pages: int = None) -> Dict[str, Any]:
    """Build standardized pagination response"""
    if total_pages is None:
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
        
    return {
        "success": True,
        "data": data,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }

def build_column_config(sitemaps_data: List[Dict]) -> List[Dict[str, Any]]:
    """
    Build column configuration exactly matching your TypeScript format
    Uses actual ObjectIds from data as colId for categories
    
    Args:
        sitemaps_data: List of sitemap documents with customCategory structure
    
    Returns:
        List of column configuration dictionaries in exact frontend format
    """
    
    # Static sitemap fields - beginning (matches your TypeScript exactly)
    static_columns_start = [
        {"colId": "name", "hide": False, "label": "Name", "type": "field"},
        {"colId": "path", "hide": False, "label": "Path", "type": "field"},
        {"colId": "contentType", "hide": False, "label": "Content Type", "type": "field"},
        {"colId": "topic", "hide": False, "label": "Topic", "type": "field"},
        {"colId": "isMarketingContent", "hide": False, "label": "Marketing Content", "type": "field"},
    ]
    
    # Extract unique categories from actual data
    categories_dict = {}
    
    if sitemaps_data:
        for sitemap in sitemaps_data:
            custom_categories = sitemap.get("customCategory", [])
            for category in custom_categories:
                category_id = category.get("_id")
                category_name = category.get("name")
                
                # Only add if both ID and name exist
                if category_id and category_name:
                    categories_dict[category_id] = category_name
    
    # Create category columns using actual ObjectIds as colId
    category_columns = []
    for category_id, category_name in categories_dict.items():
        category_columns.append({
            "colId": category_id,  # This gives you "6875f3afa677f67a172c63a7" format
            "hide": False,
            "label": category_name,  # This gives you "Funnel Stage", "Industry", etc.
            "type": "category"
        })
    
    # Static sitemap fields - ending (matches your TypeScript exactly)
    static_columns_end = [
        {"colId": "delete", "hide": False, "label": "Actions", "type": "field"},
        {"colId": "geoFocus", "hide": False, "label": "Geo Focus", "type": "field"},  # Fixed to match TS
        {"colId": "description", "hide": False, "label": "Description", "type": "field"},
        {"colId": "summary", "hide": False, "label": "Summary", "type": "field"},
        {"colId": "datePublished", "hide": False, "label": "Date Published", "type": "field"},
        {"colId": "dateModified", "hide": False, "label": "Date Modified", "type": "field"},
        {"colId": "wordCount", "hide": False, "label": "Word Count", "type": "field"},
        {"colId": "confidence", "hide": False, "label": "Confidence", "type": "field"},
        {"colId": "explanation", "hide": False, "label": "Explanation", "type": "field"},
        {"colId": "tag", "hide": False, "label": "Tags", "type": "field"},
    ]
    
    # Combine in exact order: static start + categories + static end
    return static_columns_start + category_columns + static_columns_end

# Updated API response function to use the single column config method
def format_api_response(
    chat_response, 
    tenant_schema: Dict = None, 
    tenant_id: str = None
) -> Dict[str, Any]:
    """Convert internal ChatResponse to clean API format with correct column config"""
    
    api_response = {
        "success": chat_response.success,
        "message": chat_response.response,
        "data": {}
    }
    
    # Handle different operations
    if chat_response.operation in ['list', 'semantic']:
        # Get sitemaps data
        sitemaps_data = []
        if hasattr(chat_response, 'db_response') and chat_response.db_response and hasattr(chat_response.db_response, 'data'):
            sitemaps_data = chat_response.db_response.data or []
        
        api_response["data"]["sitemaps"] = sitemaps_data
        
        # Build column config from actual data (single source of truth)
        api_response["data"]["columnConfig"] = build_column_config(sitemaps_data)
        
        # Add pagination info if available
        if hasattr(chat_response, 'db_response') and chat_response.db_response:
            pagination_fields = ["total_count", "page", "page_size", "total_pages", "has_next", "has_prev"]
            for field in pagination_fields:
                value = getattr(chat_response.db_response, field, None)
                if value is not None:
                    api_response["data"][field] = value
    
    elif chat_response.operation == 'distribution':
        # For distribution: include distribution data
        if hasattr(chat_response, 'db_response') and chat_response.db_response and hasattr(chat_response.db_response, 'data'):
            api_response["data"]["distribution"] = chat_response.db_response.data or []
        else:
            api_response["data"]["distribution"] = []
    
    else:
        # For pure_advisory: minimal data
        api_response["data"] = {
            "advisory": True,
            "suggestions": getattr(chat_response, 'suggested_questions', [])
        }
    
    # Always include these fields with safe access
    api_response["data"]["operation"] = getattr(chat_response, 'operation', 'unknown')
    api_response["data"]["confidence"] = getattr(chat_response, 'confidence', 'medium')
    api_response["data"]["suggested_questions"] = getattr(chat_response, 'suggested_questions', [])
    
    if hasattr(chat_response, 'session_id') and chat_response.session_id:
        api_response["data"]["session_id"] = chat_response.session_id
    
    return api_response

def format_error_response(error_message: str, operation: str = "unknown") -> Dict[str, Any]:
    """Format error response in API format"""
    return {
        "success": False,
        "message": error_message,
        "data": {
            "operation": operation,
            "error": error_message
        }
    }

