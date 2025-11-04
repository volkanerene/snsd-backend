#!/usr/bin/env python3
"""
Script to create test company with all role users
Uses Supabase Admin API to properly create auth users and profiles
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# Create Supabase client with service role (admin privileges)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Test users configuration
TEST_USERS = [
    {
        "email": "company-admin@testcompany.com",
        "password": "TestPass123!",
        "full_name": "Test Company Admin",
        "role_id": 2,  # Company Admin
        "role_name": "Company Admin"
    },
    {
        "email": "hse-specialist@testcompany.com",
        "password": "TestPass123!",
        "full_name": "Test HSE Specialist",
        "role_id": 3,  # HSE Specialist
        "role_name": "HSE Specialist"
    },
    {
        "email": "contractor-admin@testcompany.com",
        "password": "TestPass123!",
        "full_name": "Test Contractor Admin",
        "role_id": 4,  # Contractor Admin
        "role_name": "Contractor Admin"
    },
    {
        "email": "supervisor@testcompany.com",
        "password": "TestPass123!",
        "full_name": "Test Supervisor",
        "role_id": 5,  # Supervisor
        "role_name": "Supervisor"
    }
]


def create_tenant():
    """Create or get test company tenant"""
    print("📋 Creating/getting test company tenant...")

    # Check if tenant exists
    result = supabase.table("tenants").select("*").eq("slug", "test-company").execute()

    if result.data and len(result.data) > 0:
        tenant = result.data[0]
        print(f"✅ Tenant already exists: {tenant['name']} (ID: {tenant['id']})")
        return tenant['id']

    # Create new tenant
    result = supabase.table("tenants").insert({
        "name": "Test Company Inc.",
        "slug": "test-company",
        "status": "active"
    }).execute()

    tenant = result.data[0]
    print(f"✅ Created tenant: {tenant['name']} (ID: {tenant['id']})")
    return tenant['id']


def create_test_user(user_config, tenant_id):
    """Create a test user with auth and profile"""
    email = user_config["email"]
    password = user_config["password"]
    full_name = user_config["full_name"]
    role_id = user_config["role_id"]
    role_name = user_config["role_name"]

    print(f"\n👤 Creating {role_name}: {email}")

    try:
        # Check if profile already exists
        existing_profile = supabase.table("profiles").select("id").eq("full_name", full_name).eq("role_id", role_id).execute()

        if existing_profile.data and len(existing_profile.data) > 0:
            existing_user_id = existing_profile.data[0]['id']
            print(f"⚠️  Profile exists, checking auth user...")

            # Check if auth user exists
            try:
                auth_user = supabase.auth.admin.get_user_by_id(existing_user_id)
                if auth_user and auth_user.user:
                    print(f"✅ Auth user already exists, skipping: {email}")
                    return existing_user_id
            except:
                pass

            # Profile exists but auth user doesn't - delete profile and recreate everything
            print(f"🗑️  Profile exists without auth user, cleaning up and recreating...")
            supabase.table("tenant_users").delete().eq("user_id", existing_user_id).execute()
            supabase.table("profiles").delete().eq("id", existing_user_id).execute()

        # Create auth user
        print(f"   Creating auth user...")
        auth_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Auto-confirm email
            "user_metadata": {
                "full_name": full_name,
                "role_id": role_id
            }
        })

        if not auth_response.user:
            raise Exception("Failed to create auth user")

        user_id = auth_response.user.id
        print(f"   ✅ Auth user created: {user_id}")

        # Create profile
        print(f"   Creating profile...")
        profile_data = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role_id": role_id,
            "tenant_id": tenant_id,
            "status": "active"
        }

        profile_result = supabase.table("profiles").insert(profile_data).execute()
        print(f"   ✅ Profile created")

        # Add to tenant_users
        print(f"   Adding to tenant_users...")
        tenant_user_data = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role_id": role_id,
            "status": "active"
        }

        supabase.table("tenant_users").insert(tenant_user_data).execute()
        print(f"   ✅ Added to tenant_users")

        print(f"✅ Successfully created {role_name}: {email}")
        return user_id

    except Exception as e:
        print(f"❌ Error creating {role_name}: {str(e)}")
        return None


def main():
    print("=" * 70)
    print("🚀 Test Company Creation Script")
    print("=" * 70)

    # Create tenant
    tenant_id = create_tenant()

    # Create users
    print("\n" + "=" * 70)
    print("Creating Test Users")
    print("=" * 70)

    created_users = []
    for user_config in TEST_USERS:
        user_id = create_test_user(user_config, tenant_id)
        if user_id:
            created_users.append({
                "id": user_id,
                "email": user_config["email"],
                "role": user_config["role_name"]
            })

    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)
    print(f"Tenant ID: {tenant_id}")
    print(f"Created/Verified {len(created_users)} users:\n")

    for user in created_users:
        print(f"  • {user['role']:20} | {user['email']:35} | {user['id']}")

    print("\n" + "=" * 70)
    print("✅ Test company setup complete!")
    print("=" * 70)
    print("\n📧 Login Credentials:")
    for user_config in TEST_USERS:
        print(f"  {user_config['email']:40} | {user_config['password']}")

    print("\n💡 You can now log in to the application with any of these accounts.")


if __name__ == "__main__":
    main()
