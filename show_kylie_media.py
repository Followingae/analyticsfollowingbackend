"""
Show all media URLs and content data for kyliejenner from Decodo
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
        print("\n📸 PROFILE PICTURE URLS:")
        print(f"Standard: {profile_data.get('profile_pic_url', 'N/A')}")
        print(f"HD Version: {profile_data.get('profile_pic_url_hd', 'N/A')}")
        
        # Show external URLs
        print(f"\n🔗 EXTERNAL LINKS:")
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
                            
                            print(f"\n🖼️ DETAILED PROFILE IMAGES:")
                            print(f"Profile Pic URL: {user_data.get('profile_pic_url', 'N/A')}")
                            print(f"Profile Pic HD: {user_data.get('profile_pic_url_hd', 'N/A')}")
                            
                            # Check bio links
                            bio_links = user_data.get('bio_links', [])
                            if bio_links:
                                print(f"\n🔗 BIO LINKS ({len(bio_links)} items):")
                                for i, link in enumerate(bio_links, 1):
                                    print(f"{i}. {json.dumps(link, indent=2)}")
                            
                            # Check external URL details
                            external_url = user_data.get('external_url')
                            external_shimmed = user_data.get('external_url_linkshimmed')
                            if external_url:
                                print(f"\n🌐 EXTERNAL URL DETAILS:")
                                print(f"Direct URL: {external_url}")
                                print(f"Instagram Shimmed: {external_shimmed}")
                            
                            # Check edge data for media content
                            print(f"\n📱 CONTENT COLLECTIONS & MEDIA:")
                            
                            # Timeline media (posts)
                            timeline_media = user_data.get('edge_owner_to_timeline_media', {})
                            if timeline_media and 'edges' in timeline_media:
                                posts = timeline_media['edges']
                                print(f"Timeline Posts: {timeline_media.get('count', 0)} total")
                                if posts:
                                    print(f"Sample posts (first 3):")
                                    for i, post in enumerate(posts[:3], 1):
                                        node = post.get('node', {})
                                        print(f"  Post {i}:")
                                        print(f"    ID: {node.get('id', 'N/A')}")
                                        print(f"    Shortcode: {node.get('shortcode', 'N/A')}")
                                        print(f"    Thumbnail: {node.get('display_url', 'N/A')}")
                                        print(f"    Is Video: {node.get('is_video', False)}")
                                        if node.get('is_video'):
                                            print(f"    Video URL: {node.get('video_url', 'N/A')}")
                                        print(f"    Caption: {node.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', 'N/A')[:100]}...")
                                        print()
                            
                            # Felix video timeline (Reels)
                            felix_videos = user_data.get('edge_felix_video_timeline', {})
                            if felix_videos and 'edges' in felix_videos:
                                reels = felix_videos['edges']
                                print(f"Reels: {felix_videos.get('count', 0)} total")
                                if reels:
                                    print(f"Sample reels (first 2):")
                                    for i, reel in enumerate(reels[:2], 1):
                                        node = reel.get('node', {})
                                        print(f"  Reel {i}:")
                                        print(f"    ID: {node.get('id', 'N/A')}")
                                        print(f"    Shortcode: {node.get('shortcode', 'N/A')}")
                                        print(f"    Thumbnail: {node.get('display_url', 'N/A')}")
                                        print(f"    Video URL: {node.get('video_url', 'N/A')}")
                                        print()
                            
                            # Media collections
                            media_collections = user_data.get('edge_media_collections', {})
                            print(f"Media Collections: {media_collections.get('count', 0)}")
                            
                            # Saved media
                            saved_media = user_data.get('edge_saved_media', {})
                            print(f"Saved Media: {saved_media.get('count', 0)}")
                            
                            # Check if there are any other media-related fields
                            print(f"\n🔍 OTHER MEDIA-RELATED FIELDS:")
                            media_fields = [k for k in user_data.keys() if any(term in k.lower() for term in ['url', 'pic', 'image', 'media', 'photo', 'video', 'thumbnail'])]
                            for field in media_fields:
                                value = user_data[field]
                                if isinstance(value, str) and len(value) > 100:
                                    display_value = value[:100] + "..."
                                else:
                                    display_value = value
                                print(f"{field}: {display_value}")
                        
                        # Check if there's any additional content in other parts of the response
                        print(f"\n📦 RAW RESPONSE STRUCTURE:")
                        print(f"Content keys: {list(result.get('content', {}).keys())}")
                        print(f"Data keys: {list(data.keys())}")
                        
                        # Check if there are any other media URLs in the response
                        def find_urls_recursive(obj, path=""):
                            urls = []
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    new_path = f"{path}.{key}" if path else key
                                    if isinstance(value, str) and ('http' in value or 'url' in key.lower()):
                                        urls.append((new_path, value))
                                    urls.extend(find_urls_recursive(value, new_path))
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    urls.extend(find_urls_recursive(item, f"{path}[{i}]"))
                            return urls
                        
                        all_urls = find_urls_recursive(result)
                        url_types = {}
                        for path, url in all_urls:
                            url_type = "unknown"
                            if "profile_pic" in path:
                                url_type = "profile_picture"
                            elif "display_url" in path:
                                url_type = "post_thumbnail"
                            elif "video_url" in path:
                                url_type = "video"
                            elif "external_url" in path:
                                url_type = "external_link"
                            elif "instagram.com" in url:
                                url_type = "instagram_media"
                            
                            if url_type not in url_types:
                                url_types[url_type] = []
                            url_types[url_type].append((path, url))
                        
                        print(f"\n🔗 ALL URLS BY TYPE:")
                        for url_type, urls in url_types.items():
                            print(f"\n{url_type.upper()} ({len(urls)} URLs):")
                            for path, url in urls[:5]:  # Show first 5 of each type
                                print(f"  {path}: {url[:80]}...")
                            if len(urls) > 5:
                                print(f"  ... and {len(urls) - 5} more")
                        
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