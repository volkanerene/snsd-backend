-- Migration: Create subscription tiers and tenant subscriptions
-- Purpose: Manage tenant subscription tiers and feature limits
-- Author: System
-- Date: 2025-10-17

-- Create subscription_tiers table
CREATE TABLE IF NOT EXISTS subscription_tiers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  display_name VARCHAR(100) NOT NULL,
  description TEXT,
  price_monthly DECIMAL(10,2),
  price_yearly DECIMAL(10,2),
  max_users INTEGER,
  max_evaluations_per_month INTEGER,
  max_contractors INTEGER,
  max_storage_gb INTEGER,
  features JSONB DEFAULT '{}'::jsonb,
  is_active BOOLEAN DEFAULT true,
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create tenant_subscriptions table
CREATE TABLE IF NOT EXISTS tenant_subscriptions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  tier_id INTEGER NOT NULL REFERENCES subscription_tiers(id),
  status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired', 'trial')),
  billing_cycle VARCHAR(20) CHECK (billing_cycle IN ('monthly', 'yearly')),
  starts_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  ends_at TIMESTAMP WITH TIME ZONE,
  trial_ends_at TIMESTAMP WITH TIME ZONE,
  cancelled_at TIMESTAMP WITH TIME ZONE,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(tenant_id, starts_at) -- Prevent overlapping subscriptions
);

-- Create usage_tracking table for feature usage
CREATE TABLE IF NOT EXISTS usage_tracking (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  users_count INTEGER DEFAULT 0,
  evaluations_count INTEGER DEFAULT 0,
  contractors_count INTEGER DEFAULT 0,
  storage_used_gb DECIMAL(10,2) DEFAULT 0,
  api_calls_count INTEGER DEFAULT 0,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(tenant_id, period_start)
);

-- Create indexes
CREATE INDEX idx_subscription_tiers_is_active ON subscription_tiers(is_active);
CREATE INDEX idx_subscription_tiers_sort_order ON subscription_tiers(sort_order);
CREATE INDEX idx_tenant_subscriptions_tenant_id ON tenant_subscriptions(tenant_id);
CREATE INDEX idx_tenant_subscriptions_tier_id ON tenant_subscriptions(tier_id);
CREATE INDEX idx_tenant_subscriptions_status ON tenant_subscriptions(status);
CREATE INDEX idx_tenant_subscriptions_ends_at ON tenant_subscriptions(ends_at);
CREATE INDEX idx_usage_tracking_tenant_id ON usage_tracking(tenant_id);
CREATE INDEX idx_usage_tracking_period ON usage_tracking(period_start, period_end);

-- Enable RLS
ALTER TABLE subscription_tiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_tracking ENABLE ROW LEVEL SECURITY;

-- RLS Policies for subscription_tiers
CREATE POLICY "Anyone can view active tiers"
  ON subscription_tiers FOR SELECT
  TO authenticated
  USING (is_active = true);

CREATE POLICY "Only super admins can manage tiers"
  ON subscription_tiers FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

-- RLS Policies for tenant_subscriptions
CREATE POLICY "Super admins can view all subscriptions"
  ON tenant_subscriptions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

CREATE POLICY "Tenant users can view their subscription"
  ON tenant_subscriptions FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM tenant_users
      WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Only super admins can manage subscriptions"
  ON tenant_subscriptions FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

-- RLS Policies for usage_tracking
CREATE POLICY "Super admins can view all usage"
  ON usage_tracking FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.role_id = 1
    )
  );

CREATE POLICY "Tenant admins can view their usage"
  ON usage_tracking FOR SELECT
  TO authenticated
  USING (
    tenant_id IN (
      SELECT tenant_id FROM tenant_users
      WHERE user_id = auth.uid()
      AND role_id IN (1, 2)
    )
  );

-- Seed default subscription tiers
INSERT INTO subscription_tiers (
  name, display_name, description,
  price_monthly, price_yearly,
  max_users, max_evaluations_per_month, max_contractors, max_storage_gb,
  features, sort_order
) VALUES
  (
    'free',
    'Free Trial',
    'Perfect for trying out SnSD',
    0.00, 0.00,
    3, 10, 5, 1,
    '{"custom_branding": false, "api_access": false, "priority_support": false, "advanced_analytics": false}'::jsonb,
    1
  ),
  (
    'starter',
    'Starter',
    'Great for small teams',
    49.00, 490.00,
    10, 50, 20, 5,
    '{"custom_branding": false, "api_access": true, "priority_support": false, "advanced_analytics": false}'::jsonb,
    2
  ),
  (
    'professional',
    'Professional',
    'For growing organizations',
    149.00, 1490.00,
    50, 200, 100, 20,
    '{"custom_branding": true, "api_access": true, "priority_support": true, "advanced_analytics": true}'::jsonb,
    3
  ),
  (
    'enterprise',
    'Enterprise',
    'For large scale operations',
    499.00, 4990.00,
    NULL, NULL, NULL, 100, -- NULL = unlimited
    '{"custom_branding": true, "api_access": true, "priority_support": true, "advanced_analytics": true, "dedicated_account_manager": true, "sla": true}'::jsonb,
    4
  )
