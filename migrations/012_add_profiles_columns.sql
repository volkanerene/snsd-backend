-- =====================================================================
-- Migration: Add Missing Columns to Profiles Table
-- Purpose: Add email, phone, and status columns to profiles table
-- Author: System
-- Date: 2025-10-31
-- =====================================================================

-- Add email column (should match auth.users email)
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- Add phone column (optional)
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS phone VARCHAR(50);

-- Add status column (active/inactive)
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);

-- Create index on status for filtering
CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles(status);

-- Add email unique constraint (optional - uncomment if needed)
-- ALTER TABLE profiles ADD CONSTRAINT profiles_email_unique UNIQUE (email);

SELECT '✅ Added email, phone, and status columns to profiles table' as status;
