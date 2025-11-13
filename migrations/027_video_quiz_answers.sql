-- 027_video_quiz_answers.sql
-- Creates tables for storing video quiz question answers and scores

CREATE TABLE IF NOT EXISTS video_quiz_answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  assignment_id UUID NOT NULL,
  user_id UUID NOT NULL,
  video_id UUID NOT NULL,
  question_index INT NOT NULL,
  question_text TEXT NOT NULL,
  question_type VARCHAR(20) NOT NULL, -- 'text', 'multiple_choice'
  user_answer TEXT,
  correct_answer TEXT,
  is_correct BOOLEAN,
  ai_score FLOAT, -- For text answers: 0-100 score from AI
  points_earned FLOAT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_assignment FOREIGN KEY (assignment_id) REFERENCES marcel_gpt_video_assignments(id) ON DELETE CASCADE,
  CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_video FOREIGN KEY (video_id) REFERENCES video_jobs(id) ON DELETE CASCADE
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_video_quiz_assignment ON video_quiz_answers(assignment_id);
CREATE INDEX IF NOT EXISTS idx_video_quiz_user ON video_quiz_answers(user_id);
CREATE INDEX IF NOT EXISTS idx_video_quiz_video ON video_quiz_answers(video_id);
CREATE INDEX IF NOT EXISTS idx_video_quiz_tenant ON video_quiz_answers(tenant_id);

-- Add quiz_completed column to video_assignments to track if quiz is done
ALTER TABLE marcel_gpt_video_assignments
ADD COLUMN IF NOT EXISTS quiz_completed_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS quiz_score FLOAT;

COMMENT ON TABLE video_quiz_answers IS 'Stores user answers to video quiz questions';
COMMENT ON COLUMN video_quiz_answers.ai_score IS 'Score from AI evaluation (0-100) for text answers';
COMMENT ON COLUMN video_quiz_answers.points_earned IS 'Points earned for this question (0-100/question_count)';
