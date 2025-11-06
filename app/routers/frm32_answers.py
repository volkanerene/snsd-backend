from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/answers")
async def list_answers(
    submission_id: str = Query(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    # Submission var mı (tenant scoped)?
    sub = (
        supabase.table("frm32_submissions")
        .select("id")
        .eq("id", submission_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    if not ensure_response(sub):
        raise HTTPException(404, "Submission not found")

    res = (
        supabase.table("frm32_answers")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("submission_id", submission_id)
        .execute()
    )
    return ensure_response(res)


@router.post("/answers/batch-upsert")
async def batch_upsert_answers(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    answers = payload.get("answers")
    if not answers or not isinstance(answers, list):
        raise HTTPException(400, "answers array required")

    submission_ids = {item.get("submission_id") for item in answers}
    if None in submission_ids:
        raise HTTPException(400, "submission_id required for each answer")

    # Tüm submission'lar bu tenant'a mı ait?
    for submission_id in submission_ids:
        res = (
            supabase.table("frm32_submissions")
            .select("id")
            .eq("id", submission_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        data = ensure_response(res)
        if not data:
            raise HTTPException(404, f"Submission {submission_id} not found")

    # Upsert
    upsert_payload = []
    for item in answers:
        answer = dict(item)
        answer["tenant_id"] = tenant_id
        upsert_payload.append(answer)

    res = (
        supabase.table("frm32_answers")
        .upsert(upsert_payload, on_conflict="submission_id,question_id")
        .execute()
    )
    return ensure_response(res)