-- Migration: Create invitations table
-- Purpose: Manage user invitations to tenants
-- Author: System
-- Date: 2025-10-17

-- Create invitations table
CREATE TABLE IF NOT EXISTS invitations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
  invited_by UUID NOT NULL REFERENCES auth.users(id),
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired', 'cancelled')),
  token TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  accepted_at TIMESTAMP WITH TIME ZONE,
  accepted_by UUID REFERENCES auth.users(id),
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_invitations_email ON invitations(email);
CREATE INDEX idx_invitations_tenant_id ON invitations(tenant_id);
CREATE INDEX idx_invitations_status ON invitations(status);
CREATE INDEX idx_invitations_token ON invitations(token);
CREATE INDEX idx_invitations_expires_at ON invitations(expires_at);
CREATE INDEX idx_invitations_invited_by ON invitations(invited_by);

-- Enable RLS
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Super admins can see all invitations
CREATE POLICY "Super admins can view all invitations"
  ON invitations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

-- Users can see invitations they sent
CREATE POLICY "Users can view invitations they sent"
  ON invitations FOR SELECT
  TO authenticated
  USING (invited_by = auth.uid());

-- Tenant admins can see invitations for their tenant
CREATE POLICY "Tenant admins can view their tenant invitations"
  ON invitations FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM tenant_users
      WHERE user_id = auth.uid()
      AND role_id IN (1, 2)
    )
  );

-- Users can view invitations sent to their email
CREATE POLICY "Users can view invitations sent to them"
  ON invitations FOR SELECT
  TO authenticated
  USING (
    email = (SELECT email FROM auth.users WHERE id = auth.uid())
  );

-- Admins can create invitations
CREATE POLICY "Admins can create invitations"
  ON invitations FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
    OR
    tenant_id IN (
      SELECT tenant_id FROM tenant_users
      WHERE user_id = auth.uid()
      AND role_id = 2
    )
  );

-- Admins can update invitations
CREATE POLICY "Admins can update invitations"
  ON invitations FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
    OR invited_by = auth.uid()
  );

-- Admins can delete invitations
CREATE POLICY "Admins can delete invitations"
  ON invitations FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id IN (1, 2)
    )
    OR invited_by = auth.uid()
  );

-- Create function to generate invitation token
CREATE OR REPLACE FUNCTION generate_invitation_token()
RETURNS TEXT AS $$
DECLARE
  token TEXT;
  exists_count INTEGER;
BEGIN
  LOOP
    -- Generate a random token (URL-safe base64)
    token := encode(gen_random_bytes(32), 'base64');
    token := replace(replace(replace(token, '+', '-'), '/', '_'), '=', '');

    -- Check if token already exists
    SELECT COUNT(*) INTO exists_count FROM invitations WHERE invitations.token = token;

    EXIT WHEN exists_count = 0;
  END LOOP;

  RETURN token;
END;
$$ LANGUAGE plpgsql;

-- Create function to auto-expire invitations
CREATE OR REPLACE FUNCTION auto_expire_invitations()
RETURNS void AS $$
BEGIN
  UPDATE invitations
  SET status = 'expired'
  WHERE status = 'pending'
    AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_invitations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER invitations_updated_at
  BEFORE UPDATE ON invitations
  FOR EACH ROW
  EXECUTE FUNCTION update_invitations_updated_at();

-- Create trigger to set default expiration (7 days)
CREATE OR REPLACE FUNCTION set_invitation_expiration()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.expires_at IS NULL THEN
    NEW.expires_at := NOW() + INTERVAL '7 days';
  END IF;

  IF NEW.token IS NULL OR NEW.token = '' THEN
    NEW.token := generate_invitation_token();
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER invitations_set_defaults
  BEFORE INSERT ON invitations
  FOR EACH ROW
  EXECUTE FUNCTION set_invitation_expiration();

-- Add comments
COMMENT ON TABLE invitations IS 'User invitations to join tenants';
COMMENT ON COLUMN invitations.email IS 'Email address of invitee';
COMMENT ON COLUMN invitations.tenant_id IS 'Tenant the user is invited to';
COMMENT ON COLUMN invitations.role_id IS 'Role the user will have in the tenant';
COMMENT ON COLUMN invitations.token IS 'Unique invitation token for acceptance link';
COMMENT ON COLUMN invitations.expires_at IS 'When the invitation expires';
COMMENT ON COLUMN invitations.metadata IS 'Additional invitation metadata (welcome message, etc.)';
