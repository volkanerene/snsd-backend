from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/scores")
async def list_scores(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    submission_id: str | None = Query(None),
):
    if not submission_id:
        raise HTTPException(400, "submission_id required")
    res = (
        supabase.table("frm32_scores")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("submission_id", submission_id)
        .execute()
    )
    return ensure_response(res)
