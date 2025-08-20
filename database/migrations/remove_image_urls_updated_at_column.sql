-- Migration: Remove image_urls_updated_at column from profiles table
-- Date: 2025-08-20
-- Purpose: Remove URL staleness tracking system - Instagram URLs don't expire every 5 days

-- Remove the column and its index
DROP INDEX IF EXISTS idx_profiles_image_urls_updated_at;
ALTER TABLE profiles DROP COLUMN IF EXISTS image_urls_updated_at;

-- Verification query (optional - run to confirm column is removed)
-- SELECT column_name 
-- FROM information_schema.columns 
-- WHERE table_name = 'profiles' AND column_name = 'image_urls_updated_at';
-- Should return 0 rows if successful