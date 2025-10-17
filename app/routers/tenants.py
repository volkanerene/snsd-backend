from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user
from app.middleware.subscription import get_tenant_usage_stats

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


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Get usage statistics for a tenant"""
    # Check permission - must be admin or belong to this tenant
    if user.get("role_id") not in [1, 2]:  # Not Super Admin or Admin
        # Check if user belongs to this tenant
        tenant_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )

        if not tenant_check.data:
            raise HTTPException(403, "Access denied")

    stats = await get_tenant_usage_stats(tenant_id)
    return stats


@router.get("/{tenant_id}/users")
async def get_tenant_users(
    tenant_id: str,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get all users in a tenant"""
    # Check permission
    if user.get("role_id") not in [1, 2]:  # Not Super Admin or Admin
        # Check if user belongs to this tenant
        tenant_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )

        if not tenant_check.data:
            raise HTTPException(403, "Access denied")

    res = (
        supabase.table("tenant_users")
        .select(
            """
            *,
            user:user_id(id, email, full_name, avatar_url, status),
            role:role_id(id, name)
            """
        )
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
        .order("joined_at", desc=True)
        .execute()
    )

    return ensure_response(res)


@router.get("/{tenant_id}/statistics")
async def get_tenant_statistics(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Get tenant statistics dashboard"""
    require_admin(user)

    # Get counts
    users_count = (
        supabase.table("tenant_users")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .execute()
        .count or 0
    )

    contractors_count = (
        supabase.table("contractors")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .execute()
        .count or 0
    )

    evaluations_count = (
        supabase.table("frm32_submissions")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .execute()
        .count or 0
    )

    # Get recent activity
    recent_evaluations = (
        supabase.table("frm32_submissions")
        .select("id, status, created_at, contractor:contractor_id(name)")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data or []
    )

    return {
        "tenant_id": tenant_id,
        "counts": {
            "users": users_count,
            "contractors": contractors_count,
            "evaluations": evaluations_count,
        },
        "recent_activity": {
            "evaluations": recent_evaluations,
        },
    }
