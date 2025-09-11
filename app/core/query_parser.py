# app/core/query_parser.py
import json
import time
import logging
from loguru import logger

from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional
from ..config.settings import settings
from ..models.query import QueryResult, FilterDict, DateFilter, Pagination
from .schema_extractor import get_tenant_schema

# logger = logging.getLogger(__name__)

class SmartQueryParser:
    """
    Intelligent query parser that converts natural language to structured queries using OpenAI
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None, openai_api_key: str = None):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self.client = OpenAI(api_key=openai_api_key or settings.OPENAI_API_KEY)
        self._schema_cache: Dict[str, Dict] = {}
        self.max_schema_values = settings.MAX_SCHEMA_VALUES
    
    def parse(self, query_text: str, tenant_id: str) -> QueryResult:
        """
        Parse natural language query into structured QueryResult
        
        Args:
            query_text: User's natural language query
            tenant_id: Tenant ID for schema context
            
        Returns:
            QueryResult object with parsed query components
        """
        # Input validation
        if not query_text or not query_text.strip():
            raise ValueError("query_text cannot be empty")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        
        if len(query_text) > settings.MAX_QUERY_LENGTH:
            raise ValueError(f"Query too long. Maximum length: {settings.MAX_QUERY_LENGTH}")
            
        try:
            schema_data = self._get_cached_schema(tenant_id)
            parsed = self._ai_parse(query_text, schema_data)
            
            # Convert parsed data to QueryResult using our models
            return self._build_query_result(parsed, tenant_id)
            
        except Exception as e:
            logger.error(f"Error parsing query '{query_text}' for tenant {tenant_id}: {e}")
            # Return fallback semantic search
            return self._get_fallback_query_result(query_text, tenant_id)
    
    def _build_query_result(self, parsed: Dict, tenant_id: str) -> QueryResult:
        """Convert parsed dictionary to QueryResult model"""
        
        # Process filters with proper FilterDict structure
        filters = {}
        for cat, val in parsed.get("filters", {}).items():
            if isinstance(val, list):
                # Backward compatibility for old list format
                filters[cat] = FilterDict(include=val, exclude=[])
            elif isinstance(val, dict):
                filters[cat] = FilterDict(
                    include=val.get("include", []),
                    exclude=val.get("exclude", [])
                )
            else:
                filters[cat] = FilterDict(include=[str(val)], exclude=[])
        
        # Process date filter
        date_filter = None
        if parsed.get("date_filter"):
            date_data = parsed["date_filter"]
            date_filter = DateFilter(
                start_date=date_data.get("start_date"),
                end_date=date_data.get("end_date")
            )
        
        # Process pagination
        pagination_data = parsed.get("pagination", {})
        if not isinstance(pagination_data, dict):
            pagination_data = {}
        
        pagination = Pagination(
            skip=pagination_data.get("skip", 0),
            limit=pagination_data.get("limit", settings.DEFAULT_PAGE_SIZE)
        )
        
        return QueryResult(
            route=parsed.get("route", "database"),
            operation=parsed.get("operation", "semantic"),
            filters=filters,
            date_filter=date_filter,
            marketing_filter=parsed.get("marketing_filter"),
            is_negation=parsed.get("is_negation", False),
            semantic_terms=parsed.get("semantic_terms", []),
            tenant_id=tenant_id,
            needs_data=parsed.get("needs_data", True),
            distribution_fields=parsed.get("distribution_fields", []),
            pagination=pagination
        )
    
    def _get_cached_schema(self, tenant_id: str) -> Dict:
        """Get schema with caching to avoid redundant database calls"""
        if tenant_id not in self._schema_cache:
            schema_data = get_tenant_schema(self.mongo_uri, self.db_name, tenant_id)
            if not schema_data:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Validate schema structure
            if not isinstance(schema_data.get("categories", {}), dict):
                raise ValueError(f"Invalid schema structure for tenant {tenant_id}: categories must be dict")
                
            self._schema_cache[tenant_id] = schema_data
        return self._schema_cache[tenant_id]
    
    def _get_fallback_query_result(self, query_text: str, tenant_id: str) -> QueryResult:
        """Generate fallback QueryResult for error cases"""
        return QueryResult(
            route="database",
            operation="semantic",
            filters={},
            date_filter=None,
            marketing_filter=None,
            is_negation=False,
            semantic_terms=[query_text],
            tenant_id=tenant_id,
            needs_data=True,
            distribution_fields=[],
            pagination=Pagination()
        )
    
    def _handle_large_schema(self, query_text: str, schema_data: Dict) -> Dict:
        """Handle queries for tenants with large schemas"""
        total_values = schema_data.get('summary', {}).get('total_values', 0)
        logger.info(f"Using fallback for large schema with {total_values} values")
        return {
            "route": "database",
            "operation": "semantic",
            "filters": {},
            "date_filter": None,
            "marketing_filter": None,
            "is_negation": False,
            "semantic_terms": [query_text],
            "needs_data": True,
            "distribution_fields": [],
            "pagination": {"skip": 0, "limit": settings.DEFAULT_PAGE_SIZE}
        }
    
    def _ai_parse(self, query_text: str, schema_data: Dict) -> Dict:
        """Use OpenAI to parse natural language query with retry logic"""
        
        # Check for large schema safeguard
        summary = schema_data.get("summary", {})
        total_values = summary.get("total_values", 0)
        
        if total_values > self.max_schema_values:
            logger.info(f"Schema too large ({total_values} values), using dynamic handler")
            return self._handle_large_schema(query_text, schema_data)
        
        # Build OpenAI function schema
        categories = schema_data.get("categories", {})
        tool_schema = self._build_openai_tool_schema(categories)
        system_message = self._build_system_message(categories, schema_data, query_text)
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                completion = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": query_text}
                    ],
                    tools=tool_schema,
                    tool_choice={"type": "function", "function": {"name": "parse_query"}},
                    temperature=settings.OPENAI_TEMPERATURE
                )
                
                result = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return self._handle_large_schema(query_text, schema_data)
                    
            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"API error ({error_type}) on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return self._handle_large_schema(query_text, schema_data)
            
            # Exponential backoff
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
        
        # Fallback (should not reach here)
        return self._handle_large_schema(query_text, schema_data)
    
    def _build_openai_tool_schema(self, categories: Dict[str, List[str]]) -> List[Dict]:
        """Build OpenAI function schema dynamically based on tenant categories"""
        
        return [
            {
                "type": "function",
                "function": {
                    "name": "parse_query",
                    "description": "Parse user queries into structured JSON for database routing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "route": {
                                "type": "string",
                                "enum": ["database", "advisory"],
                                "description": "database=get data, advisory=business insights"
                            },
                            "operation": {
                                "type": "string",
                                "enum": ["list", "distribution", "semantic", "pure_advisory"],
                                "description": "list=show items, distribution=group by, semantic=text search, pure advisory=insights only"
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    cat: {
                                        "type": "object",
                                        "properties": {
                                            "include": {
                                                "type": "array",
                                                "items": {"type": "string", "enum": values if values else []}
                                            },
                                            "exclude": {
                                                "type": "array",
                                                "items": {"type": "string", "enum": values if values else []}
                                            }
                                        },
                                        "additionalProperties": False
                                    }
                                    for cat, values in categories.items()
                                },
                                "additionalProperties": False
                            },
                            "date_filter": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "properties": {
                                            "start_date": {"anyOf": [{"type": "string", "format": "date"}, {"type": "null"}]},
                                            "end_date": {"anyOf": [{"type": "string", "format": "date"}, {"type": "null"}]}
                                        },
                                        "required": ["start_date", "end_date"],
                                        "additionalProperties": False
                                    },
                                    {"type": "null"}
                                ]
                            },
                            "marketing_filter": {"type": ["boolean", "null"]},
                            "is_negation": {"type": "boolean"},
                            "semantic_terms": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "needs_data": {"type": "boolean"},
                            "pagination": {
                                "type": ["object", "null"],
                                "properties": {
                                    "skip": {"type": "integer", "minimum": -2, "default": 0},
                                    "limit": {"type": "integer", "minimum": 0, "maximum": settings.MAX_PAGE_SIZE, "default": settings.DEFAULT_PAGE_SIZE}
                                },
                                "required": [],
                                "additionalProperties": False
                            },
                            "distribution_fields": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": list(categories.keys())
                                },
                                "description": "Categories to group by for distributions"
                            },
                        },
                        "required": ["route", "operation", "filters", "is_negation", "needs_data"]
                    }
                }
            }
        ]
    
    def _build_system_message(self, categories: Dict, schema_data: Dict, query_text: str) -> str:
        """Build system message with current date and schema context"""
        
        categories_context = json.dumps(categories, indent=2)
        field_mappings_context = json.dumps(schema_data.get("field_mappings", {}), indent=2)
        today = datetime.today().strftime("%Y-%m-%d")
        
        return f"""
