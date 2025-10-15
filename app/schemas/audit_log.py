"""
Audit Log schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AuditLogBase(BaseModel):
    """Base audit log schema"""
    tenant_id: str
    user_id: Optional[str] = None
    action: str  # create, update, delete, login, logout, etc.
    resource_type: str  # tenant, contractor, submission, etc.
    resource_id: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditLogCreate(AuditLogBase):
    """Schema for creating an audit log entry"""
    pass


class AuditLog(AuditLogBase):
    """Schema for audit log response"""
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}
