-- =====================================================================
-- Migration: FRM32 AI Suggestions
-- Purpose : Add AI-generated score suggestions to frm32_submissions (JSONB)
-- Date    : 2025-11-10
-- =====================================================================

-- Add AI suggestions as JSONB to frm32_submissions table
-- Format: {"K2.1": {"suggested_score": 10, "reasoning": "..."}, "K2.2": ...}
ALTER TABLE frm32_submissions
ADD COLUMN IF NOT EXISTS ai_suggestions JSONB DEFAULT '{}';

-- Create index for faster AI suggestion queries
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_ai_suggestions
    ON frm32_submissions USING GIN (ai_suggestions);
