-- Migration: MarcelGPT - HeyGen Video Generation System
-- Purpose: Complete video generation system with HeyGen API integration
-- Author: System
-- Date: 2025-10-27

-- =====================================================================
-- 1. Update tenants table with HeyGen API key
-- =====================================================================

-- Add HeyGen API key to tenants
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS heygen_api_key TEXT;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS heygen_webhook_secret TEXT;

COMMENT ON COLUMN tenants.heygen_api_key IS 'HeyGen API key for this tenant';
COMMENT ON COLUMN tenants.heygen_webhook_secret IS 'Webhook secret for HeyGen callbacks';

-- =====================================================================
-- 2. Brand Presets - Saved video configurations per tenant
-- =====================================================================

CREATE TABLE IF NOT EXISTS brand_presets (
  id SERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,

  -- Avatar settings
  avatar_id VARCHAR(100) NOT NULL,
  avatar_style VARCHAR(50) DEFAULT 'normal',

  -- Voice settings
  voice_id VARCHAR(100) NOT NULL,
  language VARCHAR(10) DEFAULT 'en',
  tts_speed DECIMAL(3,2) DEFAULT 1.0,

  -- Background settings
  bg_asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
  bg_type VARCHAR(50) DEFAULT 'color', -- color, image, video
  bg_value TEXT, -- color code or asset URL

  -- Overlay settings
  overlay_logo_url TEXT,
  overlay_logo_position VARCHAR(20) DEFAULT 'bottom-right',
  ppe_theme JSONB DEFAULT '{}',

  -- Subtitle settings
  enable_subtitles BOOLEAN DEFAULT false,
  subtitle_format VARCHAR(10) DEFAULT 'srt', -- srt, vtt

  -- Video settings
  video_width INTEGER DEFAULT 1920,
  video_height INTEGER DEFAULT 1080,
  aspect_ratio VARCHAR(10) DEFAULT '16:9',

  -- Metadata
  is_default BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_brand_presets_tenant ON brand_presets(tenant_id);
CREATE INDEX idx_brand_presets_user ON brand_presets(user_id);

COMMENT ON TABLE brand_presets IS 'Saved video generation presets per tenant';

-- =====================================================================
-- 3. Assets - User uploaded backgrounds, logos, etc.
-- =====================================================================

CREATE TABLE IF NOT EXISTS marcel_assets (
  id SERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,

  -- Asset info
  type VARCHAR(50) NOT NULL, -- logo, background_image, background_video
  name VARCHAR(255) NOT NULL,
  source VARCHAR(50) NOT NULL, -- upload, heygen, url

  -- HeyGen asset tracking
  heygen_asset_id VARCHAR(100),

  -- Storage
  url TEXT NOT NULL,
  storage_key TEXT, -- S3/Spaces key for permanent storage
  file_size BIGINT,
  mime_type VARCHAR(100),

  -- Metadata
  meta JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_marcel_assets_tenant ON marcel_assets(tenant_id);
CREATE INDEX idx_marcel_assets_type ON marcel_assets(type);
CREATE INDEX idx_marcel_assets_heygen ON marcel_assets(heygen_asset_id);

COMMENT ON TABLE marcel_assets IS 'User uploaded assets for video generation';

-- =====================================================================
-- 4. Video Jobs - Track video generation requests
-- =====================================================================

CREATE TABLE IF NOT EXISTS video_jobs (
  id SERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  preset_id INTEGER REFERENCES brand_presets(id) ON DELETE SET NULL,

  -- Job info
  title VARCHAR(255),
  engine VARCHAR(20) NOT NULL, -- v2, av4, template
  status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, queued, processing, completed, failed, cancelled

  -- HeyGen tracking
  heygen_job_id VARCHAR(100),
  callback_url TEXT,

  -- Input data
  input_text TEXT NOT NULL,
  input_config JSONB NOT NULL DEFAULT '{}', -- Full request payload

  -- Error handling
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  queued_at TIMESTAMP WITH TIME ZONE,
  processing_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  failed_at TIMESTAMP WITH TIME ZONE,

  -- Duration tracking
  estimated_duration INTEGER, -- seconds
  actual_duration INTEGER -- seconds
);

CREATE INDEX idx_video_jobs_tenant ON video_jobs(tenant_id);
CREATE INDEX idx_video_jobs_user ON video_jobs(user_id);
CREATE INDEX idx_video_jobs_status ON video_jobs(status);
CREATE INDEX idx_video_jobs_heygen ON video_jobs(heygen_job_id);
CREATE INDEX idx_video_jobs_created ON video_jobs(created_at DESC);

COMMENT ON TABLE video_jobs IS 'Video generation job tracking';

-- =====================================================================
-- 5. Video Artifacts - Generated video outputs
-- =====================================================================

CREATE TABLE IF NOT EXISTS video_artifacts (
  id SERIAL PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,

  -- Video file
  heygen_url TEXT, -- Temporary HeyGen URL
  storage_key TEXT NOT NULL, -- Permanent S3/Spaces storage
  signed_url TEXT, -- Pre-signed URL for download
  expires_at TIMESTAMP WITH TIME ZONE,

  -- Video metadata
  duration INTEGER, -- seconds
  file_size BIGINT, -- bytes
  width INTEGER,
  height INTEGER,
  format VARCHAR(20) DEFAULT 'mp4',

  -- Subtitle files
  subtitle_url TEXT,
  subtitle_storage_key TEXT,

  -- Thumbnail
  thumbnail_url TEXT,
  thumbnail_storage_key TEXT,

  -- Metadata
  meta JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_video_artifacts_job ON video_artifacts(job_id);
CREATE INDEX idx_video_artifacts_expires ON video_artifacts(expires_at);

COMMENT ON TABLE video_artifacts IS 'Generated video files and outputs';

-- =====================================================================
-- 6. Catalog Cache - HeyGen avatars and voices
-- =====================================================================

CREATE TABLE IF NOT EXISTS catalog_avatars (
  avatar_id VARCHAR(100) PRIMARY KEY,
  avatar_name VARCHAR(255),
  gender VARCHAR(20),
  preview_image_url TEXT,
  preview_video_url TEXT,
  is_public BOOLEAN DEFAULT true,
  is_instant BOOLEAN DEFAULT false,
  data JSONB NOT NULL, -- Full API response
  cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_catalog_avatars_gender ON catalog_avatars(gender);
CREATE INDEX idx_catalog_avatars_public ON catalog_avatars(is_public);

COMMENT ON TABLE catalog_avatars IS 'Cached HeyGen avatar catalog (24h TTL)';

CREATE TABLE IF NOT EXISTS catalog_voices (
  voice_id VARCHAR(100) PRIMARY KEY,
  voice_name VARCHAR(255),
  language VARCHAR(10),
  gender VARCHAR(20),
  accent VARCHAR(50),
  age_range VARCHAR(50),
  supports_emotion BOOLEAN DEFAULT false,
  data JSONB NOT NULL, -- Full API response
  cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_catalog_voices_language ON catalog_voices(language);
CREATE INDEX idx_catalog_voices_gender ON catalog_voices(gender);

COMMENT ON TABLE catalog_voices IS 'Cached HeyGen voice catalog (24h TTL)';

-- =====================================================================
-- 7. Consents - User consent tracking for AI usage
-- =====================================================================

CREATE TABLE IF NOT EXISTS marcel_consents (
  id SERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,

  -- Consent details
  type VARCHAR(50) NOT NULL, -- logo, voice, photo, likeness
  scope VARCHAR(100) NOT NULL, -- internal, marketing, external
  purpose TEXT,

  -- Documentation
  consent_document_url TEXT,
  consent_text TEXT,

  -- Status
  accepted_at TIMESTAMP WITH TIME ZONE,
  revoked_at TIMESTAMP WITH TIME ZONE,
  expires_at TIMESTAMP WITH TIME ZONE,

  -- Metadata
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_marcel_consents_tenant ON marcel_consents(tenant_id);
CREATE INDEX idx_marcel_consents_user ON marcel_consents(user_id);
CREATE INDEX idx_marcel_consents_type ON marcel_consents(type);

COMMENT ON TABLE marcel_consents IS 'AI usage consent tracking';

-- =====================================================================
-- 8. Enable RLS on all tables
-- =====================================================================

ALTER TABLE brand_presets ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcel_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog_avatars ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog_voices ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcel_consents ENABLE ROW LEVEL SECURITY;

-- =====================================================================
-- 9. RLS Policies
-- =====================================================================

-- Brand Presets: Users can only see their tenant's presets
CREATE POLICY "Users can view their tenant's presets"
  ON brand_presets FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM profiles WHERE id = auth.uid()
    )
  );

CREATE POLICY "Users can create presets in their tenant"
  ON brand_presets FOR INSERT
  TO authenticated
  WITH CHECK (
    tenant_id IN (
      SELECT tenant_id FROM profiles WHERE id = auth.uid()
    )
    AND user_id = auth.uid()
  );

-- Assets: Tenant isolation
CREATE POLICY "Users can view their tenant's assets"
  ON marcel_assets FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM profiles WHERE id = auth.uid()
    )
  );

-- Video Jobs: Tenant isolation
CREATE POLICY "Users can view their tenant's jobs"
  ON video_jobs FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM profiles WHERE id = auth.uid()
    )
  );

