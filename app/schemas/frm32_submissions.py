"""
FRM32 Submission schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FRM32SubmissionBase(BaseModel):
    """Base FRM32 submission schema"""
    tenant_id: str
    contractor_id: str
    evaluation_period: str  # e.g., "2025-Q3" or "2025-09"
    evaluation_type: str = "periodic"  # periodic, incident, audit
    status: str = "draft"  # draft, submitted, in_review, completed, rejected
    progress_percentage: int = 0
    answers: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FRM32SubmissionCreate(FRM32SubmissionBase):
    """Schema for creating an FRM32 submission"""
    pass


class FRM32SubmissionUpdate(BaseModel):
    """Schema for updating an FRM32 submission"""
    tenant_id: Optional[str] = None
    contractor_id: Optional[str] = None
    evaluation_period: Optional[str] = None
    evaluation_type: Optional[str] = None
    status: Optional[str] = None
    progress_percentage: Optional[int] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    final_score: Optional[float] = None
    risk_classification: Optional[str] = None
    ai_summary: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[str] = None


class FRM32Submission(FRM32SubmissionBase):
    """Schema for FRM32 submission response"""
    id: str
    answers: Dict[str, Any] = Field(default_factory=dict)
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    final_score: Optional[float] = None
    risk_classification: Optional[str] = None  # green, yellow, red
    ai_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    reviewed_by: Optional[str] = None

    model_config = {"from_attributes": True}
