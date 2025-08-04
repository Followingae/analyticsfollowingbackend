-- Migration to calculate engagement rates for existing data
-- Run this after deploying the engagement rate functions and triggers

-- =============================================================================
-- BACKUP AND PREPARATION
-- =============================================================================

-- Create backup of engagement rate columns before update (optional but recommended)
-- CREATE TABLE IF NOT EXISTS engagement_rate_backup AS
-- SELECT id, engagement_rate, updated_at FROM posts WHERE engagement_rate IS NOT NULL
-- UNION ALL 
-- SELECT id, engagement_rate, updated_at FROM profiles WHERE engagement_rate IS NOT NULL;

-- =============================================================================
-- BATCH UPDATE EXISTING POSTS WITH ENGAGEMENT RATES
-- =============================================================================

-- Update posts in batches to calculate engagement rates
-- This uses the database functions we created earlier

DO $$
DECLARE
    batch_size INTEGER := 1000;
    processed_count INTEGER := 0;
    total_posts INTEGER;
    current_batch INTEGER := 0;
    posts_updated INTEGER := 0;
BEGIN
    -- Get total count of posts needing engagement rate calculation
    SELECT COUNT(*) INTO total_posts 
    FROM posts p
    JOIN profiles pr ON p.profile_id = pr.id
    WHERE p.engagement_rate IS NULL OR p.engagement_rate = 0;
    
    RAISE NOTICE 'Starting engagement rate calculation for % posts', total_posts;
    
    -- Disable triggers temporarily for better performance
    PERFORM disable_engagement_rate_triggers();
    
    -- Process posts in batches
    WHILE processed_count < total_posts LOOP
        current_batch := current_batch + 1;
        
        -- Update batch of posts with calculated engagement rates
        WITH post_batch AS (
            SELECT 
                p.id,
                p.likes_count,
                p.comments_count,
                p.video_view_count,
                p.is_video,
                pr.followers_count
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE p.engagement_rate IS NULL OR p.engagement_rate = 0
            ORDER BY p.created_at DESC
            LIMIT batch_size
            OFFSET processed_count
        )
        UPDATE posts
        SET 
            engagement_rate = calculate_post_engagement_rate(
                pb.likes_count,
                pb.comments_count,
                pb.video_view_count,
                pb.is_video,
                pb.followers_count
            ),
            updated_at = now()
        FROM post_batch pb
        WHERE posts.id = pb.id;
        
        GET DIAGNOSTICS posts_updated = ROW_COUNT;
        processed_count := processed_count + posts_updated;
        
        RAISE NOTICE 'Batch %: Updated % posts (% total processed)', current_batch, posts_updated, processed_count;
        
        -- Exit if no more posts to update
        IF posts_updated = 0 THEN
            EXIT;
        END IF;
        
        -- Commit after each batch
        COMMIT;
    END LOOP;
    
    -- Re-enable triggers
    PERFORM enable_engagement_rate_triggers();
    
    RAISE NOTICE 'Completed post engagement rate calculation: % posts updated', processed_count;
END $$;

-- =============================================================================
-- UPDATE PROFILE ENGAGEMENT RATES
-- =============================================================================

-- Calculate average engagement rate for each profile based on their posts
DO $$
DECLARE
    profile_record RECORD;
    profiles_updated INTEGER := 0;
    avg_engagement DOUBLE PRECISION;
BEGIN
    RAISE NOTICE 'Starting profile engagement rate calculation';
    
    -- Update each profile's engagement rate
    FOR profile_record IN 
        SELECT DISTINCT p.id, p.username
        FROM profiles p
        WHERE EXISTS (
            SELECT 1 FROM posts po 
            WHERE po.profile_id = p.id 
            AND po.engagement_rate IS NOT NULL 
            AND po.engagement_rate > 0
        )
    LOOP
        -- Calculate average engagement rate for this profile
        SELECT AVG(engagement_rate) INTO avg_engagement
        FROM posts
        WHERE profile_id = profile_record.id
        AND engagement_rate IS NOT NULL
        AND engagement_rate > 0;
        
        -- Update the profile
        IF avg_engagement IS NOT NULL THEN
            UPDATE profiles
            SET 
                engagement_rate = ROUND(avg_engagement, 4),
                updated_at = now()
            WHERE id = profile_record.id;
            
            profiles_updated := profiles_updated + 1;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Completed profile engagement rate calculation: % profiles updated', profiles_updated;
END $$;

-- =============================================================================
-- DATA QUALITY VERIFICATION
-- =============================================================================

-- Verify the engagement rate calculations
DO $$
DECLARE
    posts_with_engagement INTEGER;
    posts_total INTEGER;
    profiles_with_engagement INTEGER;
    profiles_total INTEGER;
    avg_post_engagement DOUBLE PRECISION;
    avg_profile_engagement DOUBLE PRECISION;
