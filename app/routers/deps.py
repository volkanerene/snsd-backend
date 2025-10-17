from fastapi import Header, HTTPException
from app.db.supabase_client import supabase


def require_tenant(x_tenant_id: str | None = Header(None, alias="x-tenant-id")):
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return x_tenant_id


def require_admin(user: dict):
    """
    Check if user is admin.
    Admin = role_id <= 2 (SNSD Admin or Company Admin)

    Note: get_current_user now returns the full profile, so we can check role_id directly
    """
    role_id = user.get("role_id")

    # Only role_id <= 2 (SNSD Admin and Company Admin) are allowed
    if role_id is None or role_id > 2:
        raise HTTPException(403, "Admin access required")


def require_super_admin(user: dict):
    """
    Check if user is super admin (role_id = 1)
    """
    role_id = user.get("role_id")

    if role_id != 1:
        raise HTTPException(403, "Super admin access required")


def check_permission(user: dict, required_role_id: int):
    """
    Check if user has at least the required role level
    Lower role_id = higher permission level (1 = Super Admin is highest)
    """
    user_role_id = user.get("role_id")

    if user_role_id is None or user_role_id > required_role_id:
        raise HTTPException(403, f"Insufficient permissions (required role_id <= {required_role_id})")


def ensure_response(res):
    error = getattr(res, "error", None)
    if error:
        if isinstance(error, dict):
            message = error.get("message") or error.get("details") or "Supabase error"
        else:
            message = str(error)
        raise HTTPException(400, message)
    return res.data
