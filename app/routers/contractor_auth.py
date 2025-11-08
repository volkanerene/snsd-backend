from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, validator

from app.db.supabase_client import supabase

router = APIRouter(prefix="/contractor", tags=["Contractor Auth"])


class SignupVerifyResponse(BaseModel):
    contractor_email: str
    contractor_name: str
    session_id: str
    contractor_id: str
    valid: bool


class ContractorSignupRequest(BaseModel):
    email: EmailStr
    password: str
    password_confirm: str
    session_id: str            # TEXT session_id (örn: sess_503760)
    contractor_id: UUID        # UUID doğrulama

    @validator("password")
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @validator("password_confirm")
    def passwords_match(cls, v: str, values) -> str:
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")
        return v


class SignupResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None


def _maybe_single_or_404(res, not_found_msg: str):
    row = getattr(res, "data", None)
    if not row:
        raise HTTPException(status_code=404, detail=not_found_msg)
    return row


@router.get("/signup/verify", response_model=SignupVerifyResponse)
async def verify_signup(
    session_id: str = Query(...),           # <-- TEXT
    contractor_id: UUID = Query(...),       # <-- UUID
) -> SignupVerifyResponse:
    try:
        # 1) Session var mı? (bilgi amaçlı çekiyoruz)
        sess_res = supabase.table("evren_gpt_sessions") \
            .select("id, session_id") \
            .eq("session_id", session_id) \
            .maybe_single() \
            .execute()
        _maybe_single_or_404(sess_res, "Session not found or expired")

        # 2) Link var mı? (link tablosu session_id'yi TEXT olarak tutuyor!)
        link_res = (
            supabase.table("evren_gpt_session_contractors")
            .select("contractor_id, status")
            .eq("session_id", session_id)
            .eq("contractor_id", str(contractor_id))
            .maybe_single()
            .execute()
        )
        link_row = _maybe_single_or_404(link_res, "Contractor not linked to this session")

        if link_row.get("status") == "registered":
            raise HTTPException(status_code=400, detail="Contractor already registered for this session")

        # 3) Contractor bilgisi
        c_res = supabase.table("contractors") \
            .select("id, name, contact_email") \
            .eq("id", str(contractor_id)) \
            .maybe_single() \
            .execute()
        c_row = _maybe_single_or_404(c_res, "Contractor not found")

        return SignupVerifyResponse(
            contractor_email=c_row.get("contact_email") or "",
            contractor_name=c_row.get("name") or "",
            session_id=session_id,
            contractor_id=str(contractor_id),
            valid=True,
        )

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[verify_signup] Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(exc)}")


