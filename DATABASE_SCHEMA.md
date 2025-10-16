# Database Schema Documentation

This document describes the database schema for the SnSD Backend application.

## Overview

The SnSD (Safety & Sustainability Database) backend manages multi-tenant safety evaluation and contractor management system. The system is built on Supabase (PostgreSQL) and uses row-level security (RLS) for data isolation.

## Tables

### 1. tenants
Multi-tenant organization/company information.

**Columns:**
- `id` (UUID, PK) - Unique tenant identifier
- `name` (string) - Company name
- `slug` (string) - URL-friendly identifier
- `logo_url` (string, nullable) - Company logo URL
- `subdomain` (string) - Subdomain for tenant access
- `license_plan` (string) - Subscription plan (basic, professional, enterprise)
- `modules_enabled` (array) - List of enabled modules (evren_gpt, marcel_gpt, safety_bud)
- `max_users` (int) - Maximum allowed users
- `max_contractors` (int) - Maximum allowed contractors
- `max_video_requests_monthly` (int) - Monthly video request limit
- `settings` (jsonb) - Tenant-specific settings
- `contact_email` (string) - Primary contact email
- `contact_phone` (string, nullable) - Contact phone number
- `address` (string, nullable) - Physical address
- `status` (string) - Tenant status (active, inactive, suspended)
- `trial_ends_at` (timestamp, nullable) - Trial period end date
- `subscription_ends_at` (timestamp, nullable) - Subscription end date
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `created_by` (UUID, nullable) - Creator user ID

### 2. roles
User role definitions and permissions.

**Columns:**
- `id` (int, PK) - Role identifier
- `name` (string) - Role name
- `slug` (string) - URL-friendly identifier
- `description` (string, nullable) - Role description
- `level` (int) - Hierarchical level (0=highest)
- `permissions` (array) - List of permission strings
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp

**Default Roles:**
- SNSD Admin (level 0) - Platform administrator
- Company Admin (level 1) - Tenant administrator
- HSE Manager (level 2) - Safety manager
- Evaluator (level 3) - Evaluation specialist
- Viewer (level 4) - Read-only access

### 3. profiles
User profiles linked to Supabase auth users.

**Columns:**
- `id` (UUID, PK) - User identifier (matches auth.users.id)
- `tenant_id` (UUID, FK) - Associated tenant
- `full_name` (string) - User's full name
- `username` (string) - Unique username
- `avatar_url` (string, nullable) - Profile picture URL
- `phone` (string, nullable) - Phone number
- `locale` (string) - Language preference (tr, en)
- `timezone` (string) - Timezone (Europe/Istanbul)
- `role_id` (int, FK) - User role
- `contractor_id` (UUID, FK, nullable) - Associated contractor (for contractor users)
- `department` (string, nullable) - Department name
- `job_title` (string, nullable) - Job title
- `notification_preferences` (jsonb) - Notification settings
- `is_active` (boolean) - Account active status
- `last_login_at` (timestamp, nullable) - Last login timestamp
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp

### 4. contractors
Contractor/supplier company information.

**Columns:**
- `id` (UUID, PK) - Contractor identifier
- `tenant_id` (UUID, FK) - Parent tenant
- `name` (string) - Company name
- `legal_name` (string) - Legal company name
- `tax_number` (string) - Tax identification number
- `trade_registry_number` (string, nullable) - Trade registry number
- `contact_person` (string) - Primary contact person
- `contact_email` (string) - Contact email
- `contact_phone` (string) - Contact phone
- `address` (string, nullable) - Physical address
- `city` (string) - City
- `country` (string) - Country code (TR)
- `documents` (jsonb array) - Document metadata
- `status` (string) - Contractor status (active, inactive, blacklisted)
- `risk_level` (string, nullable) - Risk classification (green, yellow, red)
- `last_evaluation_score` (float, nullable) - Most recent evaluation score
- `last_evaluation_date` (timestamp, nullable) - Last evaluation date
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `created_by` (UUID, FK) - Creator user ID

### 5. frm32_questions
FRM-32 evaluation questionnaire.

**Columns:**
- `id` (UUID, PK) - Question identifier
- `question_code` (string) - Unique question code (Q1, Q2, etc.)
- `question_text_tr` (string) - Question text in Turkish
- `question_text_en` (string, nullable) - Question text in English
- `k2_category` (string) - K2 category classification
- `k2_weight` (float) - Category weight for scoring
- `question_type` (string) - Type (yes_no, number, multiple_choice, text, file_upload)
- `options` (array, nullable) - Answer options for multiple choice
- `scoring_rules` (jsonb) - Scoring logic per answer
- `max_score` (float) - Maximum achievable score
- `is_required` (boolean) - Whether answer is required
- `is_active` (boolean) - Question active status
- `position` (int) - Display order
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp

