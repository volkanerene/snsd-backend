# app/utils/auth.py
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=True)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    """
    Validate JWT token from Supabase Auth and fetch user profile

    IMPORTANT: You need to add SUPABASE_JWT_SECRET to your .env file
    Get it from: Supabase Dashboard -> Settings -> API -> JWT Secret

    Returns user profile with role_id, tenant_id, and other profile data
    """
    from app.db.supabase_client import supabase

    token = credentials.credentials

    # Determine which secret to use
    # If JWT_SECRET is provided, use it (recommended)
    # Otherwise fall back to ANON_KEY (may not work for all cases)
    jwt_secret = settings.SUPABASE_JWT_SECRET
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET not set on server")

    try:
        # Decode and verify the JWT token
        # Supabase uses HS256 algorithm
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={
                "verify_aud": False,  # Supabase doesn't require audience verification
                "verify_signature": True
            }
        )

        user_id = payload.get("sub")

        # Fetch user profile from database to get role_id, tenant_id, etc.
        profile_res = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()

        if not profile_res.data:
            # User authenticated but no profile - return basic info
            return {
                "id": user_id,
                "user_id": user_id,  # Backward compatibility
                "email": payload.get("email"),
                "role": payload.get("role"),
                "role_id": None,
                "tenant_id": None,
            }

        # Return profile data with both 'id' and 'user_id' for compatibility
        profile = profile_res.data[0]
        profile["user_id"] = user_id  # Add for backward compatibility

        return profile

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token signature. Please add SUPABASE_JWT_SECRET to your .env file. "
                   "Get it from Supabase Dashboard -> Settings -> API -> JWT Secret"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


def require_admin(user: dict):
    """
    Check if user is an admin (role_id <= 2)
    Raises HTTPException if not authorized
    """
    role_id = user.get("role_id")
    if role_id is None or role_id > 2:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )


def require_permission(user: dict, permission: str):
    """
    Check if user has a specific permission
    Raises HTTPException if not authorized

    Args:
        user: User dict from get_current_user
        permission: Permission name (e.g. 'users.read')
    """
    from app.db.supabase_client import supabase

    user_id = user.get("id") or user.get("user_id")
    role_id = user.get("role_id")

    if not user_id or not role_id:
        raise HTTPException(
            status_code=403,
            detail="User profile not properly configured"
        )

    # Super Admin (role_id = 1) has all permissions
    if role_id == 1:
        return True

    # Check if user's role has the permission
    query = supabase.table("user_permissions_view").select("permission_name").eq("user_id", user_id).eq("permission_name", permission).limit(1).execute()

    if not query.data:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: '{permission}' required"
        )

    return True


def require_any_permission(user: dict, permissions: list[str]):
    """
    Check if user has any of the specified permissions
    Raises HTTPException if none are found

    Args:
        user: User dict from get_current_user
        permissions: List of permission names
    """
    from app.db.supabase_client import supabase

    user_id = user.get("id") or user.get("user_id")
    role_id = user.get("role_id")

    if not user_id or not role_id:
        raise HTTPException(
            status_code=403,
            detail="User profile not properly configured"
        )

    # Super Admin (role_id = 1) has all permissions
    if role_id == 1:
        return True

    # Check if user has any of the permissions
    query = supabase.table("user_permissions_view").select("permission_name").eq("user_id", user_id).in_("permission_name", permissions).limit(1).execute()

    if not query.data:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: one of {permissions} required"
        )

    return True


def get_user_permissions(user: dict) -> list[str]:
    """
    Get all permissions for a user

    Args:
        user: User dict from get_current_user

    Returns:
        List of permission names
    """
    from app.db.supabase_client import supabase

    user_id = user.get("id") or user.get("user_id")
    role_id = user.get("role_id")

    if not user_id or not role_id:
        return []

    # Query user_permissions_view
    query = supabase.table("user_permissions_view").select("permission_name").eq("user_id", user_id).execute()

    if not query.data:
        return []

    return [p["permission_name"] for p in query.data]