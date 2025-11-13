-- 025_photo_avatar_generated_images.sql
-- Stores generated Marcel look selections so they can be reused later

CREATE TABLE IF NOT EXISTS photo_avatar_generated_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  group_id TEXT,
  image_key TEXT NOT NULL,
  image_url TEXT,
  prompt TEXT,
  avatar_id TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_avatar_generated_images_tenant_key
  ON photo_avatar_generated_images(tenant_id, image_key);
