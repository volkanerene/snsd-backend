# How to Apply Migrations to Supabase

## Quick Start Guide

Follow these steps to apply all migrations to your Supabase database:

### Step 1: Open Supabase SQL Editor

1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project
3. Click **"SQL Editor"** in the left sidebar

### Step 2: Apply Each Migration in Order

Apply migrations in this exact order:

#### Migration 1: tenant_users Table
1. Click **"+ New query"**
2. Open `001_tenant_users.sql` and copy all content
3. Paste into the SQL Editor
4. Click **"Run"** (or press Ctrl/Cmd + Enter)
5. ✅ Wait for "Success. No rows returned" message

#### Migration 2: permissions & role_permissions Tables
1. Click **"+ New query"**
2. Open `002_permissions.sql` and copy all content
3. Paste into the SQL Editor
4. Click **"Run"**
5. ✅ Should see success message with ~40 permissions seeded

#### Migration 3: invitations Table
1. Click **"+ New query"**
2. Open `003_invitations.sql` and copy all content
3. Paste into the SQL Editor
4. Click **"Run"**
5. ✅ Should see success message

#### Migration 4: subscription_tiers & tenant_subscriptions Tables
1. Click **"+ New query"**
2. Open `004_subscriptions.sql` and copy all content
3. Paste into the SQL Editor
4. Click **"Run"**
5. ✅ Should see success with 4 tiers seeded (free, starter, professional, enterprise)

### Step 3: Verify Migrations

Run this verification query in SQL Editor:

```sql
-- Check all tables were created
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'tenant_users',
    'permissions',
    'role_permissions',
    'invitations',
    'subscription_tiers',
    'tenant_subscriptions',
    'usage_tracking'
  )
ORDER BY table_name;
```

**Expected result:** 7 rows (all table names listed above)

### Step 4: Verify Data Seeding

```sql
-- 1. Check permissions were seeded
SELECT COUNT(*) as permission_count FROM permissions;
-- Expected: ~40

-- 2. Check role permissions were assigned
SELECT
  r.name as role,
  COUNT(rp.permission_id) as permission_count
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
GROUP BY r.id, r.name
ORDER BY r.id;
-- Expected:
-- Super Admin: 40+
-- Admin: 30+
-- HSE Manager: 10+
-- Contractor: 3

-- 3. Check subscription tiers
SELECT name, display_name, price_monthly, max_users
FROM subscription_tiers
ORDER BY sort_order;
-- Expected: free, starter, professional, enterprise

-- 4. Check functions exist
SELECT proname
FROM pg_proc
WHERE proname IN (
  'check_subscription_limit',
  'get_current_usage',
  'generate_invitation_token',
  'auto_expire_invitations'
);
-- Expected: 4 functions
```

### Step 5: Post-Migration Setup

After all migrations are applied, run these setup queries:

#### A. Assign Free Tier to All Existing Tenants

```sql
-- Assign free tier subscription to all tenants
DO $$
DECLARE
  free_tier_id INTEGER;
BEGIN
  SELECT id INTO free_tier_id FROM subscription_tiers WHERE name = 'free';

  INSERT INTO tenant_subscriptions (tenant_id, tier_id, status, billing_cycle, trial_ends_at)
  SELECT
    id,
    free_tier_id,
    'trial',
    'monthly',
    NOW() + INTERVAL '30 days'
  FROM tenants
  WHERE NOT EXISTS (
    SELECT 1 FROM tenant_subscriptions WHERE tenant_id = tenants.id
  );
END $$;
```

#### B. Migrate Profile Data to tenant_users

```sql
-- Create tenant_users entries from existing profiles
INSERT INTO tenant_users (tenant_id, user_id, role_id, status)
SELECT
  p.tenant_id,
  p.id,
  p.role_id,
  'active'
FROM profiles p
WHERE p.tenant_id IS NOT NULL
ON CONFLICT (tenant_id, user_id) DO NOTHING;

-- Verify migration
SELECT COUNT(*) as migrated_users FROM tenant_users;
```

### Step 6: Verify Everything Works

```sql
-- Test subscription limit check
SELECT check_subscription_limit(
  (SELECT id FROM tenants LIMIT 1),
  'users',
  2
) as can_add_users;
-- Should return true if tenant has free tier (max 3 users)

-- Test get current usage
SELECT get_current_usage(
  (SELECT id FROM tenants LIMIT 1),
  'users'
) as current_user_count;
-- Should return count of active users in that tenant
```

## Troubleshooting

### Error: "relation already exists"
- Some tables might already be created
- Safe to continue - the migrations use `IF NOT EXISTS`

### Error: "duplicate key value violates unique constraint"
- Data might already be seeded
- Safe to continue - the migrations use `ON CONFLICT DO NOTHING`

### Error: "function does not exist"
- Make sure you applied migrations in order (001 → 002 → 003 → 004)
- Migration 001 creates the `update_tenant_users_updated_at()` function used in later migrations

### Error: Permission issues
- Make sure you're logged in as the Supabase project owner
- Check that your database has `auth.users` table (should exist by default)

## What's Next?

After successful migration:

1. ✅ Test backend APIs locally
2. ✅ Deploy backend to ECS (git push to trigger GitHub Actions)
3. 🔜 Create frontend hooks for new APIs
4. 🔜 Create admin UI pages
5. 🔜 Implement permission-based rendering

## Files Reference

- `001_tenant_users.sql` - Junction table for tenant-user relationships
- `002_permissions.sql` - Permission system with 40+ permissions
- `003_invitations.sql` - User invitation system with tokens
- `004_subscriptions.sql` - Subscription tiers and usage tracking
