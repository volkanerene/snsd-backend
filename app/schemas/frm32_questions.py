"""
FRM32 Question schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FRM32QuestionBase(BaseModel):
    """Base FRM32 question schema"""
    question_code: str
    question_text_tr: str
    question_text_en: Optional[str] = None
    k2_category: str
    k2_weight: float = 1.0
    question_type: str  # yes_no, number, multiple_choice, text, file_upload
    options: Optional[List[str]] = None
    scoring_rules: Dict[str, Any] = Field(default_factory=dict)
    max_score: float = 100.0
    is_required: bool = True
    is_active: bool = True
    position: int = 0


class FRM32QuestionCreate(FRM32QuestionBase):
    """Schema for creating an FRM32 question"""
    pass


class FRM32QuestionUpdate(BaseModel):
    """Schema for updating an FRM32 question"""
    question_code: Optional[str] = None
    question_text_tr: Optional[str] = None
    question_text_en: Optional[str] = None
    k2_category: Optional[str] = None
    k2_weight: Optional[float] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    scoring_rules: Optional[Dict[str, Any]] = None
    max_score: Optional[float] = None
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None
    position: Optional[int] = None


class FRM32Question(FRM32QuestionBase):
    """Schema for FRM32 question response"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
