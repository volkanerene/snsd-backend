-- 024_video_job_training_questions.sql
-- Adds training_questions JSONB column to video_jobs for storing assessment items

ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS training_questions JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN video_jobs.training_questions IS 'Generated assessment questions (JSON)';
