-- =====================================================================
-- Migration: Incident Report Dialogues
-- Purpose : Store incident report examples for training video generation
-- Date    : 2025-11-10
-- =====================================================================

CREATE TABLE IF NOT EXISTS incident_report_dialogues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  what_happened TEXT NOT NULL,
  why_did_it_happen TEXT NOT NULL,
  what_did_they_learn TEXT NOT NULL,
  ask_yourself_or_crew TEXT,
  severity VARCHAR(20) CHECK (severity IN ('critical', 'high', 'medium', 'low')),
  department VARCHAR(100),
  category VARCHAR(100),
  is_template BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_incident_dialogues_tenant
    ON incident_report_dialogues(tenant_id);

CREATE INDEX IF NOT EXISTS idx_incident_dialogues_severity
    ON incident_report_dialogues(severity);

CREATE INDEX IF NOT EXISTS idx_incident_dialogues_department
    ON incident_report_dialogues(department);

-- RLS Policy: Users can only see incidents from their tenant
ALTER TABLE incident_report_dialogues ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their tenant incidents and global templates"
  ON incident_report_dialogues
  FOR SELECT
  USING (
    is_template AND tenant_id IS NULL
    OR tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  );

CREATE POLICY "Only admins can insert incident dialogues"
  ON incident_report_dialogues
  FOR INSERT
  WITH CHECK (
    tenant_id = (auth.jwt() ->> 'tenant_id')::uuid AND
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid()
      AND role_id = 1  -- Admin role
      AND tenant_id = incident_report_dialogues.tenant_id
    )
  );

CREATE POLICY "Only admins can update incident dialogues"
  ON incident_report_dialogues
  FOR UPDATE
  USING (
    tenant_id = (auth.jwt() ->> 'tenant_id')::uuid AND
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid()
      AND role_id = 1  -- Admin role
      AND tenant_id = incident_report_dialogues.tenant_id
    )
  );
