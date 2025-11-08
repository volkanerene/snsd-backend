-- =====================================================================
-- Migration: Fix Supervisor Role Permissions
-- Purpose: Ensure supervisor (role_id 5) has correct permissions
-- Author: System
-- Date: 2025-11-08
-- =====================================================================

-- Supervisor role should have:
-- 1. modules.access_evren_gpt - to access EvrenGPT/Submissions
-- 2. evaluations.fill_frm32 - to review and score contractor FRM32s
-- 3. frm.view_scores - to view evaluation scores
--
-- Supervisors should NOT have FRM33/34/35 fill permissions
-- (those are for contractors to fill after FRM32 submission)

-- First, let's check what role_id 5 currently has and fix it

-- Insert supervisor permissions if they don't exist
INSERT INTO role_permissions (role_id, permission_id)
SELECT 5, p.id
FROM permissions p
WHERE p.slug IN (
  'modules.access_evren_gpt',
  'evaluations.fill_frm32',
  'frm.view_scores'
)
AND NOT EXISTS (
  SELECT 1 FROM role_permissions rp
  WHERE rp.role_id = 5 AND rp.permission_id = p.id
)
ON CONFLICT DO NOTHING;

-- Remove FRM33/34/35 fill permissions from supervisor if they exist
-- (these should only be available to contractors)
DELETE FROM role_permissions
WHERE role_id = 5
AND permission_id IN (
  SELECT id FROM permissions
  WHERE slug IN (
    'evaluations.fill_frm33',
    'evaluations.fill_frm34',
    'evaluations.fill_frm35'
  )
);

-- Log the changes
SELECT 'Supervisor permissions have been configured correctly' as status;
