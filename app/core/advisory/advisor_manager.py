# app/core/advisory/advisor_manager.py
"""
Advisory Manager - Main orchestrator that routes to appropriate agents
Replaces the complex advisory_answer.py with operation-based routing
"""

from typing import Dict, Any, Optional
from loguru import logger
from openai import OpenAI

from ...config.settings import settings
from ...models.query import QueryResult
from ...models.database import DatabaseResponse
from .agents import ContentResultsAgent, DistributionAgent, AdvisoryAgent
from .data_processor import DataProcessor
from ..session_handler import SessionHandler


class AdvisorManager:
    """
    Main advisory orchestrator that routes queries to specialized agents
    """
    
    def __init__(self, openai_api_key: str = None):
        # Initialize OpenAI client
        self.client = OpenAI(api_key=openai_api_key or settings.OPENAI_API_KEY)
        
        # Initialize components
        self.data_processor = DataProcessor()
        self.session_handler = SessionHandler()
        
        # Initialize agents with shared client
        self.content_agent = ContentResultsAgent(self.client, self.data_processor)
        self.distribution_agent = DistributionAgent(self.client, self.data_processor)
        self.advisory_agent = AdvisoryAgent(self.client, self.data_processor)
    
    def generate_response(
        self,
        operation: str,
        query_result: QueryResult,
        db_response: DatabaseResponse,
        tenant_schema: Dict,
        original_query: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate advisory response using operation-based routing
        
        Args:
            operation: Query operation type ('list', 'semantic', 'distribution', 'pure_advisory')
            query_result: Parsed query result
            db_response: Database response with actual results
            tenant_schema: Tenant schema information
            original_query: User's original query
            session_id: Optional session ID
            
        Returns:
            Advisory response dictionary
        """
        try:
            # Build data-first context using your proven logic
            context = self.data_processor.build_context(
                operation, query_result, db_response, tenant_schema, 
                original_query, session_id, self.session_handler
            )
            
            # Route to appropriate agent based on operation (no classification needed)
            if operation in ['list', 'semantic']:
                response = self.content_agent.generate_response(context)
            elif operation == 'distribution':
                response = self.distribution_agent.generate_response(context)
            else:  # pure_advisory
                response = self.advisory_agent.generate_response(context)
            
            # Store interaction in session if provided
            if session_id:
                self.session_handler.store_interaction(session_id, original_query, response, operation)
            
            return response
            
        except Exception as e:
            logger.error(f"Advisory manager error: {e}")
            return self._fallback_response(original_query, operation)
    
    def _fallback_response(self, query: str, operation: str) -> Dict[str, Any]:
        """Fallback response when analysis fails"""
        fallback_messages = {
            'list': "I found your content but having trouble analyzing it right now.",
            'semantic': "I found matching content but having trouble providing insights right now.",
            'distribution': "I have your distribution data but having trouble analyzing patterns right now.",
            'pure_advisory': "I encountered an issue generating insights. Let me help you with a simpler query."
        }
        
        return {
            "response": fallback_messages.get(operation, "I encountered an issue processing your request."),
            "suggested_questions": [
                "Show me my content overview",
                "What content categories do I have?",
                "Help me understand my content distribution"
            ],
            "confidence": "low"
        }
    
    def clear_session(self, session_id: Optional[str] = None):
        """Clear session data"""
        self.session_handler.clear_session(session_id)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        return self.session_handler.get_stats()


# Factory functions for service integration
def create_advisor_manager(openai_api_key: str = None, mongo_uri: str = None, db_name: str = None) -> AdvisorManager:
    """Create AdvisorManager instance with MongoDB session support"""
    return AdvisorManager(openai_api_key, mongo_uri, db_name)

# Global instance for backward compatibility
_advisor_manager = None

def get_advisor_manager(mongo_uri: str = None, db_name: str = None) -> AdvisorManager:
    """Get global advisor manager instance with MongoDB support"""
    global _advisor_manager
    if _advisor_manager is None:
        _advisor_manager = AdvisorManager(mongo_uri=mongo_uri, db_name=db_name)
    return _advisor_manager