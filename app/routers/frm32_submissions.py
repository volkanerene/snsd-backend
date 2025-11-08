from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()

USER_EDITABLE_FIELDS = {"progress_percentage", "notes", "answers", "scores"}


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

        # VALIDATE: Check that at least one file has been uploaded
        attachments = submission_data.get("attachments", []) or []
        if not attachments or len(attachments) == 0:
            raise HTTPException(
                400,
                "Cannot submit: Please upload required documents before submitting. At least one file is required."
            )

        # Update submission status to 'submitted'
        now = datetime.now(timezone.utc).isoformat()
        update_res = (
            supabase.table("frm32_submissions")
            .update({
                "status": "submitted",
                "submitted_at": now,
                "updated_at": now
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


async def _notify_supervisor_submission(
    submission: Dict[str, Any],
    contractor: Dict[str, Any]
):
    """
    Background task: Send supervisor notification when submission is completed
    """
    try:
        print(f"[supervisor_notification] FRM32 submitted for contractor: {contractor.get('name')}")
        # TODO: Implement email sending to supervisor(s)
        # EmailService.send_email(
        #     to_email=supervisor_email,
        #     subject=f"FRM32 Submission: {contractor['name']}",
        #     text_body=...,
        #     html_body=...
        # )
    except Exception as e:
        print(f"[supervisor_notification] Error: {e}")