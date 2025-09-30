# app/utilities/embeddings.py
"""
Embedding generation utilities using OpenAI
Synchronous implementation to match codebase pattern
"""

from typing import List, Optional
from openai import OpenAI
from loguru import logger

from ..config.setting import settings

class EmbeddingGenerator:
    """Generate embeddings for text using OpenAI"""
    
    def __init__(self, model: str = None):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model or settings.EMBEDDING_MODEL
        self.max_tokens = 8000  # OpenAI token limit
    
    def combine_fields(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[str] = None,
        readerBenefit: Optional[str] = None,
        explanation: Optional[str] = None
    ) -> str:
        """
        Combine multiple text fields with weighted importance
        Priority: name > description > summary > reader_benefit > explanation
        """
        parts = []
        
        # Title is most important - include multiple times for weight
        if name:
            parts.append(f"{name}")
            parts.append(f"Title: {name}")
        
        # Core content
        if description:
            parts.append(f"Description: {description}")
        
        if summary:
            parts.append(f"Summary: {summary}")
        
        # Supporting information
        if readerBenefit:
            parts.append(f"Reader Benefit: {readerBenefit}")
        
        if explanation:
            parts.append(f"Context: {explanation}")
        
        combined = " | ".join(parts)
        
        # Truncate if too long (rough estimate: 1 token ≈ 4 chars)
        max_chars = self.max_tokens * 4
        if len(combined) > max_chars:
            combined = combined[:max_chars]
            logger.warning(f"Text truncated from {len(combined)} to {max_chars} chars")
        
        return combined
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text
        
        Args:
            text: Input text (will be truncated if too long)
        
        Returns:
            List of floats representing the embedding vector
        
        Raises:
            Exception: If OpenAI API call fails
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * settings.EMBEDDING_DIMENSIONS
        
        try:
            # Truncate text if needed
            if len(text) > self.max_tokens * 4:
                text = text[:self.max_tokens * 4]
            
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            logger.debug(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    def generate_embedding_for_sitemap(self, sitemap_data: dict) -> List[float]:
        """
        Generate embedding from sitemap document
        
        Args:
            sitemap_data: Sitemap document from MongoDB
        
        Returns:
            Embedding vector
        """
        text = self.combine_fields(
            name=sitemap_data.get("name"),
            description=sitemap_data.get("description"),
            summary=sitemap_data.get("summary"),
            reader_benefit=sitemap_data.get("readerBenefit"),
            explanation=sitemap_data.get("explanation")
        )
        
        return self.generate_embedding(text)


# Global instance
embedding_generator = EmbeddingGenerator()

# Convenience functions
def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text"""
    return embedding_generator.generate_embedding(text)

def combine_fields(**kwargs) -> str:
    """Combine text fields"""
    return embedding_generator.combine_fields(**kwargs)