"""
Set real HeyGen API key to all tenants
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.supabase_client import supabase

HEYGEN_API_KEY = "sk_V2_hgu_kmLB8XDi2mZ_ivL65prGVgSf1NcRCcJakGxhxAvvuOd2"

print("🔧 Setting REAL HeyGen API key to all tenants...")

# Get all tenants
tenants = supabase.table("tenants").select("id, name, slug").execute()

if not tenants.data:
    print("❌ No tenants found!")
    sys.exit(1)

print(f"\n📋 Found {len(tenants.data)} tenants:")

for tenant in tenants.data:
    try:
        result = supabase.table("tenants").update({
            "heygen_api_key": HEYGEN_API_KEY
        }).eq("id", tenant["id"]).execute()
        print(f"✅ Updated: {tenant['name']} ({tenant['slug']})")
    except Exception as e:
        print(f"❌ Failed to update {tenant['name']}: {e}")

print(f"\n✅ Done! All tenants now have real HeyGen API key.")
print(f"🔑 Key: {HEYGEN_API_KEY[:20]}...")
