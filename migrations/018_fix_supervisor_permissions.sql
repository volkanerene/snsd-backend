-- =====================================================================
-- Migration: Fix Supervisor Permissions
-- Purpose: Ensure supervisor role (role_id: 5) has all required permissions
-- Date: 2025-11-08
-- =====================================================================

-- First, ensure all permissions exist
INSERT INTO permissions (name, description, category) VALUES
  ('pages.view_dashboard', 'View dashboard page', 'pages'),
  ('pages.view_contractors', 'View contractors page', 'pages'),
  ('pages.view_evaluations', 'View evaluations page', 'pages'),
  ('modules.access_evren_gpt', 'Access EvrenGPT module', 'modules'),
  ('evren_gpt.view_evaluations', 'View EvrenGPT evaluations', 'evren_gpt'),
  ('evaluations.fill_frm33', 'Fill/Submit FRM33 form (Supervisor)', 'evaluations'),
  ('evaluations.fill_frm34', 'Fill/Submit FRM34 form (Supervisor)', 'evaluations'),
  ('evaluations.fill_frm35', 'Fill/Submit FRM35 form (Supervisor)', 'evaluations'),
  ('evaluations.view_frm32', 'View FRM32 evaluations', 'evaluations'),
  ('evaluations.view_frm33', 'View FRM33 evaluations', 'evaluations'),
  ('evaluations.view_frm34', 'View FRM34 evaluations', 'evaluations'),
  ('frm.access_frm33', 'Access FRM33 form (Supervisor evaluation)', 'frm'),
  ('frm.access_frm34', 'Access FRM34 form (Supervisor final)', 'frm'),
  ('frm.access_frm35', 'Access FRM35 form (HSE Specialist evaluation)', 'frm'),
  ('frm.view_progress', 'View FRM form progress and status', 'frm'),
  ('frm.submit_frm33', 'Submit FRM33 form', 'frm'),
  ('frm.submit_frm34', 'Submit FRM34 form', 'frm'),
  ('notifications.receive', 'Receive system notifications', 'notifications'),
  ('notifications.send', 'Send notifications to users', 'notifications')
ON CONFLICT (name) DO NOTHING;

-- Delete existing supervisor permissions (to avoid duplicates)
DELETE FROM role_permissions WHERE role_id = 5;

-- Assign all required permissions to Supervisor (role_id: 5)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 5, id FROM permissions
WHERE name IN (
  'pages.view_dashboard',
  'pages.view_contractors',
  'pages.view_evaluations',
  'modules.access_evren_gpt',
  'evren_gpt.view_evaluations',
  'evaluations.fill_frm33',
  'evaluations.fill_frm34',
  'evaluations.fill_frm35',
  'evaluations.view_frm32',
  'evaluations.view_frm33',
  'evaluations.view_frm34',
  'frm.access_frm33',
  'frm.access_frm34',
  'frm.access_frm35',
  'frm.view_progress',
  'frm.submit_frm33',
  'frm.submit_frm34',
  'notifications.receive',
  'notifications.send'
);

-- Verify the assignments
SELECT
  COUNT(*) as supervisor_permission_count,
  STRING_AGG(p.name, ', ' ORDER BY p.name) as permission_names
FROM role_permissions rp
JOIN permissions p ON rp.permission_id = p.id
WHERE rp.role_id = 5;
