"""
Payment schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PaymentBase(BaseModel):
    """Base payment schema"""
    tenant_id: str
    amount: float
    currency: str = "TRY"
    payment_method: str  # credit_card, bank_transfer, paypal, etc.
    provider: Optional[str] = None  # stripe, paytr, iyzico, bank, etc.
    provider_transaction_id: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, completed, failed, refunded
    subscription_period: Optional[str] = None  # monthly, yearly
    subscription_starts_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    invoice_number: Optional[str] = None
    invoice_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PaymentCreate(PaymentBase):
    """Schema for creating a payment"""
    pass


class PaymentUpdate(BaseModel):
    """Schema for updating a payment"""
    amount: Optional[float] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    provider: Optional[str] = None
    provider_transaction_id: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    subscription_period: Optional[str] = None
    subscription_starts_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    invoice_number: Optional[str] = None
    invoice_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Payment(PaymentBase):
    """Schema for payment response"""
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = {"from_attributes": True}
