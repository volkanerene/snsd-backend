"""
EvrenGPT Evaluations Router
Handles the evaluations overview page for Company Admin & HSE Specialist
"""
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks, Body
from typing import List, Optional
from datetime import datetime

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user
from app.services.email_service import EmailService, render_html_from_text

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


@router.get("/")
async def list_evaluations(
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None),
    session_id: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Get all contractor evaluations with their progress and scores

    Returns list of contractors with:
    - FRM32, 33, 34, 35 status and scores
    - Overall progress percentage
    - Final score calculation (FRM32 * 0.5 + FRM35 * 0.5)
    """
    tenant_id = require_tenant(x_tenant_id, user)

    # Use the view we created in migration
    query = supabase.from_("evren_gpt_form_completion_status").select("*")

    # Filter by tenant through session
    sessions_query = supabase.table("evren_gpt_sessions").select("session_id").eq("tenant_id", tenant_id)
    if session_id:
        sessions_query = sessions_query.eq("session_id", session_id)

    sessions = sessions_query.execute()
    if sessions.data:
        session_ids = [s["session_id"] for s in sessions.data]

        # Get all completion statuses for these sessions
        if session_ids:
            # Supabase doesn't support IN directly, so we use or_ syntax
            completions = []
            for sid in session_ids:
                result = supabase.from_("evren_gpt_form_completion_status").select("*").eq("session_id", sid).execute()
                if result.data:
                    completions.extend(result.data)

            # Calculate final scores and progress
            evaluations = []
            for comp in completions:
                frm32_score = comp.get("frm32_score")
                frm35_score = comp.get("frm35_score")

                # Calculate final score
                final_score = None
                if frm32_score is not None and frm35_score is not None:
                    final_score = (float(frm32_score) * 0.5) + (float(frm35_score) * 0.5)

                # Calculate progress percentage
                statuses = [
                    comp.get("frm32_status"),
                    comp.get("frm33_status"),
                    comp.get("frm34_status"),
                    comp.get("frm35_status")
                ]
                completed = sum(1 for s in statuses if s == "completed")
                progress_percentage = (completed / 4) * 100

                # Determine if answers are available
                answers_available = completed > 0

                evaluations.append({
                    "id": f"{comp['session_id']}_{comp['contractor_id']}_{comp['cycle']}",
                    "contractor_id": comp["contractor_id"],
                    "contractor_name": comp["contractor_name"],
                    "session_id": comp["session_id"],
                    "cycle": comp["cycle"],
                    "frm32_status": comp.get("frm32_status") or "pending",
                    "frm33_status": comp.get("frm33_status") or "pending",
                    "frm34_status": comp.get("frm34_status") or "pending",
                    "frm35_status": comp.get("frm35_status") or "pending",
                    "frm32_score": frm32_score,
                    "frm33_score": comp.get("frm33_score"),
                    "frm34_score": comp.get("frm34_score"),
                    "frm35_score": frm35_score,
                    "final_score": final_score,
                    "progress_percentage": progress_percentage,
                    "last_updated": datetime.now().isoformat(),
                    "answers_available": answers_available
                })

            return evaluations

    return []


@router.post("/send-assessment")
async def send_assessment(
    evaluation_ids: List[str] = Body(..., embed=True),
    background_tasks: BackgroundTasks = None,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Send assessment to selected contractors
    """
    tenant_id = require_tenant(x_tenant_id, user)

    # TODO: Implement actual assessment sending logic
    # This would typically send emails or create tasks

    return {
        "success": True,
        "message": f"Assessment sent to {len(evaluation_ids)} contractor(s)",
        "count": len(evaluation_ids)
    }


