from fastapi import APIRouter, Body, Depends, HTTPException

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("/invites")
async def create_invite(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)
    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    if not payload.get("email"):
        raise HTTPException(400, "email required")
    if not payload.get("invitation_token"):
        raise HTTPException(400, "invitation_token required")
    res = supabase.table("frm35_invites").insert(payload).execute()
    return ensure_response(res)


@router.get("/invites/{invite_id}")
async def get_invite(
    invite_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("frm35_invites")
        .select("*")
        .eq("id", invite_id)
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


@router.post("/invites/{invite_id}/accept")
async def accept_invite(
    invite_id: str,
    payload: dict = Body(...),
):
    token = payload.get("invitation_token") if payload else None
    if not token:
        raise HTTPException(400, "invitation_token required")
    lookup = (
        supabase.table("frm35_invites")
        .select("*")
        .eq("id", invite_id)
        .eq("invitation_token", token)
        .limit(1)
        .execute()
    )
    data = ensure_response(lookup)
    if not data:
        raise HTTPException(404, "Invalid invite token")
    invite = data[0] if isinstance(data, list) else data
    update = (
        supabase.table("frm35_invites")
        .update({"status": "accepted"})
        .eq("id", invite_id)
        .eq("invitation_token", token)
        .execute()
    )
    updated = ensure_response(update)
    if updated:
        if isinstance(updated, list):
            invite = updated[0]
        else:
            invite = updated
    return invite
