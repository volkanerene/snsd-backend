"""
EvrenGPT Evaluation Process Schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal


# ================================================
# Session Schemas
# ================================================

class EvrenGPTSessionBase(BaseModel):
    tenant_id: str
    custom_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EvrenGPTSessionCreate(EvrenGPTSessionBase):
    contractor_ids: List[str] = Field(..., min_items=1, description="List of contractor IDs to include in this session")


class EvrenGPTSessionUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|completed|cancelled)$")
    custom_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EvrenGPTSessionResponse(EvrenGPTSessionBase):
    id: str
    session_id: str
    created_by: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    updated_at: datetime

    # Additional computed fields
    total_contractors: Optional[int] = None
    completed_contractors: Optional[int] = None
    average_score: Optional[Decimal] = None

    class Config:
        orm_mode = True


class StartProcessResponse(BaseModel):
    session_id: str
    contractors_notified: int
    message: str


# ================================================
# Session Contractor Schemas
# ================================================

class SessionContractorBase(BaseModel):
    session_id: str
    contractor_id: str
    cycle: int = Field(default=1, ge=1)


class SessionContractorCreate(SessionContractorBase):
    pass


class SessionContractorUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|frm32_sent|frm32_completed|frm33_completed|frm34_completed|frm35_completed|completed)$")
    final_score: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionContractorResponse(SessionContractorBase):
    id: str
    status: str
    frm32_sent_at: Optional[datetime] = None
    frm32_completed_at: Optional[datetime] = None
    frm33_completed_at: Optional[datetime] = None
    frm34_completed_at: Optional[datetime] = None
    frm35_completed_at: Optional[datetime] = None
    final_score: Optional[Decimal] = None
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    # Joined data
    contractor_name: Optional[str] = None
    contractor_email: Optional[str] = None

    class Config:
        orm_mode = True


# ================================================
# Form Submission Schemas
# ================================================

class FormSubmissionBase(BaseModel):
    session_id: str
    contractor_id: str
    form_id: str = Field(..., pattern="^(frm32|frm33|frm34|frm35)$")
    cycle: int = Field(default=1, ge=1)
    answers: Dict[str, Any] = Field(default_factory=dict)


class FormSubmissionCreate(FormSubmissionBase):
    """Used when contractor/supervisor submits a form"""
    submitted_by: Optional[str] = None  # Will be set from auth token

    @validator('answers')
    def validate_answers(cls, v):
        if not v:
            raise ValueError('Answers cannot be empty')
        return v


class FormSubmissionUpdate(BaseModel):
    answers: Optional[Dict[str, Any]] = None
    raw_score: Optional[Decimal] = None
    final_score: Optional[Decimal] = None
    status: Optional[str] = Field(None, pattern="^(pending|submitted|scored|completed)$")
    n8n_processed_at: Optional[datetime] = None
    n8n_webhook_response: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class FormSubmissionResponse(FormSubmissionBase):
    id: str
    raw_score: Optional[Decimal] = None
    final_score: Optional[Decimal] = None
    status: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    n8n_processed_at: Optional[datetime] = None
    n8n_webhook_response: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    # Joined data
    contractor_name: Optional[str] = None
    submitted_by_name: Optional[str] = None
    question_scores: Optional[List['QuestionScoreResponse']] = None

    class Config:
        orm_mode = True


# ================================================
# Question Score Schemas
# ================================================

class QuestionScoreBase(BaseModel):
    submission_id: str
    question_id: str
    question_text: Optional[str] = None
    answer_text: Optional[str] = None
    ai_score: int = Field(..., ge=0, le=10)
    ai_reasoning: Optional[str] = None
    weight: Decimal = Field(default=Decimal('1.0'), ge=0, le=1)


class QuestionScoreCreate(QuestionScoreBase):
    pass


class QuestionScoreResponse(QuestionScoreBase):
    id: str
    created_at: datetime

    class Config:
        orm_mode = True


# ================================================
# Notification Schemas
# ================================================

class NotificationBase(BaseModel):
    session_id: str
    contractor_id: Optional[str] = None
    recipient_email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    recipient_name: Optional[str] = None
    notification_type: str = Field(..., pattern="^(frm32_invite|frm33_invite|frm34_invite|frm35_invite|process_complete|reminder)$")
    form_id: Optional[str] = Field(None, pattern="^(frm32|frm33|frm34|frm35)$")
    subject: str
    body: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|sent|failed|bounced)$")
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None


class NotificationResponse(NotificationBase):
    id: str
    status: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime

    # Joined data
    contractor_name: Optional[str] = None

    class Config:
        orm_mode = True


# ================================================
# n8n Webhook Schemas
# ================================================

class N8NWebhookPayload(BaseModel):
    """Payload received from n8n after AI processing"""
    submission_id: str
    session_id: str
    contractor_id: str
    form_id: str
    cycle: int
    question_scores: List[Dict[str, Any]]
    raw_score: Decimal
    final_score: Decimal
    ai_summary: Optional[str] = None
    processed_at: datetime
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class N8NWebhookResponse(BaseModel):
    success: bool
    message: str
    submission_id: str
    final_score: Optional[Decimal] = None


# ================================================
# Statistics and Dashboard Schemas
# ================================================

class SessionStatistics(BaseModel):
    session_id: str
    tenant_id: str
    total_contractors: int
    pending_contractors: int
    in_progress_contractors: int
    completed_contractors: int
    average_final_score: Optional[Decimal] = None
    frm32_completion_rate: float
    frm33_completion_rate: float
    frm34_completion_rate: float
    frm35_completion_rate: float
    created_at: datetime
    last_updated: datetime


class ContractorFormProgress(BaseModel):
    contractor_id: str
    contractor_name: str
    session_id: str
    cycle: int
    frm32_status: Optional[str] = None
    frm33_status: Optional[str] = None
    frm34_status: Optional[str] = None
    frm35_status: Optional[str] = None
    frm32_score: Optional[Decimal] = None
    frm33_score: Optional[Decimal] = None
    frm34_score: Optional[Decimal] = None
    frm35_score: Optional[Decimal] = None
    final_score: Optional[Decimal] = None
    overall_status: str


class FormCompletionStats(BaseModel):
    form_id: str
    total_submissions: int
    completed_submissions: int
    pending_submissions: int
    average_score: Optional[Decimal] = None
    min_score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None


class TenantEvrenGPTStats(BaseModel):
    tenant_id: str
    total_sessions: int
    active_sessions: int
    completed_sessions: int
    total_contractors_evaluated: int
    total_forms_submitted: int
    average_completion_time_days: Optional[float] = None
    form_stats: List[FormCompletionStats]


# ================================================
# Bulk Operations
# ================================================

class BulkFormSubmission(BaseModel):
    submissions: List[FormSubmissionCreate] = Field(..., min_items=1, max_items=100)


class BulkSubmissionResponse(BaseModel):
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    submission_ids: List[str] = Field(default_factory=list)


# Update forward references
FormSubmissionResponse.update_forward_refs()
