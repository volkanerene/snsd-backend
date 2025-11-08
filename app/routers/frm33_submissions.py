"""FRM33 Submissions - Safety Management Form"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from datetime import datetime, timezone

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter(prefix="/frm33", tags=["FRM33 Submissions"])


@router.get("/submissions")
async def list_frm33_submissions(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    contractor_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List FRM33 submissions (tenant scoped)"""
    query = (
        supabase.table("frm33_submissions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
        .order("created_at", desc=True)
    )
    if contractor_id:
        query = query.eq("contractor_id", contractor_id)
    if status:
        query = query.eq("status", status)

    res = query.execute()
    return ensure_response(res)


@router.get("/submissions/{submission_id}")
async def get_frm33_submission(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Get specific FRM33 submission"""
    res = (
        supabase.table("frm33_submissions")
        .select("*")
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Submission not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.post("/submissions")
async def create_frm33_submission(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Create/update FRM33 submission"""
    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id

    contractor_id = payload.get("contractor_id")
    evaluation_period = payload.get("evaluation_period")

    if not contractor_id:
        raise HTTPException(400, "contractor_id required")
    if not evaluation_period:
        raise HTTPException(400, "evaluation_period required")

    # Verify contractor exists
    contractor_res = (
        supabase.table("contractors")
        .select("id")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    if not ensure_response(contractor_res):
        raise HTTPException(404, "Contractor not found")

    payload.setdefault("status", "draft")
    payload.setdefault("answers", {})
    payload.setdefault("progress_percentage", 0)

    try:
        res = supabase.table("frm33_submissions").insert(payload).execute()
        data = ensure_response(res)
        if isinstance(data, list):
            return data[0]
        return data
    except Exception as e:
        raise HTTPException(400, f"Failed to create submission: {str(e)}")


@router.put("/submissions/{submission_id}")
async def update_frm33_submission(
    submission_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Update FRM33 submission"""
    if not payload:
        raise HTTPException(400, "No fields to update")

    update_payload = {k: v for k, v in payload.items() if k != "tenant_id"}

    res = (
        supabase.table("frm33_submissions")
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


@router.post("/submissions/{submission_id}/submit")
async def submit_frm33(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Submit FRM33 submission"""
    try:
        submission_res = (
            supabase.table("frm33_submissions")
            .select("*")
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        submission = ensure_response(submission_res)
        if not submission:
            raise HTTPException(404, "Submission not found")

        now = datetime.now(timezone.utc).isoformat()
        update_res = (
            supabase.table("frm33_submissions")
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

        return {
            "success": True,
            "message": "FRM33 submitted successfully",
            "submission_id": submission_id,
            "status": "submitted",
            "submitted_at": now
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to submit: {str(e)}")
