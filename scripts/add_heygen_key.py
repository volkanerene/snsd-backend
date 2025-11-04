"""
Add HeyGen API key to tenant
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.supabase_client import supabase

# Load environment
load_dotenv()

# Get HeyGen API key from environment or use placeholder
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "YOUR_HEYGEN_API_KEY_HERE")

print("🔧 Adding HeyGen API key to tenants...")
print(f"Using API key: {HEYGEN_API_KEY[:20]}..." if len(HEYGEN_API_KEY) > 20 else HEYGEN_API_KEY)

# Get all tenants
tenants_result = supabase.table("tenants").select("id, name, slug, heygen_api_key").execute()

if not tenants_result.data:
    print("❌ No tenants found!")
    sys.exit(1)

print(f"\n📋 Found {len(tenants_result.data)} tenants:")
for tenant in tenants_result.data:
    has_key = "✅" if tenant.get("heygen_api_key") else "❌"
    print(f"  {has_key} {tenant['name']} (slug: {tenant['slug']}, id: {tenant['id']})")

# Ask which tenant to update
print("\n" + "="*60)
tenant_slug = input("Enter tenant slug to update (or 'all' for all tenants): ").strip()

if tenant_slug == "all":
    # Update all tenants
    for tenant in tenants_result.data:
        result = supabase.table("tenants").update({
            "heygen_api_key": HEYGEN_API_KEY
        }).eq("id", tenant["id"]).execute()
        print(f"✅ Updated {tenant['name']}")
    print("\n🎉 All tenants updated with HeyGen API key!")
else:
    # Update specific tenant
    tenant = next((t for t in tenants_result.data if t["slug"] == tenant_slug), None)
    if not tenant:
        print(f"❌ Tenant with slug '{tenant_slug}' not found!")
        sys.exit(1)

    result = supabase.table("tenants").update({
        "heygen_api_key": HEYGEN_API_KEY
    }).eq("id", tenant["id"]).execute()

    print(f"\n✅ Updated tenant: {tenant['name']}")
    print(f"   Slug: {tenant['slug']}")
    print(f"   ID: {tenant['id']}")
    print(f"   HeyGen API Key: {HEYGEN_API_KEY[:20]}...")

print("\n✅ Done! You can now use Marcel GPT features.")
