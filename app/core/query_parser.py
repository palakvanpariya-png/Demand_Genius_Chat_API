# app/core/query_parser.py
import json
import time
import logging
from loguru import logger

from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional
from ..config.settings import settings
from ..config.database import db_connection
from ..models.query import QueryResult, FilterDict, DateFilter, Pagination
from .schema_extractor import get_tenant_schema
from ..utilities.token_calculator import log_token_usage

class SmartQueryParser:
    """
    Enhanced query parser with context support for handling vague references like "those", "that"
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None, openai_api_key: str = None):
        self.mongo_uri = mongo_uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DATABASE_NAME
        self.client = OpenAI(api_key=openai_api_key or settings.OPENAI_API_KEY)
        self._schema_cache: Dict[str, Dict] = {}
        self.max_schema_values = settings.MAX_SCHEMA_VALUES
    
    def parse(self, query_text: str, tenant_id: str, previous_queries: List[Dict] = None) -> QueryResult:
        """
        Parse natural language query into structured QueryResult with context support
        
        Args:
            query_text: User's natural language query
            tenant_id: Tenant ID for schema context
            previous_queries: List of previous parsed queries for context (NEW)
            
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
            
            # Enhanced: Parse with context
            parsed = self._ai_parse_with_context(query_text, schema_data, previous_queries)
            
            # Convert parsed data to QueryResult using our models
            query_result = self._build_query_result(parsed, tenant_id)
            
            # Log the parsed result for debugging
            logger.info(f"Query parsed - operation: {query_result.operation}, filters: {query_result.filters}, confidence: {query_result.confidence}")
            
            return query_result
            
        except Exception as e:
            logger.error(f"Error parsing query '{query_text}' for tenant {tenant_id}: {e}")
            # Return fallback semantic search
            return self._get_fallback_query_result(query_text, tenant_id)
    
    def _ai_parse_with_context(self, query_text: str, schema_data: Dict, previous_queries: List[Dict] = None) -> Dict:
        """Enhanced AI parsing with context support"""
        
        # Check for large schema safeguard
        summary = schema_data.get("summary", {})
        total_values = summary.get("total_values", 0)
        
        if total_values > self.max_schema_values:
            logger.info(f"Schema too large ({total_values} values), using dynamic handler")
            return self._handle_large_schema(query_text, schema_data)
        
        # Build OpenAI function schema
        categories = schema_data.get("categories", {})
        tool_schema = self._build_openai_tool_schema(categories)
        
        # Enhanced: Build system message with context
        system_message = self._build_system_message_with_context(categories, schema_data, query_text, previous_queries)
        
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
                log_token_usage(messages, response_text, execution_time, "contextual_query_parser")
                
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
    
    def _build_system_message_with_context(self, categories: Dict, schema_data: Dict, query_text: str, previous_queries: List[Dict] = None) -> str:
        """Enhanced system message with context handling"""
        
        categories_context = json.dumps(categories, indent=2)
        today = datetime.today().strftime("%Y-%m-%d")
        
        # Build context section
        context_section = ""
        if previous_queries and len(previous_queries) > 0:
            context_section = "\n**PREVIOUS QUERIES CONTEXT:**\n"
            
            for i, prev_query in enumerate(previous_queries[-3:], 1):  # Last 3 queries
                query = prev_query.get("original_query", "")
                operation = prev_query.get("operation", "unknown")
                filters = prev_query.get("filters", {})
                
                context_section += f"{i}. Query: \"{query}\"\n"
                context_section += f"   Operation: {operation}\n"
                
                if filters:
                    filters_str = []
                    for cat, filter_dict in filters.items():
                        if filter_dict.get("include"):
                            filters_str.append(f"{cat}: {filter_dict['include']}")
                    if filters_str:
                        context_section += f"   Filters: {', '.join(filters_str)}\n"
                context_section += "\n"
            
            context_section += "**CONTEXT RULES:**\n"
            context_section += "- 'those', 'that', 'these' = inherit filters from most recent query with filters\n"
            context_section += "- 'show me more' = inherit all parameters, adjust pagination\n"
            context_section += "- 'distribution of those' = inherit filters, change operation to distribution\n\n"
        
        return f"""
You are a contextual query parser that handles both explicit and contextual queries.

{context_section}

**CONTEXTUAL PARSING RULES:**
1. If query contains "those", "that", "these", "them" - look at previous queries for context
2. Find the most recent query that has filters applied
3. INHERIT those exact filters for the current query
4. Adapt the operation based on current query intent

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
- "high" = Clear intent, specific request, or clear contextual reference
- "medium" = Mostly clear intent
- "low" = Vague or ambiguous

**STEP 4: FILTERS (Context-aware)**
- If contextual query ("those", "that", "these") → inherit filters from context above
- If explicit filters mentioned → use those filters
- If no context or explicit filters → empty filters
- Only use exact schema values from categories below

**STEP 5: OTHER FIELDS**
- marketing_filter: inherit from context or detect from current query
- is_negation: true only for "not X", "without Y"
- semantic_terms: descriptive words for semantic search
- needs_data: false only for pure advisory
- distribution_fields: category names for distribution operation

**EXAMPLES:**

Context: Previous query had filters {{"Funnel Stage": {{"include": ["TOFU"]}}}}
Current: "show me distribution of those"
Result: operation="distribution", filters={{"Funnel Stage": {{"include": ["TOFU"]}}}}

Context: No previous context
Current: "show me TOFU content"
Result: operation="list", filters={{"Funnel Stage": {{"include": ["TOFU"]}}}}

**AVAILABLE CATEGORIES:**
{categories_context}

**TODAY:** {today}

Return valid JSON matching the function schema exactly."""
    
    def to_dict(self, query_result: QueryResult, original_query: str) -> Dict:
        """Convert QueryResult to dict for storage in session context"""
        return {
            "original_query": original_query,
            "operation": query_result.operation,
            "filters": {
                k: {
                    "include": v.include,
                    "exclude": v.exclude
                } for k, v in query_result.filters.items()
            },
            "confidence": query_result.confidence,
            "route": query_result.route,
            "needs_data": query_result.needs_data
        }
    
    # All existing methods remain the same
    def _build_query_result(self, parsed: Dict, tenant_id: str) -> QueryResult:
        """Convert parsed dictionary to QueryResult model - UNCHANGED"""
        
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
            pagination=pagination
        )
    
    def _get_cached_schema(self, tenant_id: str) -> Dict:
        """Get schema using centralized database connection - UNCHANGED"""
        if tenant_id not in self._schema_cache:
            from .schema_extractor import SchemaExtractor
            extractor = SchemaExtractor()
            schema_data = extractor.extract_tenant_schema(tenant_id)
            if not schema_data:
                raise ValueError(f"Tenant {tenant_id} not found")
            self._schema_cache[tenant_id] = schema_data
        return self._schema_cache[tenant_id]
    
    def _get_fallback_query_result(self, query_text: str, tenant_id: str) -> QueryResult:
        """Generate fallback QueryResult for error cases - UNCHANGED"""
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
        """Handle queries for tenants with large schemas - UNCHANGED"""
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
    
    def _build_openai_tool_schema(self, categories: Dict[str, List[str]]) -> List[Dict]:
        """Build OpenAI function schema dynamically based on tenant categories - UNCHANGED"""
        
        return [
            {
                "type": "function",
                "function": {
                    "name": "parse_query",
                    "description": "Parse user queries into structured JSON for database routing with context support.",
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
                        },
                        "required": ["route", "operation", "filters", "is_negation", "needs_data"]
                    }
                }
            }
        ]
    
    def clear_cache(self):
        """Clear schema cache - UNCHANGED"""
        self._schema_cache.clear()
        logger.info("Query parser schema cache cleared")

# Factory function for dependency injection - UNCHANGED
def create_smart_parser(mongo_uri: str = None, db_name: str = None, openai_api_key: str = None) -> SmartQueryParser:
    """Create SmartQueryParser instance"""
    return SmartQueryParser(mongo_uri, db_name, openai_api_key)

# Global parser instance for backward compatibility - UNCHANGED
_parser_instance = None

def get_query_parser() -> SmartQueryParser:
    """Get global query parser instance"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = SmartQueryParser()
    return _parser_instance