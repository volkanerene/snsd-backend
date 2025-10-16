from fastapi import APIRouter, Body, Depends, HTTPException, Query
from typing import List

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_roles(
    user=Depends(get_current_user),
    include_permissions: bool = Query(False, description="Include role permissions"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all roles, optionally with their permissions"""
    if include_permissions:
        res = (
            supabase.table("roles")
            .select(
                """
                *,
                role_permissions(
                    permission:permission_id(id, name, description, category)
                )
                """
            )
            .range(offset, offset + limit - 1)
            .execute()
        )
    else:
        res = (
            supabase.table("roles")
            .select("*")
            .range(offset, offset + limit - 1)
            .execute()
        )

    return ensure_response(res)


@router.post("/")
async def create_role(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Create a new role (admin only)"""
    require_admin(user)

    name = payload.get("name")
    description = payload.get("description")

    if not name:
        raise HTTPException(400, "name is required")

    role_data = {
        "name": name,
        "description": description,
    }

    res = supabase.table("roles").insert(role_data).execute()
    return ensure_response(res)


@router.get("/{role_id}")
async def get_role(
    role_id: int,
    user=Depends(get_current_user),
):
    """Get role details with permissions"""
    res = (
        supabase.table("roles")
        .select(
            """
            *,
            role_permissions(
                permission:permission_id(id, name, description, category)
            )
            """
        )
        .eq("id", role_id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Role not found")

    return data[0] if isinstance(data, list) else data


@router.patch("/{role_id}")
async def update_role(
    role_id: int,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Update role details (admin only)"""
    require_admin(user)

    # Don't allow changing id
    payload.pop("id", None)

    res = supabase.table("roles").update(payload).eq("id", role_id).execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Role not found")

    return data[0] if isinstance(data, list) else data


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    user=Depends(get_current_user),
):
    """Delete a role (admin only)"""
    require_admin(user)

    # Check if role is in use
    users_with_role = (
        supabase.table("profiles")
        .select("id", count="exact")
        .eq("role_id", role_id)
        .execute()
    )

    if users_with_role.count and users_with_role.count > 0:
        raise HTTPException(
            400, f"Cannot delete role: {users_with_role.count} users have this role"
        )

    res = supabase.table("roles").delete().eq("id", role_id).execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Role not found")

    return {"message": "Role deleted successfully"}


@router.get("/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    user=Depends(get_current_user),
):
    """Get all permissions assigned to a role"""
    res = (
        supabase.table("role_permissions")
        .select(
            """
            *,
            permission:permission_id(id, name, description, category)
            """
        )
        .eq("role_id", role_id)
        .execute()
    )

    return ensure_response(res)


@router.put("/{role_id}/permissions")
async def update_role_permissions(
    role_id: int,
    permission_ids: List[int] = Body(..., embed=True),
    user=Depends(get_current_user),
):
    """
    Update all permissions for a role
    Replaces existing permissions with the provided list
    """
    require_admin(user)

    # Check if role exists
    role_check = (
        supabase.table("roles").select("id").eq("id", role_id).limit(1).execute()
    )

    if not role_check.data:
        raise HTTPException(404, "Role not found")

    # Delete existing permissions
    supabase.table("role_permissions").delete().eq("role_id", role_id).execute()

    # Insert new permissions
    if permission_ids:
        new_permissions = [
            {"role_id": role_id, "permission_id": pid} for pid in permission_ids
        ]

        res = supabase.table("role_permissions").insert(new_permissions).execute()
        return ensure_response(res)

    return {"message": "Role permissions updated", "count": 0}


@router.post("/{role_id}/permissions/{permission_id}")
async def add_role_permission(
    role_id: int,
    permission_id: int,
    user=Depends(get_current_user),
):
    """Add a single permission to a role"""
    require_admin(user)

    # Check if already exists
    existing = (
        supabase.table("role_permissions")
        .select("id")
        .eq("role_id", role_id)
        .eq("permission_id", permission_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        raise HTTPException(400, "Permission already assigned to role")

    permission_data = {"role_id": role_id, "permission_id": permission_id}

    res = supabase.table("role_permissions").insert(permission_data).execute()
    return ensure_response(res)


@router.delete("/{role_id}/permissions/{permission_id}")
async def remove_role_permission(
    role_id: int,
    permission_id: int,
    user=Depends(get_current_user),
):
    """Remove a permission from a role"""
    require_admin(user)

    res = (
        supabase.table("role_permissions")
        .delete()
        .eq("role_id", role_id)
        .eq("permission_id", permission_id)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Permission not assigned to this role")

    return {"message": "Permission removed from role"}
