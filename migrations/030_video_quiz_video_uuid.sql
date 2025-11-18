-- 030_video_quiz_video_uuid.sql
-- Allow storing quiz results for library videos (UUID) and keep job references optional

ALTER TABLE video_quiz_answers
ADD COLUMN IF NOT EXISTS video_uuid UUID;

ALTER TABLE video_quiz_answers
ALTER COLUMN video_id DROP NOT NULL;
