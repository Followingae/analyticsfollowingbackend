-- Add avatar_config column to users table for BoringAvatars configuration
-- This stores the user's selected avatar configuration as JSON

ALTER TABLE users ADD COLUMN avatar_config JSONB;

-- Add comment for documentation
COMMENT ON COLUMN users.avatar_config IS 'Stores BoringAvatars configuration (variant, colorScheme, colors, seed) as JSON';

-- Example data structure:
-- {
--   "variant": "beam",
--   "colorScheme": "Brand Primary", 
--   "colors": ["#d3ff02", "#5100f3", "#c9a7f9", "#0a1221"],
--   "seed": "randomSeed123-beam-1"
-- }