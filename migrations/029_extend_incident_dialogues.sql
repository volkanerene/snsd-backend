-- =====================================================================
-- Migration: Extend Incident Report Dialogues for 8-Part Training Format
-- Purpose: Add fields for reference cases, process safety and life safety rules
-- Date: 2025-11-14
-- =====================================================================

-- Add new columns to incident_report_dialogues table for enhanced training content
ALTER TABLE incident_report_dialogues
ADD COLUMN IF NOT EXISTS reference_case_title VARCHAR(500),
ADD COLUMN IF NOT EXISTS reference_case_description TEXT,
ADD COLUMN IF NOT EXISTS reference_case_year INT,
ADD COLUMN IF NOT EXISTS reference_case_location VARCHAR(255),
ADD COLUMN IF NOT EXISTS process_safety_fundamentals_violated TEXT[],
ADD COLUMN IF NOT EXISTS life_saving_rules_violated TEXT[],
ADD COLUMN IF NOT EXISTS preventive_actions TEXT[];

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_incident_dialogues_process_safety
    ON incident_report_dialogues USING GIN(process_safety_fundamentals_violated);

CREATE INDEX IF NOT EXISTS idx_incident_dialogues_life_saving
    ON incident_report_dialogues USING GIN(life_saving_rules_violated);

-- Add comment describing the 8-part training format
COMMENT ON COLUMN incident_report_dialogues.reference_case_title IS
'Title of reference incident from industry (e.g., "Thistle Field, North Sea - 1981")';

COMMENT ON COLUMN incident_report_dialogues.process_safety_fundamentals_violated IS
'Array of violated process safety fundamentals (e.g., ["We Respect Hazards", "Stay Aware"])';

COMMENT ON COLUMN incident_report_dialogues.life_saving_rules_violated IS
'Array of violated life saving rules (e.g., ["Control of Work", "Verification before Start"])';

COMMENT ON COLUMN incident_report_dialogues.preventive_actions IS
'Array of preventive actions taken to prevent recurrence';

-- =====================================================================
-- Migration Complete
-- =====================================================================

SELECT '✅ Extended incident_report_dialogues table for 8-part training format' as status;
