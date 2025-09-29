# app/utils/token_calculator.py
"""
Simple token calculation utility for debugging OpenAI API usage
Uses tiktoken for accurate token counting
"""

import tiktoken
from typing import Dict, List, Any, Optional
from loguru import logger
import time
from functools import wraps

from ..config.setting import settings


class TokenCalculator:
    """
    Simple token calculator for OpenAI API calls
    Provides debugging information without complexity
    """
    
    def __init__(self, model: str = None):
        self.model = model or settings.OPENAI_MODEL
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback for newer models
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        # Simple tracking
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string"""
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
    def count_messages_tokens(self, messages: List[Dict]) -> int:
        """Count tokens in OpenAI messages format"""
        total_tokens = 0
        
        for message in messages:
            # Each message has overhead tokens
            total_tokens += 3  # role + content wrapper
            
            role = message.get("role", "")
            content = message.get("content", "")
            
            total_tokens += self.count_tokens(role)
            total_tokens += self.count_tokens(content)
        
        # Add overhead for the conversation
        total_tokens += 3
        
        return total_tokens
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost based on token usage
        Using approximate GPT-4 pricing for debugging
        """
        # Approximate pricing (update as needed)
        pricing = {
            "gpt-4": {"input": 0.03 / 1000, "output": 0.06 / 1000},
            "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
            "gpt-3.5-turbo": {"input": 0.0015 / 1000, "output": 0.002 / 1000}
        }
        
        model_key = "gpt-4o"  # Default
        if "gpt-3.5" in self.model:
            model_key = "gpt-3.5-turbo"
        elif "gpt-4" in self.model and "gpt-4o" not in self.model:
            model_key = "gpt-4"
        
        rates = pricing.get(model_key, pricing["gpt-4o"])
        
        cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
        return round(cost, 6)
    
    def track_api_call(self, messages: List[Dict], response_text: str, 
                      execution_time: float = None) -> Dict[str, Any]:
        """
        Track an API call and return debug information
        
        Args:
            messages: OpenAI messages format
            response_text: Response from API
            execution_time: Time taken for API call
            
        Returns:
            Debug information dictionary
        """
        input_tokens = self.count_messages_tokens(messages)
        output_tokens = self.count_tokens(response_text)
        cost = self.estimate_cost(input_tokens, output_tokens)
        
        # Update totals
        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        
        debug_info = {
            "call_number": self.total_calls,
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": cost,
            "execution_time_seconds": execution_time,
            "cumulative_cost": round(self.total_cost, 6),
            "cumulative_tokens": self.total_input_tokens + self.total_output_tokens
        }
        
        logger.debug(f"OpenAI API Call #{self.total_calls}: "
                    f"{input_tokens}→{output_tokens} tokens, "
                    f"${cost:.6f}, {execution_time:.2f}s" if execution_time else f"${cost:.6f}")
        
        return debug_info
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get cumulative statistics for current session"""
        return {
            "total_api_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_total_cost": round(self.total_cost, 6),
            "average_tokens_per_call": round((self.total_input_tokens + self.total_output_tokens) / max(1, self.total_calls), 1),
            "model": self.model
        }
    
    def reset_stats(self):
        """Reset all statistics"""
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0


# Global instance
token_calculator = TokenCalculator()


def track_openai_call(func):
    """
    Decorator to automatically track OpenAI API calls
    Usage: @track_openai_call above any function that calls OpenAI
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Try to extract debug info if possible
            # This is basic - can be enhanced based on your specific function patterns
            if hasattr(result, 'choices') and result.choices:
                response_text = result.choices[0].message.content
                # Would need messages from function context - this is a simplified version
                logger.debug(f"OpenAI call completed in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"OpenAI call failed after {execution_time:.2f}s: {e}")
            raise
    
    return wrapper


def log_token_usage(messages: List[Dict], response_text: str, 
                   execution_time: float = None, context: str = ""):
    """
    Simple function to log token usage for any OpenAI call
    
    Args:
        messages: OpenAI messages format
        response_text: Response text from API
        execution_time: Time taken for API call
        context: Context string for debugging (e.g., "query_parser", "content_agent")
    """
    debug_info = token_calculator.track_api_call(messages, response_text, execution_time)
    
    if context:
        logger.info(f"[{context}] Token usage: "
                   f"in={debug_info['input_tokens']}, "
                   f"out={debug_info['output_tokens']}, "
                   f"cost=${debug_info['estimated_cost']:.6f}")
    
    return debug_info