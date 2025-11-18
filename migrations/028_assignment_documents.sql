-- 028_assignment_documents.sql
-- Stores document attachments for each video assignment

CREATE TABLE IF NOT EXISTS marcel_gpt_assignment_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id UUID NOT NULL REFERENCES marcel_gpt_video_assignments(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  storage_key TEXT,
  public_url TEXT,
  content_type TEXT,
  file_size BIGINT,
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assignment_documents_assignment
  ON marcel_gpt_assignment_documents(assignment_id);
