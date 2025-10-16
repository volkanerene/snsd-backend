-- Migration: Create permissions and role_permissions tables
-- Purpose: Granular permission system for RBAC
-- Author: System
-- Date: 2025-10-17

-- Create permissions table
CREATE TABLE IF NOT EXISTS permissions (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  category VARCHAR(50) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create role_permissions junction table
CREATE TABLE IF NOT EXISTS role_permissions (
  id SERIAL PRIMARY KEY,
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(role_id, permission_id)
);

-- Create indexes
CREATE INDEX idx_permissions_category ON permissions(category);
CREATE INDEX idx_permissions_is_active ON permissions(is_active);
CREATE INDEX idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX idx_role_permissions_permission_id ON role_permissions(permission_id);

-- Enable RLS
ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for permissions
CREATE POLICY "Anyone can view active permissions"
  ON permissions FOR SELECT
  TO authenticated
  USING (is_active = true);

CREATE POLICY "Only super admins can manage permissions"
  ON permissions FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

-- RLS Policies for role_permissions
CREATE POLICY "Anyone can view role_permissions"
  ON role_permissions FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Only admins can manage role_permissions"
  ON role_permissions FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
  );

-- Seed default permissions
INSERT INTO permissions (name, description, category) VALUES
  -- User management
  ('users.create', 'Create new users', 'users'),
  ('users.read', 'View user details', 'users'),
  ('users.update', 'Update user information', 'users'),
  ('users.delete', 'Delete or deactivate users', 'users'),
  ('users.invite', 'Invite new users to platform', 'users'),
  ('users.reset_password', 'Trigger password reset for users', 'users'),

  -- Tenant management
  ('tenants.create', 'Create new tenants', 'tenants'),
  ('tenants.read', 'View tenant details', 'tenants'),
  ('tenants.update', 'Update tenant information', 'tenants'),
  ('tenants.delete', 'Delete tenants', 'tenants'),
  ('tenants.activate', 'Activate tenants', 'tenants'),
  ('tenants.suspend', 'Suspend tenants', 'tenants'),
  ('tenants.users.manage', 'Manage users within tenant', 'tenants'),

  -- Role management
  ('roles.create', 'Create new roles', 'roles'),
  ('roles.read', 'View role details', 'roles'),
  ('roles.update', 'Update role information', 'roles'),
  ('roles.delete', 'Delete roles', 'roles'),
  ('roles.permissions.manage', 'Manage role permissions', 'roles'),

  -- Contractor management
  ('contractors.create', 'Create new contractors', 'contractors'),
  ('contractors.read', 'View contractor details', 'contractors'),
  ('contractors.update', 'Update contractor information', 'contractors'),
  ('contractors.delete', 'Delete contractors', 'contractors'),

  -- Evaluation management
  ('evaluations.create', 'Create new evaluations', 'evaluations'),
  ('evaluations.read', 'View evaluations', 'evaluations'),
  ('evaluations.update', 'Update evaluations', 'evaluations'),
  ('evaluations.delete', 'Delete evaluations', 'evaluations'),
  ('evaluations.submit', 'Submit evaluations', 'evaluations'),
  ('evaluations.approve', 'Approve evaluations', 'evaluations'),
  ('evaluations.reject', 'Reject evaluations', 'evaluations'),

  -- Payment management
  ('payments.create', 'Record new payments', 'payments'),
  ('payments.read', 'View payment details', 'payments'),
  ('payments.update', 'Update payment information', 'payments'),
  ('payments.delete', 'Delete payments', 'payments'),

  -- Reports & Analytics
  ('reports.view', 'View reports and analytics', 'reports'),
  ('reports.export', 'Export reports', 'reports'),

  -- System administration
  ('system.settings', 'Manage system settings', 'system'),
  ('system.logs', 'View system logs', 'system'),
  ('system.backup', 'Create system backups', 'system')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to roles
-- Super Admin (role_id: 1) - ALL permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Admin (role_id: 2) - Most permissions except system-level
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions
WHERE category NOT IN ('system')
  AND name NOT IN ('tenants.create', 'tenants.delete', 'roles.create', 'roles.delete')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- HSE Manager (role_id: 3) - Evaluation and contractor management
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions
WHERE category IN ('contractors', 'evaluations', 'reports')
  OR name IN ('users.read')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Contractor (role_id: 4) - Limited to own evaluations
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions
WHERE name IN (
  'evaluations.read',
  'evaluations.submit',
  'contractors.read'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Create updated_at trigger for permissions
CREATE OR REPLACE FUNCTION update_permissions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER permissions_updated_at
  BEFORE UPDATE ON permissions
  FOR EACH ROW
  EXECUTE FUNCTION update_permissions_updated_at();

-- Add comments
COMMENT ON TABLE permissions IS 'System permissions for granular access control';
COMMENT ON TABLE role_permissions IS 'Maps roles to their assigned permissions';
COMMENT ON COLUMN permissions.category IS 'Permission category for grouping (users, tenants, evaluations, etc.)';
COMMENT ON COLUMN permissions.is_active IS 'Whether this permission is currently active';
