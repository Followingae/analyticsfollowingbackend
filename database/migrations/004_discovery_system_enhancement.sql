-- Migration: Discovery System Enhancement
-- Implements credit-gated discovery with advanced filtering and profile unlocking

BEGIN;

-- ============================================================================
-- 1. ENHANCE PROFILES TABLE FOR DISCOVERY
-- Add discovery metadata and pricing information
-- ============================================================================

-- Add discovery and pricing columns to existing profiles table
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS discovery_visible BOOLEAN DEFAULT true;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS blacklisted BOOLEAN DEFAULT false;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS inactive BOOLEAN DEFAULT false;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS cost_price_usd INTEGER DEFAULT 0; -- Internal pricing (superadmin)
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS sell_price_usd INTEGER DEFAULT 0; -- Brand-facing pricing
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS access_level VARCHAR(20) DEFAULT 'public'; -- public, premium, restricted
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS categories JSONB DEFAULT '[]'::jsonb; -- ["Fashion", "Travel", "Tech"]
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS languages JSONB DEFAULT '[]'::jsonb; -- ["en", "ar", "fr"]
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS barter_eligible BOOLEAN DEFAULT false;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS min_collaboration_fee INTEGER; -- Minimum fee for collaborations

-- Add indexes for discovery filtering
CREATE INDEX IF NOT EXISTS idx_profiles_discovery_visible ON profiles(discovery_visible) WHERE discovery_visible = true;
CREATE INDEX IF NOT EXISTS idx_profiles_blacklisted ON profiles(blacklisted);
CREATE INDEX IF NOT EXISTS idx_profiles_inactive ON profiles(inactive);
CREATE INDEX IF NOT EXISTS idx_profiles_access_level ON profiles(access_level);
CREATE INDEX IF NOT EXISTS idx_profiles_categories ON profiles USING GIN(categories);
CREATE INDEX IF NOT EXISTS idx_profiles_languages ON profiles USING GIN(languages);
CREATE INDEX IF NOT EXISTS idx_profiles_followers ON profiles(followers_count) WHERE followers_count IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_engagement ON profiles(engagement_rate) WHERE engagement_rate IS NOT NULL;

-- ============================================================================
-- 2. DISCOVERY SESSIONS TABLE
-- Track paginated discovery searches and credit consumption
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.discovery_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Search metadata
    search_criteria JSONB NOT NULL DEFAULT '{}'::jsonb, -- Filters used in search
    total_results INTEGER DEFAULT 0,
    pages_viewed INTEGER DEFAULT 1,
    results_per_page INTEGER DEFAULT 20,
    
    -- Credit tracking
    credits_consumed INTEGER DEFAULT 0,
    free_pages_used INTEGER DEFAULT 0, -- First 3 pages are free
    
    -- Session timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '2 hours') NOT NULL,
    
    -- Search performance
    search_duration_ms INTEGER,
    data_source VARCHAR(50) DEFAULT 'database' -- database, cache, api
);

-- Performance indexes for discovery sessions
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_user ON discovery_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_expires ON discovery_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_active ON discovery_sessions(user_id, expires_at);

