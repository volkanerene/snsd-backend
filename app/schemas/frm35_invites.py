"""
FRM35 Invite schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class FRM35InviteBase(BaseModel):
    """Base FRM35 invite schema"""
    tenant_id: str
    contractor_id: str
    invited_email: EmailStr
    invited_name: Optional[str] = None
    invited_phone: Optional[str] = None
    invite_type: str = "safety_video"  # safety_video, document_review, interview
    subject: str
    message: Optional[str] = None
    status: str = "pending"  # pending, sent, opened, completed, expired
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FRM35InviteCreate(FRM35InviteBase):
    """Schema for creating an FRM35 invite"""
    pass


class FRM35InviteUpdate(BaseModel):
    """Schema for updating an FRM35 invite"""
    invited_email: Optional[EmailStr] = None
    invited_name: Optional[str] = None
    invited_phone: Optional[str] = None
    invite_type: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    status: Optional[str] = None
    expires_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class FRM35Invite(FRM35InviteBase):
    """Schema for FRM35 invite response"""
    id: str
    token: Optional[str] = None
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = {"from_attributes": True}
