"""
Fetch fresh profile data and analyze raw_data structure
"""
import asyncio
import httpx
import json
import asyncpg
from typing import Dict, Any, Set, List
from app.core.config import settings

async def fetch_and_analyze_profile():
    """Fetch a profile and analyze its raw_data structure"""
    
    await asyncio.sleep(5)  # Wait for server to start
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Register a test user
            register_data = {
                'email': 'analyzer@example.com',
                'password': 'TestPassword123!',
                'full_name': 'Data Analyzer'
            }
            
            print("Registering user...")
            register_response = await client.post(
                'http://localhost:8000/api/v1/auth/register',
                json=register_data
            )
            
            if register_response.status_code != 200:
                print(f"Registration failed: {register_response.text}")
                return
            
            # Login
            login_data = {
                'email': 'analyzer@example.com',
                'password': 'TestPassword123!'
            }
            
            print("Logging in...")
            login_response = await client.post(
                'http://localhost:8000/api/v1/auth/login',
                json=login_data
            )
            
            if login_response.status_code != 200:
                print(f"Login failed: {login_response.text}")
                return
            
            token = login_response.json().get('access_token')
            headers = {'Authorization': f'Bearer {token}'}
            
            # Fetch a profile to populate the database
            print("Fetching profile data...")
            profile_response = await client.get(
                'http://localhost:8000/api/v1/instagram/profile/karenwazen',
                headers=headers
            )
            
            if profile_response.status_code != 200:
                print(f"Profile fetch failed: {profile_response.text}")
                return
            
            print("Profile fetched successfully!")
            
            # Wait a moment for data to be stored
            await asyncio.sleep(2)
            
            # Now analyze the raw_data in the database
            await analyze_stored_raw_data()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def analyze_stored_raw_data():
    """Analyze the raw_data that was just stored"""
    
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        print("\n=== ANALYZING STORED RAW_DATA ===")
        
        # Get the most recent profile
        profile = await conn.fetchrow("""
            SELECT username, raw_data, followers_count, posts_count
            FROM profiles 
            WHERE raw_data IS NOT NULL 
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        if not profile:
            print("No profile data found in database")
            await conn.close()
            return
        
        print(f"Analyzing profile: {profile['username']}")
        print(f"Followers: {profile['followers_count']}, Posts: {profile['posts_count']}")
        
        raw_data = profile['raw_data']
        
        # Save the raw data to a file for inspection
        with open('profile_raw_data_sample.json', 'w') as f:
            json.dump(raw_data, f, indent=2)
        
        print("Raw data saved to: profile_raw_data_sample.json")
        
        # Analyze structure
        all_keys = extract_all_keys(raw_data)
        print(f"Total keys in raw_data: {len(all_keys)}")
        
        # Get existing profile columns
        profile_columns = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'profiles' AND table_schema = 'public'
        """)
        
        existing_columns = [col['column_name'] for col in profile_columns]
        print(f"Existing columns: {len(existing_columns)}")
        
        # Find unmapped data
        unmapped_keys = find_unmapped_keys(all_keys, existing_columns)
        
        print(f"\nPotentially unmapped keys ({len(unmapped_keys)}):")
        for key in sorted(unmapped_keys)[:50]:  # Show first 50
            print(f"  {key}")
        
        # Get sample posts too
        posts = await conn.fetch("""
            SELECT shortcode, raw_data, likes_count, comments_count
            FROM posts 
            WHERE raw_data IS NOT NULL 
            ORDER BY created_at DESC
            LIMIT 3
        """)
        
        if posts:
            print(f"\n=== POST RAW_DATA ANALYSIS ===")
            print(f"Found {len(posts)} posts with raw_data")
            
            all_post_keys = set()
            for post in posts:
                post_keys = extract_all_keys(post['raw_data'])
                all_post_keys.update(post_keys)
                print(f"Post {post['shortcode']}: {len(post_keys)} keys, {post['likes_count']} likes, {post['comments_count']} comments")
            
            # Save sample post data
            with open('post_raw_data_sample.json', 'w') as f:
                json.dump(posts[0]['raw_data'], f, indent=2)
            
            print(f"Sample post raw data saved to: post_raw_data_sample.json")
            
            # Get post columns
            post_columns = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'posts' AND table_schema = 'public'
            """)
            
            existing_post_columns = [col['column_name'] for col in post_columns]
            unmapped_post_keys = find_unmapped_keys(all_post_keys, existing_post_columns)
            
            print(f"\nPotentially unmapped post keys ({len(unmapped_post_keys)}):")
            for key in sorted(unmapped_post_keys)[:50]:
                print(f"  {key}")
        
        # Save comprehensive analysis
        analysis = {
            'profile_analysis': {
                'username': profile['username'],
                'total_raw_keys': len(all_keys),
                'existing_columns': existing_columns,
                'unmapped_keys': sorted(list(unmapped_keys)),
                'sample_raw_keys': sorted(list(all_keys))[:100]
            },
            'post_analysis': {
                'total_posts_analyzed': len(posts),
                'total_raw_keys': len(all_post_keys) if posts else 0,
                'existing_columns': existing_post_columns if posts else [],
                'unmapped_keys': sorted(list(unmapped_post_keys)) if posts else [],
                'sample_raw_keys': sorted(list(all_post_keys))[:100] if posts else []
            }
        }
        
        with open('comprehensive_raw_data_analysis.json', 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\nComprehensive analysis saved to: comprehensive_raw_data_analysis.json")
        
        await conn.close()
        
    except Exception as e:
        print(f"Database analysis error: {e}")
        import traceback
        traceback.print_exc()

def extract_all_keys(data: Any, parent_key: str = "", max_depth: int = 5) -> Set[str]:
    """Recursively extract all keys from nested structure with depth limit"""
    keys = set()
    
    if max_depth <= 0:
        return keys
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_key = f"{parent_key}.{key}" if parent_key else key
            keys.add(current_key)
            
            # Recurse with depth limit
            nested_keys = extract_all_keys(value, current_key, max_depth - 1)
            keys.update(nested_keys)
            
    elif isinstance(data, list) and data and len(data) > 0:
        # Analyze first few items in lists
        for i, item in enumerate(data[:3]):  # Only first 3 items
            current_key = f"{parent_key}[{i}]" if parent_key else f"[{i}]"
            nested_keys = extract_all_keys(item, current_key, max_depth - 1)
            keys.update(nested_keys)
    
    return keys

def find_unmapped_keys(raw_keys: Set[str], existing_columns: List[str]) -> Set[str]:
    """Find keys that don't seem to be mapped to existing columns"""
    unmapped = set()
    columns_lower = {col.lower().replace('_', '') for col in existing_columns}
    
    for key in raw_keys:
        # Clean the key
        clean_key = key.lower()
        
        # Remove common prefixes/suffixes
        clean_key = clean_key.replace('results[0].content.data.user.', '')
        clean_key = clean_key.replace('edge_', '').replace('[0]', '').replace('.', '').replace('_', '')
        
        # Skip internal/metadata keys
        if any(skip in clean_key.lower() for skip in ['typename', 'id', 'clientmutationid', 'cursor']):
            continue
        
        # Check if similar column exists
        found_match = False
        for col_clean in columns_lower:
            if clean_key in col_clean or col_clean in clean_key:
                if len(clean_key) > 2:  # Avoid matching very short keys
                    found_match = True
                    break
        
        if not found_match and len(clean_key) > 2:
            unmapped.add(key)
    
    return unmapped

if __name__ == '__main__':
    asyncio.run(fetch_and_analyze_profile())