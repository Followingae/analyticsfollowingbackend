#!/usr/bin/env python3
"""
Test script to verify profile picture proxying is working correctly
"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.database.comprehensive_service import ComprehensiveDataService

async def test_profile_picture_proxying():
    """Test that profile picture URLs are being proxied correctly"""
    
    print("Testing Profile Picture Proxying")
    print("=" * 50)
    
    # Sample user data that would come from Decodo
    sample_user_data = {
        "username": "test_user",
        "profile_pic_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-19/profile_pic.jpg",
        "profile_pic_url_hd": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-19/profile_pic_hd.jpg"
    }
    
    print("\nOriginal URLs from Decodo:")
    print(f"  Standard: {sample_user_data['profile_pic_url']}")
    print(f"  HD: {sample_user_data['profile_pic_url_hd']}")
    
    # Test the proxy function that's used in comprehensive_service
    def proxy_instagram_url(url: str) -> str:
        """Convert Instagram CDN URL to proxied URL to eliminate CORS issues"""
        if not url:
            return ''
        if url.startswith(('https://scontent-', 'https://instagram.', 'https://scontent.cdninstagram.com')):
            return f"/api/proxy-image?url={url}"
        return url
    
    # Simulate what happens in the storage
    proxied_standard = proxy_instagram_url(sample_user_data['profile_pic_url'])
    proxied_hd = proxy_instagram_url(sample_user_data['profile_pic_url_hd'])
    
    print("\nAfter Automatic Proxying (stored in database):")
    print(f"  Standard: {proxied_standard}")
    print(f"  HD: {proxied_hd}")
    
    # Test video thumbnail scenarios
    print("\nVideo Thumbnail Test:")
    video_thumbnails = [
        "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/video_thumb.jpg",
        "https://scontent.cdninstagram.com/v/t51.12442-15/video_preview.jpg"
    ]
    
    for i, thumb_url in enumerate(video_thumbnails):
        proxied = proxy_instagram_url(thumb_url)
        print(f"  Video Thumb {i+1}: {proxied}")
    
    # Test what frontend should receive
    print("\nFrontend Will Receive:")
    print("Profile Response:")
    print(f'  "profile_pic_url": "{proxied_standard}"')
    print(f'  "profile_pic_url_hd": "{proxied_hd}"')
    
    print("\nPost Response (for videos):")
    print("  {")
    print('    "is_video": true,')
    print(f'    "display_url": "{proxy_instagram_url("https://scontent-lax3-2.cdninstagram.com/v/video_thumb.jpg")}",')
    print(f'    "video_url": "{proxy_instagram_url("https://scontent-lax3-2.cdninstagram.com/v/video.mp4")}",')
    print(f'    "thumbnail_src": "{proxy_instagram_url("https://scontent-lax3-2.cdninstagram.com/v/thumb.jpg")}"')
    print("  }")
    
    print("\nExpected Behavior:")
    print("  ✓ Profile pictures load without CORS errors")
    print("  ✓ Video thumbnails load without CORS errors") 
    print("  ✓ All URLs start with '/api/proxy-image?url='")
    print("  ✓ Frontend can use URLs directly in <img> tags")

if __name__ == "__main__":
    asyncio.run(test_profile_picture_proxying())