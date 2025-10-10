from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/by-submission/{submission_id}")
async def get_final_score(
    submission_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("public.final_scores")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("submission_id", submission_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data
