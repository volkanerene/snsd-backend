from fastapi import APIRouter, Body, Depends, HTTPException, Query
from typing import Optional

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_tenant_users(
    user=Depends(get_current_user),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    role_id: Optional[int] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all tenant-user relationships
    Super admin can see all, tenant admins can see their tenant
    """
    # Build query with joins to tenant and role (skip user join - auth.users not exposed by PostgREST)
    query = supabase.table("tenant_users").select(
        """
        *,
        tenant:tenant_id(id, name, slug, logo_url, status),
        role:role_id(id, name, slug)
        """
    )

    # If not super admin, filter to own tenants
    if user.get("role_id") != 1:
        # Get user's tenant IDs (all tenants they're a member of, regardless of role)
        user_tenants_res = (
            supabase.table("tenant_users")
            .select("tenant_id")
            .eq("user_id", user["id"])
            .execute()
        )
        user_tenant_ids = [t["tenant_id"] for t in user_tenants_res.data]

        if not user_tenant_ids:
            # Some roles (like contractors) may not have explicit tenant_user rows.
            # Fall back to the tenant on their profile so the UI can still display context.
            fallback_tenant_id = user.get("tenant_id")
            if fallback_tenant_id:
                tenant_res = (
                    supabase.table("tenants")
                    .select("id, name, slug, logo_url, status")
                    .eq("id", fallback_tenant_id)
                    .limit(1)
                    .execute()
                )
                tenant_data = tenant_res.data[0] if tenant_res.data else None
                if tenant_data:
                    virtual_relationship = {
                        "id": f"virtual-{user['id']}-{fallback_tenant_id}",
                        "tenant_id": fallback_tenant_id,
                        "user_id": user["id"],
                        "role_id": user.get("role_id"),
                        "status": "active",
                        "tenant": tenant_data,
                        "role": {
                            "id": user.get("role_id"),
                            "name": user.get("role_name") or "Member",
                            "slug": None
                        }
                    }
                    return [virtual_relationship]

            # User has no tenant memberships we can infer
            return []

        query = query.in_("tenant_id", user_tenant_ids)

    # Apply filters
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)

    if user_id:
        query = query.eq("user_id", user_id)

    if role_id:
        query = query.eq("role_id", role_id)

    if status:
        query = query.eq("status", status)

    # Apply pagination
    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)

    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_tenant_user(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Assign a user to a tenant with a role
    Requires: tenant_id, user_id, role_id
    """
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    role_id = payload.get("role_id", 4)  # Default to Contractor

    if not tenant_id or not user_id:
        raise HTTPException(400, "tenant_id and user_id are required")

    # Check if user has permission
    if user.get("role_id") != 1:  # Not super admin
        # Check if user is admin of this tenant
        admin_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .eq("role_id", 2)
            .limit(1)
            .execute()
        )

        if not admin_check.data:
            raise HTTPException(403, "Only tenant admins can add users")

    # Check if relationship already exists
    existing = (
        supabase.table("tenant_users")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        raise HTTPException(400, "User is already assigned to this tenant")

    # Check subscription limits
    current_users = (
        supabase.table("tenant_users")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .execute()
    )

    user_count = current_users.count or 0

    # Call subscription limit check function
    limit_check = supabase.rpc(
        "check_subscription_limit", {"p_tenant_id": tenant_id, "p_limit_type": "users", "p_current_count": user_count}
    ).execute()

    if not limit_check.data:
        raise HTTPException(403, "Subscription limit reached for users")

    # Create tenant_user relationship
    tenant_user_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role_id": role_id,
        "invited_by": user["id"],
        "status": "active",
    }

    res = supabase.table("tenant_users").insert(tenant_user_data).execute()
    return ensure_response(res)


@router.get("/{id}")
async def get_tenant_user(
    id: str,
    user=Depends(get_current_user),
):
    """Get tenant-user relationship details"""
    res = (
        supabase.table("tenant_users")
        .select(
            """
            *,
            tenant:tenant_id(id, name, status),
            user:user_id(id, email, full_name),
            role:role_id(id, name)
            """
        )
        .eq("id", id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Relationship not found")

    relationship = data[0] if isinstance(data, list) else data

    # Check permission
    if user.get("role_id") != 1:  # Not super admin
        # Check if user is admin of this tenant
        admin_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", relationship["tenant_id"])
            .eq("user_id", user["id"])
            .eq("role_id", 2)
            .limit(1)
            .execute()
        )

        if not admin_check.data:
            raise HTTPException(403, "Access denied")

    return relationship


@router.patch("/{id}")
async def update_tenant_user(
    id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Update tenant-user relationship (e.g., change role)"""
    # Get current relationship
    current = (
        supabase.table("tenant_users").select("*").eq("id", id).limit(1).execute()
    )

    if not current.data:
        raise HTTPException(404, "Relationship not found")

    tenant_id = current.data[0]["tenant_id"]

    # Check permission
    if user.get("role_id") != 1:  # Not super admin
        admin_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .eq("role_id", 2)
            .limit(1)
            .execute()
        )

        if not admin_check.data:
            raise HTTPException(403, "Only tenant admins can update roles")

    # Don't allow changing tenant_id or user_id
    payload.pop("tenant_id", None)
    payload.pop("user_id", None)
    payload.pop("id", None)
    payload.pop("created_at", None)

    res = supabase.table("tenant_users").update(payload).eq("id", id).execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Relationship not found")

    return data[0] if isinstance(data, list) else data


@router.delete("/{id}")
async def delete_tenant_user(
    id: str,
    user=Depends(get_current_user),
):
    """Remove user from tenant"""
    # Get current relationship
    current = (
        supabase.table("tenant_users").select("*").eq("id", id).limit(1).execute()
    )

    if not current.data:
        raise HTTPException(404, "Relationship not found")

    tenant_id = current.data[0]["tenant_id"]

    # Check permission
    if user.get("role_id") != 1:  # Not super admin
        admin_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .eq("role_id", 2)
            .limit(1)
            .execute()
        )

        if not admin_check.data:
            raise HTTPException(403, "Only tenant admins can remove users")

    res = supabase.table("tenant_users").delete().eq("id", id).execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Relationship not found")

    return {"message": "User removed from tenant successfully"}