-- Enable RLS
ALTER TABLE discovery_sessions ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "discovery_sessions_user_policy" ON discovery_sessions
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "discovery_sessions_service_policy" ON discovery_sessions
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 3. SAVED DISCOVERY FILTERS TABLE
-- Allow users to save and reuse complex filter combinations
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.discovery_filters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Filter metadata
    filter_name VARCHAR(200) NOT NULL,
    description TEXT,
    filter_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_discovery_filters_user ON discovery_filters(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_filters_name ON discovery_filters(user_id, filter_name);

-- Enable RLS
ALTER TABLE discovery_filters ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "discovery_filters_user_policy" ON discovery_filters
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "discovery_filters_service_policy" ON discovery_filters
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 4. UNLOCKED PROFILES TABLE
-- Track which profiles each user has unlocked with credits
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.unlocked_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Unlock details
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    credits_spent INTEGER NOT NULL CHECK (credits_spent >= 0),
    unlock_type VARCHAR(50) DEFAULT 'profile_analysis', -- profile_analysis, discovery_unlock
    
    -- Unlock metadata
    unlock_reason TEXT, -- Optional reason for unlock
    transaction_id BIGINT REFERENCES credit_transactions(id), -- Link to credit transaction
    
    -- Constraints
    UNIQUE(user_id, profile_id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_unlocked_profiles_user ON unlocked_profiles(user_id, unlocked_at DESC);
CREATE INDEX IF NOT EXISTS idx_unlocked_profiles_profile ON unlocked_profiles(profile_id);
CREATE INDEX IF NOT EXISTS idx_unlocked_profiles_user_profile ON unlocked_profiles(user_id, profile_id);

-- Enable RLS
ALTER TABLE unlocked_profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "unlocked_profiles_user_policy" ON unlocked_profiles
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "unlocked_profiles_service_policy" ON unlocked_profiles
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 5. DISCOVERY ANALYTICS TABLE
-- Track discovery usage patterns for insights and optimization
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.discovery_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Time dimension
    date_recorded DATE NOT NULL DEFAULT CURRENT_DATE,
    hour_recorded INTEGER NOT NULL DEFAULT EXTRACT(HOUR FROM CURRENT_TIMESTAMP),
    
    -- Aggregated metrics
    total_searches INTEGER DEFAULT 0,
    total_pages_viewed INTEGER DEFAULT 0,
    total_credits_consumed INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    unique_profiles_viewed INTEGER DEFAULT 0,
    
    -- Popular filters (top 10 filter combinations)
    popular_filters JSONB DEFAULT '[]'::jsonb,
    
    -- Performance metrics
    avg_search_duration_ms INTEGER,
    cache_hit_rate DECIMAL(5,2),
    
    -- Constraints
    UNIQUE(date_recorded, hour_recorded)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_discovery_analytics_date ON discovery_analytics(date_recorded DESC);

-- Enable RLS
ALTER TABLE discovery_analytics ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Only service role can access analytics
CREATE POLICY "discovery_analytics_service_only" ON discovery_analytics
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 6. DATABASE FUNCTIONS FOR DISCOVERY
-- Optimized functions for common discovery operations
-- ============================================================================

-- Function to check if user has unlocked a profile
CREATE OR REPLACE FUNCTION public.is_profile_unlocked(p_user_id UUID, p_profile_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM unlocked_profiles 
        WHERE user_id = p_user_id AND profile_id = p_profile_id
    );
END;
$$;

-- Function to get discovery search results with access levels
CREATE OR REPLACE FUNCTION public.get_discovery_results(
    p_user_id UUID,
    p_search_criteria JSONB DEFAULT '{}'::jsonb,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    profile_id UUID,
    username VARCHAR,
    platform VARCHAR,
    followers_count BIGINT,
    engagement_rate DECIMAL,
    is_unlocked BOOLEAN,
    access_level VARCHAR,
    preview_data JSONB,
    full_data JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_category_filter TEXT[];
    v_language_filter TEXT[];
    v_min_followers BIGINT;
    v_max_followers BIGINT;
    v_min_engagement DECIMAL;
    v_max_engagement DECIMAL;
    v_platform_filter TEXT;
BEGIN
    -- Extract filter criteria
    v_category_filter := (p_search_criteria->>'categories')::TEXT[];
    v_language_filter := (p_search_criteria->>'languages')::TEXT[];
    v_min_followers := (p_search_criteria->>'min_followers')::BIGINT;
    v_max_followers := (p_search_criteria->>'max_followers')::BIGINT;
    v_min_engagement := (p_search_criteria->>'min_engagement')::DECIMAL;
    v_max_engagement := (p_search_criteria->>'max_engagement')::DECIMAL;
    v_platform_filter := p_search_criteria->>'platform';
    
    RETURN QUERY
    SELECT 
        p.id,
        p.username,
        p.platform,
        p.followers_count,
        p.engagement_rate,
        COALESCE(up.user_id IS NOT NULL, false) as is_unlocked,
        p.access_level,
        -- Preview data (always available)
        jsonb_build_object(
            'username', p.username,
            'platform', p.platform,
            'followers_range', 
                CASE 
                    WHEN p.followers_count < 10000 THEN '1K-10K'
                    WHEN p.followers_count < 100000 THEN '10K-100K'
                    WHEN p.followers_count < 1000000 THEN '100K-1M'
                    ELSE '1M+'
                END,
            'profile_picture_url', p.profile_picture_url,
            'verified', p.verified
        ),
        -- Full data (only if unlocked)
        CASE 
            WHEN up.user_id IS NOT NULL THEN
                jsonb_build_object(
                    'followers_count', p.followers_count,
                    'following_count', p.following_count,
                    'posts_count', p.posts_count,
                    'engagement_rate', p.engagement_rate,
                    'avg_likes', p.avg_likes,
                    'avg_comments', p.avg_comments,
                    'categories', p.categories,
                    'languages', p.languages,
                    'sell_price_usd', p.sell_price_usd,
                    'min_collaboration_fee', p.min_collaboration_fee,
                    'barter_eligible', p.barter_eligible,
                    'ai_primary_content_type', p.ai_primary_content_type,
                    'ai_avg_sentiment_score', p.ai_avg_sentiment_score
                )
            ELSE NULL
        END
    FROM profiles p
    LEFT JOIN unlocked_profiles up ON (p.id = up.profile_id AND up.user_id = p_user_id)
    WHERE 
        p.discovery_visible = true
        AND p.blacklisted = false
        AND p.inactive = false
        AND (v_platform_filter IS NULL OR p.platform = v_platform_filter)
        AND (v_min_followers IS NULL OR p.followers_count >= v_min_followers)
        AND (v_max_followers IS NULL OR p.followers_count <= v_max_followers)
        AND (v_min_engagement IS NULL OR p.engagement_rate >= v_min_engagement)
        AND (v_max_engagement IS NULL OR p.engagement_rate <= v_max_engagement)
        AND (v_category_filter IS NULL OR p.categories ?| v_category_filter)
        AND (v_language_filter IS NULL OR p.languages ?| v_language_filter)
    ORDER BY 
        -- Prioritize unlocked profiles, then by followers
        up.user_id IS NOT NULL DESC,
        p.followers_count DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$;

-- Function to record discovery page view and calculate credits
CREATE OR REPLACE FUNCTION public.record_discovery_page_view(
    p_session_id UUID,
    p_page_number INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_session_record RECORD;
    v_credits_required INTEGER := 0;
    v_free_pages INTEGER := 3; -- First 3 pages are free
BEGIN
    -- Get session info
    SELECT * INTO v_session_record
    FROM discovery_sessions
    WHERE id = p_session_id AND expires_at > CURRENT_TIMESTAMP;
    
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'error', 'Session not found or expired',
            'credits_required', 0
        );
    END IF;
    
    -- Calculate credits required for this page
    IF p_page_number > v_free_pages THEN
        v_credits_required := 1; -- 1 credit per page after free pages
    END IF;
    
    -- Update session
    UPDATE discovery_sessions 
    SET 
        pages_viewed = GREATEST(pages_viewed, p_page_number),
        credits_consumed = credits_consumed + v_credits_required,
        free_pages_used = LEAST(free_pages_used + 1, v_free_pages),
        last_accessed = CURRENT_TIMESTAMP
    WHERE id = p_session_id;
    
    RETURN jsonb_build_object(
        'credits_required', v_credits_required,
        'total_credits_consumed', v_session_record.credits_consumed + v_credits_required,
        'free_pages_remaining', GREATEST(0, v_free_pages - p_page_number),
        'page_number', p_page_number
    );
END;
$$;

-- ============================================================================
-- 7. UPDATE EXISTING USER_PROFILE_ACCESS FOR COMPATIBILITY
-- Ensure compatibility with existing profile access system
-- ============================================================================

-- Add indexes for better performance with unlocked profiles
CREATE INDEX IF NOT EXISTS idx_user_profile_access_user_profile ON user_profile_access(user_id, profile_id, expires_at DESC);

-- ============================================================================
-- 8. SEED DEFAULT DATA
-- Add some default discovery filters and update existing profiles
-- ============================================================================

-- Update existing profiles to be discoverable by default
UPDATE profiles 
SET discovery_visible = true, 
    blacklisted = false, 
    inactive = false,
    access_level = 'public'
WHERE discovery_visible IS NULL;

-- Set default categories based on AI analysis
UPDATE profiles 
SET categories = COALESCE(
    CASE 
        WHEN ai_primary_content_type IS NOT NULL 
        THEN jsonb_build_array(ai_primary_content_type)
        ELSE '["General"]'::jsonb
    END,
    '["General"]'::jsonb
)
WHERE categories = '[]'::jsonb OR categories IS NULL;

-- Set default languages based on AI analysis  
UPDATE profiles 
SET languages = COALESCE(
    CASE 
        WHEN ai_language_distribution IS NOT NULL 
        THEN (SELECT jsonb_agg(key) FROM jsonb_each(ai_language_distribution))
        ELSE '["en"]'::jsonb
    END,
    '["en"]'::jsonb
)
WHERE languages = '[]'::jsonb OR languages IS NULL;

COMMIT;

-- Verification queries (for manual checking)
/*
-- Check discovery-enabled profiles
SELECT COUNT(*) as discoverable_profiles 
FROM profiles 
WHERE discovery_visible = true AND blacklisted = false AND inactive = false;

-- Check discovery session structure
SELECT * FROM discovery_sessions LIMIT 1;

-- Test discovery function
SELECT * FROM get_discovery_results(
    '00000000-0000-0000-0000-000000000000'::UUID, 
    '{}'::jsonb, 
    5, 
    0
) LIMIT 5;
*/