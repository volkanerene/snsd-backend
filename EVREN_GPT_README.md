# EvrenGPT Backend Integration Guide

Complete backend implementation for the EvrenGPT evaluation process.

## Overview

EvrenGPT is a multi-step evaluation process that includes:
1. **FRM32** - Contractor self-assessment (AI-scored)
2. **FRM33** - Supervisor evaluation (AI-scored)
3. **FRM34** - Supervisor evaluation (AI-scored)
4. **FRM35** - Final supervisor evaluation (AI-scored)
5. **Final Score** - Average of all form scores

## Architecture

```
Company Admin/HSE Specialist
    ↓ (Start Process)
EvrenGPT Session Created
    ↓
Contractors Selected
    ↓
Email Sent with FRM32 Link
    ↓
Contractor Fills FRM32
    ↓
n8n Webhook → AI Scoring (0, 3, 6, 10 per question)
    ↓
FRM33 Triggered → Supervisor
    ↓
n8n Webhook → AI Scoring
    ↓
FRM34 Triggered → Supervisor
    ↓
n8n Webhook → AI Scoring
    ↓
FRM35 Triggered → Supervisor
    ↓
n8n Webhook → AI Scoring
    ↓
Final Score Calculated (Average)
    ↓
Process Complete
```

## Database Schema

### Tables

#### 1. evren_gpt_sessions
Main session tracking table.

```sql
Columns:
- id (UUID, PK)
- session_id (VARCHAR, UNIQUE) - Format: sess_XXXXXX
- tenant_id (UUID, FK → tenants)
- created_by (UUID, FK → profiles)
- status (VARCHAR) - active, completed, cancelled
- custom_message (TEXT)
- metadata (JSONB)
- created_at (TIMESTAMP)
- completed_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### 2. evren_gpt_session_contractors
Links contractors to sessions.

```sql
Columns:
- id (UUID, PK)
- session_id (VARCHAR, FK → evren_gpt_sessions)
- contractor_id (UUID, FK → contractors)
- cycle (INT) - Allows re-evaluation
- status (VARCHAR) - pending, frm32_sent, frm32_completed, etc.
- frm32_sent_at, frm32_completed_at, etc. (TIMESTAMP)
- final_score (DECIMAL)
- metadata (JSONB)
- created_at, updated_at (TIMESTAMP)

Unique: (session_id, contractor_id, cycle)
```

#### 3. evren_gpt_form_submissions
Stores all form submissions.

```sql
Columns:
- id (UUID, PK)
- session_id (VARCHAR, FK)
- contractor_id (UUID, FK)
- form_id (VARCHAR) - frm32, frm33, frm34, frm35
- cycle (INT)
- answers (JSONB) - Form responses
- raw_score (DECIMAL) - Before weighting
- final_score (DECIMAL) - After weighting
- status (VARCHAR) - pending, submitted, scored, completed
- submitted_by (UUID, FK → profiles)
- submitted_at (TIMESTAMP)
- n8n_processed_at (TIMESTAMP)
- n8n_webhook_response (JSONB)
- metadata (JSONB)
- created_at, updated_at (TIMESTAMP)

