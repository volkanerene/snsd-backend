-- =====================================================================
-- Migration: Create FRM32 Submission Notifications Table
-- Purpose : Track supervisor notification emails for FRM32 submissions
-- Date    : 2025-11-09
-- =====================================================================

CREATE TABLE IF NOT EXISTS frm32_submission_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES frm32_submissions(id) ON DELETE CASCADE,
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255),
    subject TEXT,
    body TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_frm32_notif_submission ON frm32_submission_notifications(submission_id);
CREATE INDEX IF NOT EXISTS idx_frm32_notif_tenant ON frm32_submission_notifications(tenant_id);
CREATE INDEX IF NOT EXISTS idx_frm32_notif_recipient ON frm32_submission_notifications(recipient_email);

COMMENT ON TABLE frm32_submission_notifications IS 'Audit log of supervisor notification emails triggered by FRM32 submissions.';