BEGIN
    -- Check posts
    SELECT COUNT(*) INTO posts_total FROM posts;
    SELECT COUNT(*) INTO posts_with_engagement FROM posts WHERE engagement_rate IS NOT NULL AND engagement_rate > 0;
    SELECT AVG(engagement_rate) INTO avg_post_engagement FROM posts WHERE engagement_rate IS NOT NULL AND engagement_rate > 0;
    
    -- Check profiles  
    SELECT COUNT(*) INTO profiles_total FROM profiles;
    SELECT COUNT(*) INTO profiles_with_engagement FROM profiles WHERE engagement_rate IS NOT NULL AND engagement_rate > 0;
    SELECT AVG(engagement_rate) INTO avg_profile_engagement FROM profiles WHERE engagement_rate IS NOT NULL AND engagement_rate > 0;
    
    RAISE NOTICE '=== ENGAGEMENT RATE CALCULATION SUMMARY ===';
    RAISE NOTICE 'Posts: %/% have engagement rates (%.1f%% coverage)', posts_with_engagement, posts_total, (posts_with_engagement::FLOAT / posts_total * 100);
    RAISE NOTICE 'Average post engagement rate: %.4f%%', COALESCE(avg_post_engagement, 0);
    RAISE NOTICE 'Profiles: %/% have engagement rates (%.1f%% coverage)', profiles_with_engagement, profiles_total, (profiles_with_engagement::FLOAT / profiles_total * 100);
    RAISE NOTICE 'Average profile engagement rate: %.4f%%', COALESCE(avg_profile_engagement, 0);
    RAISE NOTICE '==========================================';
END $$;

-- =============================================================================
-- IDENTIFY HIGH AND LOW PERFORMERS
-- =============================================================================

-- Show top performing posts by engagement rate
SELECT 
    'Top 10 Posts by Engagement Rate' as report_section,
    p.shortcode,
    pr.username,
    p.likes_count,
    p.comments_count,
    p.video_view_count,
    p.is_video,
    p.engagement_rate,
    CASE 
        WHEN p.engagement_rate >= 10.0 THEN 'Excellent (10%+)'
        WHEN p.engagement_rate >= 5.0 THEN 'Very Good (5-10%)'
        WHEN p.engagement_rate >= 2.0 THEN 'Good (2-5%)'
        WHEN p.engagement_rate >= 1.0 THEN 'Average (1-2%)'
        ELSE 'Below Average (<1%)'
    END as engagement_category
FROM posts p
JOIN profiles pr ON p.profile_id = pr.id
WHERE p.engagement_rate IS NOT NULL
ORDER BY p.engagement_rate DESC
LIMIT 10;

-- Show top performing profiles by engagement rate
SELECT 
    'Top 10 Profiles by Engagement Rate' as report_section,
    pr.username,
    pr.followers_count,
    pr.engagement_rate,
    COUNT(p.id) as total_posts,
    CASE 
        WHEN pr.engagement_rate >= 10.0 THEN 'Excellent (10%+)'
        WHEN pr.engagement_rate >= 5.0 THEN 'Very Good (5-10%)'
        WHEN pr.engagement_rate >= 2.0 THEN 'Good (2-5%)'
        WHEN pr.engagement_rate >= 1.0 THEN 'Average (1-2%)'
        ELSE 'Below Average (<1%)'
    END as engagement_category
FROM profiles pr
LEFT JOIN posts p ON pr.id = p.profile_id
WHERE pr.engagement_rate IS NOT NULL
GROUP BY pr.id, pr.username, pr.followers_count, pr.engagement_rate
ORDER BY pr.engagement_rate DESC
LIMIT 10;

-- =============================================================================
-- ENGAGEMENT RATE DISTRIBUTION ANALYSIS
-- =============================================================================

-- Analyze engagement rate distribution
SELECT 
    'Engagement Rate Distribution' as analysis_type,
    CASE 
        WHEN engagement_rate >= 10.0 THEN 'Excellent (10%+)'
        WHEN engagement_rate >= 5.0 THEN 'Very Good (5-10%)'
        WHEN engagement_rate >= 2.0 THEN 'Good (2-5%)'
        WHEN engagement_rate >= 1.0 THEN 'Average (1-2%)'
        ELSE 'Below Average (<1%)'
    END as engagement_category,
    COUNT(*) as post_count,
    ROUND(COUNT(*)::NUMERIC / (SELECT COUNT(*) FROM posts WHERE engagement_rate IS NOT NULL) * 100, 2) as percentage
FROM posts
WHERE engagement_rate IS NOT NULL
GROUP BY 
    CASE 
        WHEN engagement_rate >= 10.0 THEN 'Excellent (10%+)'
        WHEN engagement_rate >= 5.0 THEN 'Very Good (5-10%)'
        WHEN engagement_rate >= 2.0 THEN 'Good (2-5%)'
        WHEN engagement_rate >= 1.0 THEN 'Average (1-2%)'
        ELSE 'Below Average (<1%)'
    END
ORDER BY 
    CASE 
        WHEN engagement_rate >= 10.0 THEN 1
        WHEN engagement_rate >= 5.0 THEN 2
        WHEN engagement_rate >= 2.0 THEN 3
        WHEN engagement_rate >= 1.0 THEN 4
        ELSE 5
    END;

-- =============================================================================
-- COMMENTS AND COMPLETION
-- =============================================================================

/*
MIGRATION COMPLETED SUCCESSFULLY!

This migration has:
✅ Calculated engagement rates for all existing posts
✅ Updated profile engagement rates based on post averages  
✅ Verified data quality and coverage
✅ Provided performance analysis and insights

Next Steps:
1. Review the summary statistics above
2. Check that engagement rates look reasonable for your data
3. Monitor the triggers to ensure new data gets calculated automatically
4. Consider running the bulk recalculation function periodically for data consistency

Functions Available:
- recalculate_all_engagement_rates() - Recalculate everything
- update_profile_engagement_rate(profile_id) - Update specific profile
- get_post_engagement_breakdown(post_id) - Detailed post analysis

The engagement rate system is now fully operational!
*/