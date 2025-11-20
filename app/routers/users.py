from fastapi import APIRouter, Body, Depends, HTTPException, Query
from typing import Optional, List

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_users(
    user=Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search by email or name"),
    role_id: Optional[int] = Query(None, description="Filter by role"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all users (admin only)
    Supports filtering by role, tenant, status, and search
    """
    require_admin(user)

    # Build query with joins
    query = supabase.table("profiles").select(
        """
        *,
        roles(id, name),
        tenant:tenant_id(id, name)
        """
    )

    # Apply filters
    if role_id:
        query = query.eq("role_id", role_id)

    if tenant_id:
        query = query.eq("tenant_id", tenant_id)

    if status:
        query = query.eq("status", status)

    if search:
        # Search in email or full_name
        query = query.or_(f"email.ilike.%{search}%,full_name.ilike.%{search}%")

    # Apply pagination
    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)

    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_user(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Create a new user with Supabase Auth
    Requires: email, password, full_name, role_id
    Optional: tenant_id, phone, metadata
    """
    require_admin(user)

    email = payload.get("email")
    password = payload.get("password")
    full_name = payload.get("full_name")
    role_id = payload.get("role_id", 4)  # Default to Contractor
    tenant_id = payload.get("tenant_id")

    if not email or not password:
        raise HTTPException(400, "email and password are required")

    # Create user in Supabase Auth
    try:
        auth_res = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,  # Auto-confirm email
                "user_metadata": {
                    "full_name": full_name,
                    "role_id": role_id,
                },
            }
        )

        if not auth_res.user:
            raise HTTPException(500, "Failed to create user in auth system")

        user_id = auth_res.user.id

        # Create or update profile (Supabase may auto-create an empty shell,
        # so using upsert avoids duplicate key errors on id)
        profile_data = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role_id": role_id,
            "tenant_id": tenant_id,
            "status": "active",
        }

        # Add optional fields
        if payload.get("phone"):
            profile_data["phone"] = payload["phone"]

        profile_res = (
            supabase.table("profiles")
            .upsert(profile_data, on_conflict="id")
            .execute()
        )

        # If tenant_id provided, create tenant_users entry
        if tenant_id:
            tenant_user_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role_id": role_id,
                "invited_by": user["id"],
            }
            supabase.table("tenant_users").insert(tenant_user_data).execute()

        return ensure_response(profile_res)

    except Exception as e:
        # If profile creation fails, try to clean up auth user
        if "user_id" in locals():
            try:
                supabase.auth.admin.delete_user(user_id)
            except:
                pass
        raise HTTPException(500, f"Failed to create user: {str(e)}")


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    user=Depends(get_current_user),
):
    """Get user details by ID"""
    require_admin(user)

    res = (
        supabase.table("profiles")
        .select(
            """
            *,
            roles(id, name),
            tenant:tenant_id(id, name)
            """
        )
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "User not found")

    return data[0] if isinstance(data, list) else data


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Update user information"""
    require_admin(user)

    # Don't allow changing id or created_at
    payload.pop("id", None)
    payload.pop("created_at", None)

    # Update profile
    res = supabase.table("profiles").update(payload).eq("id", user_id).execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "User not found")

    return data[0] if isinstance(data, list) else data


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    user=Depends(get_current_user),
):
    """
    Permanently delete a user and all their data
    - Removes from Supabase Auth
    - Deletes profile record
    - Deletes tenant_users associations
    """
    require_admin(user)

    try:
        # Delete from Supabase Auth first
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception as auth_error:
            print(f"[Delete User] Auth deletion error: {auth_error}")
            # Continue with DB deletion even if auth fails

        # Delete tenant_users associations
        try:
            supabase.table("tenant_users").delete().eq("user_id", user_id).execute()
        except Exception as tenant_error:
            print(f"[Delete User] Tenant association deletion error: {tenant_error}")

        # Delete profile record
        res = (
            supabase.table("profiles")
            .delete()
            .eq("id", user_id)
            .execute()
        )

        # Check if deletion was successful
        if res.count == 0:
            raise HTTPException(404, "User not found")

        return {"message": "User permanently deleted", "user_id": user_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to delete user: {str(e)}")


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: str,
    user=Depends(get_current_user),
):
    """Activate a user"""
    require_admin(user)

    res = (
        supabase.table("profiles")
        .update({"status": "active"})
        .eq("id", user_id)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "User not found")

    return data[0] if isinstance(data, list) else data


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    user=Depends(get_current_user),
):
    """Send password reset email to user"""
    require_admin(user)

    # Get user email
    profile_res = (
        supabase.table("profiles").select("email").eq("id", user_id).limit(1).execute()
    )

    profile_data = ensure_response(profile_res)
    if not profile_data:
        raise HTTPException(404, "User not found")

    email = (
        profile_data[0]["email"]
        if isinstance(profile_data, list)
        else profile_data["email"]
    )

    try:
        # Trigger password reset email
        supabase.auth.reset_password_email(email)
        return {"message": "Password reset email sent", "email": email}
    except Exception as e:
        raise HTTPException(500, f"Failed to send reset email: {str(e)}")


@router.get("/{user_id}/tenants")
async def get_user_tenants(
    user_id: str,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get all tenants a user belongs to"""
    require_admin(user)

    res = (
        supabase.table("tenant_users")
        .select(
            """
            *,
            tenant:tenant_id(id, name, status),
            role:role_id(id, name)
            """
        )
        .eq("user_id", user_id)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return ensure_response(res)


@router.post("/{user_id}/tenants")
async def add_user_to_tenant(
    user_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Add user to a tenant with a specific role"""
    require_admin(user)

    tenant_id = payload.get("tenant_id")
    role_id = payload.get("role_id", 4)  # Default to Contractor

    if not tenant_id:
        raise HTTPException(400, "tenant_id is required")

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

    # Create tenant_user relationship
    tenant_user_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role_id": role_id,
        "invited_by": user["id"],
    }

    res = supabase.table("tenant_users").insert(tenant_user_data).execute()
    return ensure_response(res)


@router.delete("/{user_id}/tenants/{tenant_id}")
async def remove_user_from_tenant(
    user_id: str,
    tenant_id: str,
    user=Depends(get_current_user),
):
    """Remove user from a tenant"""
    require_admin(user)

    res = (
        supabase.table("tenant_users")
        .delete()
        .eq("tenant_id", tenant_id)
        .eq("user_id", user_id)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "User-tenant relationship not found")

    return {"message": "User removed from tenant successfully"}
