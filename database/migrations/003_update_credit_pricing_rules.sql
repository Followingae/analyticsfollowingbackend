-- Migration: Update Credit Pricing Rules to New Specifications
-- This updates the pricing rules to match the new credit system requirements

BEGIN;

-- 1. Delete old pricing rules
DELETE FROM credit_pricing_rules;

-- 2. Insert new simplified pricing rules
INSERT INTO credit_pricing_rules (action_type, display_name, cost_per_action, free_allowance_per_month, description, is_active, created_at, updated_at) VALUES
('discovery', 'Discovery', 1, 50, 'Browse profiles and discovery pages - very minimal cost to encourage exploration', true, NOW(), NOW()),
('profile_analysis', 'Profile Analysis', 25, 2, 'Complete profile analysis including AI insights, detailed analytics, influencer unlock, and posts viewing', true, NOW(), NOW()),
('posts_analytics', 'Posts Analytics', 10, 5, 'Campaign-specific individual post URL analysis for detailed campaign insights', true, NOW(), NOW());

-- 3. Update any existing transactions to use new action types (if needed)
-- Note: This is safe to run even if no old transactions exist

-- Map old action types to new ones in credit_transactions
UPDATE credit_transactions 
SET action_type = 'profile_analysis' 
WHERE action_type IN ('detailed_analytics', 'ai_insights', 'influencer_unlock');

UPDATE credit_transactions 
SET action_type = 'posts_analytics' 
WHERE action_type = 'profile_posts';

-- 4. Update any existing usage tracking to use new action types
UPDATE credit_usage_tracking 
SET action_type = 'profile_analysis' 
WHERE action_type IN ('detailed_analytics', 'ai_insights', 'influencer_unlock');

UPDATE credit_usage_tracking 
SET action_type = 'posts_analytics' 
WHERE action_type = 'profile_posts';

-- 5. Clean up any duplicate usage tracking records that might have been created
DELETE FROM credit_usage_tracking a
USING credit_usage_tracking b 
WHERE a.id > b.id 
  AND a.user_id = b.user_id 
  AND a.action_type = b.action_type 
  AND DATE_TRUNC('month', a.month_year) = DATE_TRUNC('month', b.month_year);

COMMIT;

-- Verification queries (for manual checking)
-- SELECT * FROM credit_pricing_rules ORDER BY action_type;
-- SELECT action_type, COUNT(*) FROM credit_transactions GROUP BY action_type;
-- SELECT action_type, COUNT(*) FROM credit_usage_tracking GROUP BY action_type;