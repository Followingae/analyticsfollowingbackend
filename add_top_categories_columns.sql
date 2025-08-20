-- Add top 3 and top 10 categories columns to profiles table
-- This migration adds the new JSONB columns for storing top categories

BEGIN;

-- Add the new columns
ALTER TABLE profiles 
ADD COLUMN ai_top_3_categories JSONB NULL,
ADD COLUMN ai_top_10_categories JSONB NULL;

-- Add indexes for performance (optional but recommended)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_ai_top_3_categories 
ON profiles USING GIN(ai_top_3_categories);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_ai_top_10_categories 
ON profiles USING GIN(ai_top_10_categories);

-- Add comments to document the columns
COMMENT ON COLUMN profiles.ai_top_3_categories IS 'Top 3 content categories for creator - used for main badges display';
COMMENT ON COLUMN profiles.ai_top_10_categories IS 'Top 10 content categories for creator - used for detailed breakdown charts';

COMMIT;