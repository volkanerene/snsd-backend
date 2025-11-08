"""FRM34 Submissions - Environmental Management Form"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from datetime import datetime, timezone

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter(prefix="/frm34", tags=["FRM34 Submissions"])


@router.get("/submissions")
async def list_frm34_submissions(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    contractor_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List FRM34 submissions"""
    query = (
        supabase.table("frm34_submissions")
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


@router.post("/submissions")
async def create_frm34_submission(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Create/update FRM34 submission"""
    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id

    if not payload.get("contractor_id"):
        raise HTTPException(400, "contractor_id required")
    if not payload.get("evaluation_period"):
        raise HTTPException(400, "evaluation_period required")

    payload.setdefault("status", "draft")
    payload.setdefault("answers", {})
    payload.setdefault("progress_percentage", 0)

    try:
        res = supabase.table("frm34_submissions").insert(payload).execute()
        data = ensure_response(res)
        return data[0] if isinstance(data, list) else data
    except Exception as e:
        raise HTTPException(400, f"Failed to create submission: {str(e)}")


@router.put("/submissions/{submission_id}")
async def update_frm34_submission(
    submission_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Update FRM34 submission"""
    if not payload:
        raise HTTPException(400, "No fields to update")

    update_payload = {k: v for k, v in payload.items() if k != "tenant_id"}
    res = (
        supabase.table("frm34_submissions")
        .update(update_payload)
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    return data[0] if isinstance(data, list) else data


@router.post("/submissions/{submission_id}/submit")
async def submit_frm34(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Submit FRM34"""
    try:
        res = (
            supabase.table("frm34_submissions")
            .select("*")
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not ensure_response(res):
            raise HTTPException(404, "Submission not found")

        now = datetime.now(timezone.utc).isoformat()
        supabase.table("frm34_submissions").update({
            "status": "submitted",
            "submitted_at": now,
            "updated_at": now
        }).eq("id", submission_id).eq("tenant_id", tenant_id).execute()

        return {
            "success": True,
            "message": "FRM34 submitted successfully",
            "submission_id": submission_id,
            "status": "submitted",
            "submitted_at": now
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to submit: {str(e)}")
