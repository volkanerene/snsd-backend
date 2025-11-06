"""
Form Submissions Router
Handles FRM32, FRM33, FRM34, FRM35 form submissions with auto-save and final submission
Integrates with N8N workflows for processing
"""
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel

from app.db.supabase_client import supabase
from app.routers.deps import require_tenant
from app.utils.auth import get_current_user
from app.services.email_service import EmailService, render_html_from_text
from app.config import settings

router = APIRouter(prefix="/frm32", tags=["Form Submissions"])

# N8N webhook endpoint - configure this with your actual N8N instance
N8N_WEBHOOK_URL = "https://n8n.your-instance.com/webhook/frm32"  # TODO: Configure


class FormSubmissionRequest(BaseModel):
    form_id: str
    session_id: str
    contractor_id: str
    cycle: int
    answers: Dict[str, str]
    status: str  # 'draft' or 'submitted'


@router.get("/submissions")
async def get_form_submissions(
    session_id: str,
    contractor_id: str,
    cycle: int = 1,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Get existing form submission(s)
    """
    tenant_id = require_tenant(x_tenant_id, user)

    try:
        # Verify session belongs to tenant
        session = supabase.table("evren_gpt_sessions") \
            .select("id") \
            .eq("session_id", session_id) \
            .eq("tenant_id", tenant_id) \
            .execute()

        if not session.data:
            raise HTTPException(404, "Session not found or access denied")

        # Get submission
        submissions = supabase.table("evren_gpt_form_submissions") \
            .select("*") \
            .eq("session_id", session_id) \
            .eq("contractor_id", contractor_id) \
            .eq("form_id", "frm32") \
            .eq("cycle", cycle) \
            .execute()

        return submissions.data if submissions.data else []

    except HTTPException:
        raise
    except Exception as e:
        print(f"[get_form_submissions] Error: {e}")
        raise HTTPException(500, f"Failed to load submissions: {str(e)}")


@router.post("/submissions")
async def save_form_submission(
    request: FormSubmissionRequest,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Auto-save form submission as draft
    """
    tenant_id = require_tenant(x_tenant_id, user)

    try:
        # Verify session belongs to tenant
        session = supabase.table("evren_gpt_sessions") \
            .select("id") \
            .eq("session_id", request.session_id) \
            .eq("tenant_id", tenant_id) \
            .execute()

        if not session.data:
            raise HTTPException(404, "Session not found or access denied")

        # Upsert submission
        submission_data = {
            "session_id": request.session_id,
            "contractor_id": request.contractor_id,
            "form_id": request.form_id,
            "cycle": request.cycle,
            "answers": request.answers,
            "status": request.status,
            "updated_at": datetime.now().isoformat()
        }

        result = supabase.table("evren_gpt_form_submissions") \
            .upsert(submission_data, on_conflict="session_id,contractor_id,form_id,cycle") \
            .execute()

        return {
            "success": True,
            "message": "Draft saved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[save_form_submission] Error: {e}")
        raise HTTPException(500, f"Failed to save submission: {str(e)}")


@router.post("/submit")
async def submit_form(
    request: FormSubmissionRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Submit form - final submission with N8N trigger and supervisor notification
    """
    tenant_id = require_tenant(x_tenant_id, user)

    try:
        # Verify session belongs to tenant
        session_query = supabase.table("evren_gpt_sessions") \
            .select("id, tenant_id") \
            .eq("session_id", request.session_id) \
            .eq("tenant_id", tenant_id) \
            .execute()

        if not session_query.data:
            raise HTTPException(404, "Session not found or access denied")

        session = session_query.data[0]

        # Get contractor details
        contractor = supabase.table("contractors") \
            .select("*") \
            .eq("id", request.contractor_id) \
            .single() \
            .execute()

        if not contractor.data:
            raise HTTPException(404, "Contractor not found")

        # Save submission as completed
        submission_data = {
            "session_id": request.session_id,
            "contractor_id": request.contractor_id,
            "form_id": request.form_id,
            "cycle": request.cycle,
            "answers": request.answers,
            "status": "submitted",
            "submitted_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        supabase.table("evren_gpt_form_submissions") \
            .upsert(submission_data, on_conflict="session_id,contractor_id,form_id,cycle") \
            .execute()

        # Trigger N8N workflow in background
        background_tasks.add_task(
            trigger_n8n_workflow,
            request.form_id,
            request.session_id,
            request.contractor_id,
            request.cycle,
            request.answers,
            contractor.data
        )

        # Send supervisor notification in background
        background_tasks.add_task(
            notify_supervisor,
            request.session_id,
            contractor.data,
            tenant_id
        )

        # Unlock FRM33, FRM34, FRM35
        background_tasks.add_task(
            unlock_next_forms,
            request.session_id,
            request.contractor_id
        )

        return {
            "success": True,
            "message": "Form submitted successfully. Processing will begin shortly.",
            "submission_id": f"{request.session_id}_{request.contractor_id}_{request.cycle}"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[submit_form] Error: {e}")
        raise HTTPException(500, f"Failed to submit form: {str(e)}")


async def trigger_n8n_workflow(
    form_id: str,
    session_id: str,
    contractor_id: str,
    cycle: int,
    answers: Dict[str, str],
    contractor: Dict[str, Any]
):
    """
    Trigger N8N workflow for form processing
    """
    try:
        # Get session and tenant info
        session = supabase.table("evren_gpt_sessions") \
            .select("*") \
            .eq("session_id", session_id) \
            .single() \
            .execute()

        if not session.data:
            return

        payload = {
            "form_id": form_id,
            "session_id": session_id,
            "session_name": session.data.get("name"),
            "contractor_id": contractor_id,
            "contractor_name": contractor.get("name"),
            "contractor_email": contractor.get("contact_email"),
            "cycle": cycle,
            "answers": answers,
            "submitted_at": datetime.now().isoformat()
        }

        # Call N8N webhook (configure URL in environment)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=30.0
            )
            print(f"[N8N] Webhook response: {response.status_code}")

    except Exception as e:
        print(f"[trigger_n8n_workflow] Error: {e}")
        # Don't raise - this is background task


async def notify_supervisor(
    session_id: str,
    contractor: Dict[str, Any],
    tenant_id: str
):
    """
    Send email notification to supervisor when form is submitted
    """
    try:
        # Get session
        session = supabase.table("evren_gpt_sessions") \
            .select("*") \
            .eq("session_id", session_id) \
            .single() \
            .execute()

        if not session.data:
            return

        # Get supervisor email(s) from session or tenant settings
        # TODO: Implement logic to get supervisor email(s)
        # For now, just log
        print(f"[notify_supervisor] Session {session_id}, Contractor {contractor['name']} submitted FRM32")

        # Email template
        body_text = f"""
Dear Supervisor,

Contractor {contractor['name']} has completed FRM32 - HSE Capability Assessment.

Name: {contractor['name']}
Email: {contractor['contact_email']}
Company Type: {contractor.get('company_type', 'N/A')}
Tax Number: {contractor.get('tax_number', 'N/A')}

Please review their assessment and proceed with the evaluation process.

Best regards,
SnSD Team
        """.strip()

        # TODO: Send email to supervisor(s)
        # EmailService.send_email(
        #     to_email=supervisor_email,
        #     subject=f"FRM32 Submission: {contractor['name']}",
        #     text_body=body_text,
        #     html_body=render_html_from_text(body_text)
        # )

    except Exception as e:
        print(f"[notify_supervisor] Error: {e}")


async def unlock_next_forms(
    session_id: str,
    contractor_id: str
):
    """
    Unlock FRM33, FRM34, FRM35 forms after FRM32 submission
    """
    try:
        # Create form submission records for FRM33, FRM34, FRM35
        # so they appear as available/unlocked
        forms_to_create = ["frm33", "frm34", "frm35"]

        for form_id in forms_to_create:
            submission_data = {
                "session_id": session_id,
                "contractor_id": contractor_id,
                "form_id": form_id,
                "cycle": 1,
                "answers": {},
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            supabase.table("evren_gpt_form_submissions") \
                .upsert(submission_data, on_conflict="session_id,contractor_id,form_id,cycle") \
                .execute()

        print(f"[unlock_next_forms] Unlocked FRM33, FRM34, FRM35 for contractor {contractor_id}")

    except Exception as e:
        print(f"[unlock_next_forms] Error: {e}")
