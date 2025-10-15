from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()

USER_EDITABLE_FIELDS = {"progress_percentage", "notes"}


@router.get("/submissions")
async def list_submissions(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    status: str | None = Query(None),
    contractor_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        supabase.table("frm32_submissions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)
    if contractor_id:
        query = query.eq("contractor_id", contractor_id)
    res = query.execute()
    return ensure_response(res)


@router.post("/submissions")
async def create_submission(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    if not payload.get("contractor_id"):
        raise HTTPException(400, "contractor_id required")
    contractor_res = (
        supabase.table("contractors")
        .select("id")
        .eq("id", payload["contractor_id"])
        .eq("tenant_id", tenant_id)
        .execute()
    )
    contractor_data = ensure_response(contractor_res)
    if not contractor_data:
        raise HTTPException(404, "Contractor not found")
    res = supabase.table("frm32_submissions").insert(payload).execute()
    return ensure_response(res)


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
    if not is_admin:
        update_payload = {k: v for k, v in update_payload.items() if k in USER_EDITABLE_FIELDS}
        if not update_payload:
            raise HTTPException(403, "Not allowed")
    update_payload.pop("tenant_id", None)
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
