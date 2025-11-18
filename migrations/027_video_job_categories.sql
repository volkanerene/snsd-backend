-- 027_video_job_categories.sql
-- Adds structured category metadata for Marcel video jobs

ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS main_category TEXT,
ADD COLUMN IF NOT EXISTS category_tags TEXT[],
ADD COLUMN IF NOT EXISTS category_metadata JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_video_jobs_main_category
  ON video_jobs (main_category);

CREATE INDEX IF NOT EXISTS idx_video_jobs_category_tags
  ON video_jobs USING GIN (category_tags);
