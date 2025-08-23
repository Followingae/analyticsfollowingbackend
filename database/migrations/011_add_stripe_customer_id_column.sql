-- Add missing stripe_customer_id column to users table
-- Migration: 011_add_stripe_customer_id_column.sql
-- Date: 2025-08-23

DO $$
BEGIN
    -- Add stripe_customer_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' 
        AND column_name='stripe_customer_id'
    ) THEN
        ALTER TABLE public.users ADD COLUMN stripe_customer_id TEXT;
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_stripe_customer_id ON public.users(stripe_customer_id);
    END IF;
END $$;

-- Verify the column was added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name = 'stripe_customer_id';