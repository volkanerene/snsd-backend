-- =====================================================================
-- Migration: Create FRM32 Submissions Table
-- Purpose: Create standalone FRM32 submissions table for sidebar access
-- (in addition to evren_gpt_form_submissions for email invitation flow)
-- Author: System
-- Date: 2025-11-06
-- =====================================================================

-- =====================================================================
-- Create FRM32 Submissions Table
-- =====================================================================
-- Standalone table for contractors accessing FRM32 from their dashboard sidebar
-- (without email invitation/session)
CREATE TABLE IF NOT EXISTS frm32_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    evaluation_period VARCHAR(10) NOT NULL, -- e.g., "2025-01", "2025-Q3"
    evaluation_type VARCHAR(20) DEFAULT 'periodic' CHECK (evaluation_type IN ('periodic', 'incident', 'audit')),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'in_review', 'completed', 'rejected')),
    progress_percentage INT DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),

    -- Form answers stored as JSONB
    -- Keys are question IDs (e.g., 'question_11A', 'question_12B')
    -- Values are the answers (strings, numbers, arrays, etc.)
    answers JSONB DEFAULT '{}'::jsonb,

    -- Evaluation results
    submitted_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    final_score DECIMAL(5, 2),
    risk_classification VARCHAR(10) CHECK (risk_classification IN ('green', 'yellow', 'red', NULL)),
    ai_summary TEXT,

    -- File attachments
    attachments JSONB DEFAULT '[]'::jsonb,

    -- User notes
    notes TEXT,

    -- Metadata for extensibility
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    reviewed_by UUID REFERENCES profiles(id) ON DELETE SET NULL,

    -- Unique constraint: one submission per contractor per evaluation period per tenant
    UNIQUE(tenant_id, contractor_id, evaluation_period)
);

-- =====================================================================
-- Indexes for Performance
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_tenant ON frm32_submissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_contractor ON frm32_submissions(contractor_id);
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_tenant_contractor ON frm32_submissions(tenant_id, contractor_id);
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_evaluation_period ON frm32_submissions(evaluation_period);
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_status ON frm32_submissions(status);
CREATE INDEX IF NOT EXISTS idx_frm32_submissions_created_at ON frm32_submissions(created_at DESC);

-- =====================================================================
-- Row Level Security (RLS)
-- =====================================================================
ALTER TABLE frm32_submissions ENABLE ROW LEVEL SECURITY;

-- Policy: Contractors can view/update their own submissions
CREATE POLICY "Contractors can view their own submissions"
    ON frm32_submissions FOR SELECT
    USING (
        contractor_id IN (
            SELECT contractor_id FROM profiles WHERE id = auth.uid()
        )
        OR
        -- Admins can view all submissions for their tenant
        tenant_id IN (
            SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
        )
    );

-- Contractors can insert their own submissions
CREATE POLICY "Contractors can create their own submissions"
    ON frm32_submissions FOR INSERT
    WITH CHECK (
        contractor_id IN (
            SELECT contractor_id FROM profiles WHERE id = auth.uid()
        )
    );

-- Contractors can update their own submissions (only draft status)
CREATE POLICY "Contractors can update their own draft submissions"
    ON frm32_submissions FOR UPDATE
    USING (
        contractor_id IN (
            SELECT contractor_id FROM profiles WHERE id = auth.uid()
        )
        AND status = 'draft'
    )
    WITH CHECK (
        contractor_id IN (
            SELECT contractor_id FROM profiles WHERE id = auth.uid()
        )
    );

-- Admins can update any submission in their tenant
CREATE POLICY "Admins can update submissions in their tenant"
    ON frm32_submissions FOR UPDATE
    USING (
        tenant_id IN (
            SELECT tu.tenant_id
            FROM tenant_users tu
            JOIN profiles p ON p.id = tu.user_id
            WHERE tu.user_id = auth.uid() AND p.role_id <= 3  -- Admin or HSE Specialist
        )
    );

-- =====================================================================
-- Create FRM32 Answers Table (Optional - for normalized answers storage)
-- =====================================================================
-- This is optional. If using this table, answers are stored normalized
-- instead of as JSONB in the submissions table.
-- For now, we'll keep answers in the submissions table as JSONB for simplicity.
-- If you want to use this table later, uncomment below:

/*
CREATE TABLE IF NOT EXISTS frm32_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES frm32_submissions(id) ON DELETE CASCADE,
    question_id VARCHAR(50) NOT NULL, -- e.g., 'question_11A'
    answer_value JSONB NOT NULL,
    score DECIMAL(5, 2),
    attachments JSONB DEFAULT '[]'::jsonb,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(submission_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_frm32_answers_submission ON frm32_answers(submission_id);
CREATE INDEX IF NOT EXISTS idx_frm32_answers_question_id ON frm32_answers(question_id);

ALTER TABLE frm32_answers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view answers for their submissions"
    ON frm32_answers FOR SELECT
    USING (
        submission_id IN (
            SELECT id FROM frm32_submissions
            WHERE contractor_id IN (
                SELECT contractor_id FROM profiles WHERE id = auth.uid()
            )
            OR tenant_id IN (
                SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
            )
        )
    );
*/
