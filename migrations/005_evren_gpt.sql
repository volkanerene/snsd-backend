-- ================================================
-- EvrenGPT Process Management Tables
-- ================================================
-- This migration creates tables for managing the EvrenGPT evaluation process
-- which includes sessions, form submissions (FRM32-35), and scoring

-- ================================================
-- 1. EvrenGPT Sessions Table
-- ================================================
-- Tracks evaluation sessions initiated by Company Admin or HSE Specialist
CREATE TABLE IF NOT EXISTS evren_gpt_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(50) UNIQUE NOT NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    custom_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_evren_sessions_tenant ON evren_gpt_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_evren_sessions_status ON evren_gpt_sessions(status);
CREATE INDEX IF NOT EXISTS idx_evren_sessions_created_by ON evren_gpt_sessions(created_by);
CREATE INDEX IF NOT EXISTS idx_evren_sessions_created_at ON evren_gpt_sessions(created_at DESC);

-- RLS Policies
ALTER TABLE evren_gpt_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view sessions for their tenant"
    ON evren_gpt_sessions FOR SELECT
    USING (tenant_id IN (
        SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
    ));

CREATE POLICY "Admins can create sessions"
    ON evren_gpt_sessions FOR INSERT
    WITH CHECK (
        tenant_id IN (
            SELECT tu.tenant_id
            FROM tenant_users tu
            JOIN profiles p ON p.id = tu.user_id
            WHERE tu.user_id = auth.uid() AND p.role_id <= 3  -- Admin or HSE Specialist
        )
    );

CREATE POLICY "Admins can update sessions"
    ON evren_gpt_sessions FOR UPDATE
    USING (
        tenant_id IN (
            SELECT tu.tenant_id
            FROM tenant_users tu
            JOIN profiles p ON p.id = tu.user_id
            WHERE tu.user_id = auth.uid() AND p.role_id <= 3
        )
    );

-- ================================================
-- 2. Session Contractors Junction Table
-- ================================================
-- Links contractors to specific evaluation sessions
CREATE TABLE IF NOT EXISTS evren_gpt_session_contractors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(50) NOT NULL REFERENCES evren_gpt_sessions(session_id) ON DELETE CASCADE,
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    cycle INT DEFAULT 1 CHECK (cycle > 0),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'frm32_sent', 'frm32_completed', 'frm33_completed', 'frm34_completed', 'frm35_completed', 'completed')),
    frm32_sent_at TIMESTAMP WITH TIME ZONE,
    frm32_completed_at TIMESTAMP WITH TIME ZONE,
    frm33_completed_at TIMESTAMP WITH TIME ZONE,
    frm34_completed_at TIMESTAMP WITH TIME ZONE,
    frm35_completed_at TIMESTAMP WITH TIME ZONE,
    final_score DECIMAL(5,2),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id, contractor_id, cycle)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_session_contractors_session ON evren_gpt_session_contractors(session_id);
CREATE INDEX IF NOT EXISTS idx_session_contractors_contractor ON evren_gpt_session_contractors(contractor_id);
CREATE INDEX IF NOT EXISTS idx_session_contractors_status ON evren_gpt_session_contractors(status);

-- RLS Policies
ALTER TABLE evren_gpt_session_contractors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view session contractors for their tenant"
    ON evren_gpt_session_contractors FOR SELECT
    USING (
        session_id IN (
            SELECT session_id FROM evren_gpt_sessions
            WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
            )
        )
    );

CREATE POLICY "Admins can manage session contractors"
    ON evren_gpt_session_contractors FOR ALL
    USING (
        session_id IN (
            SELECT s.session_id FROM evren_gpt_sessions s
            JOIN tenant_users tu ON tu.tenant_id = s.tenant_id
            JOIN profiles p ON p.id = tu.user_id
            WHERE tu.user_id = auth.uid() AND p.role_id <= 3
        )
    );

-- ================================================
-- 3. Form Submissions Table (FRM32-35)
-- ================================================
-- Stores all form submissions for the EvrenGPT process
CREATE TABLE IF NOT EXISTS evren_gpt_form_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(50) NOT NULL REFERENCES evren_gpt_sessions(session_id) ON DELETE CASCADE,
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    form_id VARCHAR(10) NOT NULL CHECK (form_id IN ('frm32', 'frm33', 'frm34', 'frm35')),
    cycle INT DEFAULT 1 CHECK (cycle > 0),
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_score DECIMAL(5,2),
    final_score DECIMAL(5,2),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'scored', 'completed')),
    submitted_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    submitted_at TIMESTAMP WITH TIME ZONE,
    n8n_processed_at TIMESTAMP WITH TIME ZONE,
    n8n_webhook_response JSONB,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id, contractor_id, form_id, cycle)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_form_submissions_session ON evren_gpt_form_submissions(session_id);
