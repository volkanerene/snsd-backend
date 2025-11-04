#!/usr/bin/env python3
"""
Quick script to test if users can authenticate
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_ANON_KEY must be set")
    sys.exit(1)

# Create client with ANON key (like frontend does)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Test credentials
TEST_EMAIL = "company-admin@testcompany.com"
TEST_PASSWORD = "TestPass123!"

print(f"🧪 Testing login for: {TEST_EMAIL}")
print(f"📍 Supabase URL: {SUPABASE_URL}")
print("=" * 70)

try:
    # Try to sign in (like frontend does)
    response = supabase.auth.sign_in_with_password({
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })

    if response.user:
        print(f"✅ Login successful!")
        print(f"   User ID: {response.user.id}")
        print(f"   Email: {response.user.email}")
        print(f"   Email confirmed: {response.user.email_confirmed_at is not None}")
        print(f"   Created at: {response.user.created_at}")
    else:
        print("❌ Login failed: No user returned")

except Exception as e:
    print(f"❌ Login failed with error:")
    print(f"   {type(e).__name__}: {str(e)}")

    # Try to get more details
    if hasattr(e, 'message'):
        print(f"   Message: {e.message}")
    if hasattr(e, 'status'):
        print(f"   Status: {e.status}")
