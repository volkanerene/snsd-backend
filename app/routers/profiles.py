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

    print(f"\n[/profiles/me] DEBUG: user object = {user}")
    print(f"[/profiles/me] DEBUG: user_id = {user_id}")

    res = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)

    # Handle list vs dict response
    if data and isinstance(data, list):
        data = data[0] if data else None

    # Check if profile exists but is INCOMPLETE (NULL critical fields)
    # This happens when Supabase auto-creates an empty profile on auth user creation
    if data:
        profile_missing_email = not data.get("email")
        missing_tenant = not data.get("tenant_id")
        missing_contractor = not data.get("contractor_id")
        # Only treat as incomplete if email missing, or both tenant & contractor missing
        is_incomplete = profile_missing_email or (missing_tenant and missing_contractor)

        print(f"[/profiles/me] Profile found, incomplete={is_incomplete}")
        if is_incomplete:
            print(f"[/profiles/me] Profile exists but is incomplete (NULL values), treating as missing to populate it")
            data = None  # Treat as missing so we can populate with correct values

    if not data:
        print(f"[/profiles/me] Profile not found or incomplete for user_id={user_id}, attempting auto-creation")

        # Profile doesn't exist - try to create a default one
        # This handles cases where profile creation failed during signup
        user_email = user.get("email", "")
        print(f"[/profiles/me] User email from token: '{user_email}'")

        # Try to find contractor info (optional - only for contractor users)
        # Admin users won't have a contractor entry and that's OK
        contractor_id = None
        tenant_id = None

        try:
            print(f"[/profiles/me] Querying contractors by contact_email = '{user_email}'")
            # Query contractors by contact_email
            contractor_res = (
                supabase.table("contractors")
                .select("id, tenant_id, contact_email")
                .eq("contact_email", user_email)
                .limit(1)
                .execute()
            )

            print(f"[/profiles/me] Contractor query result: {contractor_res}")
            print(f"[/profiles/me] Contractor data: {contractor_res.data if contractor_res else 'None'}")

            if contractor_res and contractor_res.data:
                if isinstance(contractor_res.data, list) and len(contractor_res.data) > 0:
                    contractor = contractor_res.data[0]
                    contractor_id = contractor.get("id")
                    tenant_id = contractor.get("tenant_id")
                    print(f"[/profiles/me] Found contractor: id={contractor_id}, tenant_id={tenant_id}")
                elif isinstance(contractor_res.data, dict):
                    contractor_id = contractor_res.data.get("id")
                    tenant_id = contractor_res.data.get("tenant_id")
                    print(f"[/profiles/me] Found contractor (dict): id={contractor_id}, tenant_id={tenant_id}")
            else:
                print(f"[/profiles/me] No contractor found for email '{user_email}' - assuming admin/non-contractor user")

        except Exception as e:
            print(f"[/profiles/me] Warning: Error during contractor lookup: {e}")
            print(f"[/profiles/me] Assuming this is an admin/non-contractor user and continuing")
            # Don't raise error - contractor lookup is optional

        # Log the result
        print(f"[/profiles/me] Contractor lookup result: contractor_id={contractor_id}, tenant_id={tenant_id}")
        print(f"[/profiles/me] Proceeding to create profile (contractor_id and tenant_id are optional for non-contractor users)")

        # Now create or update profile
        # For contractors: includes tenant_id and contractor_id
        # For admins/non-contractors: just basic profile fields
        try:
            profile_data = {
                "email": user_email,
                "full_name": user_email.split("@")[0],
                "is_active": True,
            }
            # Only include contractor fields if they were found
            if tenant_id:
                profile_data["tenant_id"] = tenant_id
            if contractor_id:
                profile_data["contractor_id"] = contractor_id

            print(f"[/profiles/me] Attempting to populate profile with data: {profile_data}")

            # Try UPDATE first (in case profile exists with NULL values)
            # If profile doesn't exist, UPDATE will return no rows and we'll then INSERT
            update_res = (
                supabase.table("profiles")
                .update(profile_data)
                .eq("id", user_id)
                .execute()
            )
            updated_data = ensure_response(update_res)

            if updated_data:
                print(f"[/profiles/me] ✅ Profile updated successfully")
                if isinstance(updated_data, list):
                    return updated_data[0]
                return updated_data

            # If UPDATE returned nothing, profile doesn't exist - INSERT instead
            print(f"[/profiles/me] Profile doesn't exist, inserting new profile...")
            profile_data["id"] = user_id

            create_res = supabase.table("profiles").insert(profile_data).execute()

            if create_res and create_res.data:
                print(f"[/profiles/me] ✅ Profile created successfully")
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
            print(f"[/profiles/me] ERROR: Failed to populate profile: {str(e)}")
            # If profile operations fail, it's likely due to foreign key or RLS issues
            raise HTTPException(
                status_code=500,
                detail=f"Failed to auto-create/update profile: {str(e)}"
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
