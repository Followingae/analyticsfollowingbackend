"""
Debug why media URLs aren't displaying on frontend
Check database storage and API response format
"""
import asyncio
import json
import sys
import os
sys.path.append(os.getcwd())

from app.database.postgres_direct import postgres_direct


async def debug_media_storage():
    """Debug media URL storage and retrieval"""
    try:
        print("="*80)
        print("DEBUGGING MEDIA URL STORAGE & RETRIEVAL")
        print("="*80)
        
        # Initialize database
        await postgres_direct.init()
        
        # Check if leomessi was stored from our fresh search
        print("1. Checking if leomessi is in database...")
        leomessi_data = await postgres_direct.get_profile('leomessi')
        
        if leomessi_data:
            print("✓ Leomessi found in database")
            print(f"   Last refreshed: {leomessi_data.get('last_refreshed', 'N/A')}")
            
            # Check profile picture URLs
            print(f"\n2. Profile Picture URLs in Database:")
            profile_pic = leomessi_data.get('profile_pic_url', 'N/A')
            profile_pic_hd = leomessi_data.get('profile_pic_url_hd', 'N/A')
            
            print(f"   Standard: {profile_pic}")
            print(f"   HD: {profile_pic_hd}")
            
            if profile_pic == 'N/A' or not profile_pic:
                print("   ❌ ISSUE: Profile picture URL not stored properly")
            else:
                print("   ✓ Profile picture URLs stored")
            
            # Check if raw_data contains the post thumbnails
            print(f"\n3. Checking raw_data for post thumbnails...")
            raw_data = leomessi_data.get('raw_data')
            
            if raw_data:
                if isinstance(raw_data, str):
                    try:
                        raw_json = json.loads(raw_data)
                    except:
                        print("   ❌ ISSUE: raw_data is not valid JSON")
                        raw_json = None
                else:
                    raw_json = raw_data
                
                if raw_json and 'results' in raw_json:
                    result = raw_json['results'][0]
                    user_data = result['content']['data']['user']
                    
                    # Check timeline media
                    timeline_media = user_data.get('edge_owner_to_timeline_media', {})
                    if 'edges' in timeline_media and timeline_media['edges']:
                        posts = timeline_media['edges'][:2]  # First 2 posts
                        print(f"   ✓ Found {len(timeline_media['edges'])} posts in raw_data")
                        
                        for i, post in enumerate(posts, 1):
                            node = post['node']
                            print(f"   Post {i}:")
                            print(f"     ID: {node.get('id', 'N/A')}")
                            print(f"     Thumbnail: {node.get('display_url', 'N/A')[:80]}...")
                            print(f"     Has thumbnail_resources: {len(node.get('thumbnail_resources', []))} sizes")
                    else:
                        print("   ❌ ISSUE: No posts found in raw_data")
                else:
                    print("   ❌ ISSUE: Invalid raw_data structure")
            else:
                print("   ❌ ISSUE: No raw_data stored")
        else:
            print("❌ Leomessi not found in database")
            print("   This means the fresh search didn't store the data")
            return
        
        print(f"\n4. Testing API response format...")
        
        # Simulate what the API would return to frontend
        response_data = {
            "profile": {
                "username": leomessi_data.get('username', 'N/A'),
                "full_name": leomessi_data.get('full_name', 'N/A'),
                "profile_pic_url": leomessi_data.get('profile_pic_url', 'N/A'),
                "profile_pic_url_hd": leomessi_data.get('profile_pic_url_hd', 'N/A'),
                "followers": leomessi_data.get('followers_count', 0),
                "following": leomessi_data.get('following_count', 0),
                "posts_count": leomessi_data.get('posts_count', 0)
            },
            "database_available": True,
            "data_source": "database"
        }
        
        print("   Sample API Response:")
        print(json.dumps(response_data, indent=2))
        
        # Check what happens when we request leomessi through the API
        print(f"\n5. Testing actual API endpoint response...")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def test_api_endpoint():
    """Test the actual API endpoint response"""
    try:
        import requests
        
        print("Testing API endpoint for leomessi...")
        response = requests.get('http://localhost:8000/api/v1/instagram/profile/leomessi', timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API Response Status: {response.status_code}")
            
            profile = data.get('profile', {})
            print(f"\nProfile data returned:")
            print(f"  Username: {profile.get('username', 'N/A')}")
            print(f"  Full Name: {profile.get('full_name', 'N/A')}")
            print(f"  Profile Pic: {profile.get('profile_pic_url', 'N/A')[:80]}...")
            print(f"  Profile Pic HD: {profile.get('profile_pic_url_hd', 'N/A')[:80]}...")
            print(f"  Data Source: {data.get('data_source', 'N/A')}")
            print(f"  Database Available: {data.get('database_available', 'N/A')}")
            
            # Check if posts are included
            recent_posts = data.get('recent_posts', [])
            print(f"  Recent Posts: {len(recent_posts)} posts")
            
            if len(recent_posts) == 0:
                print("  ❌ ISSUE: No recent posts in API response")
                print("  This suggests posts aren't being extracted from raw_data")
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ API server not running")
    except Exception as e:
        print(f"API test error: {e}")


if __name__ == "__main__":
    async def main():
        await debug_media_storage()
        await test_api_endpoint()
    
    asyncio.run(main())