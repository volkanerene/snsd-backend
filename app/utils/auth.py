# app/utils/auth.py
import httpx, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWKS_URL = "https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/jwks"
    
bearer_scheme = HTTPBearer(auto_error=True)  # Swagger'da Authorize butonunu etkinleştirir

_cached_keys = None
async def get_jwks():
    global _cached_keys
    if not _cached_keys:
        async with httpx.AsyncClient() as client:
            resp = await client.get(JWKS_URL)
            resp.raise_for_status()
            _cached_keys = resp.json()
    return _cached_keys

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials
    jwks = await get_jwks()
    try:
        unverified = jwt.get_unverified_header(token)
        key = next(k for k in jwks["keys"] if k["kid"] == unverified["kid"])
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        payload = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_aud": False})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"user_id": payload.get("sub"), "role": payload.get("role")}