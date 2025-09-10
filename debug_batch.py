#!/usr/bin/env python3
"""Debug script to understand the batch API response format"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_batch_submission():
    username = os.getenv('SMARTPROXY_USERNAME')
    password = os.getenv('SMARTPROXY_PASSWORD')
    
    # Test with just 3 creators
    test_payload = {
        "query": ["_shafaqsfoodcam_", "Imaan.rehman", "narjesgram"],
        "target": "instagram_graphql_profile", 
        "parse": "true"
    }
    
    print("Testing batch submission...")
    print("Payload:", json.dumps(test_payload, indent=2))
    
    response = requests.post(
        "https://scraper-api.decodo.com/v2/task/batch",
        auth=(username, password),
        json=test_payload,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
    
    if response.status_code == 200:
        try:
            result = response.json()
            print(f"Response JSON: {json.dumps(result, indent=2)}")
        except json.JSONDecodeError:
            print("Could not decode JSON response")

if __name__ == "__main__":
    test_batch_submission()