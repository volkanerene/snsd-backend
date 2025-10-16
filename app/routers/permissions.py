from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_permissions(
    user=Depends(get_current_user),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: bool = Query(True, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all available permissions, optionally filtered by category"""
    query = supabase.table("permissions").select("*")

    if category:
        query = query.eq("category", category)

    query = query.eq("is_active", is_active)

    query = query.range(offset, offset + limit - 1).order("category", desc=False).order("name", desc=False)

    res = query.execute()
    return ensure_response(res)


@router.get("/categories")
async def list_permission_categories(
    user=Depends(get_current_user),
):
    """Get all permission categories"""
    res = (
        supabase.table("permissions")
        .select("category")
        .eq("is_active", True)
        .execute()
    )

    data = ensure_response(res)

    # Extract unique categories
    categories = list(set([p["category"] for p in data if p.get("category")]))
    categories.sort()

    return {"categories": categories}


@router.get("/my")
async def get_my_permissions(
    user=Depends(get_current_user),
):
    """Get current user's permissions based on their role"""
    role_id = user.get("role_id")

    if not role_id:
        return []

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

    data = ensure_response(res)

    # Extract just the permission objects
    permissions = [item["permission"] for item in data if item.get("permission")]

    return permissions


@router.get("/{permission_id}")
async def get_permission(
    permission_id: int,
    user=Depends(get_current_user),
):
    """Get permission details"""
    res = (
        supabase.table("permissions")
        .select("*")
        .eq("id", permission_id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(404, "Permission not found")

    return data[0] if isinstance(data, list) else data
