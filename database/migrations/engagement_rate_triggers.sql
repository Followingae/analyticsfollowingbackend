-- Create database triggers to automatically update engagement rates
-- These triggers ensure engagement rates stay current when data changes

-- =============================================================================
-- TRIGGER FUNCTION: UPDATE POST ENGAGEMENT RATE
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_update_post_engagement_rate()
RETURNS TRIGGER AS $$
DECLARE
    profile_followers BIGINT;
    new_engagement_rate DOUBLE PRECISION;
BEGIN
    -- Get followers count from the associated profile
    SELECT followers_count INTO profile_followers
    FROM public.profiles 
    WHERE id = NEW.profile_id;
    
    -- Calculate engagement rate for the post
    new_engagement_rate := calculate_post_engagement_rate(
        NEW.likes_count,
        NEW.comments_count,
        NEW.video_view_count,
        NEW.is_video,
        profile_followers
    );
    
    -- Update the engagement rate in the NEW record
    NEW.engagement_rate := new_engagement_rate;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGER FUNCTION: UPDATE PROFILE ENGAGEMENT RATE AFTER POST CHANGES
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_update_profile_engagement_rate()
RETURNS TRIGGER AS $$
DECLARE
    target_profile_id UUID;
BEGIN
    -- Determine which profile to update
    IF TG_OP = 'DELETE' THEN
        target_profile_id := OLD.profile_id;
    ELSE 
        target_profile_id := NEW.profile_id;
    END IF;
    
    -- Update the profile's overall engagement rate
    PERFORM update_profile_engagement_rate(target_profile_id);
    
    -- Return appropriate record based on operation
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGER FUNCTION: UPDATE ALL POST ENGAGEMENT RATES WHEN PROFILE FOLLOWERS CHANGE
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_update_posts_on_followers_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update if followers count actually changed
    IF OLD.followers_count IS DISTINCT FROM NEW.followers_count THEN
        -- Update engagement rates for all posts of this profile in background
        PERFORM update_profile_posts_engagement_rates(NEW.id);
        
        -- Update profile's overall engagement rate
        PERFORM update_profile_engagement_rate(NEW.id);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- CREATE TRIGGERS ON POSTS TABLE
-- =============================================================================

-- Trigger to calculate engagement rate when post is inserted or updated
DROP TRIGGER IF EXISTS posts_engagement_rate_trigger ON public.posts;
CREATE TRIGGER posts_engagement_rate_trigger
    BEFORE INSERT OR UPDATE OF likes_count, comments_count, video_view_count
    ON public.posts
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_post_engagement_rate();

-- Trigger to update profile engagement rate after post changes
DROP TRIGGER IF EXISTS posts_update_profile_engagement_trigger ON public.posts;
CREATE TRIGGER posts_update_profile_engagement_trigger
    AFTER INSERT OR UPDATE OR DELETE
    ON public.posts
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_profile_engagement_rate();

-- =============================================================================
-- CREATE TRIGGERS ON PROFILES TABLE
-- =============================================================================

-- Trigger to update all post engagement rates when profile followers change
DROP TRIGGER IF EXISTS profiles_followers_change_trigger ON public.profiles;
CREATE TRIGGER profiles_followers_change_trigger
    AFTER UPDATE OF followers_count
    ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_posts_on_followers_change();

-- =============================================================================
-- PERFORMANCE OPTIMIZATION TRIGGERS (Optional)
-- =============================================================================

-- Optional: Debounced trigger to avoid too many updates during bulk operations
-- This version only updates after a delay to batch multiple changes

