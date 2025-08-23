-- Create missing database functions
-- Migration: 012_create_missing_functions.sql
-- Date: 2025-08-23

-- Add missing stripe_customer_id column to users table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' 
        AND column_name='stripe_customer_id'
    ) THEN
        ALTER TABLE public.users ADD COLUMN stripe_customer_id TEXT;
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_stripe_customer_id ON public.users(stripe_customer_id);
        RAISE NOTICE 'Added stripe_customer_id column to users table';
    ELSE
        RAISE NOTICE 'stripe_customer_id column already exists';
    END IF;
END $$;

-- Create the missing calculate_total_plan_credits function
CREATE OR REPLACE FUNCTION public.calculate_total_plan_credits(user_uuid UUID)
RETURNS TABLE(
    total_plan_credits INTEGER,
    lifetime_credits_earned INTEGER,
    lifetime_credits_spent INTEGER,
    current_month_earned INTEGER,
    current_month_spent INTEGER
) AS $$
DECLARE
    current_month_start DATE;
BEGIN
    -- Get current month start
    current_month_start := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    
    RETURN QUERY
    SELECT 
        COALESCE(cw.current_balance, 0) as total_plan_credits,
        COALESCE(cw.total_earned, 0) as lifetime_credits_earned,
        COALESCE(cw.total_spent, 0) as lifetime_credits_spent,
        COALESCE(
            (SELECT SUM(credit_amount) 
             FROM public.credit_transactions ct 
             WHERE ct.user_id = user_uuid 
             AND ct.transaction_type = 'earn'
             AND DATE_TRUNC('month', ct.created_at)::DATE = current_month_start), 0
        ) as current_month_earned,
        COALESCE(
            (SELECT SUM(ABS(credit_amount)) 
             FROM public.credit_transactions ct 
             WHERE ct.user_id = user_uuid 
             AND ct.transaction_type = 'spend'
             AND DATE_TRUNC('month', ct.created_at)::DATE = current_month_start), 0
        ) as current_month_spent
    FROM public.credit_wallets cw
    WHERE cw.user_id = user_uuid
    LIMIT 1;
    
    -- If no wallet exists, return zeros
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT 0, 0, 0, 0, 0;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.calculate_total_plan_credits(UUID) TO postgres;
GRANT EXECUTE ON FUNCTION public.calculate_total_plan_credits(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.calculate_total_plan_credits(UUID) TO service_role;

-- Test the function
SELECT 'Function created successfully' as status;