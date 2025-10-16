-- Migration: Create tenant_users junction table
-- Purpose: Many-to-many relationship between tenants and users with role assignment
-- Author: System
-- Date: 2025-10-17

-- Create tenant_users table
CREATE TABLE IF NOT EXISTS tenant_users (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
  status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
  invited_by UUID REFERENCES auth.users(id),
  joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(tenant_id, user_id)
);

-- Create indexes
CREATE INDEX idx_tenant_users_tenant_id ON tenant_users(tenant_id);
CREATE INDEX idx_tenant_users_user_id ON tenant_users(user_id);
CREATE INDEX idx_tenant_users_role_id ON tenant_users(role_id);
CREATE INDEX idx_tenant_users_status ON tenant_users(status);

-- Enable RLS
ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Super admins can see all relationships
CREATE POLICY "Super admins can view all tenant_users"
  ON tenant_users FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

-- Users can see their own tenant relationships
CREATE POLICY "Users can view their own tenant relationships"
  ON tenant_users FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- Tenant admins can see users in their tenant
CREATE POLICY "Tenant admins can view their tenant users"
  ON tenant_users FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM tenant_users
      WHERE user_id = auth.uid()
      AND role_id IN (1, 2) -- Super Admin or Admin
    )
  );

-- Only admins can insert tenant_users
CREATE POLICY "Admins can insert tenant_users"
  ON tenant_users FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
  );

-- Only admins can update tenant_users
CREATE POLICY "Admins can update tenant_users"
  ON tenant_users FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
  );

-- Only admins can delete tenant_users
CREATE POLICY "Admins can delete tenant_users"
  ON tenant_users FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
  );

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_tenant_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tenant_users_updated_at
  BEFORE UPDATE ON tenant_users
  FOR EACH ROW
  EXECUTE FUNCTION update_tenant_users_updated_at();

-- Add comments
COMMENT ON TABLE tenant_users IS 'Junction table for tenant-user relationships with role assignments';
COMMENT ON COLUMN tenant_users.tenant_id IS 'Reference to tenant';
COMMENT ON COLUMN tenant_users.user_id IS 'Reference to user (auth.users)';
COMMENT ON COLUMN tenant_users.role_id IS 'User role within this tenant';
COMMENT ON COLUMN tenant_users.status IS 'User status in this tenant';
COMMENT ON COLUMN tenant_users.invited_by IS 'User who invited this person';