### 6. frm32_submissions
FRM-32 evaluation submissions.

**Columns:**
- `id` (UUID, PK) - Submission identifier
- `tenant_id` (UUID, FK) - Tenant
- `contractor_id` (UUID, FK) - Evaluated contractor
- `evaluation_period` (string) - Period (2025-Q3, 2025-09)
- `evaluation_type` (string) - Type (periodic, incident, audit)
- `status` (string) - Status (draft, submitted, in_review, completed, rejected)
- `progress_percentage` (int) - Completion percentage
- `submitted_at` (timestamp, nullable) - Submission timestamp
- `completed_at` (timestamp, nullable) - Completion timestamp
- `final_score` (float, nullable) - Final calculated score
- `risk_classification` (string, nullable) - Risk level (green, yellow, red)
- `ai_summary` (string, nullable) - AI-generated summary
- `attachments` (jsonb array) - Attachment metadata
- `notes` (string, nullable) - Additional notes
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `created_by` (UUID, FK) - Creator user ID
- `reviewed_by` (UUID, FK, nullable) - Reviewer user ID

### 7. frm32_answers
Individual question answers within submissions.

**Columns:**
- `id` (UUID, PK) - Answer identifier
- `submission_id` (UUID, FK) - Parent submission
- `question_id` (UUID, FK) - Answered question
- `answer_value` (jsonb) - Answer value (flexible type)
- `score` (float, nullable) - Calculated score for this answer
- `attachments` (jsonb array, nullable) - Supporting documents
- `notes` (string, nullable) - Additional notes
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp

### 8. frm32_scores
Category-level scores for submissions.

**Columns:**
- `id` (UUID, PK) - Score identifier
- `submission_id` (UUID, FK) - Parent submission
- `k2_category` (string) - K2 category
- `category_score` (float) - Raw category score
- `category_weight` (float) - Category weight
- `weighted_score` (float) - Weighted score contribution
- `max_possible_score` (float) - Maximum possible score
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp

### 9. k2_evaluations
K2-specific evaluation records.

**Columns:**
- `id` (UUID, PK) - Evaluation identifier
- `submission_id` (UUID, FK) - Related submission
- `contractor_id` (UUID, FK) - Evaluated contractor
- `tenant_id` (UUID, FK) - Tenant
- `evaluation_period` (string) - Evaluation period
- `k2_category` (string) - K2 category
- `category_score` (float) - Category score
- `weighted_score` (float) - Weighted score
- `risk_level` (string, nullable) - Risk classification
- `findings` (text, nullable) - Evaluation findings
- `recommendations` (text, nullable) - Recommendations
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `created_by` (UUID, FK, nullable) - Creator user ID

### 10. final_scores
Aggregated final scores and analytics.

**Columns:**
- `id` (UUID, PK) - Score identifier
- `submission_id` (UUID, FK) - Related submission
- `contractor_id` (UUID, FK) - Contractor
- `tenant_id` (UUID, FK) - Tenant
- `evaluation_period` (string) - Evaluation period
- `total_score` (float) - Total calculated score
- `risk_classification` (string) - Risk level (green, yellow, red)
- `grade` (string, nullable) - Letter grade (A+, A, B+, B, C, D, F)
- `percentile` (float, nullable) - Percentile ranking
- `industry_average` (float, nullable) - Industry benchmark
- `previous_score` (float, nullable) - Previous evaluation score
- `score_trend` (string, nullable) - Trend (improving, stable, declining)
- `summary` (text, nullable) - Executive summary
- `recommendations` (text, nullable) - Improvement recommendations
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `calculated_by` (UUID, FK, nullable) - Calculating user ID

### 11. frm35_invites
FRM-35 external invitations (e.g., safety videos, interviews).

