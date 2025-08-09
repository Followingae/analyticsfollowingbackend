"""
Direct database query to check raw_data content
"""
import asyncio
import asyncpg
import json
from typing import Dict, Any, Set
from app.core.config import settings

async def check_raw_data_directly():
    """Check raw_data content directly from database"""
    
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        print("=== CHECKING PROFILE RAW_DATA ===")
        
        # Get profiles with raw_data
        profile_query = """
            SELECT username, raw_data, followers_count, engagement_rate, influence_score
            FROM profiles 
            WHERE raw_data IS NOT NULL 
            ORDER BY created_at DESC
            LIMIT 3
        """
        
        profiles = await conn.fetch(profile_query)
        
        if not profiles:
            print("No profiles found with raw_data")
        else:
            print(f"Found {len(profiles)} profiles with raw_data")
            
            for profile in profiles:
                username = profile['username']
                raw_data = profile['raw_data']
                
                print(f"\n--- Profile: {username} ---")
                print(f"Followers: {profile['followers_count']}")
                print(f"Engagement Rate: {profile['engagement_rate']}")
                print(f"Influence Score: {profile['influence_score']}")
                
                if raw_data and isinstance(raw_data, dict):
                    print(f"Raw data structure:")
                    
                    # Show top-level keys
                    top_keys = list(raw_data.keys())
                    print(f"  Top-level keys: {top_keys}")
                    
                    # Navigate to user data if present
                    user_data = None
                    if 'results' in raw_data and raw_data['results']:
                        result = raw_data['results'][0]
                        if 'content' in result and 'data' in result['content']:
                            user_data = result['content']['data'].get('user', {})
                            
                            if user_data:
                                print(f"  User data keys: {list(user_data.keys())}")
                                
                                # Check for post data
                                edge_media = user_data.get('edge_owner_to_timeline_media', {})
                                if 'edges' in edge_media:
                                    posts = edge_media['edges']
                                    print(f"  Posts found: {len(posts)}")
                                    
                                    if posts:
                                        # Sample first post structure
                                        first_post = posts[0].get('node', {})
                                        print(f"  First post keys: {list(first_post.keys())}")
                                        
                                        # Check engagement data
                                        likes = first_post.get('edge_liked_by', {}).get('count', 0)
                                        comments = first_post.get('edge_media_to_comment', {}).get('count', 0)
                                        print(f"  First post engagement: {likes} likes, {comments} comments")
                    
                    # Save sample for detailed analysis
                    with open(f'{username}_raw_data_sample.json', 'w') as f:
                        json.dump(raw_data, f, indent=2)
                    print(f"  Saved raw data to: {username}_raw_data_sample.json")
                    
                    # Look for unmapped fields
                    unmapped_fields = find_unmapped_profile_fields(raw_data)
                    if unmapped_fields:
                        print(f"  Potentially unmapped fields: {len(unmapped_fields)}")
                        for field in list(unmapped_fields)[:10]:  # Show first 10
                            print(f"    {field}")
        
        print("\n=== CHECKING POST RAW_DATA ===")
        
        # Get posts with raw_data
        post_query = """
            SELECT shortcode, raw_data, likes_count, comments_count, engagement_rate
            FROM posts 
            WHERE raw_data IS NOT NULL 
            ORDER BY created_at DESC
            LIMIT 3
        """
        
        posts = await conn.fetch(post_query)
        
        if not posts:
            print("No posts found with raw_data")
        else:
            print(f"Found {len(posts)} posts with raw_data")
            
            for post in posts:
                shortcode = post['shortcode']
                raw_data = post['raw_data']
                
                print(f"\n--- Post: {shortcode} ---")
                print(f"Likes: {post['likes_count']}")
                print(f"Comments: {post['comments_count']}")
                print(f"Engagement Rate: {post['engagement_rate']}")
                
                if raw_data and isinstance(raw_data, dict):
                    print(f"Raw data keys: {list(raw_data.keys())}")
                    
                    # Save sample
                    with open(f'{shortcode}_post_raw_data.json', 'w') as f:
                        json.dump(raw_data, f, indent=2)
                    print(f"Saved post raw data to: {shortcode}_post_raw_data.json")
                    
                    # Look for unmapped fields
                    unmapped_fields = find_unmapped_post_fields(raw_data)
                    if unmapped_fields:
                        print(f"Potentially unmapped post fields: {len(unmapped_fields)}")
                        for field in list(unmapped_fields)[:10]:  # Show first 10
                            print(f"    {field}")
        
        await conn.close()
        
    except Exception as e:
        print(f"Database check error: {e}")
        import traceback
        traceback.print_exc()

def find_unmapped_profile_fields(raw_data: Dict[str, Any]) -> Set[str]:
    """Find profile fields that might not be mapped to columns"""
    
    # Known mapped profile fields (from unified_models.py)
    mapped_fields = {
        'username', 'full_name', 'biography', 'external_url', 'profile_pic_url',
        'profile_pic_url_hd', 'followers_count', 'following_count', 'posts_count',
        'is_verified', 'is_private', 'is_business_account', 'category',
        'engagement_rate', 'influence_score', 'data_quality_score'
    }
    
    # Extract all fields from raw data
    all_fields = set()
    
    if 'results' in raw_data and raw_data['results']:
        result = raw_data['results'][0]
        if 'content' in result and 'data' in result['content']:
            user_data = result['content']['data'].get('user', {})
            
            # Add direct user fields
            for key in user_data.keys():
                all_fields.add(key)
            
            # Add edge data fields
            for key, value in user_data.items():
                if key.startswith('edge_') and isinstance(value, dict):
                    if 'count' in value:
                        all_fields.add(f"{key}_count")
    
    # Find unmapped fields
    unmapped = all_fields - mapped_fields
    
    # Filter out obviously internal fields
    filtered_unmapped = {
        field for field in unmapped 
        if not any(skip in field.lower() for skip in ['__', 'typename', 'id', '_id', 'cursor'])
    }
    
    return filtered_unmapped

def find_unmapped_post_fields(raw_data: Dict[str, Any]) -> Set[str]:
    """Find post fields that might not be mapped to columns"""
    
    # Known mapped post fields (from unified_models.py)
    mapped_fields = {
        'instagram_post_id', 'shortcode', 'media_type', 'is_video', 'display_url',
        'thumbnail_src', 'video_url', 'video_view_count', 'video_duration',
        'has_audio', 'width', 'height', 'caption', 'accessibility_caption',
        'likes_count', 'comments_count', 'comments_disabled', 'location_name',
        'location_id', 'is_carousel', 'carousel_media_count', 'taken_at_timestamp',
        'hashtags', 'mentions', 'engagement_rate', 'performance_score'
    }
    
    # Extract fields from post raw data
    all_fields = set()
    
    if isinstance(raw_data, dict):
        for key in raw_data.keys():
            all_fields.add(key)
            
            # Add edge data
            value = raw_data[key]
            if isinstance(value, dict):
                for subkey in value.keys():
                    if subkey == 'count':
                        all_fields.add(f"{key}_count")
                    else:
                        all_fields.add(f"{key}_{subkey}")
    
    # Find unmapped
    unmapped = all_fields - mapped_fields
    
    # Filter internal fields
    filtered_unmapped = {
        field for field in unmapped 
        if not any(skip in field.lower() for skip in ['__', 'typename', 'cursor', 'page_info'])
    }
    
    return filtered_unmapped

if __name__ == '__main__':
    asyncio.run(check_raw_data_directly())