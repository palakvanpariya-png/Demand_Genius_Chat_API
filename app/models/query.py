# app/models/query.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class FilterDict(BaseModel):
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)

class DateFilter(BaseModel):
    start_date: Optional[str] = Field(None, description="ISO date string")
    end_date: Optional[str] = Field(None, description="ISO date string")

class Pagination(BaseModel):
    skip: int = Field(0, ge=-2, description="Number of items to skip (-1 for last N, -2 for count only)")
    limit: int = Field(200, ge=0, le=600, description="Number of items to return")

class QueryResult(BaseModel):
    route: str = Field(..., description="database or advisory")
    operation: str = Field(..., description="list, distribution, semantic, pure_advisory")
    confidence: str = Field(default="medium", description="high, medium, or low - indicates query clarity")
    filters: Dict[str, FilterDict] = Field(default_factory=dict)
    date_filter: Optional[DateFilter] = None
    marketing_filter: Optional[bool] = None
    is_negation: bool = False
    semantic_terms: Optional[List[str]] = None
    tenant_id: str
    needs_data: bool
    distribution_fields: List[str] = Field(default_factory=list)
    pagination: Pagination = Field(default_factory=Pagination)
    description: Optional[str] = None
    original_query: Optional[str] = None