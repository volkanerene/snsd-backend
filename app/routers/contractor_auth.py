"""
Contractor Authentication Router
Handles contractor signup and registration for EvrenGPT evaluation process
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
import uuid

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response

router = APIRouter(prefix="/contractor", tags=["Contractor Auth"])


# ================================================
# Schemas
# ================================================

class SignupVerifyResponse(BaseModel):
    """Response for signup verification"""
    contractor_email: str
    contractor_name: str
    session_id: str
    contractor_id: str
    valid: bool


class ContractorSignupRequest(BaseModel):
    """Contractor signup request"""
    email: EmailStr
    password: str
    password_confirm: str
    session_id: str
    contractor_id: str

    @validator("password")
    def password_length(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @validator("password_confirm")
    def passwords_match(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")
        return v


class SignupResponse(BaseModel):
    """Signup response"""
    success: bool
    message: str
    user_id: Optional[str] = None


# ================================================
# Endpoints
# ================================================

@router.get("/signup/verify")
async def verify_signup(
    session_id: str = Query(...),
    contractor_id: str = Query(...)
) -> SignupVerifyResponse:
    """
    Verify contractor signup session
    Validates that the session and contractor exist and match
    """
    try:
        # Get session
        session_res = ensure_response(supabase.table("evren_gpt_sessions").select("id, session_id").eq(
            "session_id", session_id
        ).single().execute())

        # Get session contractor link
        link_res = ensure_response(supabase.table("evren_gpt_session_contractors").select(
            "contractor_id, status"
        ).eq("session_id", session_res["id"]).eq("contractor_id", contractor_id).single().execute())

        if link_res.get("status") == "registered":
            raise HTTPException(status_code=400, detail="Contractor already registered for this session")

        # Get contractor details
        contractor_res = ensure_response(supabase.table("contractors").select(
            "id, name, contact_email"
        ).eq("id", contractor_id).single().execute())

        return SignupVerifyResponse(
            contractor_email=contractor_res["contact_email"],
            contractor_name=contractor_res["name"],
            session_id=session_id,
            contractor_id=contractor_id,
            valid=True
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Error verifying signup: {exc}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(exc)}")


@router.post("/signup/register")
async def register_contractor(
    payload: ContractorSignupRequest
) -> SignupResponse:
    """
    Register contractor - create Supabase Auth user and profile
    """
    try:
        # 1. Verify session and contractor again
        session_res = ensure_response(supabase.table("evren_gpt_sessions").select("id").eq(
            "session_id", payload.session_id
        ).single().execute())

        session_id_pk = session_res["id"]

        # 2. Verify contractor in session
        link_res = ensure_response(supabase.table("evren_gpt_session_contractors").select(
            "contractor_id, status"
        ).eq("session_id", session_id_pk).eq("contractor_id", payload.contractor_id).single().execute())

        if link_res.get("status") == "registered":
            raise HTTPException(status_code=400, detail="Contractor already registered")

        # 3. Check if user with this email already exists
        existing_user_res = supabase.table("profiles").select("id").eq("email", payload.email).execute()
        if existing_user_res.data:
            raise HTTPException(status_code=400, detail="Email already registered")

        # 4. Create Supabase Auth user
        auth_response = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")

        user_id = auth_response.user.id

        # 5. Create profile with contractor role (role_id = 4)
        # Get contractor info
        contractor_res = ensure_response(supabase.table("contractors").select(
            "name, tenant_id"
        ).eq("id", payload.contractor_id).single().execute())

        # Create profile
        profile_data = {
            "id": user_id,
            "email": payload.email,
            "full_name": contractor_res["name"],
            "role_id": 4,  # Contractor role
            "tenant_id": contractor_res.get("tenant_id"),
            "created_at": "now()",
        }

        profile_res = ensure_response(supabase.table("profiles").insert(profile_data).execute())

        # 6. Update session contractor status to "registered"
        update_res = ensure_response(supabase.table("evren_gpt_session_contractors").update({
            "status": "registered",
            "registered_at": "now()",
        }).eq("session_id", session_id_pk).eq("contractor_id", payload.contractor_id).execute())

        return SignupResponse(
            success=True,
            message="Registration successful! You can now login.",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as exc:
        print(f"Error registering contractor: {exc}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(exc)}")
