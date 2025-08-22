-- ADD TOTAL PLAN CREDITS TRACKING
-- Analytics Following Backend - Enhanced Credit System
-- Implementation Date: August 22, 2025

-- =============================================================================
-- ENHANCE CREDIT_WALLETS TABLE FOR TOTAL PLAN CREDITS CALCULATION
-- =============================================================================

-- Add new columns to track different types of credits separately
ALTER TABLE credit_wallets ADD COLUMN IF NOT EXISTS 
    package_credits_balance INTEGER DEFAULT 0 NOT NULL;

ALTER TABLE credit_wallets ADD COLUMN IF NOT EXISTS 
    purchased_credits_balance INTEGER DEFAULT 0 NOT NULL;

ALTER TABLE credit_wallets ADD COLUMN IF NOT EXISTS 
    bonus_credits_balance INTEGER DEFAULT 0 NOT NULL;

-- Add helpful tracking columns
ALTER TABLE credit_wallets ADD COLUMN IF NOT EXISTS 
    total_credits_received_lifetime INTEGER DEFAULT 0 NOT NULL;

ALTER TABLE credit_wallets ADD COLUMN IF NOT EXISTS 
    last_package_refresh_date DATE;

-- =============================================================================
-- UPDATE CREDIT_PACKAGES TABLE FOR MONTHLY CREDITS TRACKING
-- =============================================================================

-- Ensure credit_packages has monthly_credits column
ALTER TABLE credit_packages ADD COLUMN IF NOT EXISTS 
    monthly_credits INTEGER DEFAULT 0 NOT NULL;

-- =============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

-- Index for fast wallet lookups with package info
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_credit_wallets_package_user 
ON credit_wallets(user_id, package_id);

-- Index for package credits queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_credit_packages_monthly 
ON credit_packages(monthly_credits DESC);

-- =============================================================================
-- UPDATE EXISTING WALLETS TO REFLECT CURRENT BALANCE BREAKDOWN
-- =============================================================================

-- Transfer current_balance to appropriate category
-- Assume existing balances are package credits for now
UPDATE credit_wallets 
SET package_credits_balance = current_balance,
    total_credits_received_lifetime = current_balance
WHERE package_credits_balance = 0 AND current_balance > 0;

-- =============================================================================
-- CREATE DATABASE FUNCTION FOR CALCULATING TOTAL PLAN CREDITS
-- =============================================================================

CREATE OR REPLACE FUNCTION calculate_total_plan_credits(user_uuid UUID)
RETURNS TABLE(
    total_plan_credits INTEGER,
    package_credits INTEGER,
    purchased_credits INTEGER,
    bonus_credits INTEGER,
    monthly_allowance INTEGER,
    package_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (cw.package_credits_balance + cw.purchased_credits_balance + cw.bonus_credits_balance) as total_plan_credits,
        cw.package_credits_balance as package_credits,
        cw.purchased_credits_balance as purchased_credits,
        cw.bonus_credits_balance as bonus_credits,
        COALESCE(cp.monthly_credits, 0) as monthly_allowance,
        COALESCE(cp.display_name, 'No Package') as package_name
    FROM credit_wallets cw
    LEFT JOIN credit_packages cp ON cw.package_id = cp.id
    WHERE cw.user_id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- CREATE FUNCTION FOR UPDATING TOTAL PLAN CREDITS BREAKDOWN
-- =============================================================================

CREATE OR REPLACE FUNCTION update_wallet_credits_breakdown(
    user_uuid UUID,
    new_package_credits INTEGER DEFAULT NULL,
    new_purchased_credits INTEGER DEFAULT NULL,
    new_bonus_credits INTEGER DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    wallet_exists BOOLEAN;
    new_total INTEGER;
BEGIN
    -- Check if wallet exists
    SELECT EXISTS(SELECT 1 FROM credit_wallets WHERE user_id = user_uuid) INTO wallet_exists;
    
    IF NOT wallet_exists THEN
        RAISE EXCEPTION 'Credit wallet not found for user %', user_uuid;
    END IF;
    
    -- Update only provided values
    UPDATE credit_wallets 
    SET 
        package_credits_balance = COALESCE(new_package_credits, package_credits_balance),
        purchased_credits_balance = COALESCE(new_purchased_credits, purchased_credits_balance),
        bonus_credits_balance = COALESCE(new_bonus_credits, bonus_credits_balance),
        updated_at = NOW()
    WHERE user_id = user_uuid;
    
    -- Calculate new total balance
    SELECT (package_credits_balance + purchased_credits_balance + bonus_credits_balance)
    INTO new_total
    FROM credit_wallets
    WHERE user_id = user_uuid;
    
    -- Update current_balance to match total
    UPDATE credit_wallets 
    SET current_balance = new_total
    WHERE user_id = user_uuid;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- CREATE ROW LEVEL SECURITY POLICIES
-- =============================================================================

-- Enable RLS on credit_wallets if not already enabled
ALTER TABLE credit_wallets ENABLE ROW LEVEL SECURITY;

-- Policy for users to access their own wallet breakdown
CREATE POLICY IF NOT EXISTS "Users can view their own wallet breakdown" ON credit_wallets
    FOR SELECT USING (user_id = (SELECT auth.uid()));

-- Policy for service role to manage all wallets
CREATE POLICY IF NOT EXISTS "Service role can manage all wallets" ON credit_wallets
    FOR ALL USING (auth.role() = 'service_role');

-- =============================================================================
-- ADD HELPFUL COMMENTS
-- =============================================================================

COMMENT ON COLUMN credit_wallets.package_credits_balance IS 'Credits from monthly package allowance';
COMMENT ON COLUMN credit_wallets.purchased_credits_balance IS 'Credits purchased via Stripe/payments';
COMMENT ON COLUMN credit_wallets.bonus_credits_balance IS 'Promotional/referral bonus credits';
COMMENT ON COLUMN credit_wallets.total_credits_received_lifetime IS 'Total credits ever added to wallet';
COMMENT ON COLUMN credit_wallets.last_package_refresh_date IS 'Date when package credits were last refreshed';

COMMENT ON FUNCTION calculate_total_plan_credits(UUID) IS 'Calculate total plan credits breakdown for a user';
COMMENT ON FUNCTION update_wallet_credits_breakdown(UUID, INTEGER, INTEGER, INTEGER) IS 'Update wallet credits breakdown maintaining consistency';