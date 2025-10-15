"""
Final Score schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class FinalScoreBase(BaseModel):
    """Base final score schema"""
    submission_id: str
    contractor_id: str
    tenant_id: str
    evaluation_period: str
    total_score: float
    risk_classification: str  # green, yellow, red
    grade: Optional[str] = None  # A+, A, B+, B, C, D, F
    percentile: Optional[float] = None
    industry_average: Optional[float] = None
    previous_score: Optional[float] = None
    score_trend: Optional[str] = None  # improving, stable, declining
    summary: Optional[str] = None
    recommendations: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FinalScoreCreate(FinalScoreBase):
    """Schema for creating a final score"""
    pass


class FinalScoreUpdate(BaseModel):
    """Schema for updating a final score"""
    total_score: Optional[float] = None
    risk_classification: Optional[str] = None
    grade: Optional[str] = None
    percentile: Optional[float] = None
    industry_average: Optional[float] = None
    previous_score: Optional[float] = None
    score_trend: Optional[str] = None
    summary: Optional[str] = None
    recommendations: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FinalScore(FinalScoreBase):
    """Schema for final score response"""
    id: str
    created_at: datetime
    updated_at: datetime
    calculated_by: Optional[str] = None

    model_config = {"from_attributes": True}
