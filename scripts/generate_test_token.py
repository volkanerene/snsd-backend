"""
Generate a fresh JWT token for testing
"""
import jwt
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.config import settings

# Test user info
payload = {
    "tenant_id": "99999999-9999-9999-9999-999999999999",
    "user_id": "11111111-1111-1111-1111-111111111111",
    "email": "company-admin@testcompany.com",
    "role_id": 2,
    "exp": datetime.utcnow() + timedelta(days=7)  # Valid for 7 days
}

token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
print(token)
