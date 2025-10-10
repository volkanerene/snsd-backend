from fastapi import Header, HTTPException


def require_tenant(x_tenant_id: str | None = Header(None, convert_underscores=False)):
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return x_tenant_id


def require_admin(user: dict):
    if user.get("role") not in ("admin", "service_role"):
        raise HTTPException(403, "Not allowed")


def ensure_response(res):
    error = getattr(res, "error", None)
    if error:
        if isinstance(error, dict):
            message = error.get("message") or error.get("details") or "Supabase error"
        else:
            message = str(error)
        raise HTTPException(400, message)
    return res.data
