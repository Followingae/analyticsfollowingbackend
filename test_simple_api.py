"""
Test simple API response without complex parsing
"""
import asyncio
import json
import sys
import os
sys.path.append(os.getcwd())

from app.database.postgres_direct import postgres_direct


async def create_simple_response():
    """Create a simple API response directly from database data"""
    try:
        await postgres_direct.init()
        
        # Get leomessi data
        profile_data = await postgres_direct.get_profile('leomessi')
        
        if not profile_data:
            print("No profile data found")
            return
        
        print("Creating simple API response from database...")
        
        # Create a simple response like the frontend expects
        simple_response = {
            "profile": {
                "username": profile_data.get('username', ''),
                "full_name": profile_data.get('full_name', ''),
                "biography": profile_data.get('biography', ''),
                "followers": profile_data.get('followers_count', 0),
                "following": profile_data.get('following_count', 0),
                "posts_count": profile_data.get('posts_count', 0),
                "is_verified": profile_data.get('is_verified', False),
                "is_private": profile_data.get('is_private', False),
                "profile_pic_url": profile_data.get('profile_pic_url', ''),
                "profile_pic_url_hd": profile_data.get('profile_pic_url_hd', ''),
                "external_url": profile_data.get('external_url', ''),
                # Add dummy analytics data for now
                "engagement_rate": 5.2,
                "avg_likes": 1500000,
                "avg_comments": 25000,
                "avg_engagement": 1525000,
                "follower_growth_rate": 2.1,
                "content_quality_score": 8.7,
                "influence_score": 9.5
            },
            "recent_posts": [],  # We'll add this next
            "hashtag_analysis": [],
            "engagement_metrics": {
                "like_rate": 3.2,
                "comment_rate": 0.05,
                "save_rate": 0.8,
                "share_rate": 0.3,
                "reach_rate": 15.2
            },
            "audience_insights": {
                "primary_age_group": "25-34",
                "gender_split": {"male": 45, "female": 55},
                "top_locations": ["Argentina", "Spain", "USA"],
                "activity_times": ["19:00", "21:00", "14:00"],
                "interests": ["Football", "Sports", "Fashion"]
            },
            "competitor_analysis": {
                "similar_accounts": ["cristiano", "neymarjr", "realmadrid"],
                "competitive_score": 9.8,
                "market_position": "Leader",
                "growth_opportunities": ["Video content", "Stories engagement"]
            },
            "content_performance": {
                "top_performing_content_types": ["Photos", "Videos", "Carousels"],
                "optimal_posting_frequency": "1-2 posts per day",
                "content_themes": ["Football", "Personal", "Sponsorship"],
                "hashtag_effectiveness": 8.5
            },
            "content_strategy": "Focus on authentic football content and personal moments",
            "best_posting_times": ["14:00", "19:00", "21:00"],
            "growth_recommendations": [
                "Increase video content",
                "More story engagement",
                "Collaborate with other athletes"
            ],
            "analysis_timestamp": "2025-07-29T10:57:00Z",
            "data_quality_score": 95,
            "scraping_method": "decodo_api",
            "data_updated_on": profile_data.get('last_refreshed', ''),
            "data_source": "database",
            "database_available": True,
            "user_authenticated": False,
            "user_role": None
        }
        
        print("SIMPLE API RESPONSE CREATED:")
        print(f"Username: {simple_response['profile']['username']}")
        print(f"Profile pic URL: {simple_response['profile']['profile_pic_url'][:80]}...")
        print(f"Followers: {simple_response['profile']['followers']:,}")
        
        # Now let's extract posts from raw_data
        print("\\nExtracting posts from raw_data...")
        raw_data = profile_data.get('raw_data')
        
        if raw_data:
            if isinstance(raw_data, str):
                raw_json = json.loads(raw_data)
            else:
                raw_json = raw_data
            
            # Navigate to posts
            if 'results' in raw_json and raw_json['results']:
                result = raw_json['results'][0]
                user_data = result['content']['data']['user']
                timeline_media = user_data.get('edge_owner_to_timeline_media', {})
                
                if 'edges' in timeline_media:
                    posts_data = timeline_media['edges'][:12]  # First 12 posts
                    recent_posts = []
                    
                    for post in posts_data:
                        node = post['node']
                        post_obj = {
                            "id": node.get('id', ''),
                            "shortcode": node.get('shortcode', ''),
                            "display_url": node.get('display_url', ''),
                            "is_video": node.get('is_video', False),
                            "likes": node.get('edge_liked_by', {}).get('count', 0),
                            "comments": node.get('edge_media_to_comment', {}).get('count', 0),
                            "timestamp": node.get('taken_at_timestamp', 0),
                            "thumbnail_resources": node.get('thumbnail_resources', [])
                        }
                        
                        # Add video URL if it's a video
                        if node.get('is_video') and node.get('video_url'):
                            post_obj['video_url'] = node['video_url']
                        
                        # Add caption
                        caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
                        if caption_edges:
                            post_obj['caption'] = caption_edges[0]['node']['text']
                        
                        recent_posts.append(post_obj)
                    
                    simple_response['recent_posts'] = recent_posts
                    print(f"Added {len(recent_posts)} posts to response")
                    
                    # Show first post details
                    if recent_posts:
                        first_post = recent_posts[0]
                        print(f"First post thumbnail: {first_post['display_url'][:80]}...")
                        print(f"Thumbnail resources: {len(first_post['thumbnail_resources'])} sizes")
        
        # Save this response for testing
        with open('simple_api_response.json', 'w', encoding='utf-8') as f:
            json.dump(simple_response, f, indent=2, ensure_ascii=False)
        
        print("\\nSimple API response saved to: simple_api_response.json")
        print("This should work perfectly with your frontend!")
        
        return simple_response
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_simple_response())