-- Migration: Add Stripe Customer ID to users table
-- Date: 2025-01-23
-- Description: Add stripe_customer_id field to users table for Stripe integration

-- Add stripe_customer_id column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

-- Add unique constraint and index for performance
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS users_stripe_customer_id_unique UNIQUE (stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN users.stripe_customer_id IS 'Stripe customer ID for subscription billing and Customer Portal access';