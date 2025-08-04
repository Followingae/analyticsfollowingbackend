-- OPTIONAL: Enable RLS on public Instagram data tables
-- Run this migration only if you want to restrict access to Instagram data
-- Currently these tables are left unrestricted for data sharing across users

-- =============================================================================
-- ENABLE RLS ON INSTAGRAM DATA TABLES (OPTIONAL)
-- =============================================================================

-- Uncomment these lines if you want to enable RLS on Instagram data tables:

-- ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.audience_demographics ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.creator_metadata ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.comment_sentiment ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.mentions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.related_profiles ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- INSTAGRAM DATA POLICIES (OPTIONAL)
-- =============================================================================

-- Option 1: Allow all authenticated users to read Instagram data
-- CREATE POLICY "profiles_authenticated_read" ON public.profiles
--     FOR SELECT USING (auth.role() = 'authenticated');

-- CREATE POLICY "posts_authenticated_read" ON public.posts
--     FOR SELECT USING (auth.role() = 'authenticated');

-- CREATE POLICY "audience_demographics_authenticated_read" ON public.audience_demographics
--     FOR SELECT USING (auth.role() = 'authenticated');

-- CREATE POLICY "creator_metadata_authenticated_read" ON public.creator_metadata
--     FOR SELECT USING (auth.role() = 'authenticated');

-- CREATE POLICY "comment_sentiment_authenticated_read" ON public.comment_sentiment
--     FOR SELECT USING (auth.role() = 'authenticated');

-- CREATE POLICY "mentions_authenticated_read" ON public.mentions
--     FOR SELECT USING (auth.role() = 'authenticated');

-- CREATE POLICY "related_profiles_authenticated_read" ON public.related_profiles
--     FOR SELECT USING (auth.role() = 'authenticated');

-- Option 2: Only allow writes through service role (backend API)
-- CREATE POLICY "profiles_service_write" ON public.profiles
--     FOR INSERT, UPDATE, DELETE USING (auth.role() = 'service_role');

-- CREATE POLICY "posts_service_write" ON public.posts
--     FOR INSERT, UPDATE, DELETE USING (auth.role() = 'service_role');

-- And so on for other tables...

-- =============================================================================
-- RECOMMENDED APPROACH
-- =============================================================================
-- 
-- For Instagram analytics platform, consider this hybrid approach:
-- 1. Keep Instagram data tables (profiles, posts, etc.) PUBLIC for sharing
-- 2. Use application-level access control in your backend API
-- 3. Track user access via user_profile_access table
-- 4. Only restrict user-specific tables (favorites, searches, campaigns)
--
-- This allows:
-- - Multiple users to view the same Instagram profiles/posts
-- - Efficient data sharing and caching
-- - User-specific features (favorites, campaigns) remain private
-- - Backend API maintains full control over data access