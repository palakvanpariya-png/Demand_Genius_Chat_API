# app/core/advisory/agents.py
"""
Specialized Advisory Agents - Each handles specific operation types
Uses your proven advisory_engine logic for data-focused responses
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from loguru import logger
from openai import OpenAI

from ...config.settings import settings


class BaseAgent(ABC):
    """Base class for all advisory agents"""
    
    def __init__(self, openai_client: OpenAI, data_processor):
        self.client = openai_client
        self.data_processor = data_processor
    
    @abstractmethod
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response based on context"""
        pass
    
    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 300) -> str:
        """Call OpenAI with error handling"""
        try:
            completion = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


class ContentResultsAgent(BaseAgent):
    """
    Agent for handling 'list' and 'semantic' operations
    Uses your content analysis logic from advisory_engine
    """
    
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response for content search results"""
        
        data_results = context.get("data_results", {})
        query = context.get("original_query", "")
        operation = context.get("operation", "")
        
        # Use your proven prompt building logic
        prompt = self._build_content_analysis_prompt(query, data_results, operation)
        
        try:
            response_text = self._call_llm(
                system_prompt="You are a data analyst who provides concise, actionable insights based on actual content data. Always reference specific numbers and percentages in your analysis.",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            
            suggestions = self._generate_content_suggestions(operation, data_results)
            
            return {
                "response": response_text,
                "suggested_questions": suggestions,
                "confidence": "high"
            }
            
        except Exception as e:
            logger.error(f"Content agent LLM call failed: {e}")
            return self._fallback_content_response(query, data_results)
    
    def _build_content_analysis_prompt(self, query: str, data_results: Dict, operation: str) -> str:
        """Build content analysis prompt using your logic"""
        
        if data_results.get("status") == "no_results":
            return f'Query: "{query}" - No content found. Explain what this means and suggest alternatives.'
        
        total_found = data_results.get("total_found", 0)
        showing = data_results.get("showing", total_found)
        
        return f"""
Query: "{query}"
Results: Found {total_found} content pieces matching your search. Right now showing {showing} of them.

Your response should:
1. Clearly state how many results were found
2. Ask what specific analysis they want (distribution, gaps, categories, etc.)
3. Keep it under 100 words and be direct
4. Understand the query and respond according to that

