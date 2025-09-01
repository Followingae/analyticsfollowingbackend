#!/usr/bin/env python3
"""
Debug CORS Proxy Response
"""
import asyncio
import httpx

async def debug_corsproxy():
    """Debug CORS proxy response"""
    print("Debugging CORS Proxy Response...")
    print("-" * 40)
    
    # From .env file
    cors_proxy_url = "https://corsproxy.io"
    api_key = "b416e4ec"
    
    # Test Instagram URL
    instagram_url = "https://scontent-cdg4-1.cdninstagram.com/v/t51.2885-19/11850309_1674349799447611_206178162_a.jpg"
    
    # Try different API key methods
    test_urls = [
        f"{cors_proxy_url}/?{instagram_url}",
        f"{cors_proxy_url}/?key={api_key}&url={instagram_url}",
        f"{cors_proxy_url}/?api_key={api_key}&target={instagram_url}"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_url in enumerate(test_urls, 1):
            print(f"Test {i}: {test_url[:80]}...")
            
            try:
                response = await client.get(test_url)
                print(f"   Status: {response.status_code}")
                print(f"   Headers: {dict(response.headers)}")
                print(f"   Content: {response.text[:200]}...")
                print()
                
            except Exception as e:
                print(f"   Error: {e}")
                print()

if __name__ == "__main__":
    asyncio.run(debug_corsproxy())