CREATE INDEX IF NOT EXISTS idx_form_submissions_contractor ON evren_gpt_form_submissions(contractor_id);
CREATE INDEX IF NOT EXISTS idx_form_submissions_form_id ON evren_gpt_form_submissions(form_id);
CREATE INDEX IF NOT EXISTS idx_form_submissions_status ON evren_gpt_form_submissions(status);
CREATE INDEX IF NOT EXISTS idx_form_submissions_submitted_at ON evren_gpt_form_submissions(submitted_at DESC);

-- RLS Policies
ALTER TABLE evren_gpt_form_submissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view submissions for their tenant"
    ON evren_gpt_form_submissions FOR SELECT
    USING (
        session_id IN (
            SELECT session_id FROM evren_gpt_sessions
            WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
            )
        )
    );

CREATE POLICY "Users can submit their own forms"
    ON evren_gpt_form_submissions FOR INSERT
    WITH CHECK (
        (form_id = 'frm32' AND submitted_by IN (
            SELECT id FROM profiles WHERE role_id = 4  -- Contractor Admin
        ))
        OR
        (form_id IN ('frm33', 'frm34', 'frm35') AND submitted_by IN (
            SELECT id FROM profiles WHERE role_id = 5  -- Supervisor
        ))
    );

CREATE POLICY "Admins and form owners can update submissions"
    ON evren_gpt_form_submissions FOR UPDATE
    USING (
        submitted_by = auth.uid()
        OR
        session_id IN (
            SELECT s.session_id FROM evren_gpt_sessions s
            JOIN tenant_users tu ON tu.tenant_id = s.tenant_id
            JOIN profiles p ON p.id = tu.user_id
            WHERE tu.user_id = auth.uid() AND p.role_id <= 3
        )
    );

-- ================================================
-- 4. Form Question Scores Table
-- ================================================
-- Stores individual question scores from AI processing
CREATE TABLE IF NOT EXISTS evren_gpt_question_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES evren_gpt_form_submissions(id) ON DELETE CASCADE,
    question_id VARCHAR(50) NOT NULL,
    question_text TEXT,
    answer_text TEXT,
    ai_score INT CHECK (ai_score IN (0, 3, 6, 10)),
    ai_reasoning TEXT,
    weight DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_question_scores_submission ON evren_gpt_question_scores(submission_id);
CREATE INDEX IF NOT EXISTS idx_question_scores_question ON evren_gpt_question_scores(question_id);

-- RLS Policies
ALTER TABLE evren_gpt_question_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view question scores for their tenant"
    ON evren_gpt_question_scores FOR SELECT
    USING (
        submission_id IN (
            SELECT fs.id FROM evren_gpt_form_submissions fs
            JOIN evren_gpt_sessions s ON s.session_id = fs.session_id
            WHERE s.tenant_id IN (
                SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
            )
        )
    );

