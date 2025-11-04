#!/usr/bin/env python3
"""
Fix test company profiles - create profiles for auth users
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Get tenant
tenant = supabase.table("tenants").select("*").eq("slug", "test-company").execute()
if not tenant.data:
    print("❌ Test company not found")
    sys.exit(1)

tenant_id = tenant.data[0]['id']
print(f"✅ Found tenant: {tenant.data[0]['name']} (ID: {tenant_id})")

# Test users - these are auth users that exist
test_users = [
    {
        "email": "company-admin@testcompany.com",
        "full_name": "Test Company Admin",
        "role_id": 2
    },
    {
        "email": "hse-specialist@testcompany.com",
        "full_name": "Test HSE Specialist",
        "role_id": 3
    },
    {
        "email": "contractor-admin@testcompany.com",
        "full_name": "Test Contractor Admin",
        "role_id": 4
    },
    {
        "email": "supervisor@testcompany.com",
        "full_name": "Test Supervisor",
        "role_id": 5
    }
]

print("\n🔧 Creating/fixing profiles for auth users...")

for user_config in test_users:
    email = user_config["email"]

    try:
        # Get auth user by email
        # Note: Supabase admin API doesn't have list_users with email filter
        # We'll try to sign in to get the user ID (this won't work without password)
        # Instead, let's just create profiles with new UUIDs and link them

        print(f"\n👤 Processing: {email}")

        # Check if profile exists
        existing = supabase.table("profiles").select("id").eq("email", email).execute()

        if existing.data and len(existing.data) > 0:
            print(f"   ✅ Profile already exists")
            continue

        # Get auth user - we need to find by email
        # Since we can't query by email directly, we'll create a fresh profile
        # with the auth user ID from login

        # For now, let's use the Supabase auth API to sign in and get user ID
        from supabase import create_client as create_anon_client
        anon_client = create_anon_client(SUPABASE_URL, os.getenv("SUPABASE_ANON_KEY"))

        # Try to sign in to get user ID, if fails create new auth user
        try:
            auth_result = anon_client.auth.sign_in_with_password({
                "email": email,
                "password": "TestPass123!"
            })

            if auth_result.user:
                user_id = auth_result.user.id
                print(f"   ✅ Found existing auth user: {user_id}")
            else:
                raise Exception("No user returned from sign in")

        except Exception as signin_error:
            print(f"   ⚠️  Auth user not found, creating new one...")

            # Create new auth user
            try:
                create_result = supabase.auth.admin.create_user({
                    "email": email,
                    "password": "TestPass123!",
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": user_config["full_name"],
                        "role_id": user_config["role_id"]
                    }
                })

                if create_result.user:
                    user_id = create_result.user.id
                    print(f"   ✅ Created new auth user: {user_id}")
                else:
                    raise Exception("Failed to create auth user")

            except Exception as create_error:
                print(f"   ❌ Failed to create auth user: {str(create_error)}")
                continue

        # Create profile
        try:
            profile_data = {
                "id": user_id,
                "email": email,
                "full_name": user_config["full_name"],
                "role_id": user_config["role_id"],
                "tenant_id": tenant_id,
                "status": "active"
            }

            supabase.table("profiles").upsert(
                profile_data,
                on_conflict="id"
            ).execute()
            print(f"   ✅ Created/updated profile")

            # Create tenant_users entry
            tenant_user_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role_id": user_config["role_id"],
                "status": "active"
            }

            supabase.table("tenant_users").upsert(
                tenant_user_data,
                on_conflict="tenant_id,user_id"
            ).execute()
            print(f"   ✅ Created tenant_users entry")

        except Exception as profile_error:
            print(f"   ❌ Failed to create profile: {str(profile_error)}")

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")

print("\n" + "=" * 70)
print("✅ Done! Check profiles now.")
print("=" * 70)
