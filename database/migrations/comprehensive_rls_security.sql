-- COMPREHENSIVE ROW LEVEL SECURITY MIGRATION
-- Enables RLS on ALL tables with proper access control policies
-- This addresses Supabase security advisor warnings and implements proper multi-tenant isolation

-- =============================================================================
-- ENABLE RLS ON ALL TABLES
-- =============================================================================

-- Auth and User Management Tables
ALTER TABLE public.auth_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profile_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;

-- Campaign Management Tables
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_profiles ENABLE ROW LEVEL SECURITY;

-- Instagram Data Tables (previously public, now secured)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audience_demographics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.creator_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comment_sentiment ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mentions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.related_profiles ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- DROP EXISTING POLICIES (if any) TO AVOID CONFLICTS
-- =============================================================================

-- User-specific table policies
DROP POLICY IF EXISTS "users_own_data" ON public.users;
DROP POLICY IF EXISTS "user_profiles_own_data" ON public.user_profiles;
DROP POLICY IF EXISTS "user_profile_access_own_data" ON public.user_profile_access;
DROP POLICY IF EXISTS "user_favorites_own_data" ON public.user_favorites;
DROP POLICY IF EXISTS "user_searches_own_data" ON public.user_searches;
DROP POLICY IF EXISTS "search_history_own_data" ON public.search_history;
DROP POLICY IF EXISTS "campaigns_own_data" ON public.campaigns;
DROP POLICY IF EXISTS "campaign_posts_own_data" ON public.campaign_posts;
DROP POLICY IF EXISTS "campaign_profiles_own_data" ON public.campaign_profiles;

-- Auth users table policies
DROP POLICY IF EXISTS "auth_users_own_data" ON public.auth_users;

-- Instagram data table policies (comprehensive access policies)
DROP POLICY IF EXISTS "profiles_comprehensive_access" ON public.profiles;
DROP POLICY IF EXISTS "posts_comprehensive_access" ON public.posts;
DROP POLICY IF EXISTS "audience_demographics_comprehensive_access" ON public.audience_demographics;
DROP POLICY IF EXISTS "creator_metadata_comprehensive_access" ON public.creator_metadata;
DROP POLICY IF EXISTS "comment_sentiment_comprehensive_access" ON public.comment_sentiment;
DROP POLICY IF EXISTS "mentions_comprehensive_access" ON public.mentions;
DROP POLICY IF EXISTS "related_profiles_comprehensive_access" ON public.related_profiles;

-- Legacy Instagram data table policies (in case they exist)
DROP POLICY IF EXISTS "profiles_user_access_control" ON public.profiles;
DROP POLICY IF EXISTS "profiles_service_write" ON public.profiles;
DROP POLICY IF EXISTS "posts_user_access_control" ON public.posts;
DROP POLICY IF EXISTS "posts_service_write" ON public.posts;
DROP POLICY IF EXISTS "audience_demographics_user_access_control" ON public.audience_demographics;
DROP POLICY IF EXISTS "audience_demographics_service_write" ON public.audience_demographics;
DROP POLICY IF EXISTS "creator_metadata_user_access_control" ON public.creator_metadata;
DROP POLICY IF EXISTS "creator_metadata_service_write" ON public.creator_metadata;
DROP POLICY IF EXISTS "comment_sentiment_user_access_control" ON public.comment_sentiment;
DROP POLICY IF EXISTS "comment_sentiment_service_write" ON public.comment_sentiment;
DROP POLICY IF EXISTS "mentions_user_access_control" ON public.mentions;
DROP POLICY IF EXISTS "mentions_service_write" ON public.mentions;
DROP POLICY IF EXISTS "related_profiles_user_access_control" ON public.related_profiles;
DROP POLICY IF EXISTS "related_profiles_service_write" ON public.related_profiles;

-- =============================================================================
-- AUTH_USERS TABLE POLICIES (Public schema bridge table)
-- =============================================================================

-- Users can only see and modify their own auth_users record
CREATE POLICY "auth_users_own_data" ON public.auth_users
    FOR ALL USING (auth.uid() = id);

-- =============================================================================
-- USER MANAGEMENT TABLE POLICIES
-- =============================================================================

-- Users table: Users can only access their own record
CREATE POLICY "users_own_data" ON public.users
    FOR ALL USING (auth.uid()::text = supabase_user_id);

-- User profiles: Users can only access their own profile
CREATE POLICY "user_profiles_own_data" ON public.user_profiles
    FOR ALL USING (auth.uid() = user_id);

-- User profile access: Users can only see their own access records
CREATE POLICY "user_profile_access_own_data" ON public.user_profile_access
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_profile_access.user_id
        )
    );

-- User favorites: Users can only access their own favorites
CREATE POLICY "user_favorites_own_data" ON public.user_favorites
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_favorites.user_id
        )
    );

-- User searches: Users can only access their own search history
CREATE POLICY "user_searches_own_data" ON public.user_searches
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_searches.user_id
        )
    );

-- Search history: Users can only access their own search history
CREATE POLICY "search_history_own_data" ON public.search_history
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = search_history.user_id
        )
    );

-- =============================================================================
-- CAMPAIGN MANAGEMENT TABLE POLICIES
-- =============================================================================

