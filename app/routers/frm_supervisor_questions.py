"""
Supervisor Form Questions Router
Serves FRM33/FRM34/FRM35 question banks from frm_supervisor_questions table
"""
from fastapi import APIRouter, Depends, HTTPException, Path

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user

router = APIRouter(prefix="/supervisor-forms", tags=["Supervisor Forms"])

SUPPORTED_FORMS = {"frm33", "frm34", "frm35"}


@router.get("/{form_id}/questions")
async def get_supervisor_form_questions(
    form_id: str = Path(..., description="Form identifier (frm33, frm34, frm35)"),
    user=Depends(get_current_user)
):
    """
    Return ordered question list for the requested supervisor form.
    """
    normalized_form = form_id.lower()
    if normalized_form not in SUPPORTED_FORMS:
        raise HTTPException(404, "Unsupported supervisor form")

    try:
        res = (
            supabase.table("frm_supervisor_questions")
            .select("*")
            .eq("form_id", normalized_form)
            .order("position", desc=False)
            .execute()
        )
        questions = ensure_response(res)
        return questions if isinstance(questions, list) else [questions]
    except Exception as exc:
        print(f"[supervisor_form_questions] Error: {exc}")
        raise HTTPException(500, f"Failed to load questions for {normalized_form}") from exc
