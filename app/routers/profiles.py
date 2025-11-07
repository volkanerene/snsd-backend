from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()

SAFE_PROFILE_FIELDS = {"full_name", "phone", "avatar_url", "metadata"}
ADMIN_PROFILE_FIELDS = SAFE_PROFILE_FIELDS | {"role_id", "is_active", "department", "job_title"}


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(400, "User id missing in token")
    res = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        # Profile doesn't exist - try to create a default one
        # This handles cases where profile creation failed during signup
        user_email = user.get("email", "")

        # CRITICAL: We MUST find the contractor to get tenant_id
        # Without tenant_id, the profile will cause 403/400 errors on all endpoints
        contractor_id = None
        tenant_id = None

        try:
            # Query contractors by contact_email
            contractor_res = (
                supabase.table("contractors")
                .select("id, tenant_id, contact_email")
                .eq("contact_email", user_email)
                .limit(1)
                .execute()
            )

            if contractor_res and contractor_res.data:
                if isinstance(contractor_res.data, list) and len(contractor_res.data) > 0:
                    contractor = contractor_res.data[0]
                    contractor_id = contractor.get("id")
                    tenant_id = contractor.get("tenant_id")
                elif isinstance(contractor_res.data, dict):
                    contractor_id = contractor_res.data.get("id")
                    tenant_id = contractor_res.data.get("tenant_id")

        except Exception as e:
            # If we can't query contractors, profile creation will fail anyway
            # Better to raise error now with clear message
            raise HTTPException(
                status_code=500,
                detail=f"Failed to lookup contractor information for email {user_email}: {str(e)}"
            )

        # If contractor not found, we CANNOT create a valid profile
        # Without tenant_id, all endpoints will fail with 403/400
        if not contractor_id or not tenant_id:
            raise HTTPException(
                status_code=404,
                detail=f"Contractor not found for email {user_email}. Please contact support to link your account."
            )

        # Now create profile with valid tenant_id and contractor_id
        try:
            default_profile = {
                "id": user_id,
                "email": user_email,
                "full_name": user_email.split("@")[0],
                "is_active": True,
                "tenant_id": tenant_id,
                "contractor_id": contractor_id,
            }

            create_res = supabase.table("profiles").insert(default_profile).execute()

            if create_res and create_res.data:
                created_data = create_res.data
                if isinstance(created_data, list) and len(created_data) > 0:
                    return created_data[0]
                elif isinstance(created_data, dict):
                    return created_data

            # If insert succeeded but no data returned, something is wrong
            raise HTTPException(
                status_code=500,
                detail="Profile creation succeeded but returned no data"
            )

        except HTTPException:
            raise
        except Exception as e:
            # If profile insert fails, it's likely due to foreign key or RLS issues
            raise HTTPException(
                status_code=500,
                detail=f"Failed to auto-create profile: {str(e)}"
            )
    if isinstance(data, list):
        return data[0]
    return data


@router.put("/me")
async def update_me(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(400, "User id missing in token")
    update_payload = {k: v for k, v in payload.items() if k in SAFE_PROFILE_FIELDS}
    if not update_payload:
        raise HTTPException(400, "No valid fields to update")
    res = (
        supabase.table("profiles")
        .update(update_payload)
        .eq("id", user_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


# Admin endpoints
@router.get("/")
async def list_profiles(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    role_id: int | None = Query(None),
    is_active: bool | None = Query(None),
):
    """List all profiles in tenant (admin only)"""
    require_admin(user)

    query = supabase.table("profiles").select("*").eq("tenant_id", tenant_id)

    if role_id is not None:
        query = query.eq("role_id", role_id)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
    res = query.execute()
    return ensure_response(res)


@router.get("/{profile_id}")
async def get_profile(
    profile_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Get a specific profile by ID (admin only)"""
    require_admin(user)

    res = (
        supabase.table("profiles")
        .select("*")
        .eq("id", profile_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Profile not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.patch("/{profile_id}")
async def update_profile(
    profile_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Update a profile (admin only)"""
    require_admin(user)

    # Filter allowed fields for admin
    update_payload = {k: v for k, v in payload.items() if k in ADMIN_PROFILE_FIELDS}
    if not update_payload:
        raise HTTPException(400, "No valid fields to update")

    res = (
        supabase.table("profiles")
        .update(update_payload)
        .eq("id", profile_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Profile not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.post("/{profile_id}/activate")
async def activate_profile(
    profile_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Activate a profile (admin only)"""
    require_admin(user)

    res = (
        supabase.table("profiles")
        .update({"is_active": True})
        .eq("id", profile_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Profile not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.post("/{profile_id}/deactivate")
async def deactivate_profile(
    profile_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Deactivate a profile (admin only)"""
    require_admin(user)

    res = (
        supabase.table("profiles")
        .update({"is_active": False})
        .eq("id", profile_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Profile not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Delete a profile (admin only) - soft delete by setting is_active to False"""
    require_admin(user)

    # Prevent deleting self
    user_id = user.get("user_id")
    if user_id == profile_id:
        raise HTTPException(400, "Cannot delete your own profile")

    # Soft delete by deactivating
    res = (
        supabase.table("profiles")
        .update({"is_active": False})
        .eq("id", profile_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Profile not found")

    return {"message": "Profile deleted successfully", "profile_id": profile_id}
