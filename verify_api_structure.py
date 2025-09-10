#!/usr/bin/env python3
"""
Verify API structure matches frontend expectations
"""
import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

async def verify_api_structure():
    """Verify the API response structure"""
    try:
        print("Verifying API response structure for frontend...")
        
        # Initialize database
        from app.database.connection import init_database, get_session
        await init_database()
        
        # Import services
        from app.services.cdn_image_service import CDNImageService
        from sqlalchemy import text
        
        test_username = "fit.bayann"
        
        async with get_session() as db:
            # Get profile
            result = await db.execute(text("""
                SELECT id, username, full_name, biography, followers_count, following_count, 
                       posts_count, is_verified, profile_pic_url
                FROM profiles WHERE username = :username
            """), {"username": test_username})
            
            profile_row = result.fetchone()
            if not profile_row:
                print(f"Profile not found: {test_username}")
                return
            
            profile_id = profile_row[0]
            
            # Get CDN service response
            cdn_service = CDNImageService()
            cdn_service.set_db_session(db)
            cdn_media = await cdn_service.get_profile_media_urls(profile_id)
            
            # Simulate the API response structure
            simulated_response = {
                "success": True,
                "profile": {
                    "username": profile_row[1],
                    "full_name": profile_row[2],
                    "biography": profile_row[3],
                    "followers_count": profile_row[4],
                    "following_count": profile_row[5],
                    "posts_count": profile_row[6],
                    "is_verified": profile_row[7],
                    # CDN-EXCLUSIVE URLs
                    "profile_pic_url": cdn_media.avatar_256 if cdn_media and cdn_media.avatar_256 else None,
                    "profile_pic_url_hd": cdn_media.avatar_512 if cdn_media and cdn_media.avatar_512 else None,
                    "cdn_urls": {
                        "avatar_256": cdn_media.avatar_256 if cdn_media else None,
                        "avatar_512": cdn_media.avatar_512 if cdn_media else None
                    },
                    "posts": []
                }
            }
            
            # Add posts with CDN URLs
            if cdn_media and cdn_media.posts:
                for post in cdn_media.posts[:5]:  # First 5 posts
                    post_data = {
                        "media_id": post['media_id'],
                        "display_url": post['cdn_url_256'],  # Primary thumbnail URL
                        "cdn_urls": {
                            "256": post['cdn_url_256'],
                            "512": post['cdn_url_512']
                        },
                        "cdn_available": post['available']
                    }
                    simulated_response["profile"]["posts"].append(post_data)
            
            # Print the response for frontend verification
            print(f"\n{'='*50}")
            print("API RESPONSE STRUCTURE FOR FRONTEND:")
            print(f"{'='*50}")
            print(json.dumps(simulated_response, indent=2, default=str))
            
            # Frontend integration summary
            print(f"\n{'='*50}")
            print("FRONTEND INTEGRATION SUMMARY:")
            print(f"{'='*50}")
            
            profile_pic_available = simulated_response["profile"]["profile_pic_url"] is not None
            posts_available = len(simulated_response["profile"]["posts"]) > 0
            posts_have_urls = posts_available and simulated_response["profile"]["posts"][0]["display_url"] is not None
            
            print(f"✅ Profile Picture CDN URL: {simulated_response['profile']['profile_pic_url']}")
            print(f"✅ Profile Picture HD CDN URL: {simulated_response['profile']['profile_pic_url_hd']}")
            print(f"✅ Posts with CDN URLs: {len(simulated_response['profile']['posts'])}")
            
            if posts_available:
                first_post = simulated_response["profile"]["posts"][0]
                print(f"✅ First Post Display URL: {first_post['display_url']}")
                print(f"✅ First Post CDN Available: {first_post['cdn_available']}")
            
            print(f"\nFRONTEND STATUS:")
            print(f"Profile Pictures: {'✅ READY' if profile_pic_available else '❌ NOT READY'}")
            print(f"Post Thumbnails: {'✅ READY' if posts_have_urls else '❌ NOT READY'}")
            
            if profile_pic_available and posts_have_urls:
                print(f"\nFRONTEND SHOULD NOW DISPLAY ALL IMAGES!")
                print(f"\nFrontend should use:")
                print(f"  • response.profile.profile_pic_url (for 256px avatars)")
                print(f"  • response.profile.profile_pic_url_hd (for 512px avatars)")
                print(f"  • post.display_url (for post thumbnails)")
                print(f"  • Check post.cdn_available before displaying")
            else:
                print(f"\n❌ Issues preventing frontend display")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_api_structure())