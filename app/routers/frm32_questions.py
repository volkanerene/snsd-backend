from fastapi import APIRouter, Depends, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/questions")
async def list_questions(
    user=Depends(get_current_user),
    is_active: bool | None = Query(None),
):
    query = supabase.table("public.frm32_questions").select("*").order("position", asc=True)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    res = query.execute()
    return ensure_response(res)
