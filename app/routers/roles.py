from fastapi import APIRouter, Depends, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_roles(
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    res = (
        supabase.table("public.roles")
        .select("*")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return ensure_response(res)
