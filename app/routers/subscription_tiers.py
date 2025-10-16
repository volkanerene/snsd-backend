from fastapi import APIRouter, Body, Depends, HTTPException, Query
from typing import Optional

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_tiers(
    user=Depends(get_current_user),
    is_active: bool = Query(True, description="Filter by active status"),
):
    """List all subscription tiers"""
    query = supabase.table("subscription_tiers").select("*").eq("is_active", is_active).order("sort_order")

    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_tier(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Create a new subscription tier (super admin only)"""
    require_admin(user)

    # Only super admin can create tiers
    if user.get("role_id") != 1:
        raise HTTPException(403, "Only super admins can create subscription tiers")

    res = supabase.table("subscription_tiers").insert(payload).execute()
    return ensure_response(res)


@router.get("/{tier_id}")
async def get_tier(
    tier_id: int,
    user=Depends(get_current_user),
):
    """Get tier details"""
    res = (
        supabase.table("subscription_tiers")
        .select("*")
        .eq("id", tier_id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Tier not found")

    return data[0] if isinstance(data, list) else data


@router.patch("/{tier_id}")
async def update_tier(
    tier_id: int,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Update tier details (super admin only)"""
    require_admin(user)

    if user.get("role_id") != 1:
        raise HTTPException(403, "Only super admins can update tiers")

    payload.pop("id", None)

    res = supabase.table("subscription_tiers").update(payload).eq("id", tier_id).execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Tier not found")

    return data[0] if isinstance(data, list) else data


@router.get("/{tier_id}/features")
async def get_tier_features(
    tier_id: int,
    user=Depends(get_current_user),
):
    """Get features for a specific tier"""
    res = (
        supabase.table("subscription_tiers")
        .select("features, max_users, max_evaluations_per_month, max_contractors, max_storage_gb")
        .eq("id", tier_id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Tier not found")

    return data[0] if isinstance(data, list) else data


# Tenant Subscriptions


@router.get("/subscriptions")
async def list_subscriptions(
    user=Depends(get_current_user),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List tenant subscriptions"""
    query = supabase.table("tenant_subscriptions").select(
        """
        *,
        tenant:tenant_id(id, name),
        tier:tier_id(id, name, display_name)
        """
    )

    # If not super admin, filter to own tenants
    if user.get("role_id") != 1:
        user_tenants_res = (
            supabase.table("tenant_users")
            .select("tenant_id")
            .eq("user_id", user["id"])
            .execute()
        )
        tenant_ids = [t["tenant_id"] for t in user_tenants_res.data]

        if not tenant_ids:
            return []

        query = query.in_("tenant_id", tenant_ids)

    if tenant_id:
        query = query.eq("tenant_id", tenant_id)

    if status:
        query = query.eq("status", status)

    query = query.range(offset, offset + limit - 1).order("starts_at", desc=True)

    res = query.execute()
    return ensure_response(res)


@router.post("/subscriptions")
async def create_subscription(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Create or update tenant subscription (super admin only)"""
    require_admin(user)

    if user.get("role_id") != 1:
        raise HTTPException(403, "Only super admins can manage subscriptions")

    res = supabase.table("tenant_subscriptions").insert(payload).execute()
    return ensure_response(res)


@router.get("/subscriptions/current/{tenant_id}")
async def get_current_subscription(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Get current active subscription for a tenant"""
    # Check permission
    if user.get("role_id") != 1:
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

    # Get current active subscription
    res = (
        supabase.table("tenant_subscriptions")
        .select(
            """
            *,
            tier:tier_id(*)
            """
        )
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .order("starts_at", desc=True)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        return {"message": "No active subscription", "tenant_id": tenant_id}

    return data[0] if isinstance(data, list) else data


@router.get("/usage/{tenant_id}")
async def get_tenant_usage(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Get current usage for a tenant"""
    # Check permission
    if user.get("role_id") != 1:
        tenant_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .eq("role_id", 2)  # Must be admin
            .limit(1)
            .execute()
        )

        if not tenant_check.data:
            raise HTTPException(403, "Access denied")

    # Get usage via function
    users_count = supabase.rpc("get_current_usage", {"p_tenant_id": tenant_id, "p_usage_type": "users"}).execute()
    evaluations_count = supabase.rpc(
        "get_current_usage", {"p_tenant_id": tenant_id, "p_usage_type": "evaluations"}
    ).execute()
    contractors_count = supabase.rpc(
        "get_current_usage", {"p_tenant_id": tenant_id, "p_usage_type": "contractors"}
    ).execute()

    return {
        "tenant_id": tenant_id,
        "users_count": users_count.data or 0,
        "evaluations_count": evaluations_count.data or 0,
        "contractors_count": contractors_count.data or 0,
    }