-- ================================================
-- 5. Process Notifications Table
-- ================================================
-- Tracks email notifications sent during the process
CREATE TABLE IF NOT EXISTS evren_gpt_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(50) NOT NULL REFERENCES evren_gpt_sessions(session_id) ON DELETE CASCADE,
    contractor_id UUID REFERENCES contractors(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255),
    notification_type VARCHAR(50) NOT NULL CHECK (notification_type IN ('frm32_invite', 'frm33_invite', 'frm34_invite', 'frm35_invite', 'process_complete', 'reminder')),
    form_id VARCHAR(10),
    subject TEXT,
    body TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'bounced')),
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_notifications_session ON evren_gpt_notifications(session_id);
CREATE INDEX IF NOT EXISTS idx_notifications_contractor ON evren_gpt_notifications(contractor_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON evren_gpt_notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON evren_gpt_notifications(notification_type);

-- RLS Policies
ALTER TABLE evren_gpt_notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view notifications for their tenant"
    ON evren_gpt_notifications FOR SELECT
    USING (
        session_id IN (
            SELECT session_id FROM evren_gpt_sessions
            WHERE tenant_id IN (
                SELECT tenant_id FROM tenant_users WHERE user_id = auth.uid()
            )
        )
    );

-- ================================================
-- 6. Triggers for updated_at
-- ================================================
CREATE OR REPLACE FUNCTION update_evren_gpt_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evren_sessions_updated_at
    BEFORE UPDATE ON evren_gpt_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_evren_gpt_updated_at();

CREATE TRIGGER session_contractors_updated_at
    BEFORE UPDATE ON evren_gpt_session_contractors
    FOR EACH ROW
    EXECUTE FUNCTION update_evren_gpt_updated_at();

CREATE TRIGGER form_submissions_updated_at
    BEFORE UPDATE ON evren_gpt_form_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_evren_gpt_updated_at();

-- ================================================
-- 7. Helper Functions
-- ================================================

-- Function to generate unique session_id
CREATE OR REPLACE FUNCTION generate_evren_session_id()
RETURNS VARCHAR AS $$
DECLARE
    new_id VARCHAR;
    done BOOLEAN := FALSE;
BEGIN
    WHILE NOT done LOOP
        new_id := 'sess_' || LPAD(FLOOR(RANDOM() * 999999)::TEXT, 6, '0');
        IF NOT EXISTS (SELECT 1 FROM evren_gpt_sessions WHERE session_id = new_id) THEN
            done := TRUE;
        END IF;
    END LOOP;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate final score for a contractor in a session
CREATE OR REPLACE FUNCTION calculate_evren_final_score(
    p_session_id VARCHAR,
    p_contractor_id UUID,
    p_cycle INT
)
RETURNS DECIMAL AS $$
DECLARE
    avg_score DECIMAL;
BEGIN
    SELECT AVG(final_score)
    INTO avg_score
    FROM evren_gpt_form_submissions
    WHERE session_id = p_session_id
      AND contractor_id = p_contractor_id
      AND cycle = p_cycle
      AND status = 'completed'
      AND final_score IS NOT NULL;

    RETURN COALESCE(avg_score, 0);
END;
$$ LANGUAGE plpgsql;

-- Function to update contractor's overall status in session
CREATE OR REPLACE FUNCTION update_contractor_session_status()
RETURNS TRIGGER AS $$
BEGIN
    -- Update the session_contractors status based on completed forms
    UPDATE evren_gpt_session_contractors
    SET
        status = CASE
            WHEN (SELECT COUNT(*) FROM evren_gpt_form_submissions
                  WHERE session_id = NEW.session_id
                  AND contractor_id = NEW.contractor_id
                  AND cycle = NEW.cycle
                  AND status = 'completed') = 4 THEN 'completed'
            WHEN NEW.form_id = 'frm35' AND NEW.status = 'completed' THEN 'frm35_completed'
            WHEN NEW.form_id = 'frm34' AND NEW.status = 'completed' THEN 'frm34_completed'
            WHEN NEW.form_id = 'frm33' AND NEW.status = 'completed' THEN 'frm33_completed'
            WHEN NEW.form_id = 'frm32' AND NEW.status = 'completed' THEN 'frm32_completed'
            ELSE status
        END,
        final_score = calculate_evren_final_score(NEW.session_id, NEW.contractor_id, NEW.cycle),
        updated_at = NOW()
    WHERE session_id = NEW.session_id
      AND contractor_id = NEW.contractor_id
      AND cycle = NEW.cycle;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_session_contractor_status
    AFTER INSERT OR UPDATE ON evren_gpt_form_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_contractor_session_status();

-- ================================================
-- 8. Views for Easy Querying
-- ================================================

-- View: Session Progress Overview
CREATE OR REPLACE VIEW evren_gpt_session_progress AS
SELECT
    s.id,
    s.session_id,
    s.tenant_id,
    s.status as session_status,
    s.created_at,
    s.created_by,
    COUNT(DISTINCT sc.contractor_id) as total_contractors,
    COUNT(DISTINCT CASE WHEN sc.status = 'completed' THEN sc.contractor_id END) as completed_contractors,
    AVG(sc.final_score) as average_final_score,
    MIN(sc.created_at) as started_at,
    MAX(sc.updated_at) as last_updated
FROM evren_gpt_sessions s
LEFT JOIN evren_gpt_session_contractors sc ON s.session_id = sc.session_id
GROUP BY s.id, s.session_id, s.tenant_id, s.status, s.created_at, s.created_by;

-- View: Form Completion Status
CREATE OR REPLACE VIEW evren_gpt_form_completion_status AS
SELECT
    fs.session_id,
    fs.contractor_id,
    fs.cycle,
    c.name as contractor_name,
    MAX(CASE WHEN fs.form_id = 'frm32' THEN fs.status END) as frm32_status,
    MAX(CASE WHEN fs.form_id = 'frm33' THEN fs.status END) as frm33_status,
    MAX(CASE WHEN fs.form_id = 'frm34' THEN fs.status END) as frm34_status,
    MAX(CASE WHEN fs.form_id = 'frm35' THEN fs.status END) as frm35_status,
    MAX(CASE WHEN fs.form_id = 'frm32' THEN fs.final_score END) as frm32_score,
    MAX(CASE WHEN fs.form_id = 'frm33' THEN fs.final_score END) as frm33_score,
    MAX(CASE WHEN fs.form_id = 'frm34' THEN fs.final_score END) as frm34_score,
    MAX(CASE WHEN fs.form_id = 'frm35' THEN fs.final_score END) as frm35_score
FROM evren_gpt_form_submissions fs
JOIN contractors c ON c.id = fs.contractor_id
GROUP BY fs.session_id, fs.contractor_id, fs.cycle, c.name;

COMMENT ON TABLE evren_gpt_sessions IS 'EvrenGPT evaluation sessions initiated by admins';
COMMENT ON TABLE evren_gpt_session_contractors IS 'Links contractors to evaluation sessions with progress tracking';
COMMENT ON TABLE evren_gpt_form_submissions IS 'Stores all form submissions (FRM32-35) with AI scoring';
COMMENT ON TABLE evren_gpt_question_scores IS 'Individual question scores from AI analysis';
COMMENT ON TABLE evren_gpt_notifications IS 'Email notifications sent during the evaluation process';
