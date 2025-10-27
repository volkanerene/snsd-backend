-- Migration: Extended Permissions for Page & Module Access Control
-- Purpose: Add view and access permissions for pages, modules, and FRM forms
-- Author: System
-- Date: 2025-10-27

-- Add new permissions for page-level access control
INSERT INTO permissions (name, description, category) VALUES
  -- Page View Permissions
  ('pages.view_dashboard', 'View dashboard page', 'pages'),
  ('pages.view_admin_panel', 'Access admin panel section', 'pages'),
  ('pages.view_tenants', 'View tenants management page', 'pages'),
  ('pages.view_users', 'View users management page', 'pages'),
  ('pages.view_roles', 'View roles management page', 'pages'),
  ('pages.view_contractors', 'View contractors page', 'pages'),
  ('pages.view_evaluations', 'View evaluations page', 'pages'),
  ('pages.view_payments', 'View payments page', 'pages'),

  -- Module Access Permissions
  ('modules.access_evren_gpt', 'Access EvrenGPT module', 'modules'),
  ('modules.access_marcel_gpt', 'Access MarcelGPT module', 'modules'),
  ('modules.access_safety_bud', 'Access SafetyBud module', 'modules'),

  -- EvrenGPT Sub-pages
  ('evren_gpt.view_contractors', 'View EvrenGPT contractors page', 'evren_gpt'),
  ('evren_gpt.view_evaluations', 'View EvrenGPT evaluations', 'evren_gpt'),
  ('evren_gpt.upload_contractors', 'Upload contractors to EvrenGPT', 'evren_gpt'),

  -- FRM Form Permissions
  ('frm.access_frm32', 'Access FRM32 form (Contractor self-assessment)', 'frm'),
  ('frm.access_frm33', 'Access FRM33 form (Supervisor evaluation)', 'frm'),
  ('frm.access_frm34', 'Access FRM34 form (Supervisor final)', 'frm'),
  ('frm.access_frm35', 'Access FRM35 form (HSE Specialist evaluation)', 'frm'),
  ('frm.view_progress', 'View FRM form progress and status', 'frm'),
  ('frm.view_scores', 'View FRM evaluation scores', 'frm'),
  ('frm.submit_frm32', 'Submit FRM32 form', 'frm'),
  ('frm.submit_frm33', 'Submit FRM33 form', 'frm'),
  ('frm.submit_frm34', 'Submit FRM34 form', 'frm'),
  ('frm.submit_frm35', 'Submit FRM35 form', 'frm'),

  -- Evaluation View Permissions (by type)
  ('evaluations.view_frm32', 'View FRM32 evaluations', 'evaluations'),
  ('evaluations.view_frm33', 'View FRM33 evaluations', 'evaluations'),
  ('evaluations.view_frm34', 'View FRM34 evaluations', 'evaluations'),
  ('evaluations.view_frm35', 'View FRM35 evaluations', 'evaluations'),

  -- Notification Permissions
  ('notifications.receive', 'Receive system notifications', 'notifications'),
  ('notifications.send', 'Send notifications to users', 'notifications')
ON CONFLICT (name) DO NOTHING;

-- =====================================================================
-- Assign new permissions to existing roles
-- =====================================================================

-- Super Admin (role_id: 1) - ALL permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions
WHERE name LIKE 'pages.%'
   OR name LIKE 'modules.%'
   OR name LIKE 'evren_gpt.%'
   OR name LIKE 'frm.%'
   OR name LIKE 'evaluations.view_%'
   OR name LIKE 'notifications.%'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Company Admin (role_id: 2) - Most permissions, can view progress
-- Assuming role_id 2 exists, adjust if needed
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions
WHERE name IN (
  'pages.view_dashboard',
  'pages.view_contractors',
  'pages.view_evaluations',
  'pages.view_users',
  'modules.access_evren_gpt',
  'evren_gpt.view_contractors',
  'evren_gpt.view_evaluations',
  'evren_gpt.upload_contractors',
  'frm.view_progress',
  'frm.view_scores',
  'evaluations.view_frm32',
  'evaluations.view_frm33',
  'evaluations.view_frm34',
  'evaluations.view_frm35',
  'notifications.receive',
  'notifications.send'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- HSE Specialist (role_id: 3) - Evaluation access, can upload contractors
-- Assuming role_id 3 exists
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions
WHERE name IN (
  'pages.view_dashboard',
  'pages.view_contractors',
  'pages.view_evaluations',
  'modules.access_evren_gpt',
  'evren_gpt.view_contractors',
  'evren_gpt.view_evaluations',
  'evren_gpt.upload_contractors',
  'frm.access_frm35',
  'frm.submit_frm35',
  'frm.view_progress',
  'frm.view_scores',
  'evaluations.view_frm32',
  'evaluations.view_frm33',
  'evaluations.view_frm34',
  'evaluations.view_frm35',
  'notifications.receive'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Contractor Admin (role_id: 4) - Only FRM32 access
-- This role fills out FRM32 (self-assessment)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions
WHERE name IN (
  'pages.view_dashboard',
  'modules.access_evren_gpt',
  'frm.access_frm32',
  'frm.submit_frm32',
  'frm.view_progress',
  'evaluations.view_frm32',
  'notifications.receive'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Supervisor (role_id: 5) - FRM33 and FRM34 access
-- Assuming role_id 5 exists for Supervisor role
-- Supervisors evaluate contractors with FRM33 and FRM34
INSERT INTO role_permissions (role_id, permission_id)
SELECT 5, id FROM permissions
WHERE name IN (
  'pages.view_dashboard',
  'pages.view_contractors',
  'pages.view_evaluations',
  'modules.access_evren_gpt',
  'evren_gpt.view_evaluations',
  'frm.access_frm33',
  'frm.access_frm34',
  'frm.submit_frm33',
  'frm.submit_frm34',
  'frm.view_progress',
  'evaluations.view_frm32',
  'evaluations.view_frm33',
  'evaluations.view_frm34',
  'notifications.receive',
  'notifications.send'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- =====================================================================
-- Create helper function to check user permissions
-- =====================================================================

CREATE OR REPLACE FUNCTION user_has_permission(
  user_id UUID,
  permission_name VARCHAR
)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM profiles p
    JOIN role_permissions rp ON rp.role_id = p.role_id
    JOIN permissions perm ON perm.id = rp.permission_id
    WHERE p.id = user_id
      AND perm.name = permission_name
      AND perm.is_active = true
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Add comment
COMMENT ON FUNCTION user_has_permission IS 'Check if a user has a specific permission by name';

-- =====================================================================
-- Create view for easier permission queries
-- =====================================================================

CREATE OR REPLACE VIEW user_permissions_view AS
SELECT
  p.id AS user_id,
  p.full_name,
  r.id AS role_id,
  r.name AS role_name,
  perm.id AS permission_id,
  perm.name AS permission_name,
  perm.description AS permission_description,
  perm.category AS permission_category
FROM profiles p
JOIN roles r ON r.id = p.role_id
JOIN role_permissions rp ON rp.role_id = r.id
JOIN permissions perm ON perm.id = rp.permission_id
WHERE perm.is_active = true;

-- Add comment
COMMENT ON VIEW user_permissions_view IS 'Denormalized view of users and their permissions for easier querying';

-- Grant access to the view
GRANT SELECT ON user_permissions_view TO authenticated;
