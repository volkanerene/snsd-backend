-- =====================================================================
-- Migration: Create Test Company with All Role Users
-- Purpose: Create a complete test company with users for each role
-- Author: System
-- Date: 2025-10-31
-- =====================================================================

-- =====================================================================
-- PART 1: Create Test Tenant/Company
-- =====================================================================

-- Insert test company (simplified - adjust columns based on your tenants table)
INSERT INTO tenants (
    name,
    slug,
    status
) VALUES (
    'Test Company Inc.',
    'test-company',
    'active'
) ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name
RETURNING id;

-- Store tenant_id for later use (you'll need to copy this UUID)
-- After running this, get the tenant_id with:
-- SELECT id, name FROM tenants WHERE slug = 'test-company';

-- =====================================================================
-- PART 2: Create Test Users (Profiles Only - Auth users created manually)
-- =====================================================================

-- NOTE: Supabase Auth users must be created via Supabase Dashboard or API
-- This script creates the profiles and tenant associations
-- You'll need to invite these emails via Supabase Auth Dashboard

-- Get the tenant_id we just created
DO $$
DECLARE
    v_tenant_id UUID;
    v_company_admin_id UUID := gen_random_uuid();
    v_hse_specialist_id UUID := gen_random_uuid();
    v_contractor_admin_id UUID := gen_random_uuid();
    v_supervisor_id UUID := gen_random_uuid();
BEGIN
    -- Get tenant_id
    SELECT id INTO v_tenant_id FROM tenants WHERE slug = 'test-company';

    -- If tenant doesn't exist, raise error
    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant not found. Please ensure test-company tenant exists.';
    END IF;

    -- =====================================================================
    -- 1. Company Admin
    -- =====================================================================
    INSERT INTO profiles (
        id,
        full_name,
        role_id,
        tenant_id
    ) VALUES (
        v_company_admin_id,
        'Test Company Admin',
        2,  -- Company Admin role
        v_tenant_id
    ) ON CONFLICT (id) DO NOTHING;

    -- Add to tenant_users
    INSERT INTO tenant_users (
        tenant_id,
        user_id,
        role_id,
        status
    ) VALUES (
        v_tenant_id,
        v_company_admin_id,
        2,  -- Company Admin role
        'active'
    ) ON CONFLICT (tenant_id, user_id) DO NOTHING;

    -- =====================================================================
    -- 2. HSE Specialist
    -- =====================================================================
    INSERT INTO profiles (
        id,
        full_name,
        role_id,
        tenant_id
    ) VALUES (
        v_hse_specialist_id,
        'Test HSE Specialist',
        3,  -- HSE Specialist role
        v_tenant_id
    ) ON CONFLICT (id) DO NOTHING;

    -- Add to tenant_users
    INSERT INTO tenant_users (
        tenant_id,
        user_id,
        role_id,
        status
    ) VALUES (
        v_tenant_id,
        v_hse_specialist_id,
        3,  -- HSE Specialist role
        'active'
    ) ON CONFLICT (tenant_id, user_id) DO NOTHING;

    -- =====================================================================
    -- 3. Contractor Admin
    -- =====================================================================
    INSERT INTO profiles (
        id,
        full_name,
        role_id,
        tenant_id
    ) VALUES (
        v_contractor_admin_id,
        'Test Contractor Admin',
        4,  -- Contractor Admin role
        v_tenant_id
    ) ON CONFLICT (id) DO NOTHING;

    -- Add to tenant_users
    INSERT INTO tenant_users (
        tenant_id,
        user_id,
        role_id,
        status
    ) VALUES (
        v_tenant_id,
        v_contractor_admin_id,
        4,  -- Contractor Admin role
        'active'
    ) ON CONFLICT (tenant_id, user_id) DO NOTHING;

    -- =====================================================================
    -- 4. Supervisor
    -- =====================================================================
    INSERT INTO profiles (
        id,
        full_name,
        role_id,
        tenant_id
    ) VALUES (
        v_supervisor_id,
        'Test Supervisor',
        5,  -- Supervisor role
        v_tenant_id
    ) ON CONFLICT (id) DO NOTHING;

    -- Add to tenant_users
    INSERT INTO tenant_users (
        tenant_id,
        user_id,
        role_id,
        status
    ) VALUES (
        v_tenant_id,
        v_supervisor_id,
        5,  -- Supervisor role
        'active'
    ) ON CONFLICT (tenant_id, user_id) DO NOTHING;

    -- Print success message with user IDs
    RAISE NOTICE '✅ Test company users created successfully!';
    RAISE NOTICE 'Tenant ID: %', v_tenant_id;
    RAISE NOTICE '================================';
    RAISE NOTICE 'Company Admin ID: %', v_company_admin_id;
    RAISE NOTICE 'HSE Specialist ID: %', v_hse_specialist_id;
    RAISE NOTICE 'Contractor Admin ID: %', v_contractor_admin_id;
    RAISE NOTICE 'Supervisor ID: %', v_supervisor_id;

END $$;

-- =====================================================================
-- PART 3: Display User Information
-- =====================================================================

-- Show created users
SELECT
    p.id,
    p.full_name,
    r.name as role_name,
    t.name as company_name
FROM profiles p
JOIN roles r ON r.id = p.role_id
JOIN tenants t ON t.id = p.tenant_id
WHERE t.slug = 'test-company'
ORDER BY p.role_id;

-- =====================================================================
-- POST-MIGRATION INSTRUCTIONS
-- =====================================================================

/*
🔥 IMPORTANT: Manual Steps Required After Running This SQL

1. Copy the User IDs from the output above

2. Go to Supabase Dashboard → Authentication → Users

3. Create Auth Users Manually (or use Supabase API):

   A) Company Admin:
      - Email: company-admin@testcompany.com
      - Password: TestPass123!
      - User Metadata: {"user_id": "<company_admin_id_from_above>"}

   B) HSE Specialist:
      - Email: hse-specialist@testcompany.com
      - Password: TestPass123!
      - User Metadata: {"user_id": "<hse_specialist_id_from_above>"}

   C) Contractor Admin:
      - Email: contractor-admin@testcompany.com
      - Password: TestPass123!
      - User Metadata: {"user_id": "<contractor_admin_id_from_above>"}

   D) Supervisor:
      - Email: supervisor@testcompany.com
      - Password: TestPass123!
      - User Metadata: {"user_id": "<supervisor_id_from_above>"}

4. OR Use this SQL to get UUIDs for manual auth.users insert:

   SELECT
       p.id as profile_id,
       p.full_name,
       r.name as role_name
   FROM profiles p
   JOIN roles r ON r.id = p.role_id
   JOIN tenants t ON t.id = p.tenant_id
   WHERE t.slug = 'test-company'
   ORDER BY p.role_id;

📧 Test User Emails:
   - company-admin@testcompany.com (Company Admin)
   - hse-specialist@testcompany.com (HSE Specialist)
   - contractor-admin@testcompany.com (Contractor Admin)
   - supervisor@testcompany.com (Supervisor)

🔑 Suggested Password for All: TestPass123!

📋 What Each User Can Do:

   Company Admin:
   ✅ View Contractors (main menu)
   ✅ View Evaluations (main menu)
   ✅ Send assessments
   ✅ Send FRM32 reminders
   ✅ Manage users
   ✅ Create tenant-specific roles

   HSE Specialist:
   ✅ View Contractors (main menu)
   ✅ View Evaluations (main menu)
   ✅ View contractor progress

   Contractor Admin:
   ✅ Fill FRM32 form only
   ✅ Access EvrenGPT menu

   Supervisor:
   ✅ Fill FRM33, FRM34, FRM35 forms
   ✅ Access EvrenGPT menu
   ✅ Receive notifications when FRM32 completed

*/

-- =====================================================================
-- Migration Complete
-- =====================================================================

SELECT '✅ Test company and users created successfully! Follow post-migration instructions above.' as status;