@router.post("/signup/register", response_model=SignupResponse)
async def register_contractor(payload: ContractorSignupRequest) -> SignupResponse:
    try:
        # 1) Session kontrol
        sess_res = (
            supabase.table("evren_gpt_sessions")
            .select("id, session_id")
            .eq("session_id", payload.session_id)
            .maybe_single()
            .execute()
        )
        _maybe_single_or_404(sess_res, "Session not found or expired")

        # 2) Link kontrol
        link_res = (
            supabase.table("evren_gpt_session_contractors")
            .select("contractor_id, status")
            .eq("session_id", payload.session_id)
            .eq("contractor_id", str(payload.contractor_id))
            .maybe_single()
            .execute()
        )
        link_row = _maybe_single_or_404(link_res, "Contractor not linked to this session")
        if link_row.get("status") == "registered":
            raise HTTPException(status_code=400, detail="Contractor already registered")

        # 3) Email zaten profilde var mı ve contractor_id != NULL (yani gerçekten kayıtlı)?
        existing = getattr(
            supabase.table("profiles").select("id, contractor_id").eq("email", str(payload.email)).maybe_single().execute(),
            "data",
            None,
        )
        # Only reject if profile has a valid contractor_id (not orphaned)
        if existing and existing.get("contractor_id"):
            raise HTTPException(status_code=400, detail="Email already registered")

        # 3.5) Clean up orphaned profile with this email (contractor_id = NULL)
        # This can happen if a previous signup/deletion left a dangling profile
        if existing and not existing.get("contractor_id"):
            try:
                supabase.table("profiles").delete().eq("id", existing.get("id")).execute()
                print(f"[register_contractor] Cleaned up orphaned profile for email {payload.email}")
            except Exception as e:
                print(f"[register_contractor] Warning: Failed to clean orphaned profile: {e}")

        # 4) Auth kullanıcı oluştur (email verification bypass - contractor link'ten geldiyse, zaten email doğrulanmış)
        print(f"[register_contractor] Creating auth user for email: {payload.email}")
        try:
            # Use admin API to create user with email already confirmed
            # since contractor is registering via email link
            auth_response = supabase.auth.admin.create_user({
                "email": str(payload.email),
                "password": payload.password,
                "email_confirm": True,  # Mark email as confirmed - skip confirmation email
            })
            print(f"[register_contractor] Admin create_user response: {auth_response}")
            user = getattr(auth_response, "user", None)
            print(f"[register_contractor] Admin signup user object: {user}")
        except Exception as e:
            print(f"[register_contractor] Admin signup failed: {str(e)}, trying regular signup")
            # Fallback to regular signup if admin API fails
            try:
                auth_response = supabase.auth.sign_up({
                    "email": str(payload.email),
                    "password": payload.password,
                })
                print(f"[register_contractor] Regular sign_up response: {auth_response}")
                user = getattr(auth_response, "user", None)
                print(f"[register_contractor] Regular signup user object: {user}")
            except Exception as e2:
                print(f"[register_contractor] Regular signup also failed: {str(e2)}")
                raise HTTPException(status_code=400, detail=f"Failed to create auth user: {str(e2)}")

        if not user:
            print(f"[register_contractor] ERROR: User object is None!")
            print(f"[register_contractor] Full response: {auth_response}")
            raise HTTPException(status_code=400, detail="Failed to create user - no user object returned")

        user_id = getattr(user, "id", None)
        print(f"[register_contractor] Auth user ID: {user_id}")

        if not user_id:
            print(f"[register_contractor] ERROR: user_id is missing from user object!")
            print(f"[register_contractor] User object contents: {user}")
            raise HTTPException(status_code=400, detail="Auth user ID missing")

        # 5) Contractor bilgisi
        c_row = getattr(
            supabase.table("contractors")
            .select("name, tenant_id")
            .eq("id", str(payload.contractor_id))
            .maybe_single()
            .execute(),
            "data",
            None,
        )
        if not c_row:
            raise HTTPException(status_code=404, detail="Contractor not found")

        # 6) Create profile with all required data
        # The auth user was created, so it exists in auth.users table
        profile_data = {
            "id": user_id,
            "email": str(payload.email),
            "full_name": c_row.get("name") or "",
            "is_active": True,
            "tenant_id": c_row.get("tenant_id"),
            "contractor_id": str(payload.contractor_id),
            "role_id": 4,  # Contractor Admin role
        }

        print(f"[register_contractor] Creating profile with data:")
        print(f"  - user_id: {user_id}")
        print(f"  - email: {payload.email}")
        print(f"  - full_name: {c_row.get('name')}")
        print(f"  - tenant_id: {c_row.get('tenant_id')}")
        print(f"  - contractor_id: {str(payload.contractor_id)}")
        print(f"  - role_id: 4 (Contractor Admin)")

        try:
            # Try INSERT - if profile already exists (Supabase auto-created it), UPDATE instead
            profile_res = supabase.table("profiles").insert(profile_data).execute()
            print(f"[register_contractor] ✅ Profile created successfully")
        except Exception as e:
            # If INSERT fails (e.g., profile already exists), try UPDATE
            print(f"[register_contractor] INSERT failed: {str(e)}, attempting UPDATE...")
            try:
                profile_res = supabase.table("profiles").update(profile_data).eq("id", user_id).execute()
                print(f"[register_contractor] ✅ Profile updated successfully")
            except Exception as e2:
                print(f"[register_contractor] ERROR: Failed to create/update profile: {str(e2)}")
                raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e2)}")

        # 7) Link status -> registered
        supabase.table("evren_gpt_session_contractors") \
            .update({"status": "completed"}) \
            .eq("session_id", payload.session_id) \
            .eq("contractor_id", str(payload.contractor_id)) \
            .execute()

        return SignupResponse(
            success=True,
            message="Registration successful! You can now login.",
            user_id=user_id,
        )

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[register_contractor] Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(exc)}")