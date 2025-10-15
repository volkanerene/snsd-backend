"""
K2 Evaluation schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class K2EvaluationBase(BaseModel):
    """Base K2 evaluation schema"""
    submission_id: str
    contractor_id: str
    tenant_id: str
    evaluation_period: str
    k2_category: str
    category_score: float
    weighted_score: float
    risk_level: Optional[str] = None
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class K2EvaluationCreate(K2EvaluationBase):
    """Schema for creating a K2 evaluation"""
    pass


class K2EvaluationUpdate(BaseModel):
    """Schema for updating a K2 evaluation"""
    k2_category: Optional[str] = None
    category_score: Optional[float] = None
    weighted_score: Optional[float] = None
    risk_level: Optional[str] = None
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class K2Evaluation(K2EvaluationBase):
    """Schema for K2 evaluation response"""
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = {"from_attributes": True}