Unique: (session_id, contractor_id, form_id, cycle)
```

#### 4. evren_gpt_question_scores
Individual question scores from AI.

```sql
Columns:
- id (UUID, PK)
- submission_id (UUID, FK → evren_gpt_form_submissions)
- question_id (VARCHAR)
- question_text (TEXT)
- answer_text (TEXT)
- ai_score (INT) - 0, 3, 6, or 10
- ai_reasoning (TEXT)
- weight (DECIMAL)
- created_at (TIMESTAMP)
```

#### 5. evren_gpt_notifications
Email notification log.

```sql
Columns:
- id (UUID, PK)
- session_id (VARCHAR, FK)
- contractor_id (UUID, FK, nullable)
- recipient_email (VARCHAR)
- recipient_name (VARCHAR)
- notification_type (VARCHAR) - frm32_invite, frm33_invite, etc.
- form_id (VARCHAR)
- subject (TEXT)
- body (TEXT)
- status (VARCHAR) - pending, sent, failed, bounced
- sent_at (TIMESTAMP)
- error_message (TEXT)
- metadata (JSONB)
- created_at (TIMESTAMP)
```

### Views

#### 1. evren_gpt_session_progress
Session overview with stats.

#### 2. evren_gpt_form_completion_status
Contractor-level form completion status.

### Functions

#### 1. generate_evren_session_id()
Generates unique session IDs.

#### 2. calculate_evren_final_score(session_id, contractor_id, cycle)
Calculates average score across all forms.

#### 3. update_contractor_session_status()
Trigger function to update status when forms complete.

## API Endpoints

### Session Management

#### Start Process
```http
POST /api/evren-gpt/start-process
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
Body:
{
  "tenant_id": "uuid",
  "contractor_ids": ["uuid1", "uuid2"],
  "custom_message": "Optional message"
}
Response:
{
  "session_id": "sess_123456",
  "contractors_notified": 2,
  "message": "Success message"
}
```

#### List Sessions
```http
GET /api/evren-gpt/sessions?status=active&limit=50&offset=0
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
Response:
[
  {
    "id": "uuid",
    "session_id": "sess_123456",
    "tenant_id": "uuid",
    "created_by": "uuid",
    "status": "active",
    "total_contractors": 5,
    "completed_contractors": 2,
    "average_score": 85.5,
    "created_at": "2025-10-23T10:00:00Z"
  }
]
```

#### Get Session Details
```http
GET /api/evren-gpt/sessions/{session_id}
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
```

#### Update Session
```http
PATCH /api/evren-gpt/sessions/{session_id}
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
Body:
{
  "status": "completed",
  "custom_message": "Updated message"
}
```

### Form Submissions

#### Submit Form
```http
POST /api/evren-gpt/forms/submit
Headers:
  Authorization: Bearer {token}
Body:
{
  "session_id": "sess_123456",
  "contractor_id": "uuid",
  "form_id": "frm32",
  "cycle": 1,
  "answers": {
    "q1": "answer1",
    "q2": "answer2"
  }
}
Response:
{
  "id": "uuid",
  "session_id": "sess_123456",
  "contractor_id": "uuid",
  "form_id": "frm32",
  "status": "submitted",
  "submitted_at": "2025-10-23T10:00:00Z"
}
```

#### List Form Submissions
```http
GET /api/evren-gpt/forms/submissions?session_id=sess_123456&form_id=frm32
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
```

#### Get Submission Details
```http
GET /api/evren-gpt/forms/submissions/{submission_id}
Headers:
  Authorization: Bearer {token}
Response:
{
  "id": "uuid",
  "session_id": "sess_123456",
  "contractor_name": "Güveli İnşaat",
  "form_id": "frm32",
  "final_score": 80.5,
  "question_scores": [
    {
      "question_id": "q1",
      "question_text": "Question text",
      "answer_text": "Answer text",
      "ai_score": 10,
      "ai_reasoning": "Excellent response"
    }
  ]
}
```

### n8n Webhook

#### Receive AI Processing Results
```http
POST /api/evren-gpt/webhook/n8n/{form_id}
Body:
{
  "submission_id": "uuid",
  "session_id": "sess_123456",
  "contractor_id": "uuid",
  "form_id": "frm32",
  "cycle": 1,
  "question_scores": [
    {
      "question_id": "q1",
      "question_text": "text",
      "answer_text": "text",
      "ai_score": 10,
      "ai_reasoning": "reasoning",
      "weight": 1.0
    }
  ],
  "raw_score": 85.0,
  "final_score": 80.5,
  "ai_summary": "Overall assessment",
  "processed_at": "2025-10-23T10:00:00Z"
}
Response:
{
  "success": true,
  "message": "Successfully processed FRM32 submission",
  "submission_id": "uuid",
  "final_score": 80.5
}
```

### Statistics & Progress

#### Get Session Progress
```http
GET /api/evren-gpt/sessions/{session_id}/progress
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
Response:
[
  {
    "contractor_id": "uuid",
    "contractor_name": "Güveli İnşaat",
    "frm32_status": "completed",
    "frm33_status": "completed",
    "frm34_status": "pending",
    "frm35_status": "pending",
    "frm32_score": 80,
    "frm33_score": 85,
    "frm34_score": null,
    "frm35_score": null,
    "final_score": null,
    "overall_status": "frm33_completed"
  }
]
```

#### Get Session Statistics
```http
GET /api/evren-gpt/sessions/{session_id}/statistics
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
Response:
{
  "session_id": "sess_123456",
  "total_contractors": 10,
  "pending_contractors": 2,
  "in_progress_contractors": 5,
  "completed_contractors": 3,
  "average_final_score": 82.5,
  "frm32_completion_rate": 1.0,
  "frm33_completion_rate": 0.8,
  "frm34_completion_rate": 0.5,
  "frm35_completion_rate": 0.3
}
```

#### Get Tenant Stats
```http
GET /api/evren-gpt/admin/tenant-stats
Headers:
  Authorization: Bearer {token}
  X-Tenant-ID: {tenant_id}
