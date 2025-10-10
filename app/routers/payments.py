from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_payments(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        supabase.table("public.payments")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)
    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_payment(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)
    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    if not payload.get("amount"):
        raise HTTPException(400, "amount required")
    res = supabase.table("public.payments").insert(payload).execute()
    return ensure_response(res)


@router.get("/{payment_id}")
async def get_payment(
    payment_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("public.payments")
        .select("*")
        .eq("id", payment_id)
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


@router.post("/webhook")
async def payments_webhook(
    payload: dict = Body(...),
    signature: str | None = Header(None, alias="X-Signature"),
):
    # TODO: replace with real signature verification logic
    return {"received": True, "signature_validated": bool(signature)}