CREATE OR REPLACE FUNCTION trigger_debounced_profile_engagement_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Schedule update for later (requires pg_cron extension or application-level batching)
    -- For now, we'll use immediate update but this could be optimized
    PERFORM update_profile_engagement_rate(NEW.profile_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- UTILITY FUNCTIONS FOR TRIGGER MANAGEMENT
-- =============================================================================

-- Function to disable all engagement rate triggers (for bulk operations)
CREATE OR REPLACE FUNCTION disable_engagement_rate_triggers()
RETURNS VOID AS $$
BEGIN
    ALTER TABLE public.posts DISABLE TRIGGER posts_engagement_rate_trigger;
    ALTER TABLE public.posts DISABLE TRIGGER posts_update_profile_engagement_trigger;
    ALTER TABLE public.profiles DISABLE TRIGGER profiles_followers_change_trigger;
    
    RAISE NOTICE 'Engagement rate triggers disabled. Remember to re-enable them!';
END;
$$ LANGUAGE plpgsql;

-- Function to enable all engagement rate triggers
CREATE OR REPLACE FUNCTION enable_engagement_rate_triggers()
RETURNS VOID AS $$
BEGIN
    ALTER TABLE public.posts ENABLE TRIGGER posts_engagement_rate_trigger;
    ALTER TABLE public.posts ENABLE TRIGGER posts_update_profile_engagement_trigger;
    ALTER TABLE public.profiles ENABLE TRIGGER profiles_followers_change_trigger;
    
    RAISE NOTICE 'Engagement rate triggers enabled.';
END;
$$ LANGUAGE plpgsql;

-- Function to manually recalculate all engagement rates (use after bulk data changes)
CREATE OR REPLACE FUNCTION recalculate_all_engagement_rates()
RETURNS TABLE(profiles_updated INTEGER, posts_updated INTEGER) AS $$
DECLARE
    profile_count INTEGER := 0;
    post_count INTEGER := 0;
    profile_id UUID;
BEGIN
    RAISE NOTICE 'Starting bulk engagement rate recalculation...';
    
    -- Disable triggers to avoid redundant calculations
    PERFORM disable_engagement_rate_triggers();
    
    -- Update all posts first
    FOR profile_id IN SELECT DISTINCT id FROM public.profiles LOOP
        post_count := post_count + update_profile_posts_engagement_rates(profile_id);
        PERFORM update_profile_engagement_rate(profile_id);
        profile_count := profile_count + 1;
    END LOOP;
    
    -- Re-enable triggers
    PERFORM enable_engagement_rate_triggers();
    
    RAISE NOTICE 'Bulk recalculation complete. Updated % profiles and % posts.', profile_count, post_count;
    
    RETURN QUERY SELECT profile_count, post_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- COMMENTS AND DOCUMENTATION
-- =============================================================================

COMMENT ON FUNCTION trigger_update_post_engagement_rate IS 'Trigger function to calculate engagement rate when post data changes';
COMMENT ON FUNCTION trigger_update_profile_engagement_rate IS 'Trigger function to update profile engagement rate when posts change';
COMMENT ON FUNCTION trigger_update_posts_on_followers_change IS 'Trigger function to recalculate all post engagement rates when profile followers change';
COMMENT ON FUNCTION disable_engagement_rate_triggers IS 'Utility function to disable triggers during bulk operations';
COMMENT ON FUNCTION enable_engagement_rate_triggers IS 'Utility function to re-enable triggers after bulk operations';
COMMENT ON FUNCTION recalculate_all_engagement_rates IS 'Utility function to manually recalculate all engagement rates in the database';

-- =============================================================================
-- USAGE EXAMPLES AND NOTES
-- =============================================================================

/*
TRIGGER BEHAVIOR:

1. When a post is inserted/updated:
   - Post engagement rate is automatically calculated
   - Profile's overall engagement rate is updated

2. When a profile's followers count changes:
   - All posts for that profile get recalculated engagement rates
   - Profile's overall engagement rate is updated

3. For bulk operations:
   - Use disable_engagement_rate_triggers() before bulk inserts/updates
   - Use recalculate_all_engagement_rates() after bulk operations
   - Use enable_engagement_rate_triggers() to restore normal behavior

PERFORMANCE NOTES:
- Triggers fire for each row, so bulk operations can be slow
- Consider disabling triggers for large data imports
- Profile engagement rate updates can be expensive for profiles with many posts
- Consider implementing application-level batching for high-volume scenarios
*/