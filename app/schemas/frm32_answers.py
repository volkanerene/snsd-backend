"""
FRM32 Answer schemas
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class FRM32AnswerBase(BaseModel):
    """Base FRM32 answer schema"""
    submission_id: str
    question_id: str
    answer_value: Optional[Any] = None  # Can be string, number, list, etc.
    score: Optional[float] = None
    attachments: Optional[list] = None
    notes: Optional[str] = None


class FRM32AnswerCreate(FRM32AnswerBase):
    """Schema for creating an FRM32 answer"""
    pass


class FRM32AnswerUpdate(BaseModel):
    """Schema for updating an FRM32 answer"""
    answer_value: Optional[Any] = None
    score: Optional[float] = None
    attachments: Optional[list] = None
    notes: Optional[str] = None


class FRM32Answer(FRM32AnswerBase):
    """Schema for FRM32 answer response"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
