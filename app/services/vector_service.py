# app/services/vector_service.py
"""
Vector search service using PostgreSQL + pgvector
Synchronous implementation matching codebase pattern
"""

from typing import List, Optional, Dict, Any
import json
from loguru import logger

from ..config.database import vector_db_connection
from ..config.setting import settings
from ..utilities.embeddings import embedding_generator


class VectorService:
    """Manages vector embeddings for semantic search"""
    
    def __init__(self):
        self.similarity_threshold = settings.VECTOR_SIMILARITY_THRESHOLD
        self.embedding_dimensions = settings.EMBEDDING_DIMENSIONS
    
    def _ensure_table_exists(self):
        """Create embeddings table if it doesn't exist"""
        conn = vector_db_connection.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sitemap_embeddings (
                        sitemap_id VARCHAR(24) PRIMARY KEY,
                        tenant_id VARCHAR(24) NOT NULL,
                        embedding VECTOR(1536),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Create indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tenant_id 
                    ON sitemap_embeddings(tenant_id)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tenant_embedding 
                    ON sitemap_embeddings 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                
                conn.commit()
                logger.info("Ensured sitemap_embeddings table exists")
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create table: {e}")
            raise
        finally:
            vector_db_connection.return_connection(conn)
    
    def search_similar(
        self,
        query_text: str,
        tenant_id: str,
        limit: int = 50,
        threshold: Optional[float] = None
    ) -> List[str]:
        """
        Search for similar documents using vector similarity
        
        Args:
            query_text: User's search query
            tenant_id: Tenant ID for isolation
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)
        
        Returns:
            List of sitemap_ids ordered by similarity
        """
        if not settings.VECTOR_SEARCH_ENABLED:
            logger.warning("Vector search is disabled")
            return []
        
        threshold = threshold or self.similarity_threshold
        
        try:
            # Generate query embedding
            query_embedding = embedding_generator.generate_embedding(query_text)
            
            conn = vector_db_connection.get_connection()
            try:
                with conn.cursor() as cur:
                    # Convert embedding to PostgreSQL array format
                    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
                    
                    cur.execute("""
                        SELECT 
                            sitemap_id,
                            1 - (embedding <=> %s::vector) as similarity
                        FROM sitemap_embeddings
                        WHERE tenant_id = %s
                          AND 1 - (embedding <=> %s::vector) > %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (embedding_str, tenant_id, embedding_str, threshold, embedding_str, limit))
                    
                    results = cur.fetchall()
                    
                sitemap_ids = [row[0] for row in results]
                
                logger.info(
                    f"Vector search for tenant {tenant_id}: "
                    f"{len(sitemap_ids)} results (threshold: {threshold})"
                )
                
                return sitemap_ids
                
            finally:
                vector_db_connection.return_connection(conn)
                
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def store_embedding(
        self,
        sitemap_id: str,
        tenant_id: str,
        embedding: List[float]
    ) -> bool:
        """
        Store or update embedding for a sitemap
        
        Args:
            sitemap_id: MongoDB ObjectId as string
            tenant_id: Tenant ID
            embedding: Embedding vector
        
        Returns:
            True if successful
        """
        try:
            conn = vector_db_connection.get_connection()
            try:
                with conn.cursor() as cur:
                    # Convert embedding to PostgreSQL array format
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    
                    cur.execute("""
                        INSERT INTO sitemap_embeddings 
                            (sitemap_id, tenant_id, embedding, created_at, updated_at)
                        VALUES (%s, %s, %s::vector, NOW(), NOW())
                        ON CONFLICT (sitemap_id) 
                        DO UPDATE SET 
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                    """, (sitemap_id, tenant_id, embedding_str))
                    
                    conn.commit()
                
                logger.debug(f"Stored embedding for {sitemap_id} (tenant: {tenant_id})")
                return True
                
            finally:
                vector_db_connection.return_connection(conn)
                
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            return False
    
    def delete_embedding(self, sitemap_id: str, tenant_id: str) -> bool:
        """
        Delete embedding for a sitemap
        
        Args:
            sitemap_id: Sitemap ID
            tenant_id: Tenant ID (for verification)
        
        Returns:
            True if deleted
        """
        try:
            conn = vector_db_connection.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM sitemap_embeddings
                        WHERE sitemap_id = %s AND tenant_id = %s
                    """, (sitemap_id, tenant_id))
                    
                    deleted = cur.rowcount > 0
                    conn.commit()
                
                if deleted:
                    logger.info(f"Deleted embedding {sitemap_id} (tenant: {tenant_id})")
                
                return deleted
                
            finally:
                vector_db_connection.return_connection(conn)
                
        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}")
            return False
    
    def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get embedding statistics for a tenant"""
        try:
            conn = vector_db_connection.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_embeddings,
                            MAX(updated_at) as last_updated
                        FROM sitemap_embeddings
                        WHERE tenant_id = %s
                    """, (tenant_id,))
                    
                    row = cur.fetchone()
                
                return {
                    "tenant_id": tenant_id,
                    "total_embeddings": row[0] if row else 0,
                    "last_updated": row[1].isoformat() if row and row[1] else None
                }
                
            finally:
                vector_db_connection.return_connection(conn)
                
        except Exception as e:
            logger.error(f"Failed to get tenant stats: {e}")
            return {
                "tenant_id": tenant_id,
                "total_embeddings": 0,
                "error": str(e)
            }
    
    def health_check(self) -> bool:
        """Check if vector service is operational"""
        try:
            conn = vector_db_connection.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                vector_db_connection.return_connection(conn)
        except Exception:
            return False


# Global instance
vector_service = VectorService()