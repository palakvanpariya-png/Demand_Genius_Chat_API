# app/core/llm_helpers/prompt_builders.py
import json
from typing import Dict, List, Any
from loguru import logger
from .data_normalizers import clean_for_json

def get_classification_tool_schema() -> List[Dict]:
    """Define the tool schema for classification and response generation"""
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_classified_response",
                "description": "Classify the query intent and generate appropriate content strategy advice",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent_type": {
                            "type": "string",
                            "enum": ["GREETING", "CAPABILITY", "BUSINESS_ANALYSIS", "FOLLOW_UP"],
                            "description": "Classification of user query intent"
                        },
                        "response": {
                            "type": "string",
                            "description": "Main advisory response tailored to the intent type"
                        },
                        "suggested_questions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "2-3 contextual follow-up questions",
                            "minItems": 2,
                            "maxItems": 3
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Confidence level in the analysis"
                        }
                    },
                    "required": ["intent_type", "response", "suggested_questions", "confidence"]
                }
            }
        }
    ]

def determine_context_level(context: Dict[str, Any]) -> str:
    """Determine what context level to provide based on query characteristics"""
    query = context.get("original_query", "").lower().strip()
    operation = context.get("operation", "")
    has_history = context.get("conversation_context", {}).get("has_history", False)
    
    # Quick heuristics to pre-filter context (runs instantly)
    if len(query) <= 15 and any(word in query for word in ['hi', 'hello', 'hey']):
        return "MINIMAL"
    
    if any(phrase in query for phrase in ['what can you', 'how can you', 'capabilities']):
        return "BASIC" 
    
    if has_history and len(query) < 50:
        return "CONTEXTUAL"
    
    return "FULL"

def build_system_message(context: Dict[str, Any]) -> str:
    """Build system message that instructs LLM to classify and respond intelligently"""
    
    context_level = determine_context_level(context)
    
    # Build the core system message with classification instructions
    base_prompt = """You are an intelligent content strategy advisor. You must first classify the user's query intent, then provide an appropriate response using smart data interpretation.

CLASSIFICATION GUIDELINES:
- GREETING: Pure greetings like "hello", "hi" with no content questions
- CAPABILITY: Questions about what you can do, your features, general help requests
- BUSINESS_ANALYSIS: Requests for content analysis, insights, data exploration, strategy advice
- FOLLOW_UP: Building on previous conversation, referencing earlier topics

INTELLIGENT RESPONSE GUIDELINES BY INTENT:

GREETING Responses:
- Be warm and welcoming
- Briefly explain what you can help with (content analysis, strategy insights)
- Keep it conversational, not business-heavy
- Don't analyze any data, just explain capabilities

CAPABILITY Responses:
- Explain specifically what you can analyze for their content
- Reference their actual content library size and categories if available
- Focus on practical analytical capabilities
- Be helpful and specific about your services

BUSINESS_ANALYSIS Intelligence Guidelines:
- Naturally interpret and integrate data insights into strategic analysis
- For LIST/SEMANTIC operations: Intelligently discuss what the search results reveal
- For DISTRIBUTION operations: Calculate percentages and provide category breakdowns with strategic insights
- For ADVISORY operations: Focus on strategic consulting without data analysis
- Don't just report numbers - interpret what they mean for business strategy
- Use data as evidence for strategic recommendations
- When search results seem unexpected, explore the implications intelligently
- Maintain consultant-level thinking and natural conversation flow
- Provide 1-2 specific, actionable recommendations based on data insights
- Be conversational like a consultant colleague, never robotic
- NEVER mention technical terms like "search", "query", "database operations"

FOLLOW_UP Responses:
- Reference previous conversation naturally
- Build on established context without repeating
- Provide fresh insights that advance the discussion
- Connect current query to previous topics when relevant

CRITICAL DATA INTERPRETATION RULES:
- When data shows results found: Naturally weave findings into strategic insights
- When data shows no results: Intelligently explore what this means strategically
- When results seem mismatched to query: Question and analyze the implications
- Always interpret data contextually, not mechanically
- Use actual numbers and percentages to support strategic points
- Focus on business implications and growth opportunities"""

    # Add context based on determined level
    if context_level == "MINIMAL":
        context_section = """
AVAILABLE CONTEXT: Minimal (greeting-level interaction)
- Focus on explaining capabilities without diving into their specific data"""
        
    elif context_level == "BASIC":
        tenant_info = context.get("tenant_context", {})
        context_section = f"""
AVAILABLE CONTEXT: Basic tenant information
- Their content library: {tenant_info.get('total_content', 0)} pieces of content
- Content categories: {tenant_info.get('category_count', 0)} categories available
- Use this to explain what you can analyze for them specifically"""
        
    elif context_level == "CONTEXTUAL":
        conversation = context.get("conversation_context", {})
        context_section = f"""
AVAILABLE CONTEXT: Conversation history available
- Previous topics: {conversation.get('recent_topics', [])}
- Previous queries: {conversation.get('previous_queries', [])}
- Conversation summary: {conversation.get('conversation_summary', '')}
- Reference previous discussion naturally and build upon it"""
        
    else:  # FULL
        context_section = build_full_context_section(context)
    
    return f"{base_prompt}\n{context_section}"

