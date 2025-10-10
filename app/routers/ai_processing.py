from fastapi import APIRouter, Depends, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/processing/status")
async def list_processing_status(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
):
    query = (
        supabase.table("public.ai_processing_status")
        .select("*")
        .eq("tenant_id", tenant_id)
    )
    if resource_type:
        query = query.eq("resource_type", resource_type)
    if resource_id:
        query = query.eq("resource_id", resource_id)
    res = query.execute()
    data = ensure_response(res)
    if not data:
        return data
    status_list = data if isinstance(data, list) else [data]
    status_ids = [item.get("id") for item in status_list if item.get("id")]
    if status_ids:
        raw_res = (
            supabase.table("public.ai_raw_outputs")
            .select("status_id,id,created_at")
            .in_("status_id", status_ids)
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .execute()
        )
        raw_data = ensure_response(raw_res) or []
        seen = set()
        extras = {}
        for item in raw_data:
            status_id = item.get("status_id")
            if status_id and status_id not in seen:
                extras[status_id] = {
                    "last_raw_output_id": item.get("id"),
                    "last_raw_output_created_at": item.get("created_at"),
                }
                seen.add(status_id)
        for status in status_list:
            status_id = status.get("id")
            if status_id in extras:
                status.update(extras[status_id])
    if isinstance(data, list):
        return status_list
    return status_list[0]
