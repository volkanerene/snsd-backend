-- =====================================================================
-- Migration: Marcel GPT Library and Training System
-- Purpose: Add premade videos library and incident reports training
-- Date: 2025-11-02
-- =====================================================================

-- =====================================================================
-- PART 1: Premade Videos Library (Page 2)
-- =====================================================================

-- Table for storing premade training videos
CREATE TABLE IF NOT EXISTS marcel_gpt_premade_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    video_url TEXT NOT NULL,
    thumbnail_url TEXT,
    duration_seconds INT,
    category VARCHAR(100), -- e.g., "Safety", "Compliance", "Operations"
    tags TEXT[], -- Array of tags for filtering
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table for tracking video assignments to workers
CREATE TABLE IF NOT EXISTS marcel_gpt_video_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES marcel_gpt_premade_videos(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    assigned_to UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    assigned_by UUID NOT NULL REFERENCES profiles(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, viewed, completed
    viewed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    email_sent_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_video_assignment UNIQUE(video_id, assigned_to)
);

-- Indexes for premade videos
CREATE INDEX IF NOT EXISTS idx_premade_videos_tenant ON marcel_gpt_premade_videos(tenant_id);
CREATE INDEX IF NOT EXISTS idx_premade_videos_active ON marcel_gpt_premade_videos(is_active);
CREATE INDEX IF NOT EXISTS idx_premade_videos_category ON marcel_gpt_premade_videos(category);

-- Indexes for video assignments
CREATE INDEX IF NOT EXISTS idx_video_assignments_tenant ON marcel_gpt_video_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_video_assignments_assigned_to ON marcel_gpt_video_assignments(assigned_to);
CREATE INDEX IF NOT EXISTS idx_video_assignments_status ON marcel_gpt_video_assignments(status);
CREATE INDEX IF NOT EXISTS idx_video_assignments_video ON marcel_gpt_video_assignments(video_id);

-- =====================================================================
-- PART 2: Incident Reports Training System (Page 3)
-- =====================================================================

-- Table for storing incident report PDFs from SharePoint
CREATE TABLE IF NOT EXISTS marcel_gpt_incident_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sharepoint_id VARCHAR(500) UNIQUE, -- SharePoint file ID
    file_name VARCHAR(500) NOT NULL,
    file_url TEXT,
    sharepoint_path TEXT,
    file_size_bytes BIGINT,
    uploaded_date TIMESTAMPTZ,
    last_modified TIMESTAMPTZ,

    -- Extracted content
    text_content TEXT, -- Extracted PDF text
    summary TEXT, -- AI-generated summary
    keywords TEXT[], -- Extracted keywords
    incident_type VARCHAR(100),
    severity VARCHAR(50),

    -- Processing status
    processing_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    last_processed_at TIMESTAMPTZ,
    error_message TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table for storing SharePoint sync logs
CREATE TABLE IF NOT EXISTS marcel_gpt_sharepoint_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sync_type VARCHAR(50) NOT NULL, -- 'manual', 'scheduled', 'webhook'
    status VARCHAR(50) NOT NULL, -- 'started', 'completed', 'failed'
    files_found INT DEFAULT 0,
    files_processed INT DEFAULT 0,
    files_failed INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Table for storing generated training sessions
CREATE TABLE IF NOT EXISTS marcel_gpt_training_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    prompt TEXT NOT NULL, -- User's prompt/request
    generated_text TEXT, -- GPT-generated training script
    incident_report_ids UUID[], -- Array of used incident report IDs

    -- Video generation
    video_url TEXT,
    heygen_video_id VARCHAR(255),
    heygen_status VARCHAR(50), -- pending, processing, completed, failed

    -- Configuration
    avatar_id VARCHAR(255),
    voice_id VARCHAR(255),
    config JSONB DEFAULT '{}',

    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for incident reports
CREATE INDEX IF NOT EXISTS idx_incident_reports_tenant ON marcel_gpt_incident_reports(tenant_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_status ON marcel_gpt_incident_reports(processing_status);
CREATE INDEX IF NOT EXISTS idx_incident_reports_type ON marcel_gpt_incident_reports(incident_type);
CREATE INDEX IF NOT EXISTS idx_incident_reports_sharepoint ON marcel_gpt_incident_reports(sharepoint_id);

-- Indexes for sync log
CREATE INDEX IF NOT EXISTS idx_sharepoint_sync_tenant ON marcel_gpt_sharepoint_sync_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sharepoint_sync_started ON marcel_gpt_sharepoint_sync_log(started_at DESC);

-- Indexes for training sessions
CREATE INDEX IF NOT EXISTS idx_training_sessions_tenant ON marcel_gpt_training_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_training_sessions_created_by ON marcel_gpt_training_sessions(created_by);
CREATE INDEX IF NOT EXISTS idx_training_sessions_status ON marcel_gpt_training_sessions(heygen_status);

-- =====================================================================
-- PART 3: RLS Policies
-- =====================================================================

-- Enable RLS
ALTER TABLE marcel_gpt_premade_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcel_gpt_video_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcel_gpt_incident_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcel_gpt_sharepoint_sync_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcel_gpt_training_sessions ENABLE ROW LEVEL SECURITY;

-- Premade videos policies
DROP POLICY IF EXISTS "Users can view premade videos from their tenant" ON marcel_gpt_premade_videos;
CREATE POLICY "Users can view premade videos from their tenant"
    ON marcel_gpt_premade_videos FOR SELECT
    USING (tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid()));

DROP POLICY IF EXISTS "Admins can manage premade videos" ON marcel_gpt_premade_videos;
CREATE POLICY "Admins can manage premade videos"
    ON marcel_gpt_premade_videos FOR ALL
    USING (
        tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid() AND role_id <= 3)
    );

