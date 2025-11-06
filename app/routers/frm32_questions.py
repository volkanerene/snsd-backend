"""
FRM32 Questions Router
Handles retrieving FRM32 form questions from database
"""
from fastapi import APIRouter, Depends, HTTPException
from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/questions")
async def get_frm32_questions(
    user=Depends(get_current_user)
):
    """
    Get all FRM32 questions ordered by position
    """
    try:
        res = supabase.table("frm32_questions") \
            .select("*") \
            .order("position", desc=False) \
            .execute()

        questions = ensure_response(res)
        return questions if isinstance(questions, list) else [questions]

    except Exception as e:
        print(f"[frm32_questions] Error: {e}")
        raise HTTPException(500, f"Failed to fetch questions: {str(e)}")
