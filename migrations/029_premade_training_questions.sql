-- 029_premade_training_questions.sql
-- Adds training_questions JSONB column to marcel_gpt_premade_videos
+
+ALTER TABLE marcel_gpt_premade_videos
+ADD COLUMN IF NOT EXISTS training_questions JSONB DEFAULT '[]'::jsonb;
+
+COMMENT ON COLUMN marcel_gpt_premade_videos.training_questions IS 'Generated assessment questions stored with the premade video';
+SQL
