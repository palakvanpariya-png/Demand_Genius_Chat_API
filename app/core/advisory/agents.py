# app/core/advisory/agents.py
"""
SIMPLIFIED: Agents use context directly - no extra insight processing steps
Clean, direct approach that avoids overengineering
Now includes token tracking for debugging
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time
from loguru import logger
from openai import OpenAI

from ...config.settings import settings
from ...utilities.token_calculator import log_token_usage


class BaseAgent(ABC):
    """Base class for all advisory agents - UNCHANGED"""
    
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
                max_tokens=max_tokens,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


class ContentResultsAgent(BaseAgent):
    """
    SIMPLIFIED: Uses context directly for content analysis
    No intermediate insight processing - just raw context to LLM
    """
    
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using context directly"""
        
        query = context.get("original_query", "")
        data_results = context.get("data_results", {})
        
        # Handle conversational queries first
        # conversation_response = self._handle_conversational_query(query)
        # if conversation_response:
        #     return conversation_response
        
        # Build prompt directly from context - no extra processing
        prompt = self._build_content_prompt(query, data_results, context)
        
        try:
            response_text = self._call_llm(
                system_prompt="You are a content analyst who provides actionable insights. Be direct and helpful.",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            
            suggestions = self._generate_simple_suggestions(data_results)
            
            return {
                "response": response_text,
                "suggested_questions": suggestions,
                "confidence": "high"
            }
            
        except Exception as e:
            logger.error(f"Content agent error: {e}")
            return self._fallback_response(query, data_results)
    
    
    def _build_content_prompt(self, query: str, data_results: Dict, context: Dict) -> str:
        """
        SIMPLIFIED: Build prompt directly from context
        No intermediate insight processing
        """
        if data_results.get("status") == "no_results":
            return f'Query: "{query}" - No content found. Suggest alternatives and explain what this means.'
        
        total_found = data_results.get("total_found", 0)
        showing = data_results.get("showing", total_found)
        
        # Use context directly - pass what we have to LLM
        return f"""
Query: "{query}"
Results: Found {total_found} content pieces (showing {showing})
Context: {context}

Steps to follow to answer a query : first analyze the query of user find what they actually need, 
then look at the Context and find relevant insights and then first answer the query of user 
(If no data is found say that you might not have that particular query related data(mention that in response) or you can try different search terms)
Only provide insights when needed other wise ignore the context and just answer the query
Provide a helpful response that: 
1. States what was found
2. Keeps response under 150 words
3. Be conversational and actionable
"""
    
    def _generate_simple_suggestions(self, data_results: Dict) -> List[str]:
        """Simple suggestion generation"""
        if data_results.get("status") == "no_results":
            return [
                "Try different search terms",
                "Check other content categories", 
                "Show me all content types"
            ]
        
        return [
            "Analyze distribution of this content",
            "Show me gaps in this area",
            "What patterns exist in these results?"
        ]
    
    def _fallback_response(self, query: str, data_results: Dict) -> Dict[str, Any]:
        """Simple fallback"""
        total_found = data_results.get("total_found", 0)
        
        if total_found > 0:
            response = f"Found {total_found} content pieces but had trouble analyzing them."
        else:
            response = "No content found. Try different search terms."
        
        return {
            "response": response,
            "suggested_questions": [
                "Show me content categories",
                "What content do I have?",
                "Help me explore my library"
            ],
            "confidence": "medium"
        }



class DistributionAgent(BaseAgent):
    """
    SIMPLIFIED: Uses context directly for distribution analysis
    """
    
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate distribution response from context directly"""
        
        query = context.get("original_query", "")
        dist_results = context.get("distribution_results", {})
        
        # Simple prompt building - no complex processing
        prompt = self._build_distribution_prompt(query, dist_results)
        
        try:
            response_text = self._call_llm(
                system_prompt="You are a data analyst. Provide clear distribution insights with specific numbers.",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            
            return {
                "response": response_text,
                "suggested_questions": [
                    "Show me content in underrepresented areas",
                    "What topics are missing?",
                    "How can I rebalance this?"
                ],
                "confidence": "high"
            }
            
        except Exception as e:
            logger.error(f"Distribution agent error: {e}")
            return self._fallback_distribution_response(query, dist_results)
    
    def _build_distribution_prompt(self, query: str, dist_results: Dict) -> str:
        """Simple distribution prompt"""
        if dist_results.get("status") == "no_distribution":
            return f'Query: "{query}" - No distribution data available. Explain and suggest alternatives.'
        
        return f"""
Query: "{query}"
Distribution Data: {dist_results}

Analyze the distribution and provide:
1. STRICT RULE : Focus only on data relevant to the user's query (if query is about category X, only discuss category X not the whole Distribution Data)
2. Steps to follow to answer a query : first analyze the query of user find what they actually need, then look at the Distribution Data and find relevant insights and
then first answer the query of user as per question and then provide additional insights if relevant. remember to first answer the query of user as per question.
3. Identify patterns, gaps, or concentrations in the data
4. Keep response concise and user-focused (max 150 words)
5. Highlight specific categories and percentages when relevant
6. Do not give the intent analysis just provide the answer
"""
    
    def _fallback_distribution_response(self, query: str, dist_results: Dict) -> Dict[str, Any]:
        """Simple fallback for distribution"""
        return {
            "response": "I have distribution data but had trouble analyzing patterns. What specific insights would help?",
            "suggested_questions": [
                "What categories do I have?",
                "Show me content organization",
                "How is content categorized?"
            ],
            "confidence": "medium"
        }


class AdvisoryAgent(BaseAgent):
    """
    ENHANCED: Advisory Agent with better intent detection and rich tenant context
    Uses actual tenant data to provide specific, actionable strategic advice
    """
    
    def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate strategic advice using enhanced tenant context"""
        
        query = context.get("original_query", "")
        advisory_context = context.get("advisory_context", {})
        
        # Enhanced advisory prompt with intent detection
        prompt = self._build_enhanced_advisory_prompt(query, advisory_context)
        
        try:
            response_text = self._call_llm(
                system_prompt="You are a strategic business advisor who provides actionable content strategy advice based on actual client data. Use specific numbers and patterns from their content library to give targeted recommendations.",
                user_prompt=prompt,
                temperature=0.4,  # Slightly higher for strategic creativity
                max_tokens=500
            )
            
            return {
                "response": response_text,
                "suggested_questions": [ 
                    "How can I optimize my content strategy?",
                    "What strategic opportunities should I focus on?",
                    "What should be my next content priority?"
                ],
                "confidence": "high"
            }
            
        except Exception as e:
            logger.error(f"Enhanced advisory agent error: {e}")
            return self._fallback_advisory_response(query, advisory_context)
    
    def _build_enhanced_advisory_prompt(self, query: str, advisory_context: Dict) -> str:
        """SIMPLIFIED: Direct usage of category data with counts"""
        
        total_content = advisory_context.get("total_content", 0)
        categories = advisory_context.get("categories", {})
        category_count = advisory_context.get("content_maturity", 0)
        previous_context = advisory_context.get("previous_context", [])
        
        # Format category data for the prompt
        category_breakdown = ""
        for cat_name, cat_values in categories.items():
            if isinstance(cat_values, dict):  # New format with counts
                category_breakdown += f"\n{cat_name}:\n"
                for value, count in cat_values.items():
                    category_breakdown += f"  - {value}: {count} pieces\n"
        
        return f"""
 User Query: "{query}"
Previous Context: {previous_context}

CONTENT LIBRARY DATA:
Total Content: {total_content} pieces across {category_count} categories

CATEGORY BREAKDOWN:
{category_breakdown}

RESPONSE STRICT RULES:
1. If it related to Greeting or simple stuff which might be asking about your capabilities do not strictly give analysis with numbers yet just give specific answer according to the query; remember to understand the query and answer according to that.
if it's only greeting greet them and ask them how you can help them?
2. Irrelevant queries → "Your query does not seem related to content strategy or this dataset. Please ask a relevant question."
2. Use previous context for coherent multi-turn responses
3. Insufficient information → "I can give you this information based on my analysis, but if you provide a clearer question I can help you better"
4. Add specifications and analysis only when asked otherwsie do give a brief overview of the content library without specific numbers
5. Give your overview as to how the directory is not just numbers 

QUERY HANDLING:
• Overview ("what do you know", "hello", "tell me about" kind of questions ) → Brief overview (50-100 words)

• Specific ("analyze X category", "focus on Y", "should I prioritize Z") → Targeted analysis (100-200 words)

• Vague Strategic ("strategy", "optimize", "recommendations", "improve") → Ask for clarification:
  "I can provide strategic analysis on several areas. Which would you like me to focus on:
  [List 3-4 top categories from breakdown above]
  • Overall portfolio optimization
  • A specific area you're concerned about?
  Please specify for targeted strategic advice."

• Detailed ("comprehensive analysis", "full breakdown", "analyze everything") → Complete analysis (200-300 words)

DATA USAGE REQUIREMENTS:
- Reference exact numbers from category breakdown only when asked not every time 
- Identify specific strengths and gaps
- Base recommendations on actual content distribution
- Be actionable with concrete next steps

Analyze query intent silently, then respond using specific data above."""
        
    def _fallback_advisory_response(self, query: str, advisory_context: Dict) -> Dict[str, Any]:
        """Enhanced fallback with basic tenant context"""
        total_content = advisory_context.get("total_content", 0)
        categories = advisory_context.get("content_maturity", 0)
        
        if total_content > 0:
            response = f"I can provide strategic advice for your {total_content}-piece content library across {categories} categories. What specific strategic guidance would be most helpful?"
        else:
            response = "I can help you develop content strategy and provide strategic recommendations. What strategic challenge should we tackle first?"
        
        return {
            "response": response,
            "suggested_questions": [
                "How can I improve my content strategy?",
                "What strategic opportunities should I focus on?",
                "Help me plan my content roadmap",
                "Where should I invest my content efforts?"
            ],
            "confidence": "medium"
        }