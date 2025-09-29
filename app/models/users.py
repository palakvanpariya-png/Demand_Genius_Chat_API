# app/models/user.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class User(BaseModel):
    """User model matching your TypeScript schema"""
    id: str
    email: str
    firstName: str
    lastName: str
    tenant: List[str]  # Array of tenant ObjectIds
    isVerified: bool
    isEmailVerified: bool
    isActive: bool = True
    role: Optional[str] = None

class Tenant(BaseModel):
    """Tenant model matching your TypeScript schema"""
    id: str
    name: str
    userId: List[str]  # Array of user ObjectIds
    isActive: bool
    isVerified: bool

class UserTenant(BaseModel):
    """UserTenant junction model"""
    user: str
    tenant: str
    role: str
    isActive: bool
    providerId: Optional[str] = None