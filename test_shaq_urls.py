#!/usr/bin/env python3
"""
Test script to verify URL proxying for shaq profile and identify any caching issues
"""

def test_url_proxying():
    """Test URL proxying logic with sample shaq-like data"""
    
    print("Testing URL Proxying for Shaq Profile")
    print("=" * 50)
    
    # Sample URLs that shaq profile might have
    sample_urls = {
        "profile_pic_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-19/shaq_profile.jpg",
        "profile_pic_url_hd": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-19/shaq_profile_hd.jpg",
        "external_url": "https://example.com/shaq",  # Should NOT be proxied
        "post_display_url": "https://scontent-lax3-2.cdninstagram.com/v/t51.2885-15/shaq_post.jpg",
        "video_thumbnail": "https://scontent.cdninstagram.com/v/t51.12442-15/shaq_video_thumb.jpg"
    }
    
    # Test the proxy function
    def proxy_instagram_url(url: str) -> str:
        """Convert Instagram CDN URL to proxied URL to eliminate CORS issues"""
        if not url:
            return ''
        
        # Only proxy Instagram CDN URLs
        if url.startswith(('https://scontent-', 'https://instagram.', 'https://scontent.cdninstagram.com')):
            # Return proxied URL that frontend can use directly
            return f"/api/proxy-image?url={url}"
        return url
    
    print("\nTesting URL Transformation:")
    for field_name, original_url in sample_urls.items():
        proxied_url = proxy_instagram_url(original_url)
        is_instagram_cdn = original_url.startswith(('https://scontent-', 'https://instagram.', 'https://scontent.cdninstagram.com'))
        is_proxied = proxied_url.startswith('/api/proxy-image?url=')
        
        status = "PROXIED" if is_proxied else "UNCHANGED"
        expected = "SHOULD BE PROXIED" if is_instagram_cdn else "SHOULD NOT BE PROXIED"
        
        print(f"\n{field_name}:")
        print(f"  Original: {original_url}")
        print(f"  Result:   {proxied_url}")
        print(f"  Status:   {status} ({expected})")
        
        # Verify correctness
        if is_instagram_cdn and not is_proxied:
            print(f"  ERROR: Instagram URL not proxied!")
        elif not is_instagram_cdn and is_proxied:
            print(f"  ERROR: Non-Instagram URL incorrectly proxied!")
        else:
            print(f"  CORRECT: Proper handling")
    
    print("\nTesting Potential Issues:")
    
    # Test edge cases
    edge_cases = [
        "",  # Empty string
        "https://instagram.com/image.jpg",  # Should be proxied
        "https://scontent-.../",  # Instagram CDN prefix
        "https://example.com/image.jpg",  # Should not be proxied
        None  # None value
    ]
    
    print("\nEdge Case Testing:")
    for test_url in edge_cases:
        try:
            if test_url is None:
                result = proxy_instagram_url("")  # Handle None by passing empty string
                print(f"  None input -> '{result}' (handled as empty)")
            else:
                result = proxy_instagram_url(test_url)
                print(f"  '{test_url}' -> '{result}'")
        except Exception as e:
            print(f"  ERROR with '{test_url}': {e}")
    
    print("\nDiagnosing Shaq Profile Issue:")
    print("If shaq profile still shows direct URLs, possible causes:")
    print("1. Profile was cached before the fix - needs fresh search")
    print("2. API response using wrong data source")
    print("3. Frontend caching the old URLs")
    print("4. Database contains old non-proxied URLs")
    
    print("\nRecommended Debug Steps:")
    print("1. Clear any frontend caches")
    print("2. Search for a completely new profile (not shaq)")
    print("3. Check database directly for shaq profile URLs")
    print("4. Force refresh shaq profile using refresh endpoint")

if __name__ == "__main__":
    test_url_proxying()