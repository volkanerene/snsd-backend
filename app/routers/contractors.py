from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_contractors(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        supabase.table("contractors")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)
    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_contractor(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)

    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    payload["created_by"] = user["id"]

    # Combine country_code and contact_phone if both exist
    country_code = payload.pop("country_code", None)
    contact_phone = payload.get("contact_phone", "")
    if country_code and contact_phone:
        payload["contact_phone"] = f"{country_code} {contact_phone}"

    res = supabase.table("contractors").insert(payload).execute()
    return ensure_response(res)


@router.get("/{contractor_id}")
async def get_contractor(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("contractors")
        .select("*")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.put("/{contractor_id}")
async def update_contractor(
    contractor_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)
    if not payload:
        raise HTTPException(400, "No fields to update")

    # Combine country_code and contact_phone if both exist
    country_code = payload.pop("country_code", None)
    contact_phone = payload.get("contact_phone", "")
    if country_code and contact_phone:
        payload["contact_phone"] = f"{country_code} {contact_phone}"

    res = (
        supabase.table("contractors")
        .update(payload)
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.delete("/{contractor_id}")
async def delete_contractor(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Delete a contractor and all associated data (cascade delete)"""
    require_admin(user)

    # 1) Verify contractor exists and belongs to tenant
    contractor_res = (
        supabase.table("contractors")
        .select("id, contact_email")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    contractor = ensure_response(contractor_res)
    if not contractor:
        raise HTTPException(404, "Contractor not found")

    try:
        # 1.5) Find and delete auth users associated with this contractor's profiles
        # Auth users are stored in profiles.id field (they reference auth.users.id)
        try:
            profiles_res = (
                supabase.table("profiles")
                .select("id, email")
                .eq("contractor_id", contractor_id)
                .execute()
            )
            profiles_data = ensure_response(profiles_res) or []
            if not isinstance(profiles_data, list):
                profiles_data = [profiles_data] if profiles_data else []

            # Extract auth user IDs (profiles.id = auth.users.id)
            auth_user_ids = [p.get("id") for p in profiles_data if p.get("id")]
            print(f"[delete_contractor] Found {len(auth_user_ids)} auth users to delete")

            # Delete each auth user
            for auth_user_id in auth_user_ids:
                try:
                    supabase.auth.admin.delete_user(auth_user_id)
                    print(f"[delete_contractor] Successfully deleted auth user: {auth_user_id}")
                except Exception as e:
                    print(f"[delete_contractor] Warning: Failed to delete auth user {auth_user_id}: {e}")
                    # Continue with other deletions even if auth user delete fails
        except Exception as e:
            print(f"[delete_contractor] Warning: Error processing auth users: {e}")
            # Continue with profile/submission deletions

        # 2) Delete all FRM32 submissions for this contractor
        try:
            supabase.table("frm32_submissions").delete().eq(
                "contractor_id", contractor_id
            ).eq("tenant_id", tenant_id).execute()
            print(f"[delete_contractor] Deleted FRM32 submissions for contractor {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting FRM32 submissions: {e}")
            raise

        # 3) Delete evren_gpt_session_contractors records
        try:
            session_res = supabase.table("evren_gpt_session_contractors").delete().eq(
                "contractor_id", contractor_id
            ).execute()
            print(f"[delete_contractor] Deleted session_contractors for contractor {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting session_contractors: {e}")
            raise

        # 4) Delete profile records for this contractor
        try:
            supabase.table("profiles").delete().eq(
                "contractor_id", contractor_id
            ).execute()
            print(f"[delete_contractor] Deleted profiles for contractor {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting profiles: {e}")
            raise

        # 5) Delete the contractor itself
        try:
            delete_res = (
                supabase.table("contractors")
                .delete()
                .eq("id", contractor_id)
                .eq("tenant_id", tenant_id)
                .execute()
            )
            ensure_response(delete_res)
            print(f"[delete_contractor] Deleted contractor record: {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting contractor record: {e}")
            raise

        return {"success": True, "message": "Contractor deleted successfully"}

    except Exception as e:
        print(f"[delete_contractor] Cascade delete failed: {str(e)}")
        raise HTTPException(500, f"Failed to delete contractor: {str(e)}")