ON CONFLICT (name) DO NOTHING;

-- Create function to check subscription limits
CREATE OR REPLACE FUNCTION check_subscription_limit(
  p_tenant_id UUID,
  p_limit_type VARCHAR,
  p_current_count INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
  v_max_limit INTEGER;
  v_tier_id INTEGER;
BEGIN
  -- Get current active subscription tier
  SELECT tier_id INTO v_tier_id
  FROM tenant_subscriptions
  WHERE tenant_id = p_tenant_id
    AND status = 'active'
    AND (ends_at IS NULL OR ends_at > NOW())
  ORDER BY starts_at DESC
  LIMIT 1;

  IF v_tier_id IS NULL THEN
    RETURN false; -- No active subscription
  END IF;

  -- Get the limit based on type
  CASE p_limit_type
    WHEN 'users' THEN
      SELECT max_users INTO v_max_limit FROM subscription_tiers WHERE id = v_tier_id;
    WHEN 'evaluations' THEN
      SELECT max_evaluations_per_month INTO v_max_limit FROM subscription_tiers WHERE id = v_tier_id;
    WHEN 'contractors' THEN
      SELECT max_contractors INTO v_max_limit FROM subscription_tiers WHERE id = v_tier_id;
    WHEN 'storage' THEN
      SELECT max_storage_gb INTO v_max_limit FROM subscription_tiers WHERE id = v_tier_id;
    ELSE
      RETURN false;
  END CASE;

  -- NULL means unlimited
  IF v_max_limit IS NULL THEN
    RETURN true;
  END IF;

  RETURN p_current_count < v_max_limit;
END;
$$ LANGUAGE plpgsql;

-- Create function to get current usage
CREATE OR REPLACE FUNCTION get_current_usage(
  p_tenant_id UUID,
  p_usage_type VARCHAR
)
RETURNS INTEGER AS $$
DECLARE
  v_count INTEGER := 0;
  v_current_period_start DATE;
BEGIN
  v_current_period_start := DATE_TRUNC('month', CURRENT_DATE)::DATE;

  CASE p_usage_type
    WHEN 'users' THEN
      SELECT COUNT(*) INTO v_count
      FROM tenant_users
      WHERE tenant_id = p_tenant_id AND status = 'active';

    WHEN 'evaluations' THEN
      SELECT COALESCE(evaluations_count, 0) INTO v_count
      FROM usage_tracking
      WHERE tenant_id = p_tenant_id
        AND period_start = v_current_period_start;

    WHEN 'contractors' THEN
      SELECT COUNT(*) INTO v_count
      FROM contractors
      WHERE tenant_id = p_tenant_id AND status = 'active';

    ELSE
      v_count := 0;
  END CASE;

  RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Create updated_at triggers
CREATE TRIGGER subscription_tiers_updated_at
  BEFORE UPDATE ON subscription_tiers
  FOR EACH ROW
  EXECUTE FUNCTION update_tenant_users_updated_at(); -- Reuse existing trigger function

CREATE TRIGGER tenant_subscriptions_updated_at
  BEFORE UPDATE ON tenant_subscriptions
  FOR EACH ROW
  EXECUTE FUNCTION update_tenant_users_updated_at();

CREATE TRIGGER usage_tracking_updated_at
  BEFORE UPDATE ON usage_tracking
  FOR EACH ROW
  EXECUTE FUNCTION update_tenant_users_updated_at();

-- Add comments
COMMENT ON TABLE subscription_tiers IS 'Available subscription tiers with features and limits';
COMMENT ON TABLE tenant_subscriptions IS 'Tenant subscription history and current plan';
COMMENT ON TABLE usage_tracking IS 'Monthly usage tracking per tenant';
COMMENT ON FUNCTION check_subscription_limit IS 'Check if tenant can create more resources based on subscription';
COMMENT ON FUNCTION get_current_usage IS 'Get current usage count for a tenant';
