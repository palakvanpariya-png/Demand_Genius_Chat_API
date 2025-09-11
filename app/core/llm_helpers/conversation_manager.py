# app/core/llm_helpers/conversation_manager.py
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from ...models.session import InteractionRecord

def get_conversation_context(conversation_cache: Dict, session_id: str, current_query: str) -> Dict[str, Any]:
    """Get relevant conversation history for current query"""
    if session_id not in conversation_cache:
        return {
            "has_history": False,
            "previous_queries": [],
            "recent_topics": [],
            "conversation_summary": ""
        }
    
    history = conversation_cache[session_id]
    
    # Get last 3 interactions for context
    recent_interactions = history[-3:] if len(history) > 3 else history
    
    # Extract relevant information
    previous_queries = [interaction.message for interaction in recent_interactions]
    recent_operations = [interaction.operation for interaction in recent_interactions]
    
    # Simple topic extraction from queries
    recent_topics = []
    for query in previous_queries:
        words = query.lower().split()
        topics = [word for word in words if len(word) > 4 and word not in ['content', 'show', 'what', 'distribution']]
        recent_topics.extend(topics[:2])
    
    # Create conversation summary
    if recent_interactions:
        last_interaction = recent_interactions[-1]
        conversation_summary = f"Previously asked about: {last_interaction.message} (operation: {last_interaction.operation})"
    else:
        conversation_summary = ""
    
    return {
        "has_history": len(recent_interactions) > 0,
        "previous_queries": previous_queries,
        "recent_operations": recent_operations,
        "recent_topics": list(set(recent_topics))[:5],
        "conversation_summary": conversation_summary,
        "interaction_count": len(history)
    }

def add_to_conversation_history(
    conversation_cache: Dict, 
    session_id: str, 
    query: str, 
    response: Dict, 
    operation: str, 
    max_history_length: int,
    tenant_id: Optional[str] = None
):
    """Store interaction in conversation history"""
    if session_id not in conversation_cache:
        conversation_cache[session_id] = []
    
    # Create interaction record using our model
    interaction = InteractionRecord(
        timestamp=datetime.utcnow().isoformat(),
        message=query,
        response_summary=response.get("response", "")[:200],
        operation=operation,
        confidence=response.get("confidence")
    )
    
    # Add to history
    conversation_cache[session_id].append(interaction)
    
    # Keep only recent interactions
    if len(conversation_cache[session_id]) > max_history_length:
        conversation_cache[session_id] = conversation_cache[session_id][-max_history_length:]