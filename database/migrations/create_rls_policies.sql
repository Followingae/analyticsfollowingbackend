-- Create Row Level Security policies for user-specific data access
-- These policies ensure users can only access their own data

-- =============================================================================
-- USERS TABLE POLICIES
-- =============================================================================

-- Users can only see and modify their own record
CREATE POLICY "users_own_data" ON public.users
    FOR ALL USING (auth.uid()::text = supabase_user_id);

-- =============================================================================
-- USER_PROFILES TABLE POLICIES  
-- =============================================================================

-- Users can only access their own profile
CREATE POLICY "user_profiles_own_data" ON public.user_profiles
    FOR ALL USING (auth.uid() = user_id);

-- =============================================================================
-- USER_PROFILE_ACCESS TABLE POLICIES
-- =============================================================================

-- Users can only see their own profile access records
CREATE POLICY "user_profile_access_own_data" ON public.user_profile_access
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_profile_access.user_id
        )
    );

-- =============================================================================
-- USER_FAVORITES TABLE POLICIES
-- =============================================================================

-- Users can only access their own favorites
CREATE POLICY "user_favorites_own_data" ON public.user_favorites
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_favorites.user_id
        )
    );

-- =============================================================================
-- USER_SEARCHES TABLE POLICIES
-- =============================================================================

-- Users can only access their own search history
CREATE POLICY "user_searches_own_data" ON public.user_searches
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_searches.user_id
        )
    );

-- =============================================================================
-- SEARCH_HISTORY TABLE POLICIES
-- =============================================================================

-- Users can only access their own search history
CREATE POLICY "search_history_own_data" ON public.search_history
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = search_history.user_id
        )
    );

-- =============================================================================
-- CAMPAIGNS TABLE POLICIES
-- =============================================================================

-- Users can only access their own campaigns
CREATE POLICY "campaigns_own_data" ON public.campaigns
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = campaigns.user_id
        )
    );

-- =============================================================================
-- CAMPAIGN_POSTS TABLE POLICIES
-- =============================================================================

-- Users can only access posts from their own campaigns
CREATE POLICY "campaign_posts_own_data" ON public.campaign_posts
    FOR ALL USING (
        campaign_id IN (
            SELECT c.id FROM public.campaigns c
            JOIN public.users pu ON c.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        )
    );

-- =============================================================================
-- CAMPAIGN_PROFILES TABLE POLICIES
-- =============================================================================

-- Users can only access profiles from their own campaigns
CREATE POLICY "campaign_profiles_own_data" ON public.campaign_profiles
    FOR ALL USING (
        campaign_id IN (
            SELECT c.id FROM public.campaigns c
            JOIN public.users pu ON c.user_id = pu.id
            JOIN auth.users u ON u.id::text = pu.supabase_user_id
            WHERE u.id = auth.uid()
        )
    );