# app/routers/deps.py
from typing import Optional
from fastapi import Header, HTTPException, Depends
from app.utils.auth import get_current_user

def require_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    current_user: dict = Depends(get_current_user),
) -> str:
    """
    Tenant id'yi öncelikle X-Tenant-ID header'ından, yoksa kullanıcının profilinden alır.
    Header adı HTTP'de case-insensitive olsa da alias'ı büyük/kamel yazmak iyi pratiktir.
    """
    tenant_id = x_tenant_id or current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Missing tenant id (provide X-Tenant-ID header or ensure user profile has tenant_id)"
        )
    return tenant_id


def require_admin(user: dict):
    """
    Admin kontrolü.
    Admin = role_id <= 2 (SNSD Admin veya Company Admin)
    """
    role_id = user.get("role_id")
    if role_id is None or role_id > 2:
        raise HTTPException(403, "Admin access required")


def require_super_admin(user: dict):
    """
    Super admin kontrolü (role_id = 1)
    """
    role_id = user.get("role_id")
    if role_id != 1:
        raise HTTPException(403, "Super admin access required")


def check_permission(user: dict, required_role_id: int):
    """
    Gerekli rol seviyesini doğrula (düşük sayı = yüksek yetki).
    """
    user_role_id = user.get("role_id")
    if user_role_id is None or user_role_id > required_role_id:
        raise HTTPException(403, f"Insufficient permissions (required role_id <= {required_role_id})")


def require_library_admin(user: dict):
    """
    MarcelGPT library admin access check.
    Only Company Admin (role_id 2) and HSE Specialist (role_id 3) can view all library tabs.
    Other roles can only view "Assigned to me" tab via my-assignments endpoint.
    """
    role_id = user.get("role_id")
    if role_id is None or role_id > 3:
        raise HTTPException(403, "MarcelGPT library admin access required (Company Admin or HSE Specialist)")


def ensure_response(res):
    """
    Supabase response normalizasyonu.
    Liste endpoint'lerinde boş data için 400 fırlatmayalım;
    bu helper'ı tek-kayıt bekleyen yerlerde kullanmak daha doğru.
    """
    error = getattr(res, "error", None)
    if error:
        if isinstance(error, dict):
            message = error.get("message") or error.get("details") or "Supabase error"
        else:
            message = str(error)
        raise HTTPException(400, message)
    return res.data