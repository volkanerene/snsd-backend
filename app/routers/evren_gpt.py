"""
EvrenGPT Evaluation Process Router
Handles the complete EvrenGPT evaluation workflow from session creation to final scoring
"""
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from app.schemas.evren_gpt import (
    EvrenGPTSessionCreate,
    EvrenGPTSessionResponse,
    EvrenGPTSessionUpdate,
    StartProcessResponse,
    SessionContractorResponse,
    FormSubmissionCreate,
    FormSubmissionResponse,
    FormSubmissionUpdate,
    QuestionScoreCreate,
    QuestionScoreResponse,
    NotificationCreate,
    NotificationResponse,
    N8NWebhookPayload,
    N8NWebhookResponse,
    SessionStatistics,
    ContractorFormProgress,
    TenantEvrenGPTStats,
)
from app.utils.auth import get_current_user
from app.routers.deps import require_tenant, require_admin, ensure_response
from app.db.supabase_client import supabase

router = APIRouter(prefix="/evren-gpt", tags=["EvrenGPT"])


# ================================================
# Helper Functions
# ================================================

def generate_session_id() -> str:
    """Generate unique session ID"""
    import random
    import string
    while True:
        session_id = f"sess_{''.join(random.choices(string.digits, k=6))}"
        # Check if exists
        result = supabase.table("evren_gpt_sessions").select("id").eq("session_id", session_id).execute()
        if not result.data:
            return session_id


async def send_frm32_invitation(contractor_id: str, session_id: str, custom_message: Optional[str] = None):
    """Send FRM32 invitation email to contractor"""
    # Get contractor details
    contractor = ensure_response(
        supabase.table("contractors")
        .select("name, contact_person, contact_email")
        .eq("id", contractor_id)
        .single()
        .execute()
    )

    # Create form link (this should point to your FRM32 form with session_id)
    form_link = f"https://snsd-evrengpt.netlify.app/?session={session_id}&contractor={contractor_id}"

    subject = "EvrenGPT Evaluation Process - FRM32 Form"
    body = f"""
    Dear {contractor['contact_person']},

    You have been invited to participate in the EvrenGPT evaluation process for {contractor['name']}.

    Please click the link below to fill out the FRM32 form:
    {form_link}

    Session ID: {session_id}

    {custom_message if custom_message else ''}

    Best regards,
    SnSD Consultants Team
    """

    # Create notification record
    notification = supabase.table("evren_gpt_notifications").insert({
        "session_id": session_id,
        "contractor_id": contractor_id,
        "recipient_email": contractor['contact_email'],
        "recipient_name": contractor['contact_person'],
        "notification_type": "frm32_invite",
        "form_id": "frm32",
        "subject": subject,
        "body": body,
        "status": "pending"
    }).execute()

    # TODO: Integrate with actual email service (SendGrid, AWS SES, etc.)
    # For now, mark as sent
    supabase.table("evren_gpt_notifications").update({
        "status": "sent",
        "sent_at": datetime.now().isoformat()
    }).eq("id", notification.data[0]['id']).execute()


async def trigger_next_form(session_id: str, contractor_id: str, current_form: str, cycle: int):
    """Trigger notification for next form in sequence"""
    next_form_map = {
        "frm32": "frm33",
        "frm33": "frm34",
        "frm34": "frm35",
        "frm35": None  # No next form
    }

    next_form = next_form_map.get(current_form)
    if not next_form:
        return  # Process complete

    # Get contractor details
    contractor = ensure_response(
        supabase.table("contractors")
        .select("name, contact_person, contact_email")
        .eq("id", contractor_id)
        .single()
        .execute()
    )

    # Get supervisor email (TODO: implement supervisor assignment logic)
    # For now, use a default supervisor
    supervisor_email = "supervisor@snsdconsultant.com"  # This should come from database

    form_link = f"https://snsd-evrengpt.netlify.app/{next_form}?session={session_id}&contractor={contractor_id}&cycle={cycle}"

    subject = f"EvrenGPT Evaluation Process - {next_form.upper()} Form"
    body = f"""
    Dear Supervisor,

    The previous form in the EvrenGPT evaluation process for {contractor['name']} has been completed.

    Please proceed with the {next_form.upper()} evaluation by clicking the link below:
    {form_link}

    Session ID: {session_id}
    Cycle: {cycle}

    Best regards,
    SnSD Consultants Team
    """

    # Create notification
    supabase.table("evren_gpt_notifications").insert({
        "session_id": session_id,
        "contractor_id": contractor_id,
        "recipient_email": supervisor_email,
        "recipient_name": "Supervisor",
        "notification_type": f"{next_form}_invite",
        "form_id": next_form,
        "subject": subject,
        "body": body,
        "status": "sent",  # TODO: Send via email service
        "sent_at": datetime.now().isoformat()
    }).execute()