CREATE POLICY "Users can create jobs in their tenant"
  ON video_jobs FOR INSERT
  TO authenticated
  WITH CHECK (
    tenant_id IN (
      SELECT tenant_id FROM profiles WHERE id = auth.uid()
    )
    AND user_id = auth.uid()
  );

-- Artifacts: Via job access
CREATE POLICY "Users can view artifacts of their jobs"
  ON video_artifacts FOR SELECT
  TO authenticated
  USING (
    job_id IN (
      SELECT id FROM video_jobs
      WHERE tenant_id IN (
        SELECT tenant_id FROM profiles WHERE id = auth.uid()
      )
    )
  );

-- Catalog: Public read access
CREATE POLICY "Everyone can view catalog"
  ON catalog_avatars FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Everyone can view voice catalog"
  ON catalog_voices FOR SELECT
  TO authenticated
  USING (true);

-- Consents: User can view their own
CREATE POLICY "Users can view their consents"
  ON marcel_consents FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- =====================================================================
-- 10. Helper Functions
-- =====================================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_marcel_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER brand_presets_updated_at
  BEFORE UPDATE ON brand_presets
  FOR EACH ROW
  EXECUTE FUNCTION update_marcel_updated_at();

CREATE TRIGGER marcel_assets_updated_at
  BEFORE UPDATE ON marcel_assets
  FOR EACH ROW
  EXECUTE FUNCTION update_marcel_updated_at();

