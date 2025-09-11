# app/models/tenant.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class TenantCategories(BaseModel):
    """Tenant's available categories and values"""
    funnel_stage: List[str] = Field(default_factory=list, alias="Funnel Stage")
    industry: List[str] = Field(default_factory=list, alias="Industry") 
    page_type: List[str] = Field(default_factory=list, alias="Page Type")
    primary_audience: List[str] = Field(default_factory=list, alias="Primary Audience")
    secondary_audience: List[str] = Field(default_factory=list, alias="Secondary Audience")
    language: List[str] = Field(default_factory=list, alias="Language")
    content_type: List[str] = Field(default_factory=list, alias="Content Type")
    topics: List[str] = Field(default_factory=list, alias="Topics")
    custom_tags: List[str] = Field(default_factory=list, alias="Custom Tags")
    
    class Config:
        populate_by_name = True

class FieldMapping(BaseModel):
    """Field mapping configuration"""
    collection: str
    field: str
    requires_join: bool = False
    reference_collection: Optional[str] = None
    join_on: Optional[str] = None
    display_field: Optional[str] = None
    is_array: bool = False
    filter_by_category: bool = False
    field_type: str = "string"

class TenantSchema(BaseModel):
    """Complete tenant schema information"""
    tenant_id: str
    categories: Dict[str, List[str]] = Field(..., description="All available categories and values")
    field_mappings: Dict[str, FieldMapping] = Field(..., description="Database field mappings")
    collection_schemas: Dict[str, List[str]] = Field(..., description="Collection field schemas")
    document_counts: Dict[str, int] = Field(default_factory=dict, description="Document counts per collection")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Schema summary statistics")