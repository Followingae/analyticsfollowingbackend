-- COMPREHENSIVE RLS POLICY TESTING
-- Test all RLS policies to ensure complete security isolation
-- Run these queries as different users to verify multi-tenant security

-- =============================================================================
-- TEST SETUP (run as service_role)
-- =============================================================================

-- Create test users
-- INSERT INTO auth.users (id, email) VALUES 
--   ('00000000-0000-0000-0000-000000000001', 'user1@test.com'),
--   ('00000000-0000-0000-0000-000000000002', 'user2@test.com');

-- INSERT INTO public.users (id, supabase_user_id, email, full_name) VALUES
--   ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'user1@test.com', 'Test User 1'),
--   ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000002', 'user2@test.com', 'Test User 2');

-- Create test Instagram profiles
-- INSERT INTO public.profiles (id, username, full_name) VALUES
--   ('20000000-0000-0000-0000-000000000001', 'testprofile1', 'Test Profile 1'),
--   ('20000000-0000-0000-0000-000000000002', 'testprofile2', 'Test Profile 2');

-- Grant User 1 access to Profile 1
-- INSERT INTO public.user_profile_access (user_id, profile_id, access_granted_at) VALUES
--   ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', NOW());

-- Grant User 2 access to Profile 2  
-- INSERT INTO public.user_profile_access (user_id, profile_id, access_granted_at) VALUES
--   ('10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', NOW());

-- =============================================================================
-- RLS POLICY TESTS
-- =============================================================================

-- Test 1: Users can only see their own data in users table
-- Expected: Each user sees only their own record
SELECT 'Test 1: Users table access' as test_name;
SELECT id, email, full_name FROM public.users;

-- Test 2: Users can only see their own favorites
-- Expected: User 1 sees only User 1's favorites, User 2 sees only User 2's favorites
SELECT 'Test 2: User favorites access' as test_name;
SELECT user_id, profile_id, added_at FROM public.user_favorites;

-- Test 3: Users can only see their own campaigns
-- Expected: User 1 sees only User 1's campaigns, User 2 sees only User 2's campaigns
SELECT 'Test 3: Campaigns access' as test_name;
SELECT user_id, name, status, created_at FROM public.campaigns;

-- Test 4: Users can only see their own search history
-- Expected: User 1 sees only User 1's searches, User 2 sees only User 2's searches
SELECT 'Test 4: Search history access' as test_name;
SELECT user_id, instagram_username, search_timestamp FROM public.user_searches;

-- Test 5: Campaign posts are only visible to campaign owners
-- Expected: User 1 sees only posts from User 1's campaigns
SELECT 'Test 5: Campaign posts access' as test_name;
SELECT cp.campaign_id, c.name as campaign_name, cp.post_id 
FROM public.campaign_posts cp
JOIN public.campaigns c ON cp.campaign_id = c.id;

-- =============================================================================
-- CROSS-USER ACCESS TESTS (Should return empty results)
-- =============================================================================

-- Test 6: Try to access another user's data directly (should fail/return empty)
-- This query should return no results when run as User 1, looking for User 2's data
SELECT 'Test 6: Cross-user access attempt' as test_name;
SELECT COUNT(*) as should_be_zero FROM public.users 
WHERE supabase_user_id = '00000000-0000-0000-0000-000000000002'; -- User 2's ID

-- =============================================================================
-- INSTAGRAM DATA ACCESS TESTS (NOW SECURED WITH RLS)
-- =============================================================================

-- Test 7: Users can only access Instagram profiles they have access to
-- Expected: User 1 sees only Profile 1, User 2 sees only Profile 2
SELECT 'Test 7: Instagram profiles access control' as test_name;
SELECT id, username, full_name FROM public.profiles;

-- Test 8: Users can only access posts from profiles they have access to
-- Expected: User 1 sees only posts from Profile 1, User 2 sees only posts from Profile 2
SELECT 'Test 8: Instagram posts access control' as test_name;
SELECT COUNT(*) as accessible_posts FROM public.posts;

-- Test 9: Users can only access audience demographics for their accessible profiles
-- Expected: Limited to profiles in user_profile_access
SELECT 'Test 9: Audience demographics access control' as test_name;
SELECT COUNT(*) as accessible_demographics FROM public.audience_demographics;

-- Test 10: Auth users table - users can only see their own record
-- Expected: Each user sees only their own auth record
SELECT 'Test 10: Auth users access control' as test_name;
SELECT supabase_user_id, email FROM public.auth_users;

-- =============================================================================
-- INSTRUCTIONS FOR TESTING
-- =============================================================================

/*
COMPREHENSIVE RLS TESTING INSTRUCTIONS:

1. Run the comprehensive RLS migration:
   - database/migrations/comprehensive_rls_security.sql

2. Create test users and data (uncomment the INSERT statements above)

3. Use Supabase SQL editor with different user contexts

4. Run these test queries as each user (User 1 and User 2)

5. Expected results with comprehensive RLS:

   ✅ USER-SPECIFIC DATA ISOLATION:
   - User 1 sees only User 1's: campaigns, favorites, searches, auth records
   - User 2 sees only User 2's: campaigns, favorites, searches, auth records
   - Cross-user access attempts return empty results

   ✅ INSTAGRAM DATA ACCESS CONTROL:
   - User 1 sees only Instagram data for profiles they have accessed (Profile 1)
   - User 2 sees only Instagram data for profiles they have accessed (Profile 2)
   - No cross-user Instagram data leakage

   ✅ SERVICE ROLE VERIFICATION:
   - Backend API (service_role) can access all data for operations
   - Regular users cannot bypass access controls

   ❌ SECURITY VIOLATIONS PREVENTED:
   - User 1 cannot see User 2's private data
   - User 1 cannot see Instagram profiles User 2 searched but User 1 didn't
   - User 2 cannot see User 1's private data or Instagram data

This comprehensive approach addresses all Supabase security advisor warnings
while maintaining proper multi-tenant isolation and controlled data sharing.
*/