"""
Profile schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ProfileBase(BaseModel):
    """Base profile schema"""
    tenant_id: str
    full_name: str
    username: str
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    locale: str = "tr"
    timezone: str = "Europe/Istanbul"
    role_id: int
    contractor_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    notification_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {"email": True, "sms": False, "push": True}
    )
    is_active: bool = True


class ProfileCreate(ProfileBase):
    """Schema for creating a profile"""
    pass


class ProfileUpdate(BaseModel):
    """Schema for updating a profile"""
    tenant_id: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    role_id: Optional[int] = None
    contractor_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class Profile(ProfileBase):
    """Schema for profile response"""
    id: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
