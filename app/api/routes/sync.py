"""
Webhook endpoints for Node.js server to sync embeddings
Called after sitemap CRUD operations
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from loguru import logger

from ...services.vector_service import vector_service
from ...utilities.embeddings import embedding_generator
from ...middleware.jwt import get_current_user, JWTAccount
from ...config.setting import settings
from ...models.sitemapsSync import SitemapSyncRequest

router = APIRouter()

@router.post("/sitemap/embed", response_model=dict)
def sync_sitemap_embedding(
    data: SitemapSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    Sync embedding after sitemap create/update
    Runs in background to avoid blocking Node.js
    
    Call this from Node.js after sitemap insert/update:
    POST /api/v1/sync/sitemap/embed
    """
    try:
        # Verify tenant access
        if current_user.tenant_id != data.tenant_id:
            raise HTTPException(403, "Tenant access denied")
        
        if not settings.VECTOR_SEARCH_ENABLED:
            return {
                "success": True,
                "message": "Vector search disabled, skipping embedding"
            }
        
        # Combine text fields
        text = embedding_generator.combine_fields(
            name=data.name,
            description=data.description,
            summary=data.summary,
            readerBenefit=data.readerBenefit,
            explanation=data.explanation
        )
        
        if not text.strip():
            logger.warning(f"Empty text for sitemap {data.sitemap_id}")
            return {
                "success": False,
                "message": "No text content to embed"
            }
        
        # Generate and store embedding synchronously (fast enough)
        embedding = embedding_generator.generate_embedding(text)
        success = vector_service.store_embedding(
            sitemap_id=data.sitemap_id,
            tenant_id=data.tenant_id,
            embedding=embedding
        )
        
        if success:
            logger.info(f"✅ Synced embedding for {data.sitemap_id}")
            return {
                "success": True,
                "sitemap_id": data.sitemap_id,
                "tenant_id": data.tenant_id,
                "embedding_dimensions": len(embedding)
            }
        else:
            raise HTTPException(500, "Failed to store embedding")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding sync error: {e}")
        raise HTTPException(500, f"Sync failed: {str(e)}")


@router.delete("/sitemap/{sitemap_id}/embed")
def delete_sitemap_embedding(
    sitemap_id: str,
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    Delete embedding when sitemap is removed
    
    Call from Node.js after sitemap deletion:
    DELETE /api/v1/sync/sitemap/{sitemap_id}/embed
    """
    try:
        if not settings.VECTOR_SEARCH_ENABLED:
            return {"success": True, "message": "Vector search disabled"}
        
        success = vector_service.delete_embedding(
            sitemap_id=sitemap_id,
            tenant_id=current_user.tenant_id
        )
        
        if success:
            return {
                "success": True,
                "message": f"Embedding deleted for {sitemap_id}"
            }
        else:
            return {
                "success": False,
                "message": "Embedding not found or already deleted"
            }
        
    except Exception as e:
        logger.error(f"Embedding deletion error: {e}")
        raise HTTPException(500, str(e))


@router.get("/tenant/embeddings/stats")
def get_tenant_embedding_stats(
    current_user: JWTAccount = Depends(get_current_user)
):
    """Get embedding statistics for current tenant"""
    try:
        stats = vector_service.get_tenant_stats(current_user.tenant_id)
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Stats retrieval error: {e}")
        raise HTTPException(500, str(e))


@router.post("/tenant/embeddings/backfill")
def backfill_tenant_embeddings(
    background_tasks: BackgroundTasks,
    current_user: JWTAccount = Depends(get_current_user)
):
    """
    Backfill embeddings for all existing sitemaps
    Admin endpoint - runs in background
    """
    try:
        from ...config.database import db_connection
        from bson import ObjectId
        
        def backfill_task(tenant_id: str):
            """Background task for backfilling"""
            db = db_connection.get_database()
            tenant_obj_id = ObjectId(tenant_id)
            
            sitemaps = db.sitemaps.find({"tenant": tenant_obj_id})
            count = 0
            errors = 0
            
            for sitemap in sitemaps:
                try:
                    text = embedding_generator.combine_fields(
                        name=sitemap.get("name"),
                        description=sitemap.get("description"),
                        summary=sitemap.get("summary"),
                        reader_benefit=sitemap.get("readerBenefit"),
                        explanation=sitemap.get("explanation")
                    )
                    
                    if text.strip():
                        embedding = embedding_generator.generate_embedding(text)
                        vector_service.store_embedding(
                            sitemap_id=str(sitemap["_id"]),
                            tenant_id=tenant_id,
                            embedding=embedding
                        )
                        count += 1
                        
                        if count % 100 == 0:
                            logger.info(f"Backfilled {count} embeddings for tenant {tenant_id}")
                            
                except Exception as e:
                    logger.error(f"Backfill error for {sitemap['_id']}: {e}")
                    errors += 1
            
            logger.info(f"✅ Backfill complete: {count} success, {errors} errors")
        
        # Run in background
        background_tasks.add_task(backfill_task, current_user.tenant_id)
        
        return {
            "success": True,
            "message": "Backfill started in background"
        }
        
    except Exception as e:
        logger.error(f"Backfill initialization error: {e}")
        raise HTTPException(500, str(e))