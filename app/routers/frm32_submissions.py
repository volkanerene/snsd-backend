from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user
from app.services.email_service import EmailService, render_html_from_text
from app.config import settings

router = APIRouter()

USER_EDITABLE_FIELDS = {"progress_percentage", "notes", "answers", "scores"}
REQUIRED_DOCUMENT_IDS = {
    "doc-1",
    "doc-4",
    "doc-6",
    "doc-7",
    "doc-7.1",
    "doc-8",
    "doc-11",
    "doc-12",
    "doc-13",
}


def _has_answer(value: Any) -> bool:
    """Check whether an answer value is considered filled."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


@router.get("/submissions")
async def list_submissions(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    status: str | None = Query(None),
    contractor_id: str | None = Query(None),
    evaluation_period: str | None = Query(None),  # <-- EKLENDİ
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List FRM32 submissions (tenant scoped)
    Optional filters:
      - status
      - contractor_id
      - evaluation_period  (örn: '2025-01', '2025-09', '2025-Q3' vs.)
    """
    query = (
        supabase.table("frm32_submissions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    if contractor_id:
        query = query.eq("contractor_id", contractor_id)
    if evaluation_period:
        query = query.eq("evaluation_period", evaluation_period)  # <-- FİLTRE

    res = query.execute()
    return ensure_response(res)


@router.post("/submissions")
async def create_submission(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """
    Create FRM32 submission.
    Required body:
      - contractor_id
      - evaluation_period
    Optional:
      - status (default: 'draft')
      - evaluation_type (default: 'periodic')
      - progress_percentage (default: 0)
      - answers (default: {})
      - notes, attachments, metadata
    """
    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id

    contractor_id = payload.get("contractor_id")
    evaluation_period = payload.get("evaluation_period")

    if not contractor_id:
        raise HTTPException(400, "contractor_id required")
    if not evaluation_period:
        raise HTTPException(400, "evaluation_period required")

    # Contractor exist check (tenant scoped)
    contractor_res = (
        supabase.table("contractors")
        .select("id")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    contractor_data = ensure_response(contractor_res)
    if not contractor_data:
        raise HTTPException(404, "Contractor not found")

    # Set defaults for optional fields if not provided
    payload.setdefault("status", "draft")
    payload.setdefault("evaluation_type", "periodic")
    payload.setdefault("progress_percentage", 0)
    payload.setdefault("answers", {})
    payload.setdefault("attachments", [])
    payload.setdefault("metadata", {})

    # Aynı (tenant, contractor, evaluation_period) varsa onu döndür (idempotent create)
    existing_res = (
        supabase.table("frm32_submissions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("contractor_id", contractor_id)
        .eq("evaluation_period", evaluation_period)
        .limit(1)
        .execute()
    )
    existing = ensure_response(existing_res)
    if isinstance(existing, list) and existing:
        return existing[0]

    # Yoksa oluştur
    try:
        res = supabase.table("frm32_submissions").insert(payload).execute()
        data = ensure_response(res)
        if isinstance(data, list):
            return data[0]
        return data
    except Exception as e:
        raise HTTPException(400, f"Failed to create submission: {str(e)}")


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("frm32_submissions")
        .select("*")
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.put("/submissions/{submission_id}")
async def update_submission(
    submission_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    if not payload:
        raise HTTPException(400, "No fields to update")

    is_admin = user.get("role") in ("admin", "service_role")

    update_payload = dict(payload)
    update_payload.pop("tenant_id", None)

    if not is_admin:
        # Non-admin kullanıcı sadece USER_EDITABLE_FIELDS alanlarını güncelleyebilir
        update_payload = {k: v for k, v in update_payload.items() if k in USER_EDITABLE_FIELDS}
        if not update_payload:
            raise HTTPException(403, "Not allowed")

    res = (
        supabase.table("frm32_submissions")
        .update(update_payload)
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.post("/submissions/{submission_id}/upload")
async def upload_submission_file(
    submission_id: str,
    file: UploadFile = File(...),
    docId: str = Query(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """
    Upload a document file for FRM32 submission using Supabase Storage.

    Files are stored in Supabase Storage bucket: frm32/submissions/{submission_id}/{docId}/{filename}
    File reference is added to the submission's attachments JSONB array.
    """
    print(f"[FRM32 Upload] Starting file upload - submission_id: {submission_id}, docId: {docId}, file: {file.filename if file else 'None'}")
    try:
        # Verify submission exists and belongs to tenant
        submission_res = (
            supabase.table("frm32_submissions")
            .select("id, attachments")
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        submission = ensure_response(submission_res)
        if not submission:
            raise HTTPException(404, "Submission not found")

        submission_data = submission if isinstance(submission, dict) else submission[0]

        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024
        if file.size and file.size > max_size:
            raise HTTPException(400, f"File exceeds 10MB limit ({file.size / 1024 / 1024:.1f}MB)")

        # Validate file type
        allowed_types = {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg',
            'image/png'
        }
        if file.content_type and file.content_type not in allowed_types:
            raise HTTPException(400, f"File type not allowed: {file.content_type}")

        # Read file content
        file_content = await file.read()

        # Upload to Supabase Storage
        storage_path = f"{tenant_id}/frm32/submissions/{submission_id}/{docId}/{file.filename}"
        now_utc = datetime.now(timezone.utc).isoformat()

        try:
            supabase.storage.from_("frm32-documents").upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": file.content_type or "application/octet-stream"}
            )
        except Exception:
            # If file already exists, delete it first then upload
            try:
                supabase.storage.from_("frm32-documents").remove([storage_path])
            except:
                pass  # File might not exist

            supabase.storage.from_("frm32-documents").upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": file.content_type or "application/octet-stream"}
            )

        # Get public URL for the file
        file_url = supabase.storage.from_("frm32-documents").get_public_url(storage_path)

        # Add file reference to submission's attachments
        attachments = submission_data.get("attachments", []) or []
        if not isinstance(attachments, list):
            attachments = []

        # Add new attachment reference
        attachment_entry = {
            "docId": docId,
            "filename": file.filename,
            "storage_path": storage_path,
            "file_url": file_url,
            "size": file.size,
            "content_type": file.content_type,
            "uploaded_at": now_utc
        }

        # Remove existing attachment with same docId if present
        attachments = [a for a in attachments if a.get("docId") != docId]
        attachments.append(attachment_entry)

        # Update submission with new attachments
        update_res = (
            supabase.table("frm32_submissions")
            .update({"attachments": attachments})
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        ensure_response(update_res)

        return {
            "success": True,
            "docId": docId,
            "filename": file.filename,
            "storage_path": storage_path,
            "file_url": file_url,
            "size": file.size,
            "content_type": file.content_type,
            "message": "File uploaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to upload file: {str(e)}")


@router.post("/submissions/{submission_id}/submit")
async def submit_submission(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Submit FRM32 submission - validates required files exist, updates status to 'submitted'
    """
    try:
        # Get submission
        submission_res = (
            supabase.table("frm32_submissions")
            .select("*")
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        submission = ensure_response(submission_res)
        if not submission:
            raise HTTPException(404, "Submission not found")

        submission_data = submission if isinstance(submission, dict) else submission[0]
        answers = submission_data.get("answers") or {}

        # VALIDATE: Ensure all questions are answered before submission
        questions_res = (
            supabase.table("frm32_questions")
            .select("question_code")
            .order("position")
            .execute()
        )
        questions = ensure_response(questions_res) or []
        unanswered_questions = [
            q["question_code"]
            for q in questions
            if not _has_answer(answers.get(q["question_code"]))
        ]
        if unanswered_questions:
            raise HTTPException(
                400,
                f"Cannot submit: {len(unanswered_questions)} unanswered question(s) remain"
            )

        # VALIDATE: Check that required files have been uploaded
        attachments = submission_data.get("attachments", []) or []
        if not attachments:
            raise HTTPException(
                400,
                "Cannot submit: Please upload required documents before submitting. At least one file is required."
            )

        uploaded_doc_ids = {
            att.get("docId")
            for att in attachments
            if isinstance(att, dict) and att.get("docId")
        }
        missing_required_docs = sorted(
            doc_id for doc_id in REQUIRED_DOCUMENT_IDS if doc_id not in uploaded_doc_ids
        )
        if missing_required_docs:
            raise HTTPException(
                400,
                "Cannot submit: Missing required documents ({docs})".format(
                    docs=", ".join(missing_required_docs)
                )
            )

        # Update submission status to 'submitted'
        now = datetime.now(timezone.utc).isoformat()
        progress_value = 100 if questions else max(submission_data.get("progress_percentage") or 0, 100)
        update_res = (
            supabase.table("frm32_submissions")
            .update({
                "status": "submitted",
                "submitted_at": now,
                "updated_at": now,
                "progress_percentage": progress_value
            })
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        ensure_response(update_res)

        # Get contractor info for email
        contractor_id = submission_data.get("contractor_id")
        if contractor_id:
            contractor_res = (
                supabase.table("contractors")
                .select("*")
                .eq("id", contractor_id)
                .limit(1)
                .execute()
            )
            contractor = ensure_response(contractor_res)
            if contractor and isinstance(contractor, list):
                contractor = contractor[0]

            if contractor:
                # Send supervisor notification in background
                background_tasks.add_task(
                    _notify_supervisor_submission,
                    submission_data,
                    contractor
                )

        return {
            "success": True,
            "message": "FRM32 submission completed successfully!",
            "submission_id": submission_id,
            "status": "submitted",
            "submitted_at": now
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[submit_submission] Error: {str(e)}")
        raise HTTPException(500, f"Failed to submit: {str(e)}")


def _notify_supervisor_submission(
    submission: Dict[str, Any],
    contractor: Dict[str, Any]
):
    """
    Background task: Send supervisor notification when submission is completed
    """
    try:
        tenant_id = submission.get("tenant_id")
        if not tenant_id:
            print("[supervisor_notification] Missing tenant_id on submission; cannot notify")
            return

        supervisors_res = (
            supabase.table("profiles")
            .select("id, full_name, email, username, notification_preferences")
            .eq("tenant_id", tenant_id)
            .eq("role_id", 5)  # Supervisor role
            .eq("is_active", True)
            .execute()
        )
        supervisors = ensure_response(supervisors_res) or []
        supervisors = [
            sup for sup in supervisors
            if sup.get("email")
            and ((sup.get("notification_preferences") or {}).get("email", True))
        ]

        if not supervisors:
            print(f"[supervisor_notification] No active supervisors with email for tenant {tenant_id}")
            return

        contractor_name = contractor.get("name") or contractor.get("legal_name") or "Contractor"
        evaluation_period = submission.get("evaluation_period") or "current period"
        submission_id = submission.get("id")
        submitted_at = submission.get("submitted_at") or datetime.now(timezone.utc).isoformat()
        dashboard_base = getattr(settings, "DASHBOARD_BASE_URL", None) or "https://app.snsdconsultant.com"
        frm32_link = f"{dashboard_base.rstrip('/')}/dashboard/evren-gpt/frm32?submission={submission_id}"

        for supervisor in supervisors:
            recipient_email = supervisor.get("email")
            recipient_name = supervisor.get("full_name") or supervisor.get("username") or "Supervisor"
            subject = f"FRM32 Tamamlandı - {contractor_name}"
            body = f"""
Merhaba {recipient_name},

{contractor_name} firmasının {evaluation_period} dönemi FRM32 formu {submitted_at} tarihinde gönderildi.

Formu incelemek için aşağıdaki bağlantıyı kullanabilirsiniz:
{frm32_link}

İyi çalışmalar,
SnSD Consultants
"""

            notification_record = (
                supabase.table("frm32_submission_notifications")
                .insert({
                    "submission_id": submission_id,
                    "contractor_id": contractor.get("id"),
                    "tenant_id": tenant_id,
                    "recipient_email": recipient_email,
                    "recipient_name": recipient_name,
                    "subject": subject,
                    "body": body,
                    "status": "pending",
                })
                .execute()
            )
            notification_id = None
            record_data = notification_record.data if notification_record else None
            if record_data:
                if isinstance(record_data, list) and record_data:
                    notification_id = record_data[0].get("id")
                elif isinstance(record_data, dict):
                    notification_id = record_data.get("id")

            sent, error_message = EmailService.send_email(
                to_email=recipient_email,
                subject=subject,
                text_body=body,
                html_body=render_html_from_text(body)
            )

            status = "sent" if sent else f"failed ({error_message})"
            print(f"[supervisor_notification] Email {status} to {recipient_email} for submission {submission_id}")

            if notification_id:
                update_payload = {
                    "status": "sent" if sent else "failed",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                }
                if error_message:
                    update_payload["error_message"] = error_message
                supabase.table("frm32_submission_notifications").update(update_payload).eq("id", notification_id).execute()

    except Exception as e:
        print(f"[supervisor_notification] Error: {e}")
def _require_supervisor_role(user: dict):
    """
    Allow supervisors (role_id 5) or admin/HSE roles (<=3) to score submissions.
    """
    role_id = user.get("role_id")
    if role_id is None or (role_id > 3 and role_id != 5):
        raise HTTPException(403, "Supervisor permissions required")


def _fetch_k2_metrics(codes: Optional[List[str]] = None):
    query = supabase.table("frm32_k2_metrics").select("*")
    if codes:
        query = query.in_("k2_code", codes)
    res = query.order("k2_code").execute()
    return ensure_response(res) or []


def _recalculate_final_score(submission_id: str, tenant_id: str) -> float:
    scores_res = (
        supabase.table("frm32_submission_scores")
        .select("k2_code, score")
        .eq("submission_id", submission_id)
        .execute()
    )
    scores = ensure_response(scores_res) or []
    if not scores:
        supabase.table("frm32_submissions").update({"final_score": None}).eq("id", submission_id).eq("tenant_id", tenant_id).execute()
        return 0.0

    k2_codes = [row["k2_code"] for row in scores]
    metrics = _fetch_k2_metrics(k2_codes)
    metric_map = {m["k2_code"]: m for m in metrics}

    total = 0.0
    for row in scores:
        weight = float(metric_map[row["k2_code"]]["weight_percentage"])
        score_value = row["score"]
        total += (weight * score_value) / 10

    final_score = round(total, 2)
    supabase.table("frm32_submissions").update({"final_score": final_score}).eq("id", submission_id).eq("tenant_id", tenant_id).execute()
    return final_score


@router.get("/k2-metrics")
async def list_k2_metrics(user=Depends(get_current_user)):
    """
    Return static K2 scoring metadata (weights + comments)
    """
    metrics = _fetch_k2_metrics()
    return metrics


@router.get("/submissions/{submission_id}/k2-scores")
async def get_submission_k2_scores(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    submission_res = (
        supabase.table("frm32_submissions")
        .select("id, final_score")
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    submission = ensure_response(submission_res)
    if not submission:
        raise HTTPException(404, "Submission not found")
    if isinstance(submission, list):
        submission = submission[0]

    metrics = _fetch_k2_metrics()
    scores_res = (
        supabase.table("frm32_submission_scores")
        .select("k2_code, score, comment_en, comment_tr")
        .eq("submission_id", submission_id)
        .execute()
    )
    score_data = ensure_response(scores_res) or []
    score_map = {row["k2_code"]: row for row in score_data}

    merged = []
    for metric in metrics:
        current = score_map.get(metric["k2_code"])
        merged.append(
            {
                "k2_code": metric["k2_code"],
                "scope_en": metric["scope_en"],
                "scope_tr": metric["scope_tr"],
                "weight_percentage": float(metric["weight_percentage"]),
                "comments": {
                    "0": {
                        "en": metric["comment_0_en"],
                        "tr": metric["comment_0_tr"],
                    },
                    "3": {
                        "en": metric["comment_3_en"],
                        "tr": metric["comment_3_tr"],
                    },
                    "6": {
                        "en": metric["comment_6_en"],
                        "tr": metric["comment_6_tr"],
                    },
                    "10": {
                        "en": metric["comment_10_en"],
                        "tr": metric["comment_10_tr"],
                    },
                },
                "score": current["score"] if current else None,
                "selected_comment_en": current["comment_en"] if current else None,
                "selected_comment_tr": current["comment_tr"] if current else None,
            }
        )

    return {"scores": merged, "final_score": submission.get("final_score")}


@router.put("/submissions/{submission_id}/k2-scores")
async def update_submission_k2_scores(
    submission_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    _require_supervisor_role(user)

    raw_scores = payload.get("scores")
    if not raw_scores and payload.get("k2_code"):
        raw_scores = [payload]
    if not raw_scores:
        raise HTTPException(400, "scores payload required")

    submission_res = (
        supabase.table("frm32_submissions")
        .select("id")
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    submission = ensure_response(submission_res)
    if not submission:
        raise HTTPException(404, "Submission not found")

    k2_codes = []
    for item in raw_scores:
        code = item.get("k2_code")
        if not code:
            raise HTTPException(400, "k2_code missing in scores payload")
        k2_codes.append(code)
    metrics = _fetch_k2_metrics(k2_codes)
    metric_map = {m["k2_code"]: m for m in metrics}

    score_payload = []
    for item in raw_scores:
        code = item["k2_code"]
        score_value = item.get("score")
        if score_value not in (0, 3, 6, 10):
            raise HTTPException(400, f"Invalid score for {code}. Allowed values: 0,3,6,10")
        metric = metric_map.get(code)
        if not metric:
            raise HTTPException(400, f"Unknown K2 code: {code}")
        prefix = {0: "comment_0", 3: "comment_3", 6: "comment_6", 10: "comment_10"}[score_value]
        comment_en = metric[f"{prefix}_en"]
        comment_tr = metric[f"{prefix}_tr"]
        score_payload.append(
            {
                "submission_id": submission_id,
                "k2_code": code,
                "score": score_value,
                "comment_en": comment_en,
                "comment_tr": comment_tr,
            }
        )

    supabase.table("frm32_submission_scores").upsert(
        score_payload,
        on_conflict="submission_id,k2_code"
    ).execute()

    final_score = _recalculate_final_score(submission_id, tenant_id)

    updated_scores = await get_submission_k2_scores(submission_id, user, tenant_id)
    updated_scores["final_score"] = final_score
    return updated_scores