# ================================================
# Session Management Endpoints
# ================================================

@router.post("/start-process", response_model=StartProcessResponse)
async def start_evren_gpt_process(
    data: EvrenGPTSessionCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Start a new EvrenGPT evaluation process
    - Creates session
    - Links contractors to session
    - Sends FRM32 invitations
    """
    require_admin(current_user)  # Only admins can start process
    tenant_id = require_tenant(x_tenant_id, current_user)

    # Generate session ID
    session_id = generate_session_id()

    # Create session
    session = ensure_response(
        supabase.table("evren_gpt_sessions").insert({
            "session_id": session_id,
            "tenant_id": tenant_id,
            "created_by": current_user['id'],
            "status": "active",
            "custom_message": data.custom_message,
            "metadata": data.metadata
        }).execute()
    )

    # Link contractors to session
    contractors_notified = 0
    for contractor_id in data.contractor_ids:
        # Verify contractor belongs to tenant
        contractor = supabase.table("contractors").select("id").eq("id", contractor_id).eq("tenant_id", tenant_id).execute()
        if not contractor.data:
            continue

        # Create session_contractor record
        supabase.table("evren_gpt_session_contractors").insert({
            "session_id": session_id,
            "contractor_id": contractor_id,
            "cycle": 1,
            "status": "pending"
        }).execute()

        # Send FRM32 invitation in background
        background_tasks.add_task(send_frm32_invitation, contractor_id, session_id, data.custom_message)
        contractors_notified += 1

    # Update session contractors status to frm32_sent
    supabase.table("evren_gpt_session_contractors").update({
        "status": "frm32_sent",
        "frm32_sent_at": datetime.now().isoformat()
    }).eq("session_id", session_id).execute()

    return StartProcessResponse(
        session_id=session_id,
        contractors_notified=contractors_notified,
        message=f"Successfully started EvrenGPT process for {contractors_notified} contractor(s)"
    )


@router.get("/sessions", response_model=List[EvrenGPTSessionResponse])
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """List all EvrenGPT sessions for tenant"""
    tenant_id = require_tenant(x_tenant_id, current_user)

    query = supabase.table("evren_gpt_sessions").select("*").eq("tenant_id", tenant_id)

    if status:
        query = query.eq("status", status)

    result = ensure_response(
        query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    )

    # Enrich with contractor counts
    for session in result:
        stats = supabase.table("evren_gpt_session_contractors").select("id, status, final_score").eq("session_id", session['session_id']).execute()
        if stats.data:
            session['total_contractors'] = len(stats.data)
            session['completed_contractors'] = len([s for s in stats.data if s['status'] == 'completed'])
            scores = [s['final_score'] for s in stats.data if s['final_score'] is not None]
            session['average_score'] = sum(scores) / len(scores) if scores else None

    return result


@router.get("/sessions/{session_id}", response_model=EvrenGPTSessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """Get session details"""
    tenant_id = require_tenant(x_tenant_id, current_user)

    session = ensure_response(
        supabase.table("evren_gpt_sessions")
        .select("*")
        .eq("session_id", session_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )

    # Add contractor stats
    stats = supabase.table("evren_gpt_session_contractors").select("id, status, final_score").eq("session_id", session_id).execute()
    if stats.data:
        session['total_contractors'] = len(stats.data)
        session['completed_contractors'] = len([s for s in stats.data if s['status'] == 'completed'])
        scores = [s['final_score'] for s in stats.data if s['final_score'] is not None]
        session['average_score'] = sum(scores) / len(scores) if scores else None

    return session


@router.patch("/sessions/{session_id}", response_model=EvrenGPTSessionResponse)
async def update_session(
    session_id: str,
    data: EvrenGPTSessionUpdate,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """Update session"""
    require_admin(current_user)
    tenant_id = require_tenant(x_tenant_id, current_user)

    update_data = data.dict(exclude_unset=True)
    if "status" in update_data and update_data["status"] == "completed":
        update_data["completed_at"] = datetime.now().isoformat()

    result = ensure_response(
        supabase.table("evren_gpt_sessions")
        .update(update_data)
        .eq("session_id", session_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )

    return result[0] if result else None


# ================================================
# Form Submission Endpoints
# ================================================

@router.post("/forms/submit", response_model=FormSubmissionResponse)
async def submit_form(
    data: FormSubmissionCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a form (FRM32-35)
    - Stores submission
    - Triggers n8n webhook for AI processing
    """
    # Set submitted_by from current user
    submission_data = data.dict()
    submission_data['submitted_by'] = current_user['id']
    submission_data['submitted_at'] = datetime.now().isoformat()
    submission_data['status'] = 'submitted'

    # Create submission
    submission = ensure_response(
        supabase.table("evren_gpt_form_submissions").insert(submission_data).execute()
    )

    # TODO: Trigger n8n webhook for AI processing
    # For now, we'll just mark it as pending
    # webhook_url = f"https://n8n.snsdconsultant.com/webhook/evren-gpt/{data.form_id}"
    # requests.post(webhook_url, json=submission[0])

    # Trigger next form in background if this is not FRM35
    if data.form_id != "frm35":
        background_tasks.add_task(trigger_next_form, data.session_id, data.contractor_id, data.form_id, data.cycle)

    return submission[0]


@router.get("/forms/submissions", response_model=List[FormSubmissionResponse])
async def list_form_submissions(
    session_id: Optional[str] = None,
    contractor_id: Optional[str] = None,
    form_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """List form submissions"""
    tenant_id = require_tenant(x_tenant_id, current_user)

    # Build query
    query = supabase.table("evren_gpt_form_submissions").select(
        "*, contractors(name), profiles!submitted_by(full_name)"
    )

    # Filter by tenant through session
    if session_id:
        query = query.eq("session_id", session_id)

    if contractor_id:
        query = query.eq("contractor_id", contractor_id)

    if form_id:
        query = query.eq("form_id", form_id)

    if status:
        query = query.eq("status", status)

    result = ensure_response(
        query.order("submitted_at", desc=True).range(offset, offset + limit - 1).execute()
    )

    # Enrich response
    for item in result:
        if item.get('contractors'):
            item['contractor_name'] = item['contractors']['name']
            del item['contractors']
        if item.get('profiles'):
            item['submitted_by_name'] = item['profiles']['full_name']
            del item['profiles']

    return result


@router.get("/forms/submissions/{submission_id}", response_model=FormSubmissionResponse)
async def get_form_submission(
    submission_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get form submission with question scores"""
    submission = ensure_response(
        supabase.table("evren_gpt_form_submissions")
        .select("*, contractors(name), profiles!submitted_by(full_name)")
        .eq("id", submission_id)
        .single()
        .execute()
    )

    # Get question scores
    scores = supabase.table("evren_gpt_question_scores").select("*").eq("submission_id", submission_id).execute()
    submission['question_scores'] = scores.data if scores.data else []

    # Enrich
    if submission.get('contractors'):
        submission['contractor_name'] = submission['contractors']['name']
        del submission['contractors']
    if submission.get('profiles'):
        submission['submitted_by_name'] = submission['profiles']['full_name']
        del submission['profiles']

    return submission


# ================================================
# n8n Webhook Endpoint
# ================================================

@router.post("/webhook/n8n/{form_id}", response_model=N8NWebhookResponse)
async def n8n_webhook(
    form_id: str,
    payload: N8NWebhookPayload,
    background_tasks: BackgroundTasks
):
    """
    Receive webhook from n8n after AI processing
    - Updates submission with scores
    - Saves individual question scores
    - Updates contractor session status
    - Triggers next form if not FRM35
    """
    # Verify submission exists
    submission = supabase.table("evren_gpt_form_submissions").select("id").eq("id", payload.submission_id).execute()
    if not submission.data:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Update submission with scores
    update_data = {
        "raw_score": str(payload.raw_score),
        "final_score": str(payload.final_score),
        "status": "completed",
        "n8n_processed_at": payload.processed_at.isoformat(),
        "n8n_webhook_response": payload.metadata
    }

    supabase.table("evren_gpt_form_submissions").update(update_data).eq("id", payload.submission_id).execute()

    # Save individual question scores
    for q_score in payload.question_scores:
        supabase.table("evren_gpt_question_scores").insert({
            "submission_id": payload.submission_id,
            "question_id": q_score.get('question_id'),
            "question_text": q_score.get('question_text'),
            "answer_text": q_score.get('answer_text'),
            "ai_score": q_score.get('ai_score'),
            "ai_reasoning": q_score.get('ai_reasoning'),
            "weight": q_score.get('weight', 1.0)
        }).execute()

    # Trigger next form if not FRM35
    if form_id != "frm35":
        background_tasks.add_task(
            trigger_next_form,
            payload.session_id,
            payload.contractor_id,
            form_id,
            payload.cycle
        )

    return N8NWebhookResponse(
        success=True,
        message=f"Successfully processed {form_id.upper()} submission",
        submission_id=payload.submission_id,
        final_score=payload.final_score
    )


# ================================================
# Statistics & Progress Endpoints
# ================================================

@router.get("/sessions/{session_id}/progress", response_model=List[ContractorFormProgress])
async def get_session_progress(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """Get detailed progress for all contractors in session"""
    tenant_id = require_tenant(x_tenant_id, current_user)

    # Verify session belongs to tenant
    session = ensure_response(
        supabase.table("evren_gpt_sessions")
        .select("id")
        .eq("session_id", session_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )

    # Get progress from view
    result = ensure_response(
        supabase.from_("evren_gpt_form_completion_status")
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )

    # Add overall status
    for item in result:
        if item.get('frm35_status') == 'completed':
            item['overall_status'] = 'completed'
        elif item.get('frm34_status') == 'completed':
            item['overall_status'] = 'frm34_completed'
        elif item.get('frm33_status') == 'completed':
            item['overall_status'] = 'frm33_completed'
        elif item.get('frm32_status') == 'completed':
            item['overall_status'] = 'frm32_completed'
        else:
            item['overall_status'] = 'pending'

    return result


@router.get("/sessions/{session_id}/statistics", response_model=SessionStatistics)
async def get_session_statistics(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """Get comprehensive statistics for a session"""
    tenant_id = require_tenant(x_tenant_id, current_user)

    # Get from view
    stats = ensure_response(
        supabase.from_("evren_gpt_session_progress")
        .select("*")
        .eq("session_id", session_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )

    # Calculate completion rates
    contractors = supabase.table("evren_gpt_session_contractors").select("id").eq("session_id", session_id).execute()
    total = len(contractors.data) if contractors.data else 1

    frm32_completed = len(supabase.table("evren_gpt_form_submissions").select("id").eq("session_id", session_id).eq("form_id", "frm32").eq("status", "completed").execute().data or [])
    frm33_completed = len(supabase.table("evren_gpt_form_submissions").select("id").eq("session_id", session_id).eq("form_id", "frm33").eq("status", "completed").execute().data or [])
    frm34_completed = len(supabase.table("evren_gpt_form_submissions").select("id").eq("session_id", session_id).eq("form_id", "frm34").eq("status", "completed").execute().data or [])
    frm35_completed = len(supabase.table("evren_gpt_form_submissions").select("id").eq("session_id", session_id).eq("form_id", "frm35").eq("status", "completed").execute().data or [])

    stats['frm32_completion_rate'] = frm32_completed / total
    stats['frm33_completion_rate'] = frm33_completed / total
    stats['frm34_completion_rate'] = frm34_completed / total
    stats['frm35_completion_rate'] = frm35_completed / total

    # Count contractors by status
    contractors_data = supabase.table("evren_gpt_session_contractors").select("status").eq("session_id", session_id).execute().data or []
    stats['pending_contractors'] = len([c for c in contractors_data if c['status'] == 'pending'])
    stats['in_progress_contractors'] = len([c for c in contractors_data if c['status'] not in ('pending', 'completed')])

    return stats


# ================================================
# Admin Endpoints
# ================================================

@router.get("/admin/tenant-stats", response_model=TenantEvrenGPTStats)
async def get_tenant_evren_gpt_stats(
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """Get overall EvrenGPT statistics for tenant"""
    require_admin(current_user)
    tenant_id = require_tenant(x_tenant_id, current_user)

    # Get all sessions
    sessions = supabase.table("evren_gpt_sessions").select("id, session_id, status").eq("tenant_id", tenant_id).execute().data or []

    stats = {
        "tenant_id": tenant_id,
        "total_sessions": len(sessions),
        "active_sessions": len([s for s in sessions if s['status'] == 'active']),
        "completed_sessions": len([s for s in sessions if s['status'] == 'completed']),
        "total_contractors_evaluated": 0,
        "total_forms_submitted": 0,
        "average_completion_time_days": None,
        "form_stats": []
    }

    # Count contractors and forms
    for form_id in ['frm32', 'frm33', 'frm34', 'frm35']:
        form_submissions = []
        for session in sessions:
            forms = supabase.table("evren_gpt_form_submissions").select("id, status, final_score").eq("session_id", session['session_id']).eq("form_id", form_id).execute().data or []
            form_submissions.extend(forms)

        scores = [float(f['final_score']) for f in form_submissions if f.get('final_score') is not None]

        stats['form_stats'].append({
            "form_id": form_id,
            "total_submissions": len(form_submissions),
            "completed_submissions": len([f for f in form_submissions if f['status'] == 'completed']),
            "pending_submissions": len([f for f in form_submissions if f['status'] != 'completed']),
            "average_score": sum(scores) / len(scores) if scores else None,
            "min_score": min(scores) if scores else None,
            "max_score": max(scores) if scores else None
        })

    stats['total_forms_submitted'] = sum(s['total_submissions'] for s in stats['form_stats'])

    return stats