-- Function to clean expired artifacts
CREATE OR REPLACE FUNCTION clean_expired_artifacts()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM video_artifacts
  WHERE expires_at < NOW()
  AND heygen_url IS NOT NULL;

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION clean_expired_artifacts IS 'Clean up expired video artifact URLs';

-- =====================================================================
-- 11. Add MarcelGPT permissions
-- =====================================================================

INSERT INTO permissions (name, description, category) VALUES
  -- MarcelGPT module
  ('marcel_gpt.access', 'Access MarcelGPT video generation', 'marcel_gpt'),
  ('marcel_gpt.create_video', 'Create new video generation jobs', 'marcel_gpt'),
  ('marcel_gpt.view_jobs', 'View video generation jobs', 'marcel_gpt'),
  ('marcel_gpt.cancel_job', 'Cancel video generation jobs', 'marcel_gpt'),
  ('marcel_gpt.download_video', 'Download generated videos', 'marcel_gpt'),
  ('marcel_gpt.manage_presets', 'Manage brand presets', 'marcel_gpt'),
  ('marcel_gpt.upload_assets', 'Upload custom assets', 'marcel_gpt'),
  ('marcel_gpt.view_analytics', 'View video generation analytics', 'marcel_gpt')
ON CONFLICT (name) DO NOTHING;

-- Assign to Super Admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions WHERE category = 'marcel_gpt'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign to Company Admin (role_id 2)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions WHERE category = 'marcel_gpt'
ON CONFLICT (role_id, permission_id) DO NOTHING;
