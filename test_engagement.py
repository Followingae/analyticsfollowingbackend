"""
Test engagement calculation functionality
"""
import asyncio
import httpx
import json

async def test_engagement_calculations():
    """Test the engagement calculation API endpoints"""
    
    await asyncio.sleep(2)  # Wait for server startup
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Register and login
            register_data = {
                'email': 'engagement_test@example.com',
                'password': 'TestPassword123!',
                'full_name': 'Engagement Test User'
            }
            
            print("1. Registering test user...")
            register_response = await client.post(
                'http://localhost:8000/api/v1/auth/register',
                json=register_data
            )
            
            if register_response.status_code != 200:
                print(f"Registration failed: {register_response.text}")
                return
            
            # Login
            login_data = {
                'email': 'engagement_test@example.com',
                'password': 'TestPassword123!'
            }
            
            print("2. Logging in...")
            login_response = await client.post(
                'http://localhost:8000/api/v1/auth/login',
                json=login_data
            )
            
            if login_response.status_code != 200:
                print(f"Login failed: {login_response.text}")
                return
            
            token = login_response.json().get('access_token')
            headers = {'Authorization': f'Bearer {token}'}
            
            print("3. Fetching a profile to populate database...")
            # Fetch a profile first to have data
            profile_response = await client.get(
                'http://localhost:8000/api/v1/instagram/profile/karenwazen',
                headers=headers
            )
            
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                print(f"   Profile fetched: {profile_data['profile']['username']}")
                print(f"   Current engagement rate: {profile_data['analytics']['engagement_rate']}%")
            else:
                print(f"   Profile fetch failed: {profile_response.text}")
                return
            
            # Wait a moment for data to be stored
            await asyncio.sleep(2)
            
            print("\n4. Testing engagement calculation API...")
            
            # Test individual profile engagement calculation
            calc_response = await client.post(
                'http://localhost:8000/api/v1/engagement/calculate/profile/karenwazen',
                headers=headers
            )
            
            if calc_response.status_code == 200:
                calc_data = calc_response.json()
                print("   ✓ Profile engagement calculation successful!")
                print(f"   Overall engagement rate: {calc_data['engagement_metrics']['overall_engagement_rate']}%")
                print(f"   Engagement rate (last 12 posts): {calc_data['engagement_metrics']['engagement_rate_last_12_posts']}%")
                print(f"   Engagement rate (last 30 days): {calc_data['engagement_metrics']['engagement_rate_last_30_days']}%")
                print(f"   Average likes: {calc_data['engagement_metrics']['avg_likes']}")
                print(f"   Average comments: {calc_data['engagement_metrics']['avg_comments']}")
                print(f"   Posts analyzed: {calc_data['engagement_metrics']['posts_analyzed']}")
                print(f"   Influence score: {calc_data['influence_score']}")
                
                # Save results
                with open('engagement_calculation_result.json', 'w') as f:
                    json.dump(calc_data, f, indent=2)
                
            else:
                print(f"   ✗ Profile engagement calculation failed: {calc_response.text}")
            
            print("\n5. Getting engagement statistics...")
            
            # Test engagement stats
            stats_response = await client.get(
                'http://localhost:8000/api/v1/engagement/stats',
                headers=headers
            )
            
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                print("   ✓ Engagement statistics retrieved!")
                print(f"   Total profiles: {stats_data['stats']['profiles']['total']}")
                print(f"   Profiles with engagement calculated: {stats_data['stats']['profiles']['with_engagement_calculated']}")
                print(f"   Average engagement rate: {stats_data['stats']['profiles']['avg_engagement_rate']}%")
                print(f"   Max engagement rate: {stats_data['stats']['profiles']['max_engagement_rate']}%")
                print(f"   Total posts: {stats_data['stats']['posts']['total']}")
                print(f"   Posts with engagement calculated: {stats_data['stats']['posts']['with_engagement_calculated']}")
                
            else:
                print(f"   ✗ Stats retrieval failed: {stats_response.text}")
            
            print("\n6. Testing bulk engagement calculation...")
            
            # Test bulk calculation
            bulk_response = await client.post(
                'http://localhost:8000/api/v1/engagement/calculate/bulk?limit=5',
                headers=headers
            )
            
            if bulk_response.status_code == 200:
                bulk_data = bulk_response.json()
                print("   ✓ Bulk engagement calculation completed!")
                print(f"   Profiles processed: {bulk_data['bulk_update_results']['total_profiles_processed']}")
                print(f"   Successfully updated: {bulk_data['bulk_update_results']['successfully_updated']}")
                print(f"   Failed updates: {bulk_data['bulk_update_results']['failed_updates']}")
                
            else:
                print(f"   ✗ Bulk calculation failed: {bulk_response.text}")
            
            print("\n7. Verifying updated profile data...")
            
            # Fetch profile again to see updated data
            final_profile_response = await client.get(
                'http://localhost:8000/api/v1/instagram/profile/karenwazen',
                headers=headers
            )
            
            if final_profile_response.status_code == 200:
                final_data = final_profile_response.json()
                print("   ✓ Final profile data retrieved!")
                print(f"   Updated engagement rate: {final_data['analytics']['engagement_rate']}%")
                print(f"   Updated influence score: {final_data['analytics']['influence_score']}")
                
                # Save final data
                with open('final_profile_with_engagement.json', 'w') as f:
                    json.dump(final_data, f, indent=2)
                
            else:
                print(f"   ✗ Final profile fetch failed: {final_profile_response.text}")
            
            print("\n✅ ENGAGEMENT CALCULATION TEST COMPLETED!")
            print("Check 'engagement_calculation_result.json' and 'final_profile_with_engagement.json' for detailed results")
            
    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_engagement_calculations())