Response:
{
  "tenant_id": "uuid",
  "total_sessions": 5,
  "active_sessions": 2,
  "completed_sessions": 3,
  "total_contractors_evaluated": 50,
  "total_forms_submitted": 150,
  "form_stats": [
    {
      "form_id": "frm32",
      "total_submissions": 50,
      "completed_submissions": 45,
      "average_score": 80.5,
      "min_score": 60.0,
      "max_score": 95.0
    }
  ]
}
```

## n8n Workflow Integration

### Workflow Setup

1. **Webhook Trigger** - Receive form submission
2. **ChatGPT Node** - Analyze each answer (score: 0, 3, 6, 10)
3. **JavaScript Code** - Calculate weighted average
4. **HTTP Request** - Send results back to API

### Example n8n Workflow (JSON)

```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "webhookId": "evren-gpt-frm32"
    },
    {
      "name": "ChatGPT",
      "type": "n8n-nodes-base.openAi",
      "parameters": {
        "model": "gpt-4",
        "prompt": "Score this answer from 0, 3, 6, or 10..."
      }
    },
    {
      "name": "Calculate Score",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "code": "// Calculate weighted average"
      }
    },
    {
      "name": "Send Results",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://api.snsdconsultant.com/api/evren-gpt/webhook/n8n/frm32",
        "method": "POST"
      }
    }
  ]
}
```

## Role-Based Access Control

### Permissions

- **Company Admin (role_id = 2)** - Can start processes, view all data
- **HSE Specialist (role_id = 3)** - Can start processes, view evaluations
- **Contractor Admin (role_id = 4)** - Can submit FRM32 only
- **Supervisor (role_id = 5)** - Can submit FRM33-35
- **Worker (role_id = 6)** - Read-only access

### RLS Policies

All tables have Row Level Security enabled:
- Users can only see data for their tenant
- Form submissions restricted by role
- Admins can manage all sessions in their tenant

## Testing

### 1. Start a Process

```bash
curl -X POST https://api.snsdconsultant.com/api/evren-gpt/start-process \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Tenant-ID: YOUR_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "YOUR_TENANT_ID",
    "contractor_ids": ["contractor_uuid"],
    "custom_message": "Please complete your evaluation"
  }'
```

### 2. Submit a Form

```bash
curl -X POST https://api.snsdconsultant.com/api/evren-gpt/forms/submit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_123456",
    "contractor_id": "contractor_uuid",
    "form_id": "frm32",
    "cycle": 1,
    "answers": {
      "q1": "answer1",
      "q2": "answer2"
    }
  }'
```

### 3. Simulate n8n Webhook

```bash
curl -X POST https://api.snsdconsultant.com/api/evren-gpt/webhook/n8n/frm32 \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": "submission_uuid",
    "session_id": "sess_123456",
    "contractor_id": "contractor_uuid",
    "form_id": "frm32",
    "cycle": 1,
    "question_scores": [
      {
        "question_id": "q1",
        "question_text": "Question 1",
        "answer_text": "Answer 1",
        "ai_score": 10,
        "ai_reasoning": "Excellent",
        "weight": 1.0
      }
    ],
    "raw_score": 85.0,
    "final_score": 80.5,
    "processed_at": "2025-10-23T10:00:00Z"
  }'
```

## Deployment Checklist

- [ ] Apply database migration (005_evren_gpt.sql)
- [ ] Restart backend server
- [ ] Configure n8n webhooks
- [ ] Set up email service integration
- [ ] Test complete flow
- [ ] Update frontend to use new endpoints
- [ ] Configure CORS for production domain
- [ ] Set up monitoring and logging

## Environment Variables

No new environment variables needed. Uses existing Supabase configuration.

## Support & Troubleshooting

### Common Issues

1. **404 on endpoints** - Ensure router is registered in main.py
2. **403 Forbidden** - Check RLS policies and user permissions
3. **Email not sending** - Integrate with actual email service
4. **n8n webhook failing** - Verify webhook URL and payload format

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- [ ] Email service integration (SendGrid, AWS SES)
- [ ] Real-time progress notifications via WebSocket
- [ ] PDF report generation
- [ ] Bulk session operations
- [ ] Session templates
- [ ] Automated reminders
- [ ] Analytics dashboard

---

**Created:** 2025-10-23
**Last Updated:** 2025-10-23
**Version:** 1.0.0
