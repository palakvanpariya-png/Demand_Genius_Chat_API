# app/models/content.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class ContentItem(BaseModel):
    """Represents a content item from sitemaps collection"""
    id: str = Field(..., alias="_id", description="Content ID")
    name: str = Field(..., description="Content title/name")
    full_url: str = Field(..., alias="fullUrl", description="Complete URL")
    path: str = Field(..., description="URL path")
    domain: str = Field(..., description="Domain name")
    hide_form: bool = Field(False, alias="hideForm")
    
    # Reference fields (converted from ObjectIds)
    content_type: Optional[str] = Field(None, alias="contentType")
    topic: Optional[str] = Field(None, alias="topic") 
    tags: List[str] = Field(default_factory=list, alias="tag")
    category_attributes: List[str] = Field(default_factory=list, alias="categoryAttribute")
    tenant_id: str = Field(..., alias="tenant")
    
    # Content metadata
    is_marketing_content: bool = Field(False, alias="isMarketingContent")
    word_count: Optional[int] = Field(None, alias="wordCount")
    geo_focus: Optional[str] = Field(None, alias="geoFocus")
    description: Optional[str] = None
    summary: Optional[str] = None
    reader_benefit: Optional[str] = Field(None, alias="readerBenefit")
    confidence: Optional[str] = None
    explanation: Optional[str] = None
    
    # Dates
    date_published: Optional[str] = Field(None, alias="datePublished")
    date_modified: Optional[str] = Field(None, alias="dateModified")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    
    # Version and embedding (optional)
    version: Optional[int] = Field(None, alias="__v")
    embedding: Optional[List[float]] = None
    
    class Config:
        populate_by_name = True
        
    @classmethod
    def from_mongo(cls, data: dict):
        """Convert MongoDB document to Pydantic model"""
        converted = data.copy()
        
        # Convert ObjectId fields to strings
        if "_id" in converted:
            converted["_id"] = str(converted["_id"])
        if "tenant" in converted:
            converted["tenant"] = str(converted["tenant"])
        if "contentType" in converted and converted["contentType"]:
            converted["contentType"] = str(converted["contentType"])
        if "topic" in converted and converted["topic"]:
            converted["topic"] = str(converted["topic"])
        
        # Convert array of ObjectIds to strings
        if "tag" in converted and converted["tag"]:
            converted["tag"] = [str(t) for t in converted["tag"]]
        if "categoryAttribute" in converted and converted["categoryAttribute"]:
            converted["categoryAttribute"] = [str(ca) for ca in converted["categoryAttribute"]]
            
        return cls(**converted)

class ContentSummary(BaseModel):
    """Lightweight content summary for API responses"""
    id: str
    name: str
    content_type: Optional[str] = None
    topic: Optional[str] = None
    geo_focus: Optional[str] = None
    word_count: Optional[int] = None
    is_marketing_content: bool = False
    created_at: Optional[str] = None

class DistributionItem(BaseModel):
    """Single item in distribution results"""
    value: str = Field(..., description="Category value")
    count: int = Field(..., description="Number of items with this value")

class DistributionResult(BaseModel):
    """Distribution analysis results"""
    field: str = Field(..., description="Category field name")
    distribution: List[DistributionItem]
    total_items: int = Field(..., description="Total items in distribution")
    error: Optional[str] = None