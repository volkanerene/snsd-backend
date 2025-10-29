-- Migration: MarcelGPT Photo Avatar Support
-- Purpose: Persist HeyGen photo avatar groups and generated looks
-- Date: 2025-10-27

-- =====================================================================
-- 1. Photo Avatar Groups - per tenant
-- =====================================================================

CREATE TABLE IF NOT EXISTS photo_avatar_groups (
  id SERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  heygen_group_id VARCHAR(100) NOT NULL,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  meta JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_avatar_groups_tenant
  ON photo_avatar_groups(tenant_id);

-- =====================================================================
-- 2. Photo Avatar Looks - generated looks tied to groups
-- =====================================================================

CREATE TABLE IF NOT EXISTS photo_avatar_looks (
  id SERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  group_id INTEGER REFERENCES photo_avatar_groups(id) ON DELETE SET NULL,
  heygen_generation_id VARCHAR(100),
  heygen_look_id VARCHAR(100),
  name VARCHAR(255) NOT NULL,
  prompt TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  preview_urls JSONB DEFAULT '[]'::jsonb,
  cover_url TEXT,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  voice_id VARCHAR(100),
  error_message TEXT,
  meta JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_photo_avatar_looks_tenant
  ON photo_avatar_looks(tenant_id);

CREATE INDEX IF NOT EXISTS idx_photo_avatar_looks_status
  ON photo_avatar_looks(status);

-- =====================================================================
-- 3. Brand preset linkage (optional)
-- =====================================================================

ALTER TABLE brand_presets
  ADD COLUMN IF NOT EXISTS photo_avatar_look_id INTEGER REFERENCES photo_avatar_looks(id) ON DELETE SET NULL;