@router.post("/send-reminders")
async def send_frm32_reminders(
    contractor_ids: Optional[List[str]] = Body(None, embed=True),
    background_tasks: BackgroundTasks = None,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Send FRM32 reminder emails to contractors who haven't completed it

    If contractor_ids not provided, sends to all pending FRM32s
    """
    tenant_id = require_tenant(x_tenant_id, user)

    # Get sessions for this tenant
    sessions = supabase.table("evren_gpt_sessions").select("session_id").eq("tenant_id", tenant_id).eq("status", "active").execute()

    if not sessions.data:
        return {"success": False, "message": "No active sessions found", "count": 0}

    session_ids = [s["session_id"] for s in sessions.data]

    # Get pending FRM32 submissions
    reminders_sent = 0
    for session_id in session_ids:
        # Get contractors with pending FRM32
        submissions_query = supabase.table("evren_gpt_form_submissions").select("contractor_id").eq("session_id", session_id).eq("form_id", "frm32")

        # Get all contractors in session
        session_contractors = supabase.table("evren_gpt_session_contractors").select("contractor_id").eq("session_id", session_id).execute()

        if session_contractors.data:
            submitted_contractor_ids = []
            if submissions_query.execute().data:
                submitted_contractor_ids = [s["contractor_id"] for s in submissions_query.execute().data if s.get("status") == "completed"]

            # Find pending contractors
            for sc in session_contractors.data:
                cid = sc["contractor_id"]

                # Filter by provided contractor_ids if given
                if contractor_ids and cid not in contractor_ids:
                    continue

                if cid not in submitted_contractor_ids:
                    # Get contractor details
                    contractor = supabase.table("contractors").select("name, contact_email, contact_person").eq("id", cid).single().execute()

                    if contractor.data:
                        # Create notification
                        notification = supabase.table("evren_gpt_notifications").insert({
                            "session_id": session_id,
                            "contractor_id": cid,
                            "recipient_email": contractor.data["contact_email"],
                            "recipient_name": contractor.data["contact_person"],
                            "notification_type": "reminder",
                            "form_id": "frm32",
                            "subject": "Reminder: Complete FRM32 Safety Assessment",
                            "body": f"Dear {contractor.data['contact_person']},\n\nThis is a reminder to complete your FRM32 safety self-assessment.\n\nPlease complete it at your earliest convenience.\n\nBest regards,\nSnSD Team",
                            "status": "pending"
                        }).execute()

                        notification_id = notification.data[0]['id'] if notification.data else None

                        body_text = f"Dear {contractor.data['contact_person']},\n\nThis is a reminder to complete your FRM32 safety self-assessment.\n\nPlease complete it at your earliest convenience.\n\nBest regards,\nSnSD Team"
                        sent, error_message = EmailService.send_email(
                            to_email=contractor.data["contact_email"],
                            subject="Reminder: Complete FRM32 Safety Assessment",
                            text_body=body_text,
                            html_body=render_html_from_text(body_text)
                        )

                        update_payload = {
                            "status": "sent" if sent else "failed",
                            "sent_at": datetime.now().isoformat()
                        }
                        if not sent and error_message:
                            update_payload["error_message"] = error_message

                        if notification_id:
                            supabase.table("evren_gpt_notifications").update(update_payload).eq("id", notification_id).execute()

                        reminders_sent += 1

    return {
        "success": True,
        "message": f"Reminders sent to {reminders_sent} contractor(s)",
        "count": reminders_sent
    }


@router.get("/{evaluation_id}/answers")
async def get_evaluation_answers(
    evaluation_id: str,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Get detailed answers for a specific evaluation

    evaluation_id format: {session_id}_{contractor_id}_{cycle}
    """
    tenant_id = require_tenant(x_tenant_id, user)

    try:
        parts = evaluation_id.split("_")
        session_id = "_".join(parts[:-2])  # Handle session_id like sess_000001
        contractor_id = parts[-2]
        cycle = int(parts[-1])
    except Exception:
        raise HTTPException(400, "Invalid evaluation_id format")

    # Verify session belongs to tenant
    session = supabase.table("evren_gpt_sessions").select("id").eq("session_id", session_id).eq("tenant_id", tenant_id).execute()
    if not session.data:
        raise HTTPException(404, "Evaluation not found")

    # Get all form submissions for this contractor
    submissions = supabase.table("evren_gpt_form_submissions").select("*").eq("session_id", session_id).eq("contractor_id", contractor_id).eq("cycle", cycle).execute()

    if not submissions.data:
        raise HTTPException(404, "No submissions found")

    # Format response
    result = {
        "session_id": session_id,
        "contractor_id": contractor_id,
        "cycle": cycle,
        "forms": []
    }

    for sub in submissions.data:
        # Get question scores
        scores = supabase.table("evren_gpt_question_scores").select("*").eq("submission_id", sub["id"]).execute()

        result["forms"].append({
            "form_id": sub["form_id"],
            "status": sub["status"],
            "answers": sub.get("answers", {}),
            "raw_score": sub.get("raw_score"),
            "final_score": sub.get("final_score"),
            "submitted_at": sub.get("submitted_at"),
            "question_scores": scores.data if scores.data else []
        })

    return result
