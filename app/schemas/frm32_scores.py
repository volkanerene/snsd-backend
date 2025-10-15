"""
FRM32 Score schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FRM32ScoreBase(BaseModel):
    """Base FRM32 score schema"""
    submission_id: str
    k2_category: str
    category_score: float
    category_weight: float
    weighted_score: float
    max_possible_score: float


class FRM32ScoreCreate(FRM32ScoreBase):
    """Schema for creating an FRM32 score"""
    pass


class FRM32ScoreUpdate(BaseModel):
    """Schema for updating an FRM32 score"""
    category_score: Optional[float] = None
    category_weight: Optional[float] = None
    weighted_score: Optional[float] = None
    max_possible_score: Optional[float] = None


class FRM32Score(FRM32ScoreBase):
    """Schema for FRM32 score response"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
