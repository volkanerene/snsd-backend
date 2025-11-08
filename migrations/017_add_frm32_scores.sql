-- =====================================================================
-- Migration: Add Scores Column to FRM32 Submissions
-- Purpose: Add JSONB scores column to store supervisor evaluation scores
-- Author: System
-- Date: 2025-11-08
-- =====================================================================

-- Add scores column to frm32_submissions table if it doesn't exist
-- Stores supervisor scores as JSONB
-- Keys are question IDs (e.g., 'question_11A', 'question_12B')
-- Values are scores (0, 3, 6, or 9)
ALTER TABLE frm32_submissions
ADD COLUMN IF NOT EXISTS scores JSONB DEFAULT '{}'::jsonb;

-- Create index on scores for better query performance
CREATE INDEX IF NOT EXISTS idx_frm32_scores ON frm32_submissions USING GIN (scores);

-- Update comment to document the scores field
COMMENT ON COLUMN frm32_submissions.scores IS 'Supervisor evaluation scores stored as JSONB. Keys are question codes, values are numeric scores (0, 3, 6, 9).';
