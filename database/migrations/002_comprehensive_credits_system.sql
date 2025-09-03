-- ============================================================================
-- COMPREHENSIVE CREDITS SYSTEM MIGRATION
-- Adds complete credits-based monetization layer to the analytics platform
-- Integrates with existing user management and platform functionality
-- ============================================================================

-- Enable Row Level Security for all new tables
SET row_security = on;

-- ============================================================================
-- 1. CREDIT PACKAGES TABLE
-- Defines subscription packages and their credit allowances
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.credit_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    monthly_credits INTEGER NOT NULL CHECK (monthly_credits >= 0),
    description TEXT,
    is_active BOOLEAN DEFAULT true NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create index for active packages lookup
CREATE INDEX IF NOT EXISTS idx_credit_packages_active ON public.credit_packages(is_active, sort_order);

-- Enable RLS
ALTER TABLE public.credit_packages ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Packages are readable by all authenticated users, modifiable by service role only
CREATE POLICY "credit_packages_select_policy" ON public.credit_packages
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "credit_packages_admin_policy" ON public.credit_packages
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 2. CREDIT WALLETS TABLE  
-- Each user's credit balance and billing cycle information
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.credit_wallets (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    package_id INTEGER REFERENCES public.credit_packages(id) ON DELETE SET NULL,
    
    -- Balance tracking
    current_balance INTEGER DEFAULT 0 NOT NULL CHECK (current_balance >= 0),
    total_earned_this_cycle INTEGER DEFAULT 0 NOT NULL,
    total_purchased_this_cycle INTEGER DEFAULT 0 NOT NULL,
    total_spent_this_cycle INTEGER DEFAULT 0 NOT NULL,
    
    -- Billing cycle management
    billing_cycle_start DATE NOT NULL DEFAULT CURRENT_DATE,
    next_reset_date DATE NOT NULL DEFAULT (CURRENT_DATE + INTERVAL '1 month'),
    rollover_months_allowed INTEGER DEFAULT 0 CHECK (rollover_months_allowed IN (0, 1, 2)),
    
    -- Wallet status
    is_locked BOOLEAN DEFAULT false NOT NULL,
    subscription_active BOOLEAN DEFAULT true NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Constraints
    UNIQUE(user_id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_credit_wallets_user_id ON public.credit_wallets(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_wallets_next_reset ON public.credit_wallets(next_reset_date) WHERE subscription_active = true;
CREATE INDEX IF NOT EXISTS idx_credit_wallets_locked ON public.credit_wallets(is_locked) WHERE is_locked = true;

-- Enable RLS
ALTER TABLE public.credit_wallets ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own wallet
CREATE POLICY "credit_wallets_user_policy" ON public.credit_wallets
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "credit_wallets_service_policy" ON public.credit_wallets
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 3. CREDIT PRICING RULES TABLE
-- Configurable pricing for different platform actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.credit_pricing_rules (
    id SERIAL PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    cost_per_action INTEGER NOT NULL CHECK (cost_per_action >= 0),
    free_allowance_per_month INTEGER DEFAULT 0 CHECK (free_allowance_per_month >= 0),
    description TEXT,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Performance index
CREATE INDEX IF NOT EXISTS idx_credit_pricing_active ON public.credit_pricing_rules(action_type) WHERE is_active = true;

-- Enable RLS
ALTER TABLE public.credit_pricing_rules ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Pricing rules are readable by all, modifiable by service role only
CREATE POLICY "credit_pricing_select_policy" ON public.credit_pricing_rules
    FOR SELECT TO authenticated USING (is_active = true);

CREATE POLICY "credit_pricing_admin_policy" ON public.credit_pricing_rules
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 4. CREDIT TRANSACTIONS TABLE
-- Complete audit trail of all credit movements
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.credit_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    wallet_id INTEGER NOT NULL REFERENCES public.credit_wallets(id) ON DELETE CASCADE,
    
    -- Transaction details
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN (
        'earn', 'spend', 'purchase', 'reset', 'expire', 'rollover', 'manual_adjust', 'refund'
    )),
    action_type VARCHAR(50), -- Reference to pricing rule action_type
    amount INTEGER NOT NULL, -- Positive for credits added, negative for spent
    balance_before INTEGER NOT NULL CHECK (balance_before >= 0),
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    
    -- Reference tracking
    description TEXT,
    reference_id VARCHAR(255), -- Profile ID, campaign ID, top-up ID, etc.
    reference_type VARCHAR(50), -- 'profile', 'campaign', 'top_up', 'admin_adjust', etc.
    
    -- Billing cycle tracking
    billing_cycle_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Metadata
    transaction_metadata JSONB DEFAULT '{}' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Performance constraint
    CHECK (
        (transaction_type = 'spend' AND amount < 0) OR 
        (transaction_type != 'spend' AND amount >= 0)
    )
);

-- Critical performance indexes
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON public.credit_transactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_wallet_id ON public.credit_transactions(wallet_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON public.credit_transactions(transaction_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_billing_cycle ON public.credit_transactions(user_id, billing_cycle_date);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_reference ON public.credit_transactions(reference_type, reference_id);

-- Enable RLS
ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own transactions
CREATE POLICY "credit_transactions_user_policy" ON public.credit_transactions
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "credit_transactions_service_policy" ON public.credit_transactions
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 5. UNLOCKED INFLUENCERS TABLE
-- Track which influencers each user has permanently unlocked
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.unlocked_influencers (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    username VARCHAR(100) NOT NULL, -- Denormalized for performance
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    credits_spent INTEGER NOT NULL CHECK (credits_spent > 0),
    transaction_id BIGINT REFERENCES public.credit_transactions(id) ON DELETE SET NULL,
    
    -- Constraints
    UNIQUE(user_id, profile_id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_unlocked_influencers_user_id ON public.unlocked_influencers(user_id);
CREATE INDEX IF NOT EXISTS idx_unlocked_influencers_profile_id ON public.unlocked_influencers(profile_id);
CREATE INDEX IF NOT EXISTS idx_unlocked_influencers_username ON public.unlocked_influencers(user_id, username);

-- Enable RLS
ALTER TABLE public.unlocked_influencers ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own unlocked influencers
CREATE POLICY "unlocked_influencers_user_policy" ON public.unlocked_influencers
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "unlocked_influencers_service_policy" ON public.unlocked_influencers
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 6. CREDIT USAGE TRACKING TABLE
-- Monthly aggregated tracking for performance and analytics
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.credit_usage_tracking (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    month_year DATE NOT NULL, -- First day of the month for grouping
    
    -- Usage counters
    free_actions_used INTEGER DEFAULT 0 NOT NULL CHECK (free_actions_used >= 0),
    paid_actions_used INTEGER DEFAULT 0 NOT NULL CHECK (paid_actions_used >= 0),
    total_credits_spent INTEGER DEFAULT 0 NOT NULL CHECK (total_credits_spent >= 0),
    
    -- Metadata
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Constraints
    UNIQUE(user_id, action_type, month_year)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_credit_usage_user_month ON public.credit_usage_tracking(user_id, month_year DESC);
CREATE INDEX IF NOT EXISTS idx_credit_usage_action_month ON public.credit_usage_tracking(action_type, month_year DESC);

-- Enable RLS
ALTER TABLE public.credit_usage_tracking ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own usage tracking
CREATE POLICY "credit_usage_tracking_user_policy" ON public.credit_usage_tracking
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "credit_usage_tracking_service_policy" ON public.credit_usage_tracking
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 7. CREDIT TOP-UP ORDERS TABLE
-- Track credit purchase orders and payment status
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.credit_top_up_orders (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    wallet_id INTEGER NOT NULL REFERENCES public.credit_wallets(id) ON DELETE CASCADE,
    
    -- Order details
    order_reference VARCHAR(100) NOT NULL UNIQUE,
    credits_amount INTEGER NOT NULL CHECK (credits_amount > 0),
    price_usd_cents INTEGER NOT NULL CHECK (price_usd_cents > 0),
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    
    -- Payment processing
    stripe_payment_intent_id VARCHAR(255),
    payment_status VARCHAR(20) DEFAULT 'pending' NOT NULL CHECK (payment_status IN (
        'pending', 'processing', 'completed', 'failed', 'cancelled', 'refunded'
    )),
    payment_method VARCHAR(50),
    
    -- Fulfillment
    credits_delivered BOOLEAN DEFAULT false NOT NULL,
    delivered_at TIMESTAMP WITH TIME ZONE,
    transaction_id BIGINT REFERENCES public.credit_transactions(id) ON DELETE SET NULL,
    
    -- Failure handling
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    
    -- Metadata
    order_metadata JSONB DEFAULT '{}' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_credit_orders_user_id ON public.credit_top_up_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_orders_status ON public.credit_top_up_orders(payment_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_orders_stripe ON public.credit_top_up_orders(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_credit_orders_reference ON public.credit_top_up_orders(order_reference);

-- Enable RLS
ALTER TABLE public.credit_top_up_orders ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own orders
CREATE POLICY "credit_orders_user_policy" ON public.credit_top_up_orders
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "credit_orders_service_policy" ON public.credit_top_up_orders
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 8. FUNCTIONS FOR CREDIT MANAGEMENT
-- ============================================================================

-- Function to safely update wallet balance
CREATE OR REPLACE FUNCTION public.update_wallet_balance(
    p_wallet_id INTEGER,
    p_amount INTEGER,
    p_transaction_type VARCHAR(20),
    p_description TEXT DEFAULT NULL,
    p_reference_id VARCHAR(255) DEFAULT NULL,
    p_reference_type VARCHAR(50) DEFAULT NULL,
    p_action_type VARCHAR(50) DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_id UUID;
    v_balance_before INTEGER;
    v_balance_after INTEGER;
    v_transaction_id BIGINT;
    v_billing_cycle_date DATE;
BEGIN
    -- Get current wallet info with row lock
    SELECT user_id, current_balance, current_billing_cycle_start
    INTO v_user_id, v_balance_before, v_billing_cycle_date
    FROM public.credit_wallets 
    WHERE id = p_wallet_id
    FOR UPDATE;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Wallet not found: %', p_wallet_id;
    END IF;
    
    -- Calculate new balance
    v_balance_after := v_balance_before + p_amount;
    
    -- Validate balance doesn't go negative
    IF v_balance_after < 0 THEN
        RAISE EXCEPTION 'Insufficient credits. Current: %, Required: %', v_balance_before, ABS(p_amount);
    END IF;
    
    -- Update wallet balance
    UPDATE public.credit_wallets 
    SET 
        current_balance = v_balance_after,
        total_spent_this_cycle = total_spent_this_cycle + CASE WHEN p_amount < 0 THEN ABS(p_amount) ELSE 0 END,
        total_earned_this_cycle = total_earned_this_cycle + CASE WHEN p_transaction_type = 'earn' THEN p_amount ELSE 0 END,
        total_purchased_this_cycle = total_purchased_this_cycle + CASE WHEN p_transaction_type = 'purchase' THEN p_amount ELSE 0 END,
        updated_at = NOW()
    WHERE id = p_wallet_id;
    
    -- Record transaction
    INSERT INTO public.credit_transactions (
        user_id, wallet_id, transaction_type, action_type, amount, 
        balance_before, balance_after, description, reference_id, 
        reference_type, billing_cycle_date
    ) VALUES (
        v_user_id, p_wallet_id, p_transaction_type, p_action_type, p_amount,
        v_balance_before, v_balance_after, p_description, p_reference_id,
        p_reference_type, v_billing_cycle_date
    ) RETURNING id INTO v_transaction_id;
    
    RETURN v_transaction_id;
END;
$$;

-- Function to check if user can perform action (considering free allowances)
CREATE OR REPLACE FUNCTION public.can_perform_credit_action(
    p_user_id UUID,
    p_action_type VARCHAR(50),
    p_required_credits INTEGER DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_wallet_balance INTEGER;
    v_wallet_locked BOOLEAN;
    v_subscription_active BOOLEAN;
    v_free_allowance INTEGER;
    v_free_used INTEGER;
    v_cost_per_action INTEGER;
    v_current_month DATE;
    v_result JSONB;
BEGIN
    v_current_month := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    
    -- Get wallet info
    SELECT current_balance, is_locked, subscription_active
    INTO v_wallet_balance, v_wallet_locked, v_subscription_active
    FROM public.credit_wallets
    WHERE user_id = p_user_id;
    
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'can_perform', false,
            'reason', 'no_wallet',
            'message', 'Credit wallet not found'
        );
    END IF;
    
    -- Check if wallet is locked
    IF v_wallet_locked THEN
        RETURN jsonb_build_object(
            'can_perform', false,
            'reason', 'wallet_locked',
            'message', 'Wallet is locked. Please renew subscription.'
        );
    END IF;
    
    -- Get pricing info
    SELECT cost_per_action, free_allowance_per_month
    INTO v_cost_per_action, v_free_allowance
    FROM public.credit_pricing_rules
    WHERE action_type = p_action_type AND is_active = true;
    
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'can_perform', false,
            'reason', 'unknown_action',
            'message', 'Action type not recognized'
        );
    END IF;
    
    -- Use provided credits or calculated cost
    v_cost_per_action := COALESCE(p_required_credits, v_cost_per_action);
    
    -- Get current month usage
    SELECT COALESCE(free_actions_used, 0)
    INTO v_free_used
    FROM public.credit_usage_tracking
    WHERE user_id = p_user_id 
      AND action_type = p_action_type 
      AND month_year = v_current_month;
    
    v_free_used := COALESCE(v_free_used, 0);
    
    -- Check if free allowance available
    IF v_free_used < v_free_allowance THEN
        RETURN jsonb_build_object(
            'can_perform', true,
            'reason', 'free_allowance',
            'credits_required', 0,
            'free_remaining', v_free_allowance - v_free_used
        );
    END IF;
    
    -- Check if sufficient credits
    IF v_wallet_balance >= v_cost_per_action THEN
        RETURN jsonb_build_object(
            'can_perform', true,
            'reason', 'sufficient_credits',
            'credits_required', v_cost_per_action,
            'wallet_balance', v_wallet_balance
        );
    END IF;
    
    -- Insufficient credits
    RETURN jsonb_build_object(
        'can_perform', false,
        'reason', 'insufficient_credits',
        'credits_required', v_cost_per_action,
        'wallet_balance', v_wallet_balance,
        'credits_needed', v_cost_per_action - v_wallet_balance
    );
END;
$$;

-- ============================================================================
-- SEED DEFAULT DATA
-- ============================================================================

-- Insert default credit packages
INSERT INTO public.credit_packages (name, display_name, monthly_credits, description, sort_order) VALUES
('package_a', 'Package A - Starter', 1000, 'Perfect for small brands and agencies getting started with influencer discovery', 1),
('package_b', 'Package B - Professional', 2500, 'Ideal for growing brands with regular influencer collaboration needs', 2),
('package_enterprise', 'Enterprise', 10000, 'Unlimited access for large brands and agencies', 3)
ON CONFLICT (name) DO NOTHING;

-- Insert default pricing rules
INSERT INTO public.credit_pricing_rules (action_type, display_name, cost_per_action, free_allowance_per_month, description) VALUES
('discovery_pagination', 'Discovery Page View', 10, 5, 'Cost per page beyond free allowance in influencer discovery'),
('influencer_unlock', 'Influencer Analytics Unlock', 25, 0, 'One-time cost to permanently unlock full influencer analytics'),
('post_analytics', 'Campaign Post Analytics', 5, 0, 'Cost per campaign post for detailed analytics tracking'),
('bulk_export', 'Bulk Data Export', 50, 1, 'Cost for exporting influencer data in bulk formats'),
('advanced_search', 'Advanced Search Filters', 15, 10, 'Cost for using premium search filters beyond basic discovery')
ON CONFLICT (action_type) DO NOTHING;

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at triggers
CREATE TRIGGER update_credit_packages_updated_at BEFORE UPDATE ON public.credit_packages
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_credit_wallets_updated_at BEFORE UPDATE ON public.credit_wallets
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_credit_pricing_updated_at BEFORE UPDATE ON public.credit_pricing_rules
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_credit_orders_updated_at BEFORE UPDATE ON public.credit_top_up_orders
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Grant access to authenticated users for their own data
GRANT SELECT, INSERT, UPDATE ON public.credit_wallets TO authenticated;
GRANT SELECT, INSERT ON public.credit_transactions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.unlocked_influencers TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.credit_usage_tracking TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.credit_top_up_orders TO authenticated;
GRANT SELECT ON public.credit_packages TO authenticated;
GRANT SELECT ON public.credit_pricing_rules TO authenticated;

-- Grant sequence access
GRANT USAGE ON SEQUENCE public.credit_wallets_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.credit_transactions_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.unlocked_influencers_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.credit_usage_tracking_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.credit_top_up_orders_id_seq TO authenticated;

-- Grant function execution
GRANT EXECUTE ON FUNCTION public.update_wallet_balance TO authenticated;
GRANT EXECUTE ON FUNCTION public.can_perform_credit_action TO authenticated;

-- Service role gets full access
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

COMMIT;