# app/core/advisory/simple_orchestrator.py
"""
Simple Advisory Orchestrator - Direct routing without LangChain overhead
Single API call orchestration using existing agents and context manager
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from openai import OpenAI

from ...config.setting import settings
from ...models.query import QueryResult
from ...models.database import DatabaseResponse
from .context_manager import DataProcessor
from .agents import ContentResultsAgent, DistributionAgent, AdvisoryAgent
from ..session_handler import SessionHandler


class AdvisoryOrchestrator:
    """
    Lightweight orchestrator that directly routes to appropriate agents
    No LangChain overhead - single API call per request
    """
    
    def __init__(self, openai_api_key: str = None, mongo_uri: str = None, db_name: str = None):
        # Initialize OpenAI client for agents
        openai_client = OpenAI(api_key=openai_api_key or settings.OPENAI_API_KEY)
        
        # Initialize components (same as existing)
        self.data_processor = DataProcessor()
        self.session_handler = SessionHandler(
            mongo_uri=mongo_uri, 
            db_name=db_name, 
            max_memory_length=6
        )
        
        # Initialize domain agents (existing)
        self.content_agent = ContentResultsAgent(openai_client, self.data_processor)
        self.distribution_agent = DistributionAgent(openai_client, self.data_processor) 
        self.advisory_agent = AdvisoryAgent(openai_client, self.data_processor)
    
    def generate_response(
        self,
        operation: str,
        query_result: QueryResult,
        db_response: DatabaseResponse,
        tenant_schema: Dict,
        original_query: str,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Direct orchestration - single path to appropriate agent
        No LangChain tools or multiple API calls
        """
        try:
            # Build context using existing DataProcessor (enhanced version)
            context = self.data_processor.build_context(
                operation=operation,
                query_result=query_result,
                db_response=db_response,
                tenant_schema=tenant_schema,
                original_query=original_query,
                session_id=session_id,
                session_handler=self.session_handler,
                tenant_id=tenant_id or query_result.tenant_id
            )
            
            # Direct routing based on operation (no LangChain decision making)
            agent_response = self._route_to_agent(operation, context, original_query)
            
            # Store interaction in session (same as existing)
            if session_id:
                self._store_interaction(
                    session_id, 
                    original_query, 
                    agent_response, 
                    operation,
                    tenant_id or query_result.tenant_id
                )
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Simple orchestrator error: {e}")
            return self._fallback_response(original_query, operation)
    
    def _route_to_agent(self, operation: str, context: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Direct routing - no AI decision making overhead
        Single agent call based on operation type
        """
        
        # Direct routing based on operation
        if operation in ["list", "semantic"]:
            return self.content_agent.generate_response(context)
        elif operation == "distribution":
            return self.distribution_agent.generate_response(context)
        else:  # pure_advisory or unknown
            return self.advisory_agent.generate_response(context)
    
    def _is_conversational_query(self, query: str) -> bool:
        """Lightweight conversational detection"""
        if not query or not query.strip():
            return False
        
        query_lower = query.strip().lower()
        conversational_keywords = [
            "hi", "hello", "hey", "thanks", "thank you", 
            "help", "what can you do", "what do you do"
        ]
        
        return any(keyword in query_lower for keyword in conversational_keywords)
    
    def _default_conversational_response(self) -> Dict[str, Any]:
        """Default conversational response"""
        return {
            "response": "Hello! I can help you analyze your content library. What would you like to explore?",
            "suggested_questions": [
                "Show me my content overview",
                "What content categories do I have?",
                "Analyze my content distribution",
                "What strategic opportunities do I have?"
            ],
            "confidence": "high"
        }
    
    def _store_interaction(self, session_id: str, query: str, response: Dict[str, Any], 
                          operation: str, tenant_id: str):
        """Store interaction in MongoDB session (same as existing)"""
        try:
            self.session_handler.store_interaction(
                session_id, query, response, operation, tenant_id
            )
        except Exception as e:
            logger.error(f"Failed to store interaction: {e}")
    
    def _fallback_response(self, query: str, operation: str) -> Dict[str, Any]:
        """Fallback response with operation-specific messaging"""
        fallback_messages = {
            'list': "I found your content but having trouble analyzing it right now.",
            'semantic': "I found matching content but having trouble providing insights right now.", 
            'distribution': "I have your distribution data but having trouble analyzing patterns right now.",
            'pure_advisory': "I encountered an issue generating strategic insights, but I can still help with your content strategy."
        }
        
        return {
            "response": fallback_messages.get(operation, "I encountered an issue processing your request. Please try rephrasing your question."),
            "suggested_questions": [
                "Show me my content overview",
                "What content categories do I have?", 
                "Help me understand my content distribution",
                "What strategic opportunities do I have?"
            ],
            "confidence": "low"
        }
    
    # Interface methods for compatibility with existing service
    def clear_session(self, session_id: Optional[str] = None):
        """Clear session data"""
        try:
            self.session_handler.clear_session(session_id)
            logger.info(f"Cleared session data for {session_id or 'all sessions'}")
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        try:
            base_stats = self.session_handler.get_stats()
            base_stats.update({
                "orchestrator_type": "simple_direct_routing",
                "agents_available": 3,
                "enhanced_advisory": True,
                "latency_optimized": True,
                "api_calls_per_request": 1
            })
            return base_stats
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {"error": str(e)}


# Factory function for service integration
def create_simple_advisory_orchestrator(
    openai_api_key: str = None, 
    mongo_uri: str = None, 
    db_name: str = None
) -> AdvisoryOrchestrator:
    """Create simple orchestrator with direct routing"""
    return AdvisoryOrchestrator(openai_api_key, mongo_uri, db_name)