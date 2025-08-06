-- Remove profile_picture_url column from users table
-- This is no longer needed as we're using BoringAvatars with avatar_config

ALTER TABLE users DROP COLUMN IF EXISTS profile_picture_url;

-- Add comment for documentation
COMMENT ON TABLE users IS 'Users table updated to use avatar_config instead of profile_picture_url for avatar management';