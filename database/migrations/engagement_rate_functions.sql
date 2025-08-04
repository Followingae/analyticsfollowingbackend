-- Create PostgreSQL functions for calculating engagement rates
-- Includes views, likes, and comments for comprehensive engagement metrics

-- =============================================================================
-- POST ENGAGEMENT RATE CALCULATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION calculate_post_engagement_rate(
    p_likes_count BIGINT,
    p_comments_count BIGINT,
    p_video_view_count BIGINT,
    p_is_video BOOLEAN,
    p_followers_count BIGINT
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    total_interactions BIGINT;
    engagement_rate DOUBLE PRECISION;
BEGIN
    -- Handle null/zero followers to avoid division by zero
    IF p_followers_count IS NULL OR p_followers_count = 0 THEN
        RETURN 0.0;
    END IF;
    
    -- Calculate total interactions based on content type
    IF p_is_video = true THEN
        -- For video content: include views, likes, and comments
        total_interactions := COALESCE(p_likes_count, 0) + 
                             COALESCE(p_comments_count, 0) + 
                             COALESCE(p_video_view_count, 0);
    ELSE
        -- For image content: only likes and comments (views not meaningful for images)
        total_interactions := COALESCE(p_likes_count, 0) + 
                             COALESCE(p_comments_count, 0);
    END IF;
    
    -- Calculate engagement rate as percentage
    engagement_rate := (total_interactions::DOUBLE PRECISION / p_followers_count::DOUBLE PRECISION) * 100.0;
    
    -- Cap at reasonable maximum (1000% to handle viral content)
    IF engagement_rate > 1000.0 THEN
        engagement_rate := 1000.0;
    END IF;
    
    RETURN ROUND(engagement_rate, 4); -- Round to 4 decimal places
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- WEIGHTED ENGAGEMENT RATE CALCULATION FUNCTION (ADVANCED)
-- =============================================================================

CREATE OR REPLACE FUNCTION calculate_weighted_post_engagement_rate(
    p_likes_count BIGINT,
    p_comments_count BIGINT,
    p_video_view_count BIGINT,
    p_is_video BOOLEAN,
    p_followers_count BIGINT
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    weighted_interactions DOUBLE PRECISION;
    engagement_rate DOUBLE PRECISION;
    view_weight CONSTANT DOUBLE PRECISION := 0.1;  -- Views are easier to get
    like_weight CONSTANT DOUBLE PRECISION := 1.0;  -- Standard engagement
    comment_weight CONSTANT DOUBLE PRECISION := 3.0; -- Comments show high engagement
BEGIN
    -- Handle null/zero followers
    IF p_followers_count IS NULL OR p_followers_count = 0 THEN
        RETURN 0.0;
    END IF;
    
    -- Calculate weighted interactions
    IF p_is_video = true THEN
        weighted_interactions := (COALESCE(p_video_view_count, 0) * view_weight) +
                               (COALESCE(p_likes_count, 0) * like_weight) +
                               (COALESCE(p_comments_count, 0) * comment_weight);
    ELSE
        -- For images, no view component
        weighted_interactions := (COALESCE(p_likes_count, 0) * like_weight) +
                               (COALESCE(p_comments_count, 0) * comment_weight);
    END IF;
    
    -- Calculate engagement rate as percentage
    engagement_rate := (weighted_interactions / p_followers_count::DOUBLE PRECISION) * 100.0;
    
    -- Cap at reasonable maximum
    IF engagement_rate > 1000.0 THEN
        engagement_rate := 1000.0;
    END IF;
    
    RETURN ROUND(engagement_rate, 4);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- PROFILE ENGAGEMENT RATE CALCULATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION calculate_profile_engagement_rate(
    p_profile_id UUID
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    avg_engagement_rate DOUBLE PRECISION;
    post_count INTEGER;
BEGIN
    -- Calculate average engagement rate across all posts for the profile
    SELECT 
        AVG(engagement_rate),
        COUNT(*)
    INTO 
        avg_engagement_rate,
        post_count
    FROM public.posts 
    WHERE profile_id = p_profile_id 
      AND engagement_rate IS NOT NULL
      AND engagement_rate > 0;
    
    -- Return 0 if no posts or no engagement data
    IF post_count = 0 OR avg_engagement_rate IS NULL THEN
        RETURN 0.0;
    END IF;
    
    RETURN ROUND(avg_engagement_rate, 4);
END;
$$ LANGUAGE plpgsql STABLE;

-- =============================================================================
-- BATCH UPDATE FUNCTIONS
-- =============================================================================

-- Function to update engagement rate for a single post
CREATE OR REPLACE FUNCTION update_post_engagement_rate(p_post_id UUID)
RETURNS VOID AS $$
DECLARE
    post_record RECORD;
    profile_followers BIGINT;
    new_engagement_rate DOUBLE PRECISION;
BEGIN
    -- Get post data with profile followers count
    SELECT 
        p.*,
        pr.followers_count
    INTO post_record, profile_followers
    FROM public.posts p
    JOIN public.profiles pr ON p.profile_id = pr.id
    WHERE p.id = p_post_id;
    
    -- Calculate engagement rate
    new_engagement_rate := calculate_post_engagement_rate(
        post_record.likes_count,
        post_record.comments_count,
        post_record.video_view_count,
        post_record.is_video,
        profile_followers
    );
    
    -- Update the post
    UPDATE public.posts 
    SET engagement_rate = new_engagement_rate,
        updated_at = now()
    WHERE id = p_post_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update engagement rate for all posts of a profile
CREATE OR REPLACE FUNCTION update_profile_posts_engagement_rates(p_profile_id UUID)
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
    post_id UUID;
BEGIN
    -- Update all posts for the profile
    FOR post_id IN 
        SELECT id FROM public.posts WHERE profile_id = p_profile_id
    LOOP
        PERFORM update_post_engagement_rate(post_id);
        updated_count := updated_count + 1;
    END LOOP;
    
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Function to update profile's overall engagement rate
CREATE OR REPLACE FUNCTION update_profile_engagement_rate(p_profile_id UUID)
RETURNS VOID AS $$
DECLARE
    new_engagement_rate DOUBLE PRECISION;
BEGIN
    -- Calculate profile engagement rate
    new_engagement_rate := calculate_profile_engagement_rate(p_profile_id);
    
    -- Update the profile
    UPDATE public.profiles 
    SET engagement_rate = new_engagement_rate,
        updated_at = now()
    WHERE id = p_profile_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

-- Function to get engagement rate breakdown for a post
CREATE OR REPLACE FUNCTION get_post_engagement_breakdown(p_post_id UUID)
RETURNS TABLE(
    post_id UUID,
    likes_count BIGINT,
    comments_count BIGINT,
    video_view_count BIGINT,
    is_video BOOLEAN,
    followers_count BIGINT,
    total_interactions BIGINT,
    engagement_rate DOUBLE PRECISION,
    engagement_category TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.likes_count,
        p.comments_count,
        p.video_view_count,
        p.is_video,
        pr.followers_count,
        CASE 
            WHEN p.is_video THEN 
                COALESCE(p.likes_count, 0) + COALESCE(p.comments_count, 0) + COALESCE(p.video_view_count, 0)
            ELSE 
                COALESCE(p.likes_count, 0) + COALESCE(p.comments_count, 0)
        END as total_interactions,
        p.engagement_rate,
        CASE 
            WHEN p.engagement_rate >= 10.0 THEN 'Excellent (10%+)'
            WHEN p.engagement_rate >= 5.0 THEN 'Very Good (5-10%)'
            WHEN p.engagement_rate >= 2.0 THEN 'Good (2-5%)'
            WHEN p.engagement_rate >= 1.0 THEN 'Average (1-2%)'
            ELSE 'Below Average (<1%)'
        END as engagement_category
    FROM public.posts p
    JOIN public.profiles pr ON p.profile_id = pr.id
    WHERE p.id = p_post_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- =============================================================================
-- COMMENTS AND DOCUMENTATION
-- =============================================================================

COMMENT ON FUNCTION calculate_post_engagement_rate IS 'Calculates engagement rate for a post including views for videos. Formula: (interactions / followers) * 100';
COMMENT ON FUNCTION calculate_weighted_post_engagement_rate IS 'Calculates weighted engagement rate giving different weights to views, likes, and comments';
COMMENT ON FUNCTION calculate_profile_engagement_rate IS 'Calculates average engagement rate across all posts for a profile';
COMMENT ON FUNCTION update_post_engagement_rate IS 'Updates engagement rate for a single post';
COMMENT ON FUNCTION update_profile_posts_engagement_rates IS 'Updates engagement rates for all posts of a profile';
COMMENT ON FUNCTION update_profile_engagement_rate IS 'Updates overall engagement rate for a profile';
COMMENT ON FUNCTION get_post_engagement_breakdown IS 'Returns detailed engagement breakdown and categorization for a post';