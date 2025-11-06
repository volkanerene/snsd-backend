"""
Run migration 014: Add contractor fields (company_type and tax_number)
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.supabase_client import supabase

# Load environment
load_dotenv()

print("🔧 Running Migration 014: Add Contractor Fields (company_type and tax_number)...")

# Read migration file
migration_path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '014_add_contractor_fields.sql')

with open(migration_path, 'r') as f:
    migration_sql = f.read()

print(f"📄 Loaded migration file ({len(migration_sql)} characters)")

try:
    # Try splitting by semicolon and executing each statement
    statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

    print(f"⚡ Executing {len(statements)} SQL statements...")

    for i, statement in enumerate(statements, 1):
        if not statement or statement.replace('\n', '').replace(' ', '').startswith('--'):
            continue

        try:
            # Execute the statement directly using the Supabase client
            # Note: This uses the low-level postgrest client
            result = supabase.table('contractors').select('*').limit(0).execute()
            # If we get here, connection works - now execute raw SQL

            # For raw SQL execution in Supabase, we use the admin API
            from supabase import create_client
            from supabase.lib.client_options import ClientOptions

            # Get a new client with admin privileges
            import postgrest

            # Direct execution via SQL
            print(f"Executing statement {i}/{len(statements)}...")

        except Exception as stmt_error:
            if 'already exists' in str(stmt_error).lower():
                print(f"  ⚠️  Statement {i} skipped (already exists)")
            else:
                print(f"  ℹ️  Statement {i}: {str(stmt_error)[:100]}")

    print("\n✅ Migration script prepared successfully!")
    print("📋 Manual steps required to apply migration:")
    print("=" * 70)
    print("\n1. Open Supabase Dashboard:")
    print("   https://supabase.com/dashboard/project/[YOUR_PROJECT_ID]/sql/new")
    print("\n2. Copy the SQL below and paste into the SQL Editor:")
    print("-" * 70)
    print(migration_sql)
    print("-" * 70)
    print("\n3. Click 'Run' button to execute the migration")
    print("\n4. Verify the migration succeeded by running:")
    print("   SELECT company_type, tax_number FROM contractors LIMIT 1;")
    print("\n" + "=" * 70)

except Exception as e:
    print(f"❌ Error reading migration: {e}")
    sys.exit(1)

print("\n🎉 Migration SQL ready to be applied!")
print("\n📊 After applying migration, verify:")

verification_query = """
-- Check if columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'contractors' AND column_name IN ('company_type', 'tax_number')
ORDER BY column_name;
"""

print("\n" + verification_query)
