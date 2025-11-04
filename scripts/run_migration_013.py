"""
Run migration 013 automatically
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.supabase_client import supabase

# Load environment
load_dotenv()

print("🔧 Running Migration 013: Marcel GPT Library and Training System...")

# Read migration file
migration_path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '013_marcel_gpt_library_training.sql')

with open(migration_path, 'r') as f:
    migration_sql = f.read()

print(f"📄 Loaded migration file ({len(migration_sql)} characters)")

try:
    # Execute migration
    print("⚡ Executing migration...")
    result = supabase.rpc('exec_sql', {'sql': migration_sql}).execute()
    print("✅ Migration executed successfully!")
except Exception as e:
    # Try direct SQL execution
    print(f"⚠️  RPC method failed, trying direct execution...")
    try:
        # Split by semicolon and execute each statement
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for i, statement in enumerate(statements):
            if not statement:
                continue
            try:
                # Skip comment-only statements
                if statement.replace('\n', '').replace(' ', '').startswith('--'):
                    continue

                print(f"Executing statement {i+1}/{len(statements)}...")
                result = supabase.postgrest.rpc('query', {'query': statement}).execute()
            except Exception as stmt_error:
                # Continue on non-critical errors (like "already exists")
                if 'already exists' in str(stmt_error).lower():
                    print(f"  ⚠️  Statement {i+1} skipped (already exists)")
                else:
                    print(f"  ❌ Statement {i+1} failed: {stmt_error}")

        print("✅ Migration completed with warnings")
    except Exception as e2:
        print(f"❌ Migration failed: {e2}")
        print("\n📋 Manual steps required:")
        print("1. Open Supabase Dashboard: https://supabase.com/dashboard/project/ojkqgvkzumbnmasmajkw/sql")
        print("2. Copy and paste the migration SQL from:")
        print(f"   {migration_path}")
        print("3. Click 'Run' to execute")
        sys.exit(1)

print("\n🎉 Migration complete!")
print("\n📊 Verifying tables...")

# Verify tables exist
tables_to_check = [
    'marcel_gpt_premade_videos',
    'marcel_gpt_video_assignments',
    'marcel_gpt_incident_reports',
    'marcel_gpt_sharepoint_sync_log',
    'marcel_gpt_training_sessions'
]

for table in tables_to_check:
    try:
        result = supabase.table(table).select('*').limit(1).execute()
        print(f"✅ Table '{table}' exists")
    except Exception as e:
        print(f"❌ Table '{table}' not found: {e}")

print("\n✅ All done! Restart your backend to apply changes.")
