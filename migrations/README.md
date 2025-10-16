# Database Migrations

This directory contains SQL migration files for the SnSD SaaS admin system.

## Migration Files

1. **001_tenant_users.sql** - Creates tenant_users junction table for many-to-many tenant-user relationships
2. **002_permissions.sql** - Creates permissions and role_permissions tables for RBAC
3. **003_invitations.sql** - Creates invitations table for user invitation system
4. **004_subscriptions.sql** - Creates subscription tiers, tenant subscriptions, and usage tracking

## How to Apply Migrations

### Option 1: Supabase Dashboard (Recommended for Development)

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Create a new query
4. Copy and paste the content of each migration file **in order**
5. Run each migration

### Option 2: Supabase CLI

```bash
# Install Supabase CLI if not already installed
npm install -g supabase

# Login to Supabase
supabase login

# Link your project
supabase link --project-ref YOUR_PROJECT_REF

# Apply migrations
supabase db push

# Or apply specific migration
psql YOUR_DATABASE_URL < migrations/001_tenant_users.sql
```

### Option 3: Direct PostgreSQL Connection

```bash
# Using psql
psql "postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres" < migrations/001_tenant_users.sql
psql "postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres" < migrations/002_permissions.sql
psql "postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres" < migrations/003_invitations.sql
psql "postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres" < migrations/004_subscriptions.sql
```

## Verification

After applying migrations, verify the tables were created:

```sql
-- Check tenant_users table
SELECT * FROM tenant_users LIMIT 1;

-- Check permissions
SELECT COUNT(*) FROM permissions;
-- Should return ~40 permissions

-- Check role_permissions
SELECT r.name, COUNT(rp.permission_id) as permission_count
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
GROUP BY r.id, r.name
ORDER BY r.id;

-- Check subscription tiers
SELECT * FROM subscription_tiers;
-- Should return 4 tiers: free, starter, professional, enterprise

-- Check functions
SELECT proname FROM pg_proc
WHERE proname IN (
  'check_subscription_limit',
  'get_current_usage',
  'generate_invitation_token'
);
```

## Rollback

If you need to rollback migrations (⚠️ **CAUTION: This will delete data**):

```sql
-- Rollback in reverse order
DROP TABLE IF EXISTS usage_tracking CASCADE;
DROP TABLE IF EXISTS tenant_subscriptions CASCADE;
DROP TABLE IF EXISTS subscription_tiers CASCADE;

DROP TABLE IF EXISTS invitations CASCADE;
DROP FUNCTION IF EXISTS generate_invitation_token CASCADE;
DROP FUNCTION IF EXISTS auto_expire_invitations CASCADE;

DROP TABLE IF EXISTS role_permissions CASCADE;
DROP TABLE IF EXISTS permissions CASCADE;

DROP TABLE IF EXISTS tenant_users CASCADE;
```

## Post-Migration Setup

### 1. Assign Default Subscription to Existing Tenants

```sql
-- Get the Free tier ID
DO $$
DECLARE
  free_tier_id INTEGER;
BEGIN
  SELECT id INTO free_tier_id FROM subscription_tiers WHERE name = 'free';

  -- Assign Free tier to all existing tenants
  INSERT INTO tenant_subscriptions (tenant_id, tier_id, status, billing_cycle)
  SELECT
    id,
    free_tier_id,
    'trial',
    'monthly'
  FROM tenants
  WHERE NOT EXISTS (
    SELECT 1 FROM tenant_subscriptions WHERE tenant_id = tenants.id
  );
END $$;
```

### 2. Create tenant_users entries for existing profiles

```sql
-- Link existing profiles to their tenants
INSERT INTO tenant_users (tenant_id, user_id, role_id, status)
SELECT
  p.tenant_id,
  p.id,
  p.role_id,
  'active'
FROM profiles p
WHERE p.tenant_id IS NOT NULL
ON CONFLICT (tenant_id, user_id) DO NOTHING;
```

### 3. Verify Permissions Assignment

```sql
-- Check that Super Admin has all permissions
SELECT COUNT(*) FROM role_permissions WHERE role_id = 1;
-- Should match total permissions count

-- Check Admin permissions
SELECT COUNT(*) FROM role_permissions WHERE role_id = 2;

-- Check HSE Manager permissions
SELECT COUNT(*) FROM role_permissions WHERE role_id = 3;

-- Check Contractor permissions
SELECT COUNT(*) FROM role_permissions WHERE role_id = 4;
```

## Troubleshooting

### Permission Denied Errors

If you get permission errors when applying RLS policies:

```sql
-- Grant necessary permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO postgres, authenticated, service_role;
```

### Trigger Function Not Found

If trigger functions are missing:

```sql
-- Recreate the updated_at function
CREATE OR REPLACE FUNCTION update_tenant_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## Next Steps

After migrations are applied:

1. ✅ Update backend API routers to use new tables
2. ✅ Test RBAC with different roles
3. ✅ Implement invitation email flow
4. ✅ Create frontend admin pages
5. ✅ Add subscription tier checking middleware
