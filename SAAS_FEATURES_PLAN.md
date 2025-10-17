# SnSD SaaS Platform - Complete Feature Plan

## 📋 Overview

This document outlines the complete feature set needed for SnSD to function as a full-fledged SaaS platform with multi-tenancy, RBAC, subscription management, and tier-based access control.

## 🎯 Current Status

### ✅ Existing Features (Database Schema Ready)

#### 1. **Multi-Tenancy**
- ✅ Tenants table with full SaaS fields
- ✅ Tenant isolation via RLS
- ✅ Tenant users junction table (many-to-many)
- ✅ Subdomain support

#### 2. **User Management**
- ✅ User profiles linked to Supabase Auth
- ✅ User roles (Super Admin, Admin, HSE Manager, Evaluator, Viewer)
- ✅ User-tenant relationships
- ✅ User invitation system

####3. **Permissions & RBAC**
- ✅ 40+ granular permissions
- ✅ Role-permission mapping
- ✅ Permission categories (users, tenants, contractors, etc.)
- ✅ RLS policies for data access

#### 4. **Subscription Management**
- ✅ Subscription tiers table (Free, Starter, Professional, Enterprise)
- ✅ Tenant subscriptions
- ✅ Usage tracking
- ✅ Feature limits per tier

#### 5. **Core Business Features**
- ✅ Contractor management
- ✅ FRM-32 evaluations
- ✅ K2 evaluations
- ✅ Final scoring system
- ✅ FRM-35 invitations
- ✅ File/document management
- ✅ Audit logging

#### 6. **Payments**
- ✅ Payment records
- ✅ Invoice tracking
- ✅ Subscription billing

---

## 🚧 Missing Backend APIs

### 1. **User Management Endpoints**

Current status: Partial

**Needed:**
- ✅ GET /users - List all users (with tenant filtering)
- ❌ POST /users - Create user (currently manual via Supabase)
- ❌ PUT /users/{id} - Update user
- ❌ DELETE /users/{id} - Delete/deactivate user
- ❌ POST /users/{id}/reset-password - Trigger password reset
- ❌ PUT /users/{id}/suspend - Suspend user
- ❌ PUT /users/{id}/activate - Activate user

### 2. **Tenant Management**

Current status: Basic CRUD exists

**Needed:**
- ✅ GET /tenants - List tenants
- ✅ POST /tenants - Create tenant
- ✅ GET /tenants/{id} - Get tenant details
- ✅ PUT /tenants/{id} - Update tenant
- ❌ DELETE /tenants/{id} - Soft delete tenant
- ❌ POST /tenants/{id}/suspend - Suspend tenant
- ❌ POST /tenants/{id}/activate - Activate tenant
- ❌ GET /tenants/{id}/statistics - Tenant usage stats
- ❌ GET /tenants/{id}/users - List tenant users
- ❌ POST /tenants/{id}/users - Add user to tenant

### 3. **Invitation System**

Current status: Exists but needs completion

**Needed:**
- ✅ POST /invitations - Create invitation
- ✅ GET /invitations - List invitations
- ✅ GET /invitations/{token}/verify - Verify invitation token
- ✅ POST /invitations/{token}/accept - Accept invitation
- ❌ DELETE /invitations/{id} - Cancel invitation
- ❌ POST /invitations/{id}/resend - Resend invitation email

### 4. **Subscription & Tier Management**

Current status: Basic tier listing exists

**Needed:**
- ✅ GET /tiers - List all subscription tiers
- ✅ GET /tiers/{id} - Get tier details
- ❌ POST /tenants/{id}/subscribe - Subscribe tenant to tier
- ❌ PUT /tenants/{id}/subscription - Update subscription
- ❌ POST /tenants/{id}/subscription/cancel - Cancel subscription
- ❌ GET /tenants/{id}/usage - Get current usage stats
- ❌ POST /tenants/{id}/usage/check - Check if feature is available
- ❌ GET /tiers/compare - Compare tier features

### 5. **Role & Permission Management**

Current status: Basic endpoints exist

**Needed:**
- ✅ GET /roles - List roles
- ✅ GET /roles/{id} - Get role details
- ❌ POST /roles - Create custom role
- ❌ PUT /roles/{id} - Update role
- ❌ DELETE /roles/{id} - Delete role
- ✅ GET /permissions - List all permissions
- ❌ PUT /roles/{id}/permissions - Update role permissions
- ❌ POST /users/{id}/check-permission - Check user permission

### 6. **Dashboard & Analytics**

Current status: Missing

**Needed:**
- ❌ GET /dashboard/stats - Overall dashboard stats
- ❌ GET /dashboard/tenant/{id}/stats - Tenant-specific stats
- ❌ GET /analytics/contractors - Contractor analytics
- ❌ GET /analytics/evaluations - Evaluation trends
- ❌ GET /analytics/usage - Usage analytics

---

## 🎨 Missing Frontend Pages

### 1. **Admin Portal**

**Super Admin Pages:**
- ❌ `/admin/tenants` - Tenant management
  - List all tenants
  - Create new tenant
  - Edit tenant details
  - Suspend/activate tenant
  - View tenant statistics

- ❌ `/admin/users` - Global user management
  - List all users across tenants
  - Create super admin users
  - Manage user roles

- ❌ `/admin/subscription-tiers` - Tier management
  - Create/edit subscription tiers
  - Set pricing and limits
  - Feature toggles per tier

- ❌ `/admin/analytics` - Platform analytics
  - Total users, tenants, revenue
  - Growth charts
  - System health

### 2. **Tenant Admin Pages**

