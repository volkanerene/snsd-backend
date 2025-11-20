-- 032_marcel_premade_metadata.sql
-- Adds metadata + source tracking to Marcel premade videos

ALTER TABLE marcel_gpt_premade_videos
ADD COLUMN IF NOT EXISTS main_category TEXT,
ADD COLUMN IF NOT EXISTS category_tags TEXT[],
ADD COLUMN IF NOT EXISTS category_metadata JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'external',
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_premade_videos_main_category
  ON marcel_gpt_premade_videos(main_category);

CREATE INDEX IF NOT EXISTS idx_premade_videos_category_tags
  ON marcel_gpt_premade_videos USING GIN (category_tags);
