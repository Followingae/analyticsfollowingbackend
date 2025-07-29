"""
Fresh Decodo API search for leomessi - show raw datapoints directly from API
"""
import asyncio
import json
import sys
import os
sys.path.append(os.getcwd())

from app.scrapers.enhanced_decodo_client import EnhancedDecodoClient
from app.core.config import settings


async def fresh_decodo_search():
    """Run fresh Decodo search for leomessi and show raw response"""
    try:
        print("="*80)
        print("FRESH DECODO API SEARCH FOR LEOMESSI")
        print("="*80)
        print("Starting fresh Decodo API call...")
        
        # Create Decodo client
        async with EnhancedDecodoClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as decodo_client:
            
            print(f"Using Decodo credentials: {settings.SMARTPROXY_USERNAME}")
            print("Making API call to Decodo...")
            
            # Get raw response directly from Decodo
            raw_response = await decodo_client.get_instagram_profile_comprehensive("leomessi")
            
            print("Raw response received from Decodo API")
            print(f"Response type: {type(raw_response)}")
            
            # Show raw response structure
            if isinstance(raw_response, dict):
                print(f"Top-level keys: {list(raw_response.keys())}")
                
                # Navigate to user data
                if 'results' in raw_response and raw_response['results']:
                    result = raw_response['results'][0]
                    print(f"First result keys: {list(result.keys())}")
                    
                    # Show API metadata
                    print(f"\nAPI METADATA:")
                    print(f"Query: {result.get('query', 'N/A')}")
                    print(f"Status Code: {result.get('status_code', 'N/A')}")
                    print(f"Task ID: {result.get('task_id', 'N/A')}")
                    print(f"Created: {result.get('created_at', 'N/A')}")
                    print(f"Updated: {result.get('updated_at', 'N/A')}")
                    
                    if 'content' in result:
                        content = result['content']
                        print(f"Content keys: {list(content.keys())}")
                        print(f"Content status: {content.get('status', 'N/A')}")
                        
                        if 'data' in content:
                            data = content['data']
                            print(f"Data keys: {list(data.keys())}")
                            
                            if 'user' in data:
                                user_data = data['user']
                                
                                print(f"\n" + "="*80)
                                print(f"LEOMESSI - RAW USER DATA FROM DECODO API")
                                print(f"="*80)
                                print(f"Total fields in user object: {len(user_data)}")
                                
                                # Show basic profile info first
                                print(f"\nBASIC PROFILE INFO:")
                                basic_fields = ['id', 'username', 'full_name', 'biography', 'category_name']
                                for field in basic_fields:
                                    if field in user_data:
                                        value = user_data[field]
                                        if isinstance(value, str) and len(value) > 100:
                                            display_value = value[:100] + "..."
                                        else:
                                            display_value = value
                                        print(f"  {field}: {display_value}")
                                
                                # Show follower stats
                                print(f"\nFOLLOWER STATS:")
                                stats_fields = ['edge_followed_by', 'edge_follow', 'edge_owner_to_timeline_media']
                                for field in stats_fields:
                                    if field in user_data and isinstance(user_data[field], dict):
                                        count = user_data[field].get('count', 0)
                                        print(f"  {field}: {count:,}")
                                
                                # Show profile picture URLs
                                print(f"\nPROFILE PICTURE URLS:")
                                pic_fields = ['profile_pic_url', 'profile_pic_url_hd']
                                for field in pic_fields:
                                    if field in user_data:
                                        url = user_data[field]
                                        print(f"  {field}: {url}")
                                
                                # Show external URLs
                                print(f"\nEXTERNAL URLS:")
                                url_fields = ['external_url', 'external_url_linkshimmed']
                                for field in url_fields:
                                    if field in user_data:
                                        url = user_data[field]
                                        print(f"  {field}: {url}")
                                
                                # Show bio links
                                bio_links = user_data.get('bio_links', [])
                                if bio_links:
                                    print(f"\nBIO LINKS ({len(bio_links)} items):")
                                    for i, link in enumerate(bio_links, 1):
                                        print(f"  Link {i}: {json.dumps(link, indent=4)}")
                                
                                # Show ALL datapoints
                                print(f"\n" + "="*80)
                                print(f"ALL {len(user_data)} RAW DATAPOINTS FROM DECODO:")
                                print(f"="*80)
                                
                                for i, (key, value) in enumerate(sorted(user_data.items()), 1):
                                    if isinstance(value, dict):
                                        if 'count' in value:
                                            display_value = f"Edge object (count: {value.get('count', 0):,})"
                                        else:
                                            display_value = f"Dict with {len(value)} keys: {list(value.keys())[:3]}..."
                                    elif isinstance(value, list):
                                        display_value = f"List with {len(value)} items"
                                    elif isinstance(value, str) and len(value) > 80:
                                        display_value = value[:80] + "..."
                                    else:
                                        display_value = value
                                    
                                    print(f"{i:2d}. {key}: {display_value}")
                                
                                # Check for media content in posts
                                timeline_media = user_data.get('edge_owner_to_timeline_media', {})
                                if timeline_media and 'edges' in timeline_media:
                                    posts = timeline_media['edges'][:2]  # First 2 posts
                                    print(f"\nSAMPLE POST MEDIA URLS (first 2 posts):")
                                    for i, post in enumerate(posts, 1):
                                        node = post.get('node', {})
                                        print(f"\n  POST {i}:")
                                        print(f"    ID: {node.get('id', 'N/A')}")
                                        print(f"    Shortcode: {node.get('shortcode', 'N/A')}")
                                        print(f"    Display URL: {node.get('display_url', 'N/A')}")
                                        print(f"    Is Video: {node.get('is_video', False)}")
                                        
                                        # Show thumbnail resources
                                        thumbnails = node.get('thumbnail_resources', [])
                                        if thumbnails:
                                            print(f"    Thumbnail Resources ({len(thumbnails)} sizes):")
                                            for thumb in thumbnails:
                                                config_w = thumb.get('config_width', 'N/A')
                                                config_h = thumb.get('config_height', 'N/A')
                                                src = thumb.get('src', 'N/A')
                                                print(f"      {config_w}x{config_h}: {src}")
                                        
                                        if node.get('is_video'):
                                            print(f"    Video URL: {node.get('video_url', 'N/A')}")
                                
                                print(f"\n" + "="*80)
                                print(f"RAW JSON RESPONSE STRUCTURE:")
                                print(f"="*80)
                                print(f"Full response size: {len(json.dumps(raw_response))} characters")
                                print(f"User data size: {len(json.dumps(user_data))} characters")
                                
                                # Save raw response to file for inspection
                                with open('leomessi_raw_decodo_response.json', 'w', encoding='utf-8') as f:
                                    json.dump(raw_response, f, indent=2, ensure_ascii=False)
                                print(f"Full raw response saved to: leomessi_raw_decodo_response.json")
                            
                            else:
                                print("No 'user' key found in data")
                        else:
                            print("No 'data' key found in content")
                    else:
                        print("No 'content' key found in result")
                else:
                    print("No 'results' found in response")
            else:
                print(f"Unexpected response format: {type(raw_response)}")
                print(f"Response: {raw_response}")
            
    except Exception as e:
        print(f"Error in fresh Decodo search: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(fresh_decodo_search())