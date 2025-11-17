-- =====================================================================
-- Migration 030: Scene Composition Support for MarcelGPT Videos
-- =====================================================================

-- Scene Clips Table: Stores user-uploaded scene clips for video composition
CREATE TABLE IF NOT EXISTS scene_clips (
  id SERIAL PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,

  -- Clip metadata
  clip_name VARCHAR(255) NOT NULL,
  start_time FLOAT NOT NULL DEFAULT 0, -- seconds, when clip starts in timeline
  end_time FLOAT NOT NULL, -- seconds, when clip ends in timeline
  duration FLOAT NOT NULL, -- seconds, clip duration
  clip_type VARCHAR(50) NOT NULL DEFAULT 'scene', -- scene, background, transition

  -- Storage
  storage_key TEXT NOT NULL, -- S3/Spaces storage key
  signed_url TEXT, -- Pre-signed URL for access
  expires_at TIMESTAMP WITH TIME ZONE,

  -- Video metadata
  width INTEGER,
  height INTEGER,
  format VARCHAR(20) DEFAULT 'mp4',

  -- Optional positioning (for PiP effects)
  position_x FLOAT DEFAULT 0, -- 0-1 normalized
  position_y FLOAT DEFAULT 0, -- 0-1 normalized
  scale FLOAT DEFAULT 1, -- 0.1-1.0
  opacity FLOAT DEFAULT 1, -- 0-1

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Background Music Table: Stores background music for videos
CREATE TABLE IF NOT EXISTS background_music (
  id SERIAL PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,

  -- Music metadata
  title VARCHAR(255),
  storage_key TEXT NOT NULL, -- S3/Spaces storage key
  signed_url TEXT, -- Pre-signed URL
  expires_at TIMESTAMP WITH TIME ZONE,

  -- Audio settings
  duration FLOAT NOT NULL, -- seconds
  volume FLOAT DEFAULT 0.5, -- 0-1
  fade_in FLOAT DEFAULT 0, -- seconds
  fade_out FLOAT DEFAULT 0, -- seconds
  start_time FLOAT DEFAULT 0, -- when music starts in timeline

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Composition Config: Stores composition settings for final video
CREATE TABLE IF NOT EXISTS video_compositions (
  id SERIAL PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

  -- Composition settings
  base_video_url TEXT, -- HeyGen video URL (avatar)
  composition_status VARCHAR(50) DEFAULT 'pending', -- pending, compositing, completed, failed
  composition_error TEXT,

  -- Final output
  final_video_url TEXT,
  final_signed_url TEXT,
  final_expires_at TIMESTAMP WITH TIME ZONE,

  -- Composition metadata
  scene_count INTEGER DEFAULT 0,
  has_background_music BOOLEAN DEFAULT FALSE,
  total_duration FLOAT, -- seconds

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_scene_clips_job ON scene_clips(job_id);
CREATE INDEX idx_scene_clips_tenant ON scene_clips(tenant_id);
CREATE INDEX idx_background_music_job ON background_music(job_id);
CREATE INDEX idx_background_music_tenant ON background_music(tenant_id);
CREATE INDEX idx_video_compositions_job ON video_compositions(job_id);
CREATE INDEX idx_video_compositions_status ON video_compositions(composition_status);

-- Comments
COMMENT ON TABLE scene_clips IS 'User-uploaded video clips for composition into final training videos';
COMMENT ON TABLE background_music IS 'Background music tracks for video composition';
COMMENT ON TABLE video_compositions IS 'Composition job tracking and final video storage';
