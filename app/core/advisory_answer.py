# app/core/advisory_answer.py
import json
import logging
from loguru import logger

from typing import Dict, List, Any, Optional, Union
from openai import OpenAI
from datetime import datetime
from ..config.settings import settings
from ..models.query import QueryResult
from ..models.database import DatabaseResponse
from ..models.session import InteractionRecord
from ..models.content import DistributionItem, DistributionResult

# Import helper functions
from .llm_helpers.data_normalizers import (
    normalize_query_result,
    normalize_db_response,
    clean_for_json
)
from .llm_helpers.context_processors import prepare_advisory_context
from .llm_helpers.conversation_manager import add_to_conversation_history
from .llm_helpers.prompt_builders import (
    get_classification_tool_schema,
    build_system_message,
    build_user_message,
    generate_structured_fallback_response
)

# logger = logging.getLogger(__name__)

class IntelligentAdvisor:
    """
    Dynamic LLM-powered content advisor with conversation memory and intelligent classification
    """
    
    def __init__(self, openai_api_key: str = None):
        self.client = OpenAI(api_key=openai_api_key or settings.OPENAI_API_KEY)
        self.conversation_cache: Dict[str, List[InteractionRecord]] = {}
        self.max_history_length = settings.MAX_SESSION_INTERACTIONS
    
    def generate_advisory_response(
        self, 
        operation: str, 
        query_result: Union[QueryResult, Dict], 
        db_response: Union[DatabaseResponse, Dict], 
        tenant_schema: Dict, 
        original_query: str, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate intelligent advisory response using LLM with tool-based classification
        
        Args:
            operation: Query operation type
            query_result: Parsed query result (QueryResult or dict for backward compatibility)
            db_response: Database response (DatabaseResponse or dict for backward compatibility)
            tenant_schema: Tenant's schema from schema_extractor
            original_query: User's original query text
            session_id: Optional session ID for conversation context
        
        Returns:
            Structured advisory response with classification
        """
        
        # Handle both new and legacy input formats using helpers
        query_dict = normalize_query_result(query_result)
        db_dict = normalize_db_response(db_response)
        
        # Prepare context for LLM using helper
        context = prepare_advisory_context(
            operation, query_dict, db_dict, tenant_schema, original_query, 
            self.conversation_cache, session_id
        )
        
        # Generate response using LLM with classification
        response = self._call_classification_llm(context)
        
        # Store interaction in conversation history if session_id provided
        if session_id:
            add_to_conversation_history(
                self.conversation_cache,
                session_id, 
                original_query, 
                response, 
                operation,
                self.max_history_length,
                query_dict.get('tenant_id')
            )
        
        return response
    
    def _call_classification_llm(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM with tool-based classification and response generation"""
        
        # Get the tool schema for classification
        tool_schema = get_classification_tool_schema()
        
        # Build system and user messages using helpers
        system_message = build_system_message(context)
        user_message = build_user_message(context)
        
        try:
            completion = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                tools=tool_schema,
                tool_choice={"type": "function", "function": {"name": "generate_classified_response"}},
                temperature=0.4,  # Balanced for natural responses with consistency
            )
            
            # Parse the tool call response
            tool_call = completion.choices[0].message.tool_calls[0]
            result = json.loads(tool_call.function.arguments)

            validated_result = self._validate_llm_response(result)
            
            # Log the classification for monitoring
            intent_type = validated_result.get("intent_type", "unknown")
            logger.info(f"Query classified as: {intent_type} for query: '{context.get('original_query', '')[:50]}...'")
            
            return validated_result
            
        except Exception as e:
            logger.error(f"LLM classification call failed: {e}")
            return generate_structured_fallback_response(context)
        
    def _validate_llm_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure LLM response has all required fields"""
        
        required_fields = {
            'intent_type': 'BUSINESS_ANALYSIS',
            'response': 'I can help analyze your content and provide strategic insights.',
            'suggested_questions': ['What would you like to explore?', 'How can I help optimize your content?'],
            'confidence': 'medium'
        }
        
        validated = {}
        for field, default in required_fields.items():
            validated[field] = result.get(field, default)
            if field not in result:
                logger.warning(f"LLM response missing required field: {field}, using default")
        
        return validated
    
    def get_classification_metrics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get classification metrics for monitoring and optimization"""
        
        if session_id and session_id in self.conversation_cache:
            history = self.conversation_cache[session_id]
            
            # Count classifications (would need to track this in actual implementation)
            classifications = {}
            for interaction in history:
                # This would require storing classification info in InteractionRecord
                # For now, return basic metrics
                pass
            
            return {
                "session_interaction_count": len(history),
                "session_id": session_id
            }
        
        elif not session_id:
            # Return global metrics
            total_sessions = len(self.conversation_cache)
            total_interactions = sum(len(history) for history in self.conversation_cache.values())
            
            return {
                "total_sessions": total_sessions,
                "total_interactions": total_interactions,
                "average_interactions_per_session": total_interactions / total_sessions if total_sessions > 0 else 0
            }
        
        return {"error": "Session not found"}
    
    def clear_conversation_cache(self, session_id: Optional[str] = None):
        """Clear conversation cache for session or all sessions"""
        if session_id:
            self.conversation_cache.pop(session_id, None)
            logger.info(f"Cleared conversation cache for session {session_id}")
        else:
            self.conversation_cache.clear()
            logger.info("Cleared all conversation cache")

# Factory function for dependency injection
def create_intelligent_advisor(openai_api_key: str = None) -> IntelligentAdvisor:
    """Create IntelligentAdvisor instance"""
    return IntelligentAdvisor(openai_api_key)

# Global advisor instance for backward compatibility
_advisor_instance = None

def get_intelligent_advisor() -> IntelligentAdvisor:
    """Get global advisor instance"""
    global _advisor_instance
    if _advisor_instance is None:
        _advisor_instance = IntelligentAdvisor()
    return _advisor_instance

# Backward compatibility function
def generate_response_for_query(
    operation: str, 
    query_result: Union[QueryResult, Dict], 
    db_response: Union[DatabaseResponse, Dict], 
    tenant_schema: Dict, 
    original_query: str, 
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main function to generate advisory response - backward compatibility
    """
    advisor = get_intelligent_advisor()
    return advisor.generate_advisory_response(
        operation, query_result, db_response, tenant_schema, original_query, session_id
    )