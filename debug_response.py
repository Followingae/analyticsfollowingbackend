#!/usr/bin/env python3
"""Debug script to see the raw API response format"""

import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.append('.')
from app.scrapers.smartproxy_client import SmartProxyClient

async def debug_response():
    username = os.getenv('SMARTPROXY_USERNAME')
    password = os.getenv('SMARTPROXY_PASSWORD')
    
    if not username or not password:
        print("Missing credentials")
        return
    
    test_username = "_shafaqsfoodcam_"
    
    try:
        async with SmartProxyClient(username, password) as client:
            raw_data = await client.scrape_instagram_profile(test_username)
            
            # Save raw response for inspection
            with open('debug_response.json', 'w') as f:
                json.dump(raw_data, f, indent=2)
            
            print("Raw response saved to debug_response.json")
            print("Response keys:", list(raw_data.keys()) if isinstance(raw_data, dict) else "Not a dict")
            
            if 'results' in raw_data:
                print("Results found, length:", len(raw_data['results']) if raw_data['results'] else 0)
                if raw_data['results']:
                    print("First result keys:", list(raw_data['results'][0].keys()))
                    if 'content' in raw_data['results'][0]:
                        content = raw_data['results'][0]['content']
                        print("Content keys:", list(content.keys()) if isinstance(content, dict) else "Not a dict")
                        if isinstance(content, dict) and 'user' in content:
                            user = content['user']
                            print("User keys:", list(user.keys()) if isinstance(user, dict) else "Not a dict")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_response())