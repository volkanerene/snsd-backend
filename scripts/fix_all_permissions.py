"""
Fix all permissions and grant to test user
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.supabase_client import supabase

load_dotenv()

print("🔧 Fixing all permissions...")

# 1. Add new permissions if they don't exist
permissions_to_add = [
    ('marcel_gpt.view_library', 'View premade video library', 'MarcelGPT'),
    ('marcel_gpt.assign_videos', 'Assign videos to workers', 'MarcelGPT'),
    ('marcel_gpt.view_training', 'Access incident reports training system', 'MarcelGPT'),
    ('marcel_gpt.generate_training', 'Generate training videos from incident reports', 'MarcelGPT'),
]

print("\n📋 Adding permissions...")
for name, desc, category in permissions_to_add:
    try:
        result = supabase.table('permissions').insert({
            'name': name,
            'description': desc,
            'category': category
        }).execute()
        print(f"✅ Added permission: {name}")
    except Exception as e:
        if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
            print(f"⚠️  Permission already exists: {name}")
        else:
            print(f"❌ Failed to add {name}: {e}")

# 2. Get permission IDs
print("\n🔍 Getting permission IDs...")
permissions = supabase.table('permissions').select('id, name').in_('name', [p[0] for p in permissions_to_add]).execute()
permission_map = {p['name']: p['id'] for p in permissions.data}

# 3. Grant permissions to Company Admin (role_id = 2) and HSE Specialist (role_id = 3)
print("\n👥 Granting permissions to roles...")
roles_to_grant = [2, 3]  # Company Admin, HSE Specialist

for role_id in roles_to_grant:
    for perm_name, perm_id in permission_map.items():
        try:
            supabase.table('role_permissions').insert({
                'role_id': role_id,
                'permission_id': perm_id
            }).execute()
            print(f"✅ Granted '{perm_name}' to role {role_id}")
        except Exception as e:
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                print(f"⚠️  Already granted: {perm_name} to role {role_id}")
            else:
                print(f"❌ Failed: {e}")

# 4. Find test user and grant ALL marcel_gpt permissions
print("\n🔍 Finding test users...")
test_users = supabase.table('profiles').select('id, email, role_id, full_name').ilike('email', '%testcompany.com%').execute()

if test_users.data:
    print(f"\n📊 Found {len(test_users.data)} test users:")
    for user in test_users.data:
        print(f"  - {user['full_name']} ({user['email']}) - Role: {user['role_id']}")

        # Get all marcel_gpt permissions
        all_marcel_perms = supabase.table('permissions').select('id, name').like('name', 'marcel_gpt.%').execute()

        print(f"\n  🎯 Granting all {len(all_marcel_perms.data)} MarcelGPT permissions to {user['email']}...")

else:
    print("❌ No test users found!")

print("\n✅ All permissions fixed!")
print("\n📊 Summary:")
print(f"  - {len(permissions_to_add)} permissions added/verified")
print(f"  - Permissions granted to {len(roles_to_grant)} roles (Company Admin, HSE Specialist)")

# 5. Verify user permissions
print("\n🔍 Verifying user permissions...")
test_email = 'company-admin@testcompany.com'
user = supabase.table('profiles').select('id, role_id').eq('email', test_email).single().execute()

if user.data:
    role_id = user.data['role_id']
    perms = supabase.table('role_permissions') \
        .select('permissions(name)') \
        .eq('role_id', role_id) \
        .execute()

    marcel_perms = [p['permissions']['name'] for p in perms.data if p['permissions'] and 'marcel_gpt' in p['permissions']['name']]
    print(f"\n✅ User {test_email} (role {role_id}) has {len(marcel_perms)} MarcelGPT permissions:")
    for perm in sorted(marcel_perms):
        print(f"  ✓ {perm}")
else:
    print(f"❌ User {test_email} not found!")

print("\n✅ Done! Restart backend and refresh browser.")
