#!/usr/bin/env python3
"""
Check if test users exist in auth.users
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

# Create admin client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

print("=" * 70)
print("🔍 Checking Auth Users")
print("=" * 70)

# Get tenant first
tenant = supabase.table("tenants").select("*").eq("slug", "test-company").execute()

if not tenant.data:
    print("❌ No tenant found with slug 'test-company'")
    sys.exit(1)

tenant_id = tenant.data[0]['id']
print(f"✅ Found tenant: {tenant.data[0]['name']} (ID: {tenant_id})")

# Get profiles
profiles = supabase.table("profiles").select("id, full_name, email, role_id, tenant_id").eq("tenant_id", tenant_id).execute()

if not profiles.data:
    print(f"❌ No profiles found for tenant {tenant_id}")

    # Check if ANY profiles exist
    all_profiles = supabase.table("profiles").select("id, full_name, email").limit(5).execute()
    if all_profiles.data:
        print(f"\n📋 But found {len(all_profiles.data)} profiles in database:")
        for p in all_profiles.data:
            print(f"   - {p.get('full_name', 'N/A')} ({p.get('email', 'N/A')})")
    sys.exit(1)

print(f"\nFound {len(profiles.data)} profiles:")
print("=" * 70)

for profile in profiles.data:
    print(f"\n📋 Profile: {profile['full_name']}")
    print(f"   Email: {profile.get('email', 'N/A')}")
    print(f"   ID: {profile['id']}")
    print(f"   Role ID: {profile['role_id']}")

    # Check if auth user exists
    try:
        auth_user = supabase.auth.admin.get_user_by_id(profile['id'])
        if auth_user and auth_user.user:
            print(f"   ✅ Auth user exists")
            print(f"      Email: {auth_user.user.email}")
            print(f"      Email confirmed: {auth_user.user.email_confirmed_at is not None}")
            print(f"      Created: {auth_user.user.created_at}")
        else:
            print(f"   ❌ Auth user NOT found")
    except Exception as e:
        print(f"   ❌ Auth user NOT found: {str(e)}")

print("\n" + "=" * 70)
