# EvrenGPT Migration Application Guide

This guide explains how to apply the EvrenGPT database migration.

## Prerequisites

- Access to Supabase dashboard
- SQL Editor access in Supabase

## Step-by-Step Instructions

### 1. Access Supabase SQL Editor

1. Go to https://supabase.com/dashboard
2. Select your project: **ojkqgvkzumbnmasmajkw**
3. Click on "SQL Editor" in the left sidebar

### 2. Apply Migration

1. Click "New Query" button
2. Copy the entire contents of `005_evren_gpt.sql`
3. Paste into the SQL editor
4. Click "Run" or press Ctrl+Enter (Cmd+Enter on Mac)

### 3. Verify Migration

Run the following queries to verify the tables were created:

```sql
-- Check if tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'evren_gpt%'
ORDER BY table_name;

-- Expected output:
-- evren_gpt_form_submissions
-- evren_gpt_notifications
-- evren_gpt_question_scores
-- evren_gpt_session_contractors
-- evren_gpt_sessions
```

### 4. Verify Views

```sql
-- Check if views exist
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name LIKE 'evren_gpt%';

-- Expected output:
-- evren_gpt_form_completion_status
-- evren_gpt_session_progress
```

### 5. Verify Functions

```sql
-- Check if functions exist
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name LIKE '%evren%';

-- Expected output:
-- calculate_evren_final_score (FUNCTION)
-- generate_evren_session_id (FUNCTION)
-- update_contractor_session_status (FUNCTION)
-- update_evren_gpt_updated_at (FUNCTION)
```

### 6. Test Session ID Generation

```sql
-- Test the session ID generator
SELECT generate_evren_session_id();

-- Should return something like: sess_123456
```

## Tables Created

1. **evren_gpt_sessions** - Main session tracking
2. **evren_gpt_session_contractors** - Contractors in each session
3. **evren_gpt_form_submissions** - Form submissions (FRM32-35)
4. **evren_gpt_question_scores** - Individual question scores
5. **evren_gpt_notifications** - Email notifications log

## Row Level Security (RLS)

All tables have RLS policies that:
- Allow users to view data for their tenant
- Allow admins to manage sessions and submissions
- Allow contractors to submit their own forms (FRM32)
- Allow supervisors to submit FRM33-35

## Triggers

The following triggers are automatically set up:
- `updated_at` timestamp updates
- Automatic status updates when forms are completed
- Final score calculation when all forms are done

## Rollback (if needed)

If you need to rollback this migration:

```sql
-- Drop views
DROP VIEW IF EXISTS evren_gpt_session_progress CASCADE;
DROP VIEW IF EXISTS evren_gpt_form_completion_status CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS evren_sessions_updated_at ON evren_gpt_sessions;
DROP TRIGGER IF EXISTS session_contractors_updated_at ON evren_gpt_session_contractors;
DROP TRIGGER IF EXISTS form_submissions_updated_at ON evren_gpt_form_submissions;
DROP TRIGGER IF EXISTS update_session_contractor_status ON evren_gpt_form_submissions;

-- Drop functions
DROP FUNCTION IF EXISTS update_evren_gpt_updated_at() CASCADE;
DROP FUNCTION IF EXISTS generate_evren_session_id() CASCADE;
DROP FUNCTION IF EXISTS calculate_evren_final_score(VARCHAR, UUID, INT) CASCADE;
DROP FUNCTION IF EXISTS update_contractor_session_status() CASCADE;

-- Drop tables (order matters due to foreign keys)
DROP TABLE IF EXISTS evren_gpt_question_scores CASCADE;
DROP TABLE IF EXISTS evren_gpt_notifications CASCADE;
DROP TABLE IF EXISTS evren_gpt_form_submissions CASCADE;
DROP TABLE IF EXISTS evren_gpt_session_contractors CASCADE;
DROP TABLE IF EXISTS evren_gpt_sessions CASCADE;
```

## Support

If you encounter any issues:
1. Check Supabase logs for errors
2. Verify all prerequisite tables exist (tenants, contractors, profiles)
3. Ensure you have proper permissions

## Next Steps

After applying this migration:
1. Restart the backend server
2. The new EvrenGPT endpoints will be available at `/api/evren-gpt/*`
3. Test with Postman or the frontend application

## API Endpoints Available After Migration

- `POST /api/evren-gpt/start-process` - Start new evaluation process
- `GET /api/evren-gpt/sessions` - List sessions
- `GET /api/evren-gpt/sessions/{session_id}` - Get session details
- `POST /api/evren-gpt/forms/submit` - Submit a form
- `GET /api/evren-gpt/forms/submissions` - List submissions
- `POST /api/evren-gpt/webhook/n8n/{form_id}` - n8n webhook
- `GET /api/evren-gpt/sessions/{session_id}/progress` - Session progress
- `GET /api/evren-gpt/sessions/{session_id}/statistics` - Session stats
- `GET /api/evren-gpt/admin/tenant-stats` - Tenant statistics
