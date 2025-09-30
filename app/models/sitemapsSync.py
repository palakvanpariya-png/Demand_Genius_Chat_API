from pydantic import BaseModel, Field
from typing import  Optional



class SitemapSyncRequest(BaseModel):
    """Request model for syncing sitemap embedding"""
    sitemap_id: str = Field(..., description="MongoDB _id as string")
    tenant_id: str = Field(..., description="Tenant ID")
    name: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    readerBenefit: Optional[str] = None
    explanation: Optional[str] = None
