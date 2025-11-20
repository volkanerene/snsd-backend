-- Migration 034: Add parent_job_id to video_jobs table
-- Purpose: Track post-production videos that are derived from original videos
-- Date: 2025-11-20

-- Add parent_job_id column to video_jobs table
ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS parent_job_id INTEGER REFERENCES video_jobs(id) ON DELETE SET NULL;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_video_jobs_parent_job_id ON video_jobs(parent_job_id);

-- Add post_production_metadata column for storing effect configurations
ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS post_production_metadata JSONB DEFAULT NULL;

SELECT 'parent_job_id and post_production_metadata columns added to video_jobs!' as status;