-- Video assignments policies
DROP POLICY IF EXISTS "Users can view their own assignments" ON marcel_gpt_video_assignments;
CREATE POLICY "Users can view their own assignments"
    ON marcel_gpt_video_assignments FOR SELECT
    USING (
        assigned_to = auth.uid()
        OR tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid() AND role_id <= 3)
    );

DROP POLICY IF EXISTS "Admins can manage assignments" ON marcel_gpt_video_assignments;
CREATE POLICY "Admins can manage assignments"
    ON marcel_gpt_video_assignments FOR ALL
    USING (
        tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid() AND role_id <= 3)
    );

-- Incident reports policies
DROP POLICY IF EXISTS "Admins can view incident reports" ON marcel_gpt_incident_reports;
CREATE POLICY "Admins can view incident reports"
    ON marcel_gpt_incident_reports FOR SELECT
    USING (
        tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid() AND role_id <= 3)
    );

DROP POLICY IF EXISTS "Admins can manage incident reports" ON marcel_gpt_incident_reports;
CREATE POLICY "Admins can manage incident reports"
    ON marcel_gpt_incident_reports FOR ALL
    USING (
        tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid() AND role_id <= 3)
    );

-- Training sessions policies
DROP POLICY IF EXISTS "Users can view training sessions from their tenant" ON marcel_gpt_training_sessions;
CREATE POLICY "Users can view training sessions from their tenant"
    ON marcel_gpt_training_sessions FOR SELECT
    USING (tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid()));

DROP POLICY IF EXISTS "Admins can manage training sessions" ON marcel_gpt_training_sessions;
CREATE POLICY "Admins can manage training sessions"
    ON marcel_gpt_training_sessions FOR ALL
    USING (
        tenant_id IN (SELECT tenant_id FROM profiles WHERE id = auth.uid() AND role_id <= 3)
    );

-- =====================================================================
-- PART 4: Sample Data (4 premade videos)
-- =====================================================================

-- Insert 4 sample premade videos (update URLs with real ones later)
INSERT INTO marcel_gpt_premade_videos (
    tenant_id,
    title,
    description,
    video_url,
    thumbnail_url,
    duration_seconds,
    category,
    tags
)
SELECT
    id as tenant_id,
    'Workplace Safety Fundamentals',
    'Essential safety guidelines and best practices for all employees',
    'https://example.com/videos/safety-fundamentals.mp4',
    'https://example.com/thumbnails/safety-fundamentals.jpg',
    600,
    'Safety',
    ARRAY['safety', 'fundamentals', 'workplace']
FROM tenants
WHERE slug != 'test-company' -- Don't add to test company
ON CONFLICT DO NOTHING;

INSERT INTO marcel_gpt_premade_videos (
    tenant_id,
    title,
    description,
    video_url,
    thumbnail_url,
    duration_seconds,
    category,
    tags
)
SELECT
    id as tenant_id,
    'Emergency Response Procedures',
    'Step-by-step guide for handling workplace emergencies',
    'https://example.com/videos/emergency-response.mp4',
    'https://example.com/thumbnails/emergency-response.jpg',
    720,
    'Safety',
    ARRAY['emergency', 'safety', 'procedures']
FROM tenants
WHERE slug != 'test-company'
ON CONFLICT DO NOTHING;

INSERT INTO marcel_gpt_premade_videos (
    tenant_id,
    title,
    description,
    video_url,
    thumbnail_url,
    duration_seconds,
    category,
    tags
)
SELECT
    id as tenant_id,
    'Compliance and Regulations Overview',
    'Understanding industry compliance requirements and regulations',
    'https://example.com/videos/compliance.mp4',
    'https://example.com/thumbnails/compliance.jpg',
    540,
    'Compliance',
    ARRAY['compliance', 'regulations', 'legal']
FROM tenants
WHERE slug != 'test-company'
ON CONFLICT DO NOTHING;

INSERT INTO marcel_gpt_premade_videos (
    tenant_id,
    title,
    description,
    video_url,
    thumbnail_url,
    duration_seconds,
    category,
    tags
)
SELECT
    id as tenant_id,
    'Personal Protective Equipment (PPE) Guide',
    'Comprehensive guide on proper PPE selection and usage',
    'https://example.com/videos/ppe-guide.mp4',
    'https://example.com/thumbnails/ppe-guide.jpg',
    480,
    'Safety',
    ARRAY['ppe', 'safety', 'equipment']
FROM tenants
WHERE slug != 'test-company'
ON CONFLICT DO NOTHING;

-- =====================================================================
-- PART 5: Permissions
-- =====================================================================

-- Add new permissions
INSERT INTO permissions (name, description, category) VALUES
    ('marcel_gpt.view_library', 'View premade video library', 'MarcelGPT'),
    ('marcel_gpt.assign_videos', 'Assign videos to workers', 'MarcelGPT'),
    ('marcel_gpt.view_training', 'Access incident reports training system', 'MarcelGPT'),
    ('marcel_gpt.generate_training', 'Generate training videos from incident reports', 'MarcelGPT')
ON CONFLICT (name) DO NOTHING;

-- Grant permissions to Company Admin (role_id = 2) and HSE Specialist (role_id = 3)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions WHERE name IN (
    'marcel_gpt.view_library',
    'marcel_gpt.assign_videos',
    'marcel_gpt.view_training',
    'marcel_gpt.generate_training'
)
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions WHERE name IN (
    'marcel_gpt.view_library',
    'marcel_gpt.assign_videos',
    'marcel_gpt.view_training',
    'marcel_gpt.generate_training'
)
ON CONFLICT DO NOTHING;

-- =====================================================================
-- Migration Complete
-- =====================================================================

SELECT '✅ Marcel GPT Library and Training system created successfully!' as status;
