# scripts/init_vector_db.py
"""
Initialize pgvector database and tables
Run this once before starting the application
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config.setting import settings

def init_database():
    """Initialize database and pgvector extension"""
    
    print("🔧 Initializing Vector Database...")
    
    # Connect to PostgreSQL server (not specific database)
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database='postgres'  # Default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Create database if it doesn't exist
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{settings.POSTGRES_DB}'")
        if not cur.fetchone():
            print(f"📦 Creating database: {settings.POSTGRES_DB}")
            cur.execute(f"CREATE DATABASE {settings.POSTGRES_DB}")
        else:
            print(f"✅ Database {settings.POSTGRES_DB} already exists")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Failed to create database: {e}")
        sys.exit(1)
    
    # Connect to the specific database
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD
        )
        cur = conn.cursor()
        
        # Enable pgvector extension
        print("🔌 Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        
        # Create embeddings table
        print("📋 Creating sitemap_embeddings table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sitemap_embeddings (
                sitemap_id VARCHAR(24) PRIMARY KEY,
                tenant_id VARCHAR(24) NOT NULL,
                embedding VECTOR(1536),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        
        # Create indexes
        print("🔍 Creating indexes...")
        
        # Tenant index
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_id 
            ON sitemap_embeddings(tenant_id)
        """)
        
        # Vector similarity index (IVFFlat)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_embedding 
            ON sitemap_embeddings 
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        
        conn.commit()
        
        # Verify setup
        cur.execute("SELECT COUNT(*) FROM sitemap_embeddings")
        count = cur.fetchone()[0]
        
        print(f"\n✅ Vector database initialized successfully!")
        print(f"📊 Current embeddings: {count}")
        print(f"🚀 Ready to start the application")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()