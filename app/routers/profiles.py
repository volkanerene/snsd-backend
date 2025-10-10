from fastapi import APIRouter, Body, Depends, HTTPException

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user

router = APIRouter()

SAFE_PROFILE_FIELDS = {"full_name", "phone", "avatar_url", "metadata"}


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(400, "User id missing in token")
    res = (
        supabase.table("public.profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
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
        supabase.table("public.profiles")
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
