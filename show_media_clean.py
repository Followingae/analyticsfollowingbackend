"""
Show all media URLs and content data for kyliejenner from Decodo (Unicode-safe)
"""
import asyncio
import json
from app.database.postgres_direct import postgres_direct


async def show_kyliejenner_media():
    """Display all media URLs and content for kyliejenner from Decodo"""
    try:
        print("Connecting to database...")
        await postgres_direct.init()
        
        print("Fetching kyliejenner media data...")
        profile_data = await postgres_direct.get_profile('kyliejenner')
        
        if not profile_data:
            print("No data found for kyliejenner in database")
            return
        
        print("\n" + "="*80)
        print("KYLIEJENNER - ALL MEDIA URLS & CONTENT FROM DECODO")
        print("="*80)
        
        # Show profile picture URLs
        print("\nPROFILE PICTURE URLS:")
        print(f"Standard: {profile_data.get('profile_pic_url', 'N/A')}")
        print(f"HD Version: {profile_data.get('profile_pic_url_hd', 'N/A')}")
        
        # Show external URLs
        print(f"\nEXTERNAL LINKS:")
        print(f"Website: {profile_data.get('external_url', 'N/A')}")
        
        # Parse raw data to get more detailed content
        raw_data = profile_data.get('raw_data')
        if raw_data:
            try:
                if isinstance(raw_data, str):
                    raw_json = json.loads(raw_data)
                else:
                    raw_json = raw_data
                
                if 'results' in raw_json and raw_json['results']:
                    result = raw_json['results'][0]
                    if 'content' in result and 'data' in result['content']:
                        data = result['content']['data']
                        
                        if 'user' in data:
                            user_data = data['user']
                            
                            print(f"\nDETAILED PROFILE IMAGES:")
                            print(f"Profile Pic URL: {user_data.get('profile_pic_url', 'N/A')}")
                            print(f"Profile Pic HD: {user_data.get('profile_pic_url_hd', 'N/A')}")
                            
                            # Check bio links
                            bio_links = user_data.get('bio_links', [])
                            if bio_links:
                                print(f"\nBIO LINKS ({len(bio_links)} items):")
                                for i, link in enumerate(bio_links, 1):
                                    print(f"{i}. {json.dumps(link, indent=2)}")
                            
                            # Check external URL details
                            external_url = user_data.get('external_url')
                            external_shimmed = user_data.get('external_url_linkshimmed')
                            if external_url:
                                print(f"\nEXTERNAL URL DETAILS:")
                                print(f"Direct URL: {external_url}")
                                print(f"Instagram Shimmed: {external_shimmed}")
                            
                            # Check edge data for media content
                            print(f"\nCONTENT COLLECTIONS & MEDIA:")
                            
                            # Timeline media (posts)
                            timeline_media = user_data.get('edge_owner_to_timeline_media', {})
                            if timeline_media:
                                print(f"Timeline Posts: {timeline_media.get('count', 0)} total")
                                
                                if 'edges' in timeline_media and timeline_media['edges']:
                                    posts = timeline_media['edges']
                                    print(f"\nSample posts (first 3 with thumbnails):")
                                    for i, post in enumerate(posts[:3], 1):
                                        node = post.get('node', {})
                                        print(f"  Post {i}:")
                                        print(f"    ID: {node.get('id', 'N/A')}")
                                        print(f"    Shortcode: {node.get('shortcode', 'N/A')}")
                                        print(f"    Thumbnail URL: {node.get('display_url', 'N/A')}")
                                        print(f"    Thumbnail Resources: {len(node.get('thumbnail_resources', []))} sizes")
                                        print(f"    Is Video: {node.get('is_video', False)}")
                                        if node.get('is_video'):
                                            print(f"    Video URL: {node.get('video_url', 'N/A')}")
                                        
                                        # Show thumbnail resources
                                        thumbnails = node.get('thumbnail_resources', [])
                                        if thumbnails:
                                            print(f"    Thumbnail sizes:")
                                            for thumb in thumbnails:
                                                print(f"      {thumb.get('config_width', 'N/A')}x{thumb.get('config_height', 'N/A')}: {thumb.get('src', 'N/A')}")
                                        
                                        # Show caption
                                        caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
                                        if caption_edges:
                                            caption = caption_edges[0].get('node', {}).get('text', 'N/A')
                                            print(f"    Caption: {caption[:100]}...")
                                        print()
                            
                            # Felix video timeline (Reels)
                            felix_videos = user_data.get('edge_felix_video_timeline', {})
                            if felix_videos:
                                print(f"Reels: {felix_videos.get('count', 0)} total")
                                if 'edges' in felix_videos and felix_videos['edges']:
                                    reels = felix_videos['edges']
                                    print(f"\nSample reels (first 2):")
                                    for i, reel in enumerate(reels[:2], 1):
                                        node = reel.get('node', {})
                                        print(f"  Reel {i}:")
                                        print(f"    ID: {node.get('id', 'N/A')}")
                                        print(f"    Shortcode: {node.get('shortcode', 'N/A')}")
                                        print(f"    Thumbnail: {node.get('display_url', 'N/A')}")
                                        print(f"    Video URL: {node.get('video_url', 'N/A')}")
                                        print(f"    Video Duration: {node.get('video_duration', 'N/A')}")
                                        print()
                            
                            # Media collections
                            media_collections = user_data.get('edge_media_collections', {})
                            print(f"Media Collections: {media_collections.get('count', 0)}")
                            
                            # Saved media
                            saved_media = user_data.get('edge_saved_media', {})
                            print(f"Saved Media: {saved_media.get('count', 0)}")
                            
                            # Check for highlight reels
                            print(f"Story Highlights: {user_data.get('highlight_reel_count', 0)}")
                            
                            # Find all media-related fields
                            print(f"\nALL MEDIA-RELATED FIELDS:")
                            media_fields = []
                            for key, value in user_data.items():
                                if any(term in key.lower() for term in ['url', 'pic', 'image', 'media', 'photo', 'video', 'thumbnail', 'display']):
                                    media_fields.append((key, value))
                            
                            for field, value in media_fields:
                                if isinstance(value, str) and len(value) > 100:
                                    display_value = value[:100] + "..."
                                elif isinstance(value, (dict, list)):
                                    display_value = f"{type(value).__name__} with {len(value)} items"
                                else:
                                    display_value = value
                                print(f"  {field}: {display_value}")
                        
                        # Recursive URL finder
                        def find_all_urls(obj, path="", max_depth=5):
                            if max_depth <= 0:
                                return []
                            
                            urls = []
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    new_path = f"{path}.{key}" if path else key
                                    if isinstance(value, str) and ('http' in value or '.jpg' in value or '.mp4' in value):
                                        urls.append((new_path, value))
                                    elif isinstance(value, (dict, list)):
                                        urls.extend(find_all_urls(value, new_path, max_depth - 1))
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj[:3]):  # Limit to first 3 items in lists
                                    new_path = f"{path}[{i}]"
                                    urls.extend(find_all_urls(item, new_path, max_depth - 1))
                            return urls
                        
                        all_urls = find_all_urls(user_data)
                        
                        # Categorize URLs
                        url_categories = {
                            'profile_pictures': [],
                            'post_thumbnails': [],
                            'video_urls': [],
                            'external_links': [],
                            'other_media': []
                        }
                        
                        for path, url in all_urls:
                            if 'profile_pic' in path:
                                url_categories['profile_pictures'].append((path, url))
                            elif 'display_url' in path or 'thumbnail' in path:
                                url_categories['post_thumbnails'].append((path, url))
                            elif 'video_url' in path or '.mp4' in url:
                                url_categories['video_urls'].append((path, url))
                            elif 'external_url' in path:
                                url_categories['external_links'].append((path, url))
                            else:
                                url_categories['other_media'].append((path, url))
                        
                        print(f"\nURL SUMMARY BY CATEGORY:")
                        for category, urls in url_categories.items():
                            if urls:
                                print(f"\n{category.upper().replace('_', ' ')} ({len(urls)} URLs):")
                                for path, url in urls[:3]:  # Show first 3
                                    print(f"  {url[:80]}...")
                                if len(urls) > 3:
                                    print(f"  ... and {len(urls) - 3} more URLs")
                        
                        print(f"\nTOTAL MEDIA URLS FOUND: {len(all_urls)}")
                        
            except json.JSONDecodeError as e:
                print(f"Error parsing raw data: {e}")
        else:
            print("No raw data available")
            
    except Exception as e:
        print(f"Error retrieving data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(show_kyliejenner_media())