**Columns:**
- `id` (UUID, PK) - Invite identifier
- `tenant_id` (UUID, FK) - Tenant
- `contractor_id` (UUID, FK) - Contractor
- `invited_email` (string) - Invitee email
- `invited_name` (string, nullable) - Invitee name
- `invited_phone` (string, nullable) - Invitee phone
- `invite_type` (string) - Type (safety_video, document_review, interview)
- `subject` (string) - Invitation subject
- `message` (text, nullable) - Invitation message
- `token` (string, nullable) - Unique access token
- `status` (string) - Status (pending, sent, opened, completed, expired)
- `expires_at` (timestamp, nullable) - Expiration timestamp
- `sent_at` (timestamp, nullable) - Send timestamp
- `opened_at` (timestamp, nullable) - First open timestamp
- `completed_at` (timestamp, nullable) - Completion timestamp
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `created_by` (UUID, FK, nullable) - Creator user ID

### 12. payments
Payment and subscription records.

**Columns:**
- `id` (UUID, PK) - Payment identifier
- `tenant_id` (UUID, FK) - Tenant
- `amount` (float) - Payment amount
- `currency` (string) - Currency code (TRY, USD, EUR)
- `payment_method` (string) - Method (credit_card, bank_transfer, paypal)
- `provider` (string, nullable) - Payment provider (stripe, paytr, iyzico, bank)
- `provider_transaction_id` (string, nullable) - Provider transaction ID
- `provider_response` (jsonb, nullable) - Provider response data
- `status` (string) - Status (pending, completed, failed, refunded)
- `subscription_period` (string, nullable) - Period (monthly, yearly)
- `subscription_starts_at` (timestamp, nullable) - Subscription start
- `subscription_ends_at` (timestamp, nullable) - Subscription end
- `invoice_number` (string, nullable) - Invoice number
- `invoice_url` (string, nullable) - Invoice document URL
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `created_by` (UUID, FK, nullable) - Creator user ID

### 13. audit_log
System audit trail.

**Columns:**
- `id` (UUID, PK) - Log identifier
- `tenant_id` (UUID, FK) - Tenant
- `user_id` (UUID, FK, nullable) - Acting user
- `action` (string) - Action performed (create, update, delete, login, logout)
- `resource_type` (string) - Resource type (tenant, contractor, submission)
- `resource_id` (UUID, nullable) - Resource identifier
- `changes` (jsonb, nullable) - Change details
- `ip_address` (string, nullable) - IP address
- `user_agent` (string, nullable) - User agent string
- `metadata` (jsonb) - Additional metadata
- `created_at` (timestamp) - Record creation timestamp

## Relationships

```
tenants (1) ──< (M) profiles
tenants (1) ──< (M) contractors
tenants (1) ──< (M) frm32_submissions
tenants (1) ──< (M) payments
tenants (1) ──< (M) audit_log

roles (1) ──< (M) profiles

contractors (1) ──< (M) frm32_submissions
contractors (1) ──< (M) k2_evaluations
contractors (1) ──< (M) final_scores
contractors (1) ──< (M) frm35_invites

frm32_submissions (1) ──< (M) frm32_answers
frm32_submissions (1) ──< (M) frm32_scores
frm32_submissions (1) ─── (1) final_scores

frm32_questions (1) ──< (M) frm32_answers
```

## K2 Categories

The K2 evaluation framework categorizes safety aspects:
- **general_info** - General company information
- **legal_compliance** - Legal compliance and certifications
- **safety_organization** - Safety organization structure
- **training** - Training programs and records
- **risk_management** - Risk assessment and management
- **emergency_response** - Emergency procedures
- **equipment** - Equipment and maintenance
- **documentation** - Documentation and reporting

## Risk Classifications

- **Green** (80-100 points) - Low risk, excellent compliance
- **Yellow** (50-79 points) - Medium risk, improvements needed
- **Red** (0-49 points) - High risk, immediate action required

## Schema Files Location

All Pydantic schemas are located in `/app/schemas/`:
- Base models (Base)
- Create models (Create)
- Update models (Update)
- Response models (without suffix)

## Usage Example

```python
from app.schemas import TenantCreate, Tenant

# Create a new tenant
tenant_data = TenantCreate(
    name="Example Corp",
    slug="example",
    subdomain="example.snsdconsultant.com",
    license_plan="professional",
    contact_email="admin@example.com",
    max_users=50
)

# Use in API endpoint
@app.post("/tenants", response_model=Tenant)
def create_tenant(tenant: TenantCreate):
    # Process tenant creation
    pass
```

## Notes

- All timestamps are stored in UTC
- UUIDs are used for primary keys (except roles which uses integers)
- JSONB fields provide flexibility for metadata and settings
- Row-Level Security (RLS) enforces tenant isolation
- Supabase Auth integration for user authentication
