#!/usr/bin/env python3
"""
Test script to verify automatic image proxying during storage works correctly
"""
import asyncio
import json

async def test_image_proxying():
    """Test that Instagram URLs are automatically proxied during storage"""
    
    # Sample Instagram URLs that should be proxied
    test_urls = [
        "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/123456789_abcdef.jpg",
        "https://instagram.fxyz1-1.fna.fbcdn.net/v/t51.2885-15/123456789_abcdef.jpg",
        "https://scontent.cdninstagram.com/v/t51.2885-15/123456789_abcdef.jpg"
    ]
    
    # URLs that should NOT be proxied
    non_instagram_urls = [
        "https://example.com/image.jpg",
        "https://google.com/image.png",
        ""
    ]
    
    # Test the proxy function
    def proxy_instagram_url(url: str) -> str:
        """Convert Instagram CDN URL to proxied URL to eliminate CORS issues"""
        if not url:
            return ''
        
        # Only proxy Instagram CDN URLs
        if url.startswith(('https://scontent-', 'https://instagram.', 'https://scontent.cdninstagram.com')):
            # Return proxied URL that frontend can use directly
            return f"/api/v1/proxy-image?url={url}"
        return url
    
    print("Testing Image Proxying Logic")
    print("=" * 50)
    
    print("\nInstagram URLs (should be proxied):")
    for url in test_urls:
        proxied = proxy_instagram_url(url)
        is_proxied = proxied.startswith('/api/v1/proxy-image?url=')
        status = "PROXIED" if is_proxied else "NOT PROXIED"
        print(f"  {status}: {url}")
        print(f"    -> {proxied}")
    
    print("\nNon-Instagram URLs (should NOT be proxied):")
    for url in non_instagram_urls:
        proxied = proxy_instagram_url(url)
        is_unchanged = proxied == url
        status = "UNCHANGED" if is_unchanged else "INCORRECTLY MODIFIED"
        print(f"  {status}: {url}")
        if proxied != url:
            print(f"    -> {proxied}")
    
    print("\nSample Post Data Structure:")
    sample_post_node = {
        "id": "123456789",
        "shortcode": "ABC123def",
        "display_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/sample.jpg",
        "video_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/sample.mp4",
        "thumbnail_src": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/thumb.jpg",
        "thumbnail_resources": [
            {
                "src": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/thumb_150.jpg",
                "config_width": 150,
                "config_height": 150
            },
            {
                "src": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/thumb_320.jpg",
                "config_width": 320,
                "config_height": 320
            }
        ],
        "edge_sidecar_to_children": {
            "edges": [
                {
                    "node": {
                        "display_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/carousel1.jpg",
                        "is_video": False
                    }
                },
                {
                    "node": {
                        "display_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/carousel2.jpg",
                        "is_video": False
                    }
                }
            ]
        }
    }
    
    # Simulate the processing logic
    print("\nSimulated Post Processing:")
    main_display_url = proxy_instagram_url(sample_post_node.get('display_url', ''))
    main_video_url = proxy_instagram_url(sample_post_node.get('video_url', ''))
    thumbnail_src = proxy_instagram_url(sample_post_node.get('thumbnail_src', ''))
    
    print(f"  Main Image: {main_display_url}")
    print(f"  Video URL: {main_video_url}")
    print(f"  Thumbnail: {thumbnail_src}")
    
    # Process thumbnail resources
    print("\n  Thumbnail Resources:")
    for thumb in sample_post_node.get('thumbnail_resources', []):
        original_url = thumb.get('src', '')
        proxied_url = proxy_instagram_url(original_url)
        print(f"    {thumb.get('config_width')}x{thumb.get('config_height')}: {proxied_url}")
    
    # Process carousel items
    print("\n  Carousel Items:")
    carousel_edges = sample_post_node.get('edge_sidecar_to_children', {}).get('edges', [])
    for i, child_edge in enumerate(carousel_edges):
        child_node = child_edge.get('node', {})
        original_url = child_node.get('display_url', '')
        proxied_url = proxy_instagram_url(original_url)
        print(f"    Item {i+1}: {proxied_url}")
    
    print("\nExpected Frontend Behavior:")
    print("  - Frontend receives URLs like: /api/v1/proxy-image?url=https://scontent-...")
    print("  - No CORS issues when loading these URLs")
    print("  - Backend handles Instagram authentication transparently")
    print("  - Original URLs preserved in 'original_url' field for reference")

if __name__ == "__main__":
    asyncio.run(test_image_proxying())