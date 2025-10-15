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
    Validate JWT token from Supabase Auth

    IMPORTANT: You need to add SUPABASE_JWT_SECRET to your .env file
    Get it from: Supabase Dashboard -> Settings -> API -> JWT Secret
    """
    token = credentials.credentials

    # Determine which secret to use
    # If JWT_SECRET is provided, use it (recommended)
    # Otherwise fall back to ANON_KEY (may not work for all cases)
    jwt_secret = settings.SUPABASE_JWT_SECRET or settings.SUPABASE_ANON_KEY

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

        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role")
        }
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