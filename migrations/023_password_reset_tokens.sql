-- Create password_reset_tokens table for forgot password functionality
-- Tracks password reset tokens sent to users via email

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  used BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id
ON password_reset_tokens(user_id);

-- Create index on token for validation
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token
ON password_reset_tokens(token);

-- Create index on expires_at for cleanup queries
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at
ON password_reset_tokens(expires_at);

-- Enable RLS (Row Level Security)
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;

-- Public can insert (for forgot password endpoint)
CREATE POLICY "Allow public to insert password reset tokens"
  ON password_reset_tokens
  FOR INSERT
  WITH CHECK (true);

-- Users can only view their own tokens
CREATE POLICY "Allow users to view their own reset tokens"
  ON password_reset_tokens
  FOR SELECT
  USING (
    auth.uid() = user_id OR
    (SELECT role FROM public.roles WHERE id = (
      SELECT role_id FROM public.profiles WHERE id = auth.uid()
    )) = 'admin'
  );

-- Users and admin can update their own tokens
CREATE POLICY "Allow users to update their own reset tokens"
  ON password_reset_tokens
  FOR UPDATE
  USING (
    auth.uid() = user_id OR
    (SELECT role FROM public.roles WHERE id = (
      SELECT role_id FROM public.profiles WHERE id = auth.uid()
    )) = 'admin'
  );

-- Add comment explaining the table
COMMENT ON TABLE password_reset_tokens IS 'Stores password reset tokens for users who forgot their password. Tokens expire after 24 hours.';
