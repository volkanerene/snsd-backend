"""
Role schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    """Base role schema"""
    name: str
    slug: str
    description: Optional[str] = None
    level: int = 10
    permissions: List[str] = Field(default_factory=list)


class RoleCreate(RoleBase):
    """Schema for creating a role"""
    pass


class RoleUpdate(BaseModel):
    """Schema for updating a role"""
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    level: Optional[int] = None
    permissions: Optional[List[str]] = None


class Role(RoleBase):
    """Schema for role response"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
