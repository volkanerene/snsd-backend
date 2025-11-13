-- 026_marcel_favorites.sql
-- Favorites for Marcel voices and looks

CREATE TABLE IF NOT EXISTS marcel_voice_favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  voice_id TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(tenant_id, user_id, voice_id)
);

CREATE TABLE IF NOT EXISTS marcel_look_favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  avatar_id TEXT,
  image_key TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CHECK (avatar_id IS NOT NULL OR image_key IS NOT NULL),
  UNIQUE(tenant_id, user_id, avatar_id),
  UNIQUE(tenant_id, user_id, image_key)
);
