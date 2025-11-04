-- =====================================================================
-- Migration: EvrenGPT Complete System Update
-- Purpose: Complete overhaul of EvrenGPT with tenant-specific roles
-- Author: System
-- Date: 2025-10-31
-- =====================================================================

-- =====================================================================
-- 1. Add tenant_id to roles table for tenant-specific custom roles
-- =====================================================================

-- Add tenant_id column to roles (nullable for global roles)
ALTER TABLE roles ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;

-- Create index for tenant filtering
CREATE INDEX IF NOT EXISTS idx_roles_tenant_id ON roles(tenant_id);

-- Add comment
COMMENT ON COLUMN roles.tenant_id IS 'Tenant ID for tenant-specific roles. NULL for global system roles.';

-- Update RLS policy for roles
DROP POLICY IF EXISTS "Company admins can view their tenant roles" ON roles;
CREATE POLICY "Company admins can view their tenant roles"
  ON roles FOR SELECT
  TO authenticated
  USING (
    tenant_id IS NULL  -- Global roles visible to all
    OR
    tenant_id IN (      -- Tenant-specific roles only to tenant members
      SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
    )
  );

-- Policy for creating tenant-specific roles
DROP POLICY IF EXISTS "Company admins can create tenant roles" ON roles;
CREATE POLICY "Company admins can create tenant roles"
  ON roles FOR INSERT
  TO authenticated
  WITH CHECK (
    -- Super Admin can create any role
    (
      EXISTS (
        SELECT 1 FROM profiles
        WHERE profiles.id = auth.uid() AND profiles.role_id = 1
      )
    )
    OR
    -- Company Admin can create tenant-specific roles for their tenant
    (
      EXISTS (
        SELECT 1 FROM profiles p
        JOIN tenant_users tu ON tu.user_id = p.id
        WHERE p.id = auth.uid()
          AND p.role_id = 2
          AND tu.tenant_id = roles.tenant_id
      )
    )
  );

-- =====================================================================
-- 2. Update EvrenGPT Permissions
-- =====================================================================

-- Add/Update permissions for new EvrenGPT structure
INSERT INTO permissions (name, description, category) VALUES
  -- Main menu permissions
  ('pages.view_contractors', 'View Contractors page (main menu)', 'pages'),
  ('pages.view_evaluations', 'View Evaluations page (main menu)', 'pages'),

  -- FRM Fill permissions (for forms under EvrenGPT menu)
  ('evaluations.fill_frm32', 'Fill/Submit FRM32 form (Contractor Admin)', 'evaluations'),
  ('evaluations.fill_frm33', 'Fill/Submit FRM33 form (Supervisor)', 'evaluations'),
  ('evaluations.fill_frm34', 'Fill/Submit FRM34 form (Supervisor)', 'evaluations'),
  ('evaluations.fill_frm35', 'Fill/Submit FRM35 form (Supervisor)', 'evaluations'),

  -- Evaluation management
  ('evaluations.send_assessment', 'Send assessment to contractors', 'evaluations'),
  ('evaluations.send_reminders', 'Send FRM32 reminder emails', 'evaluations')
ON CONFLICT (name) DO NOTHING;

-- =====================================================================
-- 3. Update Role Permissions for New Structure
-- =====================================================================