You are a query parser for a content management system. Parse user queries into structured JSON operations matching the provided schema.

**CORE RULES:**
- Always match to existing categories/values - never create new ones
- Prioritize exact matches, but attempt semantic matching for unmatched terms
- ALWAYS return exact schema values, regardless of input format variations
- Return valid JSON matching the schema

**CRITICAL EXCLUSIVITY RULE - PRIMARY/SECONDARY AUDIENCE:**
- When assigning values to "Primary Audience" include array, DO NOT assign the same values to "Secondary Audience" include array
- When assigning values to "Secondary Audience" include array, DO NOT assign the same values to "Primary Audience" include array  
- Each audience value can only appear in ONE of these categories per query - NEVER in both

**STRICT OPERATION RULES:**
- If operation is distribution you must provide the distribution_fields
- Example: operation: distribution, filters: {{"Funnel Stage": {{"include": ["TOFU"], "exclude": []}}}}, then distribution_fields must be ["Funnel Stage"]

**OPERATIONS:**
- `list` → fetch content/items
- `distribution` → analyze proportions/breakdowns of categories  
- `semantic` → free-text search not tied to categories
- `pure_advisory` → strategic advice requiring no database

**KEY LOGIC:**
- Category name mentioned → `distribution` with all category values in filters
- Category value mentioned → appropriate operation with that value filtered  
- Advisory questions needing data → use `distribution` operation
- Marketing detection → set `marketing_filter: true/false` based on marketing context
- Negation ("not X", "without Y") → `"is_negation": true` + exclude arrays
- "Distribution of X" → `"distribution_fields": ["X"]`
- "Distribution of X across Y" → `"distribution_fields": ["X", "Y"]`

