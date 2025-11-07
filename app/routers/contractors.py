from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user
from app.middleware.subscription import check_usage_limit

router = APIRouter()


@router.get("/")
async def list_contractors(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        supabase.table("contractors")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)
    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_contractor(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)

    # Check subscription limit before creating
    await check_usage_limit(tenant_id, "contractors", increment=1)

    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    payload["created_by"] = user["id"]

    res = supabase.table("contractors").insert(payload).execute()
    return ensure_response(res)


@router.get("/{contractor_id}")
async def get_contractor(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("contractors")
        .select("*")
        .eq("id", contractor_id)
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


@router.put("/{contractor_id}")
async def update_contractor(
    contractor_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)
    if not payload:
        raise HTTPException(400, "No fields to update")
    res = (
        supabase.table("contractors")
        .update(payload)
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.delete("/{contractor_id}")
async def delete_contractor(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Delete a contractor and all associated data (cascade delete)"""
    require_admin(user)

    # 1) Verify contractor exists and belongs to tenant
    contractor_res = (
        supabase.table("contractors")
        .select("id")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    contractor = ensure_response(contractor_res)
    if not contractor:
        raise HTTPException(404, "Contractor not found")

    try:
        # 2) Delete all FRM32 submissions for this contractor
        supabase.table("frm32_submissions").delete().eq(
            "contractor_id", contractor_id
        ).eq("tenant_id", tenant_id).execute()

        # 3) Delete evren_gpt_session_contractors records
        supabase.table("evren_gpt_session_contractors").delete().eq(
            "contractor_id", contractor_id
        ).execute()

        # 4) Delete profile records for this contractor
        supabase.table("profiles").delete().eq(
            "contractor_id", contractor_id
        ).execute()

        # 5) Delete the contractor itself
        delete_res = (
            supabase.table("contractors")
            .delete()
            .eq("id", contractor_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        ensure_response(delete_res)

        return {"success": True, "message": "Contractor deleted successfully"}

    except Exception as e:
        raise HTTPException(500, f"Failed to delete contractor: {str(e)}")