-- Super Admin (role_id: 1) - ALL permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions
WHERE name IN (
  'pages.view_contractors',
  'pages.view_evaluations',
  'evaluations.fill_frm32',
  'evaluations.fill_frm33',
  'evaluations.fill_frm34',
  'evaluations.fill_frm35',
  'evaluations.send_assessment',
  'evaluations.send_reminders'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Company Admin (role_id: 2) - Can view Contractors & Evaluations, send assessments
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions
WHERE name IN (
  'pages.view_contractors',
  'pages.view_evaluations',
  'evren_gpt.view_contractors',
  'evren_gpt.view_evaluations',
  'evaluations.send_assessment',
  'evaluations.send_reminders'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- HSE Specialist (role_id: 3) - Can view Contractors & Evaluations
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions
WHERE name IN (
  'pages.view_contractors',
  'pages.view_evaluations',
  'evren_gpt.view_contractors',
  'evren_gpt.view_evaluations'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Contractor Admin (role_id: 4) - Can ONLY fill FRM32
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions
WHERE name IN (
  'evaluations.fill_frm32',
  'modules.access_evren_gpt'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Remove old permissions from Contractor Admin (no longer has access to contractors page)
DELETE FROM role_permissions
WHERE role_id = 4
AND permission_id IN (
  SELECT id FROM permissions
  WHERE name IN ('pages.view_contractors', 'evren_gpt.view_contractors')
);

-- Supervisor (role_id: 5) - Can fill FRM33, FRM34, FRM35
INSERT INTO role_permissions (role_id, permission_id)
SELECT 5, id FROM permissions
WHERE name IN (
  'evaluations.fill_frm33',
  'evaluations.fill_frm34',
  'evaluations.fill_frm35',
  'modules.access_evren_gpt'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- =====================================================================
-- 4. Update EvrenGPT Notifications for FRM32 Completion -> Supervisor
-- =====================================================================

-- Function to notify supervisor after FRM32 completion
CREATE OR REPLACE FUNCTION notify_supervisor_after_frm32()
RETURNS TRIGGER AS $$
DECLARE
  supervisor_email VARCHAR;
  supervisor_name VARCHAR;
  contractor_name VARCHAR;
BEGIN
  -- Only proceed if FRM32 is being completed
  IF NEW.form_id = 'frm32' AND NEW.status = 'completed' AND OLD.status != 'completed' THEN

    -- Get contractor name
    SELECT name INTO contractor_name
    FROM contractors
    WHERE id = NEW.contractor_id;

    -- TODO: Get supervisor email (this should be based on your business logic)
    -- For now, we'll create a notification that can be picked up by the system
    -- You should update this to get the actual supervisor assigned to this contractor

    -- Create notification for supervisor
    INSERT INTO evren_gpt_notifications (
      session_id,
      contractor_id,
      recipient_email,
      recipient_name,
      notification_type,
      form_id,
      subject,
      body,
      status
    ) VALUES (
      NEW.session_id,
      NEW.contractor_id,
      'supervisor@snsdconsultant.com',  -- Replace with actual supervisor email logic
      'Supervisor',
      'frm33_invite',
      'frm33',
      'Action Required: Complete FRM33 Evaluation',
      'FRM32 has been completed for contractor: ' || contractor_name ||
      '. Please proceed with FRM33 evaluation.' ||
      E'\n\nSession ID: ' || NEW.session_id ||
      E'\nContractor: ' || contractor_name,
      'pending'
    );

  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for FRM32 completion notification
DROP TRIGGER IF EXISTS notify_supervisor_on_frm32_completion ON evren_gpt_form_submissions;
CREATE TRIGGER notify_supervisor_on_frm32_completion
  AFTER UPDATE ON evren_gpt_form_submissions
  FOR EACH ROW
  EXECUTE FUNCTION notify_supervisor_after_frm32();

-- =====================================================================
-- 5. Update Final Score Calculation
-- =====================================================================

-- Update the final score calculation function to use FRM32 and FRM35 only
CREATE OR REPLACE FUNCTION calculate_evren_final_score(
    p_session_id VARCHAR,
    p_contractor_id UUID,
    p_cycle INT
)
RETURNS DECIMAL AS $$
DECLARE
    frm32_score DECIMAL;
    frm35_score DECIMAL;
    final_score DECIMAL;
BEGIN
    -- Get FRM32 score
    SELECT final_score INTO frm32_score
    FROM evren_gpt_form_submissions
    WHERE session_id = p_session_id
      AND contractor_id = p_contractor_id
      AND cycle = p_cycle
      AND form_id = 'frm32'
      AND status = 'completed'
      AND final_score IS NOT NULL;

    -- Get FRM35 score
    SELECT final_score INTO frm35_score
    FROM evren_gpt_form_submissions
    WHERE session_id = p_session_id
      AND contractor_id = p_contractor_id
      AND cycle = p_cycle
      AND form_id = 'frm35'
      AND status = 'completed'
      AND final_score IS NOT NULL;

    -- Calculate: (FRM32 * 0.5) + (FRM35 * 0.5)
    IF frm32_score IS NOT NULL AND frm35_score IS NOT NULL THEN
        final_score := (frm32_score * 0.5) + (frm35_score * 0.5);
        RETURN final_score;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- 6. Add Helper View for Evaluations Page
-- =====================================================================

-- Create or replace view for evaluations page data
CREATE OR REPLACE VIEW evren_gpt_evaluations_overview AS
SELECT
    sc.session_id,
    sc.contractor_id,
    c.name as contractor_name,
    sc.cycle,

    -- FRM statuses
    COALESCE(
        (SELECT status FROM evren_gpt_form_submissions
         WHERE session_id = sc.session_id
         AND contractor_id = sc.contractor_id
         AND cycle = sc.cycle
         AND form_id = 'frm32'
         LIMIT 1),
        'pending'
    ) as frm32_status,

    COALESCE(
        (SELECT status FROM evren_gpt_form_submissions
         WHERE session_id = sc.session_id
         AND contractor_id = sc.contractor_id
         AND cycle = sc.cycle
         AND form_id = 'frm33'
         LIMIT 1),
        'pending'
    ) as frm33_status,

    COALESCE(
        (SELECT status FROM evren_gpt_form_submissions
         WHERE session_id = sc.session_id
         AND contractor_id = sc.contractor_id
         AND cycle = sc.cycle
         AND form_id = 'frm34'
         LIMIT 1),
        'pending'
    ) as frm34_status,

    COALESCE(
        (SELECT status FROM evren_gpt_form_submissions
         WHERE session_id = sc.session_id
         AND contractor_id = sc.contractor_id
         AND cycle = sc.cycle
         AND form_id = 'frm35'
         LIMIT 1),
        'pending'
    ) as frm35_status,

    -- FRM scores
    (SELECT final_score FROM evren_gpt_form_submissions
     WHERE session_id = sc.session_id
     AND contractor_id = sc.contractor_id
     AND cycle = sc.cycle
     AND form_id = 'frm32'
     LIMIT 1) as frm32_score,

    (SELECT final_score FROM evren_gpt_form_submissions
     WHERE session_id = sc.session_id
     AND contractor_id = sc.contractor_id
     AND cycle = sc.cycle
     AND form_id = 'frm33'
     LIMIT 1) as frm33_score,

    (SELECT final_score FROM evren_gpt_form_submissions
     WHERE session_id = sc.session_id
     AND contractor_id = sc.contractor_id
     AND cycle = sc.cycle
     AND form_id = 'frm34'
     LIMIT 1) as frm34_score,

    (SELECT final_score FROM evren_gpt_form_submissions
     WHERE session_id = sc.session_id
     AND contractor_id = sc.contractor_id
     AND cycle = sc.cycle
     AND form_id = 'frm35'
     LIMIT 1) as frm35_score,

    -- Calculated final score
    sc.final_score,

    -- Timestamps
    sc.frm32_sent_at,
    sc.frm32_completed_at,
    sc.frm33_completed_at,
    sc.frm34_completed_at,
    sc.frm35_completed_at,
    sc.updated_at as last_updated

FROM evren_gpt_session_contractors sc
JOIN contractors c ON c.id = sc.contractor_id
JOIN evren_gpt_sessions s ON s.session_id = sc.session_id
WHERE s.status = 'active';

COMMENT ON VIEW evren_gpt_evaluations_overview IS 'Comprehensive view for Evaluations page showing all contractor progress';

-- Grant access
GRANT SELECT ON evren_gpt_evaluations_overview TO authenticated;

-- =====================================================================
-- 7. Comments and Documentation
-- =====================================================================

COMMENT ON COLUMN roles.tenant_id IS 'NULL = Global system role, UUID = Tenant-specific custom role';

COMMENT ON FUNCTION calculate_evren_final_score IS 'Calculates final score as: (FRM32 × 0.5) + (FRM35 × 0.5)';

COMMENT ON FUNCTION notify_supervisor_after_frm32 IS 'Sends notification to supervisor when FRM32 is completed';

-- =====================================================================
-- Migration Complete
-- =====================================================================

-- Summary of changes:
-- 1. ✅ Roles table updated with tenant_id for tenant-specific roles
-- 2. ✅ RLS policies updated for tenant-specific role visibility
-- 3. ✅ New permissions added for Contractors & Evaluations main menus
-- 4. ✅ FRM fill permissions added for Contractor Admin and Supervisor
-- 5. ✅ Role permissions updated according to new structure
-- 6. ✅ Supervisor notification trigger added for FRM32 completion
-- 7. ✅ Final score calculation updated (FRM32 × 0.5 + FRM35 × 0.5)
-- 8. ✅ Evaluations overview view created for the evaluations page

SELECT 'EvrenGPT Complete Update Migration Applied Successfully!' as status;