def build_full_context_section(context: Dict[str, Any]) -> str:
    """Build comprehensive context section for business analysis"""
    
    # Create intelligent data summary that LLM can't ignore
    try:
        data_summary = create_intelligent_data_summary(context.get("data_patterns", {}), context.get("original_query", ""))
    except Exception as e:
        logger.warning(f"Data summarization failed: {e}")
        data_summary = "Data analysis available but summary failed"
    
    # Build context sections
    sections = [f"""
AVAILABLE CONTEXT: Full business analysis context
- Query type: {context.get('operation', 'unknown')}
- SEARCH RESULTS: {data_summary}"""]
    
    # Add tenant categories if available
    if context.get("tenant_categories"):
        categories = list(context["tenant_categories"].keys())[:8]  # Limit for token efficiency
        sections.append(f"- Available categories: {categories}")
    
    # Add industry context if relevant
    if context.get("industry_context"):
        industry = context["industry_context"]
        industry_parts = []
        if industry.get("explicit_industry"):
            industry_parts.append(f"Industry: {industry['explicit_industry']}")
        if industry.get("primary_audiences"):
            industry_parts.append(f"Audiences: {industry['primary_audiences']}")
        if industry_parts:
            sections.append(f"- Business context: {', '.join(industry_parts)}")
    
    # Add tenant summary
    tenant = context.get("tenant_context", {})
    if tenant.get("total_content"):
        sections.append(f"- Content library: {tenant['total_content']} pieces across {tenant.get('category_count', 0)} categories")
    
    return "\n".join(sections)

def create_intelligent_data_summary(data_patterns: Dict, query: str = "") -> str:
    """Create intelligent, contextual data summary that LLM can properly interpret"""
    pattern_type = data_patterns.get("type", "unknown")
    
    if pattern_type == "content_list":
        total_found = data_patterns.get("total_found", 0)
        page_size = data_patterns.get("page_size", 0)
        has_results = data_patterns.get("has_results", False)
        
        if total_found > 0:
            if page_size > 0 and total_found > page_size:
                return f"FOUND {total_found} pieces matching the search (showing first {page_size}) - significant content volume to analyze for '{query}'"
            else:
                return f"FOUND {total_found} pieces matching the search for '{query}' - substantial content base for analysis"
        else:
            return f"NO MATCHES found for '{query}' search - indicates potential content gap or strategic opportunity"
    
    elif pattern_type == "distribution_analysis":
        categories_count = data_patterns.get("categories_count", 0)
        total_items = data_patterns.get("total_items", 0)
        distribution_data = data_patterns.get("distribution_data", [])
        
        if categories_count > 0 and total_items > 0:
            # Calculate concentration for strategic insight
            if distribution_data:
                # Find top category for insight
                try:
                    if isinstance(distribution_data[0], dict) and "count" in str(distribution_data[0]):
                        max_count = max(item.get("count", 0) for item in distribution_data)
                        concentration_pct = round((max_count / total_items) * 100, 1)
                        return f"DISTRIBUTION shows {categories_count} categories with {total_items} total pieces - top category holds {concentration_pct}% (concentration analysis available)"
                    else:
                        return f"DISTRIBUTION across {categories_count} categories covering {total_items} pieces - multi-dimensional breakdown available"
                except:
                    return f"DISTRIBUTION across {categories_count} categories with {total_items} total pieces - strategic analysis ready"
            else:
                return f"DISTRIBUTION shows {categories_count} categories with {total_items} total pieces"
        else:
            return "NO DISTRIBUTION data available - may indicate content categorization opportunity"
    
    elif pattern_type == "semantic_search":
        total_found = data_patterns.get("total_found", 0)
        search_effective = data_patterns.get("search_effective", False)
        
        if total_found > 0:
            if total_found == 1:
                return f"TOPIC SEARCH found 1 piece related to '{query}' - focused content analysis available"
            elif total_found < 10:
                return f"TOPIC SEARCH found {total_found} pieces related to '{query}' - targeted content set for analysis"
            else:
                return f"TOPIC SEARCH found {total_found} pieces related to '{query}' - extensive content coverage to analyze"
        else:
            return f"TOPIC SEARCH found no content related to '{query}' - potential content gap for strategic discussion"
    
    elif pattern_type == "advisory_only":
        return "ADVISORY consultation mode - no specific data analysis, focus on strategic guidance and capabilities"
    
    else:
        return f"ANALYSIS completed for {pattern_type} - data available for strategic interpretation"

