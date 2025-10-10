from fastapi import APIRouter, Body, Depends, HTTPException

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_tenants(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = supabase.table("public.tenants").select("*").eq("id", tenant_id).execute()
    data = ensure_response(res)
    return data


@router.post("/")
async def create_tenant(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    require_admin(user)
    res = supabase.table("public.tenants").insert(payload).execute()
    return ensure_response(res)


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    user=Depends(get_current_user),
    header_tenant_id: str = Depends(require_tenant),
):
    if tenant_id != header_tenant_id:
        raise HTTPException(403, "Not allowed")
    res = (
        supabase.table("public.tenants")
        .select("*")
        .eq("id", tenant_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    header_tenant_id: str = Depends(require_tenant),
):
    require_admin(user)
    if tenant_id != header_tenant_id:
        raise HTTPException(403, "Not allowed")
    res = supabase.table("public.tenants").update(payload).eq("id", tenant_id).execute()
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data