-- Campaigns: Users can only access their own campaigns
CREATE POLICY "campaigns_own_data" ON public.campaigns
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = campaigns.user_id
        )
    );

-- Campaign posts: Users can only access posts from their own campaigns
CREATE POLICY "campaign_posts_own_data" ON public.campaign_posts
    FOR ALL USING (
        campaign_id IN (
            SELECT c.id FROM public.campaigns c
            JOIN public.users pu ON c.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        )
    );

-- Campaign profiles: Users can only access profiles from their own campaigns
CREATE POLICY "campaign_profiles_own_data" ON public.campaign_profiles
    FOR ALL USING (
        campaign_id IN (
            SELECT c.id FROM public.campaigns c
            JOIN public.users pu ON c.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        )
    );

-- =============================================================================
-- INSTAGRAM DATA TABLE POLICIES (SECURED WITH USER ACCESS CONTROL)
-- =============================================================================

-- Profiles: Comprehensive access control - users can read their accessible profiles, service role can do everything
CREATE POLICY "profiles_comprehensive_access" ON public.profiles
    FOR ALL USING (
        -- Allow service role full access for backend operations
        auth.role() = 'service_role'
        OR
        -- Allow users to SELECT profiles they have accessed (tracked in user_profile_access)
        (auth.role() = 'authenticated' AND id IN (
            SELECT upa.profile_id 
            FROM public.user_profile_access upa
            JOIN public.users pu ON upa.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- Posts: Comprehensive access control - users can read posts from their accessible profiles, service role can do everything
CREATE POLICY "posts_comprehensive_access" ON public.posts
    FOR ALL USING (
        -- Allow service role full access for backend operations
        auth.role() = 'service_role'
        OR
        -- Allow users to SELECT posts from profiles they have accessed
        (auth.role() = 'authenticated' AND profile_id IN (
            SELECT upa.profile_id 
            FROM public.user_profile_access upa
            JOIN public.users pu ON upa.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- Audience Demographics: Comprehensive access control
CREATE POLICY "audience_demographics_comprehensive_access" ON public.audience_demographics
    FOR ALL USING (
        auth.role() = 'service_role'
        OR
        (auth.role() = 'authenticated' AND profile_id IN (
            SELECT upa.profile_id 
            FROM public.user_profile_access upa
            JOIN public.users pu ON upa.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- Creator Metadata: Comprehensive access control
CREATE POLICY "creator_metadata_comprehensive_access" ON public.creator_metadata
    FOR ALL USING (
        auth.role() = 'service_role'
        OR
        (auth.role() = 'authenticated' AND profile_id IN (
            SELECT upa.profile_id 
            FROM public.user_profile_access upa
            JOIN public.users pu ON upa.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- Comment Sentiment: Comprehensive access control
CREATE POLICY "comment_sentiment_comprehensive_access" ON public.comment_sentiment
    FOR ALL USING (
        auth.role() = 'service_role'
        OR
        (auth.role() = 'authenticated' AND post_id IN (
            SELECT p.id FROM public.posts p
            WHERE p.profile_id IN (
                SELECT upa.profile_id 
                FROM public.user_profile_access upa
                JOIN public.users pu ON upa.user_id = pu.id
                JOIN auth.users u ON u.id::text = pu.supabase_user_id
                WHERE u.id = auth.uid()
            )
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- Mentions: Comprehensive access control
CREATE POLICY "mentions_comprehensive_access" ON public.mentions
    FOR ALL USING (
        auth.role() = 'service_role'
        OR
        (auth.role() = 'authenticated' AND profile_id IN (
            SELECT upa.profile_id 
            FROM public.user_profile_access upa
            JOIN public.users pu ON upa.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- Related Profiles: Comprehensive access control
CREATE POLICY "related_profiles_comprehensive_access" ON public.related_profiles
    FOR ALL USING (
        auth.role() = 'service_role'
        OR
        (auth.role() = 'authenticated' AND profile_id IN (
            SELECT upa.profile_id 
            FROM public.user_profile_access upa
            JOIN public.users pu ON upa.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        ))
    ) WITH CHECK (auth.role() = 'service_role');

-- =============================================================================
-- SECURITY SUMMARY
-- =============================================================================

/*
This migration implements comprehensive Row Level Security with the following approach:

1. **True Multi-Tenant Isolation**: 
   - Each user can only access their own data in user-specific tables
   - Users can only see Instagram data for profiles they have explicitly accessed

2. **Instagram Data Access Control**:
   - Users can only view Instagram profiles/posts/analytics they have searched for
   - Backend API (service_role) has full access for data operations
   - Access is tracked via user_profile_access table

3. **Security Benefits**:
   - Prevents data leakage between users
   - Maintains sharing functionality within user boundaries  
   - Addresses all Supabase security advisor warnings
   - Proper isolation for GDPR/privacy compliance

4. **Operational Benefits**:
   - Backend API retains full control via service_role
   - Efficient caching still possible within user context
   - User access tracking enables proper billing/limits

This approach balances security with functionality - users can still access
shared Instagram data, but only for profiles they have legitimate access to
through their own searches and profile analysis activities.
*/