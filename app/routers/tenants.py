from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_tenants(
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all tenants (admin only)"""
    require_admin(user)

    res = (
        supabase.table("tenants")
        .select("*")
        .range(offset, offset + limit - 1)
        .order("created_at", desc=True)
        .execute()
    )
    return ensure_response(res)


@router.post("/")
async def create_tenant(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    require_admin(user)
    res = supabase.table("tenants").insert(payload).execute()
    return ensure_response(res)


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Get a specific tenant (admin only)"""
    require_admin(user)

    res = (
        supabase.table("tenants")
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


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Update a tenant (admin only)"""
    require_admin(user)

    res = supabase.table("tenants").update(payload).eq("id", tenant_id).execute()
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.post("/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Activate a tenant (admin only)"""
    require_admin(user)

    res = (
        supabase.table("tenants")
        .update({"status": "active"})
        .eq("id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Tenant not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.post("/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Suspend a tenant (admin only)"""
    require_admin(user)

    res = (
        supabase.table("tenants")
        .update({"status": "suspended"})
        .eq("id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Tenant not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Delete a tenant (admin only) - sets status to inactive"""
    require_admin(user)

    res = (
        supabase.table("tenants")
        .update({"status": "inactive"})
        .eq("id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Tenant not found")

    return {"message": "Tenant deleted successfully", "tenant_id": tenant_id}
