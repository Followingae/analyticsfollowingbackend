-- Enable Row Level Security on all user-specific tables
-- This migration secures your database by ensuring users can only access their own data

-- =============================================================================
-- ENABLE RLS ON USER-SPECIFIC TABLES
-- =============================================================================

-- User management tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profile_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;

-- Campaign management tables
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_profiles ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- KEEP PUBLIC DATA TABLES UNRESTRICTED (for now)
-- =============================================================================
-- These tables contain Instagram data that may be shared across users:
-- - profiles (Instagram profiles can be viewed by multiple users)
-- - posts (Instagram posts can be viewed by multiple users)
-- - audience_demographics (derived from public Instagram data)
-- - creator_metadata (enhanced analytics, potentially shareable)
-- - comment_sentiment (post analysis, potentially shareable)
-- - mentions (profile mentions, potentially shareable)
-- - related_profiles (profile suggestions, potentially shareable)
-- - auth_users (managed by Supabase auth)

-- Note: You can enable RLS on these later if you want to restrict access
-- ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.audience_demographics ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.creator_metadata ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.comment_sentiment ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.mentions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.related_profiles ENABLE ROW LEVEL SECURITY;