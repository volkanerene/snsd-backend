from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user
from app.middleware.subscription import get_tenant_usage_stats

router = APIRouter()

def _resolve_tenant_id(requested_tenant_id: str, user: dict) -> str:
    """
    Translate special identifiers like 'my' to a concrete tenant id.
    """
    if requested_tenant_id == "my":
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(400, "User is not associated with any tenant")
        return tenant_id
    return requested_tenant_id


def _ensure_tenant_access(tenant_id: str, user: dict) -> None:
    """
    Ensure the current user has access to the provided tenant id.
    Super admin (role_id == 1) is always allowed.
    Company admins (role_id == 2) must belong to the tenant.
    Other roles are denied unless explicitly a member of the tenant.
    """
    role_id = user.get("role_id")
    if role_id == 1:
        return  # Super admin

    membership = (
        supabase.table("tenant_users")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )

    if not membership.data:
        raise HTTPException(403, "Access denied")


def _hydrate_tenant_user_rows(rows: list[dict]) -> list[dict]:
    """
    Attach user and role metadata to tenant_user rows without relying on Supabase FK joins.
    """
    if not rows:
        return []

    user_ids = list({row["user_id"] for row in rows if row.get("user_id")})
    role_ids = list({row["role_id"] for row in rows if row.get("role_id")})

    user_map = {}
    if user_ids:
        profile_res = (
            supabase.table("profiles")
            .select("id, email, full_name, avatar_url, status, department, job_title")
            .in_("id", user_ids)
            .execute()
        )
        for profile in profile_res.data or []:
            user_map[profile["id"]] = profile

    role_map = {}
    if role_ids:
        role_res = (
            supabase.table("roles")
            .select("id, name, level")
            .in_("id", role_ids)
            .execute()
        )
        for role in role_res.data or []:
            role_map[role["id"]] = role

    enriched: list[dict] = []
    for row in rows:
        profile = user_map.get(row.get("user_id"))
        role = role_map.get(row.get("role_id"))

        if profile:
            # Mirror fields expected by frontend team view
            row.setdefault("full_name", profile.get("full_name"))
            row.setdefault("email", profile.get("email"))
            row.setdefault("avatar_url", profile.get("avatar_url"))
            row.setdefault("department", profile.get("department"))
            row.setdefault("job_title", profile.get("job_title"))

            # Prefer profile status for active flag, fallback to tenant_user status
            status = profile.get("status")
            if status is not None:
                row["is_active"] = status == "active"
            else:
                row["is_active"] = row.get("status") == "active"
        else:
            row.setdefault("is_active", row.get("status") == "active")

        if role:
            row["role"] = role

        # Ensure joined_at present for UI. Fallback to created_at.
        row.setdefault("joined_at", row.get("joined_at") or row.get("created_at"))

        enriched.append(row)

    return enriched


def _build_tenant_statistics_payload(tenant_id: str) -> dict:
    """
    Compute tenant level statistics shared across endpoints.
    """
    members_res = (
        supabase.table("tenant_users")
        .select("user_id, role_id, status")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    members = members_res.data or []

    total_members = len(members)
    active_members = sum(1 for member in members if member.get("status") == "active")
    inactive_members = total_members - active_members

    by_role: dict[str, int] = {}
    for member in members:
        role_id = member.get("role_id")
        if role_id is None:
            continue
        key = str(role_id)
        by_role[key] = by_role.get(key, 0) + 1

    contractors_count = (
        supabase.table("contractors")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .execute()
        .count
        or 0
    )

    evaluations_count = (
        supabase.table("frm32_submissions")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .execute()
        .count
        or 0
    )

    recent_evaluations = (
        supabase.table("frm32_submissions")
        .select("id, status, created_at, contractor:contractor_id(name)")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )

    counts = {
        "members": total_members,
        "users": total_members,  # backward compatibility
        "contractors": contractors_count,
        "evaluations": evaluations_count,
    }

    return {
        "tenant_id": tenant_id,
        "total_members": total_members,
        "active_members": active_members,
        "inactive_members": inactive_members,
        "by_role": by_role,
        "counts": counts,
        "recent_evaluations": recent_evaluations,
        "recent_activity": {
            "evaluations": recent_evaluations,
        },
    }


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
    tenant_id = _resolve_tenant_id(tenant_id, user)
    _ensure_tenant_access(tenant_id, user)

    query = (
        supabase.table("tenant_users")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("joined_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    data = ensure_response(query)
    if not data:
        return []

    return _hydrate_tenant_user_rows(data)


@router.get("/my/users")
async def get_my_tenant_users(
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Convenience endpoint for the current tenant's users"""
    tenant_id = _resolve_tenant_id("my", user)
    _ensure_tenant_access(tenant_id, user)

    query = (
        supabase.table("tenant_users")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("joined_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    data = ensure_response(query)
    if not data:
        return []

    return _hydrate_tenant_user_rows(data)


@router.get("/{tenant_id}/statistics")
async def get_tenant_statistics(
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Get tenant statistics dashboard"""
    require_admin(user)
    tenant_id = _resolve_tenant_id(tenant_id, user)
    _ensure_tenant_access(tenant_id, user)
    return _build_tenant_statistics_payload(tenant_id)


@router.get("/my/stats")
async def get_my_tenant_statistics(
    user=Depends(get_current_user),
):
    """Get statistics for the current user's tenant"""
    require_admin(user)
    tenant_id = _resolve_tenant_id("my", user)
    _ensure_tenant_access(tenant_id, user)
    return _build_tenant_statistics_payload(tenant_id)
