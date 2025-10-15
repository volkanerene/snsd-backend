from fastapi import Header, HTTPException
from app.db.supabase_client import supabase


def require_tenant(x_tenant_id: str | None = Header(None, alias="x-tenant-id")):
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return x_tenant_id


def require_admin(user: dict):
    """
    Check if user is admin by querying profiles table.
    Admin = role_id <= 1 (SNSD Admin or Company Admin)
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(403, "Not allowed")

    # Query profiles table to get user's role_id
    try:
        res = supabase.table("profiles").select("role_id").eq("id", user_id).limit(1).execute()
        if not res.data or len(res.data) == 0:
            raise HTTPException(403, "Profile not found")

        profile = res.data[0]
        role_id = profile.get("role_id")

        # Only role_id <= 1 (SNSD Admin and Company Admin) are allowed
        if role_id is None or role_id > 1:
            raise HTTPException(403, "Not allowed")
    except Exception as e:
        raise HTTPException(403, f"Authorization check failed: {str(e)}")


def ensure_response(res):
    error = getattr(res, "error", None)
    if error:
        if isinstance(error, dict):
            message = error.get("message") or error.get("details") or "Supabase error"
        else:
            message = str(error)
        raise HTTPException(400, message)
    return res.data