def build_user_message(context: Dict[str, Any]) -> str:
    """Build intelligent user message that emphasizes data interpretation"""
    
    query = context.get("original_query", "")
    context_level = determine_context_level(context)
    
    if context_level == "MINIMAL":
        return f"""User query: "{query}"

This appears to be a greeting. Classify appropriately and respond warmly while explaining your capabilities."""

    elif context_level == "BASIC":
        return f"""User query: "{query}"

This appears to be a capability inquiry. Classify appropriately and explain what you can analyze for their specific content library."""

    elif context_level == "CONTEXTUAL":
        return f"""User query: "{query}"

This appears to be a follow-up question. Classify appropriately and build on the previous conversation context."""

    else:  # FULL
        data_summary = create_intelligent_data_summary(context.get("data_patterns", {}), query)
        operation = context.get("operation", "")
        
        return f"""User query: "{query}"

OPERATION: {operation}
DATA ANALYSIS: {data_summary}

Classify the intent and provide intelligent business insights. Interpret what this data means strategically and give actionable recommendations. Use the search results contextually in your strategic analysis."""

def generate_structured_fallback_response(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate intelligent fallback response that includes classification"""
    
    query = context.get("original_query", "").lower()
    
    # Simple classification fallback
    if any(word in query for word in ['hello', 'hi', 'hey']) and len(query) <= 20:
        intent_type = "GREETING"
        response = "Hello! I'm here to help you optimize your content strategy with data-driven insights and recommendations."
        questions = [
            "What would you like to analyze about your content?",
            "How can I help improve your content performance?",
            "What content challenges are you facing?"
        ]
    
    elif any(phrase in query for phrase in ['what can you', 'how can you', 'help']):
        intent_type = "CAPABILITY"
        response = "I can analyze your content performance, identify patterns and gaps, provide strategic recommendations, and help optimize your content for better results."
        questions = [
            "What specific content area would you like to explore?",
            "How can I help improve your content strategy?",
            "What content challenges should we address first?"
        ]
    
    else:
        intent_type = "BUSINESS_ANALYSIS"
        operation = context.get('operation', 'unknown')
        data_patterns = context.get('data_patterns', {})
        
        if operation == "list":
            count = data_patterns.get("total_found", 0)
            if count > 0:
                response = f"Looking at your search results, I found {count} pieces of content that match your criteria. This gives us a solid foundation to analyze patterns and strategic opportunities in this area."
            else:
                response = "Your search didn't return any matches, which actually tells us something important about your content strategy and presents an opportunity for strategic discussion."
            questions = [
                "What patterns do you see emerging from these results?",
                "How can we optimize your content strategy in this area?",
                "What content gaps should we prioritize addressing?"
            ]
        
        elif operation == "distribution":
            categories = data_patterns.get("categories_count", 0)
            total_items = data_patterns.get("total_items", 0)
            if categories > 0:
                response = f"Your content distribution across {categories} categories reveals some interesting strategic insights. With {total_items} total pieces, we can see how your content is balanced and where opportunities exist for optimization."
            else:
                response = "The distribution analysis shows limited categorization data, which suggests an opportunity to better organize and categorize your content for strategic advantage."
            questions = [
                "Which content categories offer the best growth potential?",
                "How should we rebalance your content strategy?",
                "What's the optimal content mix for your business goals?"
            ]
        
        else:
            response = "I'm ready to help analyze your content and provide strategic recommendations based on what your data reveals about your current content landscape."
            questions = [
                "What aspect of your content strategy should we explore?",
                "How can I help improve your content performance?",
                "What content opportunities should we identify first?"
            ]
    
    return {
        "intent_type": intent_type,
        "response": response,
        "suggested_questions": questions,
        "confidence": "medium"
    }