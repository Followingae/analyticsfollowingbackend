-- ============================================================================
-- ADD LIFETIME COLUMNS TO CREDIT WALLETS
-- Adds missing lifetime_earned and lifetime_spent columns
-- Updates existing billing cycle column names to match code expectations
-- ============================================================================

-- Add missing lifetime tracking columns
ALTER TABLE public.credit_wallets 
ADD COLUMN IF NOT EXISTS lifetime_earned INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN IF NOT EXISTS lifetime_spent INTEGER DEFAULT 0 NOT NULL;

-- Rename billing cycle columns to match code expectations
DO $$
BEGIN
    -- Check if old column exists and new doesn't
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'credit_wallets' AND column_name = 'billing_cycle_start')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'credit_wallets' AND column_name = 'current_billing_cycle_start') THEN
        ALTER TABLE public.credit_wallets 
        RENAME COLUMN billing_cycle_start TO current_billing_cycle_start;
    END IF;
    
    -- Add missing billing cycle columns if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'current_billing_cycle_start') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN current_billing_cycle_start TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'current_billing_cycle_end') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN current_billing_cycle_end TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '1 month');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'next_credit_refresh_date') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN next_credit_refresh_date TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '1 month');
    END IF;
    
    -- Add subscription status columns if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'subscription_status') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN subscription_status VARCHAR(30) DEFAULT 'active' NOT NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'auto_refresh_enabled') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN auto_refresh_enabled BOOLEAN DEFAULT true NOT NULL;
    END IF;
    
    -- Add freeze management columns if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'is_frozen') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN is_frozen BOOLEAN DEFAULT false NOT NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'freeze_reason') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN freeze_reason TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'credit_wallets' AND column_name = 'last_activity_at') THEN
        ALTER TABLE public.credit_wallets 
        ADD COLUMN last_activity_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_credit_wallets_lifetime_spent ON public.credit_wallets(lifetime_spent) WHERE lifetime_spent > 0;
CREATE INDEX IF NOT EXISTS idx_credit_wallets_frozen ON public.credit_wallets(is_frozen) WHERE is_frozen = true;
CREATE INDEX IF NOT EXISTS idx_credit_wallets_subscription_status ON public.credit_wallets(subscription_status);

-- Update existing wallets to have proper billing cycle dates if null
UPDATE public.credit_wallets 
SET 
    current_billing_cycle_start = COALESCE(current_billing_cycle_start, created_at),
    current_billing_cycle_end = COALESCE(current_billing_cycle_end, created_at + INTERVAL '1 month'),
    next_credit_refresh_date = COALESCE(next_credit_refresh_date, created_at + INTERVAL '1 month')
WHERE current_billing_cycle_start IS NULL 
   OR current_billing_cycle_end IS NULL 
   OR next_credit_refresh_date IS NULL;