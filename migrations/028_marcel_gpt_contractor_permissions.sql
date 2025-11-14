-- Migration: Grant MarcelGPT permissions to Contractor and Supervisor roles
-- Purpose: Allow contractors and supervisors to access assigned training videos
-- Date: 2025-11-14

-- Assign MarcelGPT permissions to Contractor (role_id 4)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions WHERE name IN (
  'marcel_gpt.access',
  'marcel_gpt.view_jobs',
  'marcel_gpt.download_video'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign MarcelGPT permissions to Supervisor (role_id 5)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 5, id FROM permissions WHERE name IN (
  'marcel_gpt.access',
  'marcel_gpt.view_jobs',
  'marcel_gpt.download_video'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign to HSE Specialist (role_id 3) - extended access
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions WHERE category = 'marcel_gpt'
ON CONFLICT (role_id, permission_id) DO NOTHING;

SELECT 'MarcelGPT permissions assigned to contractors and supervisors' as status;
