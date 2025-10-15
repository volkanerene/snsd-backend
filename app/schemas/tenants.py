"""
Tenant schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4


class TenantBase(BaseModel):
    """Base tenant schema"""
    name: str
    slug: str
    logo_url: Optional[str] = None
    subdomain: str
    license_plan: str = "basic"
    modules_enabled: List[str] = Field(default_factory=list)
    max_users: int = 10
    max_contractors: int = 20
    max_video_requests_monthly: int = 10
    settings: Dict[str, Any] = Field(default_factory=dict)
    contact_email: str
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    status: str = "active"
    trial_ends_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None


class TenantCreate(TenantBase):
    """Schema for creating a tenant"""
    pass


class TenantUpdate(BaseModel):
    """Schema for updating a tenant"""
    name: Optional[str] = None
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    subdomain: Optional[str] = None
    license_plan: Optional[str] = None
    modules_enabled: Optional[List[str]] = None
    max_users: Optional[int] = None
    max_contractors: Optional[int] = None
    max_video_requests_monthly: Optional[int] = None
    settings: Optional[Dict[str, Any]] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None


class Tenant(TenantBase):
    """Schema for tenant response"""
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = {"from_attributes": True}