Do not analyze sample data or make statistical claims about the full dataset.
"""
    
    def _generate_content_suggestions(self, operation: str, data_results: Dict) -> List[str]:
        """Generate contextual suggestions for content operations"""
        if data_results.get("status") == "no_results":
            return [
                "Try broader search terms",
                "Check content in different categories",
                "Show me all available content types"
            ]
        
        return [
            "How is this content distributed across categories?",
            "What gaps exist in this content area?", 
            "Show me the performance metrics for these results"
        ]
    
    def _fallback_content_response(self, query: str, data_results: Dict) -> Dict[str, Any]:
        """Fallback for content analysis failures"""
        total_found = data_results.get("total_found", 0)
        
        if total_found > 0:
            response = f"I found {total_found} content pieces for your search but had trouble analyzing them. The results are available for review."
        else:
            response = "No content matched your search criteria. Try adjusting your search terms or filters."
        
        return {
            "response": response,
            "suggested_questions": [
                "Show me all my content categories",
                "What content types do I have?",
                "Help me explore my content library"
            ],
            "confidence": "medium"
        }


class DistributionAgent(BaseAgent):
    """
    Agent for handling 'distribution' operations  
    Uses your distribution analysis logic from advisory_engine
    """
    
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response for distribution analytics"""
        
        dist_results = context.get("distribution_results", {})
        query = context.get("original_query", "")
        
        # Use your proven distribution prompt logic
        prompt = self._build_distribution_analysis_prompt(query, dist_results)
        
        try:
            response_text = self._call_llm(
                system_prompt="You are a data analyst who provides concise, actionable insights based on actual content data. Always reference specific numbers and percentages in your analysis.",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            
            suggestions = self._generate_distribution_suggestions(dist_results)
            
            return {
                "response": response_text,
                "suggested_questions": suggestions,
                "confidence": "high"
            }
            
        except Exception as e:
            logger.error(f"Distribution agent LLM call failed: {e}")
            return self._fallback_distribution_response(query, dist_results)
    
    def _build_distribution_analysis_prompt(self, query: str, dist_results: Dict) -> str:
        """Build distribution analysis prompt using your logic with task detection"""
        
        if dist_results.get("status") == "no_distribution":
            return f"""
Query: "{query}"
Results: No distribution data available.

Explain what this means and suggest alternative analysis approaches. Keep under 100 words.
"""
        
        return f"""
Query: "{query}"
Distribution Data Available:
{dist_results}

INSTRUCTION: If the user is asking to "show", "list", or "what are" the categories/values, simply say we have this many categories or values and list them clearly. 
Only do distribution analysis (percentages, gaps, recommendations) if they specifically ask for "distribution", "analysis", "breakdown", or "how much".
Understad the query and give the analysis of the categories or values user has asked for.
Answer the user's actual question directly. Keep under 200 words.
"""
   
    
    def _generate_distribution_suggestions(self, dist_results: Dict) -> List[str]:
        """Generate contextual suggestions for distribution operations"""
        if dist_results.get("status") == "no_distribution":
            return [
                "Show me my content categories",
                "What content types do I have?",
                "Help me organize my content structure"
            ]
        
        return [
            "Show me specific content in the underrepresented categories",
            "What topics are missing in my top-performing categories?",
            "How can I rebalance this distribution?"
        ]
    
    def _fallback_distribution_response(self, query: str, dist_results: Dict) -> Dict[str, Any]:
        """Fallback for distribution analysis failures"""
        total_categories = dist_results.get("total_categories", 0)
        
        if total_categories > 0:
            response = f"I found distribution data across {total_categories} categories but had trouble analyzing the patterns."
        else:
            response = "No distribution data was available for analysis. This might indicate a content categorization opportunity."
        
        return {
            "response": response,
            "suggested_questions": [
                "What content categories do I have?",
                "Show me my content organization structure",
                "How is my content currently categorized?"
            ],
            "confidence": "medium"
        }


class AdvisoryAgent(BaseAgent):
    """
    Agent for handling 'pure_advisory' operations
    Uses your strategic advisory logic from advisory_engine
    """
    
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response for strategic advisory queries"""
        
        advisory_context = context.get("advisory_context", {})
        query = context.get("original_query", "")
        
        # Use your proven advisory prompt logic
        prompt = self._build_advisory_prompt(query, advisory_context)
        
        try:
            response_text = self._call_llm(
                system_prompt="You are a strategic business advisor focused on content strategy and optimization. Provide actionable strategic advice, not data listings or basic information.",
                user_prompt=prompt,
                temperature=0.4,  # Higher for strategic creativity
                max_tokens=250
            )
            
            return {
                "response": response_text,
                "suggested_questions": [
                    "How should I optimize my content strategy?",
                    "What's the best approach for content gap analysis?",
                    "Create a content planning roadmap"
                ],
                "confidence": "high"
            }
            
        except Exception as e:
            logger.error(f"Advisory agent LLM call failed: {e}")
            return self._fallback_advisory_response(query, advisory_context)
    
    def _build_advisory_prompt(self, query: str, advisory_context: Dict) -> str:
        """Build advisory prompt using your strategic logic with intent detection"""
        
        total_content = advisory_context.get("total_content", 0)
        category_structure = advisory_context.get("category_structure", {})
        content_maturity = advisory_context.get("content_maturity", 0)
        
        return f"""
User Query: "{query}"

Content Library Context:
- Content Volume: {total_content} pieces
- Content Organization: {content_maturity} categories established
- Category Structure: {list(category_structure.keys()) if category_structure else []}

ROLE: Strategic Content Advisor

CRITICAL: First analyze the user's query intent( Don't mention the query intent to the user.):

1. STRATEGIC ADVICE QUERIES (provide full advisory response):
- Content strategy questions ("how should I optimize my content?")
- Planning and roadmap requests ("what's my next step?")
- Gap analysis requests ("where are my weaknesses?")
- Optimization advice ("how can I improve performance?")
- Business recommendations ("what should I focus on?")

2. GENERAL/EXPLORATORY QUERIES (provide brief overview):
- Generic questions ("what do you know about my directory?")
- Capability questions ("how can you help me?")
- Opinion requests ("what do you think about my directory?")
- General curiosity ("tell me about my content")
- Greetinfgs ("hello", "hi", "help")
For STRATEGIC queries: Provide detailed actionable business advice, recommendations, and strategic insights.

For GENERAL queries: Give a brief overview of your content library status and mention you can provide strategic advice if needed. Keep under 100 words.

Analyze the query intent first, then respond appropriately.
Keep strategic responses under 200 words.
"""
    
    def _fallback_advisory_response(self, query: str, advisory_context: Dict) -> Dict[str, Any]:
        """Fallback for advisory failures"""
        total_content = advisory_context.get("total_content", 0)
        
        response = f"I can help you develop content strategy and provide strategic recommendations for your {total_content}-piece content library. What specific strategic guidance are you looking for?"
        
        return {
            "response": response,
            "suggested_questions": [
                "How can I improve my content strategy?",
                "What strategic opportunities should I focus on?", 
                "Help me plan my content roadmap"
            ],
            "confidence": "medium"
        }