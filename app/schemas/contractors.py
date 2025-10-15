"""
Contractor schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ContractorBase(BaseModel):
    """Base contractor schema"""
    tenant_id: str
    name: str
    legal_name: str
    tax_number: str
    trade_registry_number: Optional[str] = None
    contact_person: str
    contact_email: str
    contact_phone: str
    address: Optional[str] = None
    city: str
    country: str = "TR"
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "active"
    risk_level: Optional[str] = None
    last_evaluation_score: Optional[float] = None
    last_evaluation_date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContractorCreate(ContractorBase):
    """Schema for creating a contractor"""
    pass


class ContractorUpdate(BaseModel):
    """Schema for updating a contractor"""
    tenant_id: Optional[str] = None
    name: Optional[str] = None
    legal_name: Optional[str] = None
    tax_number: Optional[str] = None
    trade_registry_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    last_evaluation_score: Optional[float] = None
    last_evaluation_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class Contractor(ContractorBase):
    """Schema for contractor response"""
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = {"from_attributes": True}