**DATES:** Reference: {today}
- "last N days/weeks/months" → start_date = today - N, end_date = today
- "more than N ago" → end_date = today - N, start_date = null
- Format: YYYY-MM-DD

**PAGINATION:** Default: skip=0, limit={settings.DEFAULT_PAGE_SIZE}
- "top N" → limit = N
- "page P" → skip = (P-1)*{settings.DEFAULT_PAGE_SIZE}, limit = {settings.DEFAULT_PAGE_SIZE}
- "last N" → skip = -1, limit = N
- "count only" → skip = -2, limit = 0
- "all" → limit = {settings.MAX_PAGE_SIZE}

**CONTEXT:**
- Categories: {categories_context}
- Field mappings: {field_mappings_context}
"""
    
    def clear_cache(self):
        """Clear schema cache"""
        self._schema_cache.clear()
        logger.info("Query parser schema cache cleared")

# Factory function for dependency injection
def create_smart_parser(mongo_uri: str = None, db_name: str = None, openai_api_key: str = None) -> SmartQueryParser:
    """Create SmartQueryParser instance"""
    return SmartQueryParser(mongo_uri, db_name, openai_api_key)

# Global parser instance for backward compatibility
_parser_instance = None

def get_query_parser() -> SmartQueryParser:
    """Get global query parser instance"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = SmartQueryParser()
    return _parser_instance