#!/usr/bin/env python3
"""
Clean up test company data before recreating properly
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

print("=" * 70)
print("🗑️  Cleaning Up Test Company Data")
print("=" * 70)

# Get tenant
tenant = supabase.table("tenants").select("*").eq("slug", "test-company").execute()

if not tenant.data:
    print("✅ No test company found - nothing to clean up")
    sys.exit(0)

tenant_id = tenant.data[0]['id']
print(f"Found tenant: {tenant.data[0]['name']} (ID: {tenant_id})")

# Get profiles for this tenant
profiles = supabase.table("profiles").select("id, full_name, role_id").eq("tenant_id", tenant_id).execute()

if profiles.data:
    print(f"\n🔍 Found {len(profiles.data)} profiles to clean up:")

    for profile in profiles.data:
        print(f"\n   Cleaning up: {profile['full_name']}")
        user_id = profile['id']

        # Delete from tenant_users first (foreign key)
        try:
            supabase.table("tenant_users").delete().eq("user_id", user_id).execute()
            print(f"      ✅ Deleted from tenant_users")
        except Exception as e:
            print(f"      ⚠️  tenant_users: {str(e)}")

        # Delete profile
        try:
            supabase.table("profiles").delete().eq("id", user_id).execute()
            print(f"      ✅ Deleted profile")
        except Exception as e:
            print(f"      ⚠️  profile: {str(e)}")

        # Try to delete auth user if exists
        try:
            supabase.auth.admin.delete_user(user_id)
            print(f"      ✅ Deleted auth user")
        except Exception as e:
            print(f"      ⚠️  auth user: {str(e)}")

# Delete tenant
try:
    supabase.table("tenants").delete().eq("id", tenant_id).execute()
    print(f"\n✅ Deleted tenant: {tenant.data[0]['name']}")
except Exception as e:
    print(f"\n❌ Failed to delete tenant: {str(e)}")

print("\n" + "=" * 70)
print("✅ Cleanup complete! Now run:")
print("   python3 scripts/create_test_company.py")
print("=" * 70)
