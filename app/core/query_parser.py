# app/core/query_parser.py
import json
import time
import logging
from loguru import logger

from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional
from ..config.setting import settings
from ..config.database import db_connection
from ..models.query import QueryResult, FilterDict, DateFilter, Pagination
from .schema_extractor import get_tenant_schema
from ..utilities.token_calculator import log_token_usage

class SmartQueryParser:
    """
    Intelligent query parser that converts natural language to structured queries using OpenAI
    Now with conversation context awareness for better follow-up question handling
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None, openai_api_key: str = None):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self.client = OpenAI(api_key=openai_api_key or settings.OPENAI_API_KEY)
        self._schema_cache: Dict[str, Dict] = {}
        self.max_schema_values = settings.MAX_SCHEMA_VALUES
    
    def parse(
        self, 
        query_text: str, 
        tenant_id: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> QueryResult:
        """
        Parse natural language query into structured QueryResult
        
        Args:
            query_text: User's natural language query
            tenant_id: Tenant ID for schema context
            conversation_history: Optional list of previous queries for context
                Format: [{"query": "...", "parsed_result": {...}}, ...]
            
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
            parsed = self._ai_parse(query_text, schema_data, conversation_history)
            
            # Convert parsed data to QueryResult using our models
            return self._build_query_result(parsed, tenant_id)
            
        except Exception as e:
            logger.error(f"Error parsing query '{query_text}' for tenant {tenant_id}: {e}")
            # Return fallback semantic search
            return self._get_fallback_query_result(query_text, tenant_id)
    
    def _format_conversation_context(
        self, 
        conversation_history: Optional[List[Dict]]
    ) -> str:
        """
        Format last 2 queries into simple context string for LLM
        
        Args:
            conversation_history: List of previous query interactions
            
        Returns:
            Formatted context string or empty string if no history
        """
        if not conversation_history:
            return ""
        
        # Take last 1 only (configurable via settings if needed)
        max_context = 1
        recent = conversation_history[-max_context:] if len(conversation_history) > max_context else conversation_history
        
        if not recent:
            return ""
        
        # Format context simply and concisely
        context_parts = []
        for i, item in enumerate(recent, 1):
            query = item.get("query", "")
            parsed = item.get("parsed_result", {})
            
            if not query or not parsed:
                continue
            
            operation = parsed.get("operation", "unknown")
            filters = parsed.get("filters", {})
            description = parsed.get("description", "")
            
            # Create concise filter summary
            if filters:
                filter_items = []
                for category, filter_dict in filters.items():
                    includes = filter_dict.get("include", [])
                    excludes = filter_dict.get("exclude", [])
                    if includes:
                        filter_items.append(f"{category}={','.join(includes[:2])}")  # Max 2 values
                    if excludes:
                        filter_items.append(f"NOT {category}={','.join(excludes[:2])}")
                filter_summary = "; ".join(filter_items)
            else:
                filter_summary = "no filters"
            
            context_parts.append(
                f"{i}. User asked: \"{query}\"\n"
                f"   Parsed as: {operation} operation, Filters: {filter_summary}\n"
                f"   Description: \"{description or 'N/A'}\""
            )
        
        return "\n".join(context_parts)
    
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
            confidence=parsed.get("confidence", "medium"),  
            filters=filters,
            date_filter=date_filter,
            marketing_filter=parsed.get("marketing_filter"),
            is_negation=parsed.get("is_negation", False),
            semantic_terms=parsed.get("semantic_terms", []),
            tenant_id=tenant_id,
            needs_data=parsed.get("needs_data", True),
            distribution_fields=parsed.get("distribution_fields", []),
            pagination=pagination,
            description=parsed.get("description")  # NEW: Add description field
        )
    
    def _get_cached_schema(self, tenant_id: str) -> Dict:
        """Get schema using centralized database connection"""
        if tenant_id not in self._schema_cache:
            from .schema_extractor import SchemaExtractor
            extractor = SchemaExtractor()
            schema_data = extractor.extract_tenant_schema(tenant_id)
            if not schema_data:
                raise ValueError(f"Tenant {tenant_id} not found")
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
            pagination=Pagination(),
            description=f"Semantic search for: {query_text[:50]}"
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
            "pagination": {"skip": 0, "limit": settings.DEFAULT_PAGE_SIZE},
            "description": f"Semantic search for: {query_text[:50]}"
        }
    
    def _ai_parse(
        self, 
        query_text: str, 
        schema_data: Dict,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """Use OpenAI to parse natural language query with retry logic and token tracking"""
        
        # Check for large schema safeguard
        summary = schema_data.get("summary", {})
        total_values = summary.get("total_values", 0)
        
        if total_values > self.max_schema_values:
            logger.info(f"Schema too large ({total_values} values), using dynamic handler")
            return self._handle_large_schema(query_text, schema_data)
        
        # Build OpenAI function schema
        categories = schema_data.get("categories", {})
        tool_schema = self._build_openai_tool_schema(categories)
        
        # Format conversation context
        context_string = self._format_conversation_context(conversation_history)
        
        # Build system message with context
        system_message = self._build_system_message(
            categories, 
            schema_data, 
            query_text,
            context_string
        )
        
        # Prepare messages for token tracking
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query_text}
        ]
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                completion = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    tools=tool_schema,
                    tool_choice={"type": "function", "function": {"name": "parse_query"}},
                    temperature=settings.OPENAI_TEMPERATURE
                )
                
                execution_time = time.time() - start_time
                result = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
                
                # Track token usage for debugging
                response_text = json.dumps(result)
                log_token_usage(messages, response_text, execution_time, "query_parser")
                
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
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "high=clear intent and specific request, medium=mostly clear, low=vague or ambiguous query"
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    cat: {
                                        "type": "object",
                                        "properties": {
                                            "include": {
                                                "type": "array",
                                                "items": {"type": "string", "enum": list(values.keys()) if isinstance(values, dict) else values}
                                            },
                                            "exclude": {
                                                "type": "array",
                                                "items": {"type": "string", "enum": list(values.keys()) if isinstance(values, dict) else values}
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
                            "description": {
                                "type": "string",
                                "description": "Brief 1-sentence summary of the parsed query intent (10-15 words max)"
                            }
                        },
                        "required": ["route", "operation", "filters", "is_negation", "needs_data"]
                    }
                }
            }
        ]
    
    def _build_system_message(
        self, 
        categories: Dict, 
        schema_data: Dict, 
        query_text: str,
        context_string: str = ""
    ) -> str:
        """
        Build system message for query parsing with optional conversation context
        """
        
        categories_context = json.dumps(categories, indent=2)
        today = datetime.today().strftime("%Y-%m-%d")
        
        # Add context section if available
        context_section = ""
        if context_string:
            context_section = f"""
**CONVERSATION CONTEXT:**
{context_string}

**CONTEXT USAGE:**
**CONTEXT RULES (if history provided):**
- Vague queries ("it", "more", "those", "that") → inherit prev filters + operation
- "tell me more/about it" = continue prev query with same params
- "distribution of X" = inherit filters, change operation only
- pure_advisory ONLY if explicit: "advice", "help me", "strategy"
"""
        
        return f"""
You are a query parser that converts natural language into structured database queries.
Parse queries using this step-by-step approach to avoid conflicts.

{context_section}

**STEP 1: ROUTE (Always "database" unless pure advisory)**
- route: "database" = Query needs data from database
- route: "advisory" = Pure strategic advice without data

**STEP 2: OPERATION (Choose exactly ONE)**
- `list` = User wants to SEE/SHOW specific content items
Keywords: "show", "list", "find", "get", "display", "give me", "how many", "which ones"

- `distribution` = User wants to ANALYZE/BREAK DOWN by categories
Keywords: "distribution", "breakdown", "analyze", "what percentage"

- `semantic` = User searches with DESCRIPTIVE terms (not exact category names)
Keywords: topics/themes not in exact schema values

- `pure_advisory` = User wants strategic advice or help
Keywords: "help", "advice", "strategy", "what should I", "how can you"

**STEP 3: CONFIDENCE**
- "high" = Clear intent, specific request
- "medium" = Mostly clear intent  
- "low" = Vague or ambiguous

**STEP 4: FILTERS (Only use exact category values from schema)**
Match user terms to exact schema values. Use empty objects if no matches.
Example: "TOFU content" → {{"Funnel Stage": {{"include": ["TOFU"], "exclude": []}}}}

**STEP 5: PAGINATION**
- Default: {{"skip": 0, "limit": {settings.DEFAULT_PAGE_SIZE}}}
- "top N": {{"skip": 0, "limit": N}}

**STEP 6: OTHER FIELDS**
- marketing_filter: true (marketing mentioned), false (non-marketing), null (not mentioned)
- is_negation: true only for "not X", "without Y"
- semantic_terms: descriptive words for semantic search
- needs_data: false only for pure advisory
- distribution_fields: category names for distribution operation

**STEP 7: DESCRIPTION (REQUIRED)**
Provide a brief 1-sentence summary (10-15 words max) of what was parsed.
Format examples:
- "Listing TOFU content from last month"
- "Distribution breakdown by Industry category"
- "Semantic search for AI and machine learning topics"
- "Strategic advice on content gap analysis"
- "Showing Technology industry content excluding Marketing"

**CRITICAL RULES:**
1. If operation is "distribution", MUST include distribution_fields
2. Use exact schema values only - never invent new ones
3. Default to simple interpretations, avoid over-complicating
4. ALWAYS provide a description field

**AVAILABLE CATEGORIES:**
{categories_context}

**TODAY:** {today}

Return valid JSON matching the function schema exactly, including the description field."""
    
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