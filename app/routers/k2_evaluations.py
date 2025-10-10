from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/evaluations")
async def list_evaluations(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    submission_id: str | None = Query(None),
):
    if not submission_id:
        raise HTTPException(400, "submission_id required")
    res = (
        supabase.table("public.k2_evaluations")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("submission_id", submission_id)
        .execute()
    )
    return ensure_response(res)