**Company Admin Pages:**
- ❌ `/dashboard/team` - Team management
  - List team members
  - Invite new users
  - Manage user roles within tenant
  - Deactivate users

- ❌ `/dashboard/settings` - Tenant settings
  - Company profile
  - Logo upload
  - Contact information
  - Notification preferences

- ❌ `/dashboard/subscription` - Subscription management
  - Current plan details
  - Usage statistics vs limits
  - Upgrade/downgrade plan
  - Billing history
  - Payment methods

- ❌ `/dashboard/billing` - Billing & invoices
  - Payment history
  - Download invoices
  - Update payment method

- ❌ `/dashboard/roles` - Custom role management (if Enterprise tier)
  - Create custom roles
  - Assign permissions
  - Manage role hierarchy

### 3. **User Profile Pages**

- ✅ `/dashboard/profile` - User profile (exists partially)
  - Personal information
  - Password change
  - Notification preferences
  - Activity log

- ❌ `/dashboard/my-activity` - User activity log
  - Recent actions
  - Login history

### 4. **Onboarding Flow**

- ❌ `/onboarding/welcome` - Welcome screen
- ❌ `/onboarding/company-setup` - Company setup
- ❌ `/onboarding/invite-team` - Invite team members
- ❌ `/onboarding/select-plan` - Choose subscription plan
- ❌ `/onboarding/payment` - Payment setup
- ❌ `/onboarding/complete` - Onboarding complete

---

## 🔐 Tier-Based Access Control System

### Subscription Tiers & Features

| Feature | Free | Starter | Professional | Enterprise |
|---------|------|---------|-------------|------------|
| **Users** | 3 | 10 | 50 | Unlimited |
| **Contractors** | 5 | 25 | 100 | Unlimited |
| **Evaluations/month** | 10 | 50 | 200 | Unlimited |
| **Storage** | 1 GB | 10 GB | 50 GB | 500 GB |
| **Custom Roles** | ❌ | ❌ | ✅ | ✅ |
| **API Access** | ❌ | ❌ | ✅ | ✅ |
| **Advanced Analytics** | ❌ | ❌ | ✅ | ✅ |
| **White Label** | ❌ | ❌ | ❌ | ✅ |
| **Priority Support** | ❌ | ❌ | ✅ | ✅ |
| **SLA** | ❌ | ❌ | ❌ | ✅ |

### Implementation Strategy

**Backend:**
```python
# Middleware to check subscription limits
class SubscriptionMiddleware:
    async def check_limit(self, tenant_id: str, feature: str):
        # Get tenant's current tier
        # Get current usage
        # Compare with tier limits
        # Return allowed/denied
```

**Frontend:**
```tsx
// Hook to check feature availability
const { hasFeature, usage } = useSubscription();

if (!hasFeature('custom_roles')) {
  return <UpgradePlanBanner feature="Custom Roles" />;
}
```

---

## 📝 Implementation Priority

### Phase 1: Core SaaS Foundation (Week 1-2)

1. **User Management API**
   - Complete user CRUD
   - Password reset flow
   - User activation/suspension

2. **Tenant Management API**
   - Complete tenant CRUD
   - Tenant statistics
   - Tenant user management

3. **Frontend: Admin Portal**
   - `/admin/tenants` page
   - `/admin/users` page

### Phase 2: Subscription System (Week 3)

1. **Subscription API**
   - Subscribe to tier
   - Usage tracking
   - Limit checking middleware

2. **Frontend: Subscription Pages**
   - `/dashboard/subscription` page
   - Usage indicators
   - Upgrade prompts

### Phase 3: Team Management (Week 4)

1. **Invitation System Completion**
   - Email sending integration
   - Invitation acceptance flow

2. **Frontend: Team Pages**
   - `/dashboard/team` page
   - User invitation modal
   - Role assignment

### Phase 4: Tier-Based Access Control (Week 5)

1. **Access Control Middleware**
   - Feature flag system
   - Usage limit enforcement

2. **Frontend: Access Control**
   - Feature gates
   - Upgrade prompts
   - Usage warnings

### Phase 5: Analytics & Reporting (Week 6)

1. **Analytics API**
   - Dashboard statistics
   - Usage reports
   - Trend analysis

2. **Frontend: Analytics**
   - Dashboard charts
   - Reports page

---

## 🧪 Testing Checklist

### API Testing
- [ ] All endpoints return correct status codes
- [ ] RLS policies prevent unauthorized access
- [ ] Tenant isolation is enforced
- [ ] Permission checks work correctly
- [ ] Subscription limits are enforced

### Frontend Testing
- [ ] Super Admin sees all features
- [ ] Tenant Admin sees only their tenant data
- [ ] Regular users have limited access
- [ ] Upgrade prompts appear for restricted features
- [ ] Usage indicators update in real-time

### Integration Testing
- [ ] User invitation flow end-to-end
- [ ] Subscription upgrade/downgrade flow
- [ ] Team member addition flow
- [ ] Payment processing
- [ ] Email notifications

---

## 📚 Documentation Needed

1. **API Documentation**
   - Complete OpenAPI/Swagger docs
   - Authentication guide
   - Permission matrix

2. **Admin Guide**
   - How to create tenants
   - How to manage subscriptions
   - How to handle support requests

3. **User Guide**
   - How to invite team members
   - How to manage roles
   - How to upgrade subscription

---

## 🚀 Next Steps

1. Review this plan
2. Prioritize missing features
3. Create tasks for Phase 1
4. Start implementation

---

**Last Updated:** 2025-10-17
**Status:** Planning Phase
