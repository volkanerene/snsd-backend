-- Migration: EvrenGPT Permissions Update
-- Purpose: Add fill permissions for FRM forms and update role assignments
-- Author: System
-- Date: 2025-10-31

-- Add new fill permissions for FRM forms
INSERT INTO permissions (name, description, category) VALUES
  ('evaluations.fill_frm32', 'Fill/Submit FRM32 form (Contractor Admin)', 'evaluations'),
  ('evaluations.fill_frm33', 'Fill/Submit FRM33 form (Supervisor)', 'evaluations'),
  ('evaluations.fill_frm34', 'Fill/Submit FRM34 form (Supervisor)', 'evaluations'),
  ('evaluations.fill_frm35', 'Fill/Submit FRM35 form (Supervisor)', 'evaluations')
ON CONFLICT (name) DO NOTHING;

-- =====================================================================
-- Update role permissions for the new fill permissions
-- =====================================================================

-- Super Admin (role_id: 1) - ALL permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions
WHERE name LIKE 'evaluations.fill_%'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Company Admin (role_id: 2) - Can view all evaluations
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions
WHERE name IN (
  'pages.view_contractors',
  'pages.view_evaluations'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- HSE Specialist (role_id: 3) - Can view evaluations and contractors
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions
WHERE name IN (
  'pages.view_contractors',
  'pages.view_evaluations'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Contractor Admin (role_id: 4) - Can fill FRM32 only
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions
WHERE name IN (
  'evaluations.fill_frm32',
  'modules.access_evren_gpt'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Supervisor (role_id: 5) - Can fill FRM33, FRM34, FRM35
INSERT INTO role_permissions (role_id, permission_id)
SELECT 5, id FROM permissions
WHERE name IN (
  'evaluations.fill_frm33',
  'evaluations.fill_frm34',
  'evaluations.fill_frm35',
  'modules.access_evren_gpt',
  'frm.access_frm35',
  'frm.submit_frm35',
  'evaluations.view_frm35'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- =====================================================================
-- Comments
-- =====================================================================

COMMENT ON PERMISSION 'evaluations.fill_frm32' IS 'Contractor Admin fills FRM32 - Self Assessment';
COMMENT ON PERMISSION 'evaluations.fill_frm33' IS 'Supervisor fills FRM33 after FRM32 completion';
COMMENT ON PERMISSION 'evaluations.fill_frm34' IS 'Supervisor fills FRM34 for detailed observations';
COMMENT ON PERMISSION 'evaluations.fill_frm35' IS 'Supervisor fills FRM35 - Final Assessment (contributes to final score)';
