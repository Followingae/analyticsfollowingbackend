#!/usr/bin/env python3
"""Debug a single task submission and status"""

import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

def debug_single_task():
    username = os.getenv('SMARTPROXY_USERNAME')
    password = os.getenv('SMARTPROXY_PASSWORD')
    
    # Submit a single task
    payload = {
        "query": "_shafaqsfoodcam_",
        "target": "instagram_graphql_profile",
        "parse": True
    }
    
    print("Submitting task...")
    response = requests.post(
        "https://scraper-api.decodo.com/v2/task",
        auth=(username, password),
        json=payload,
        timeout=30
    )
    
    print(f"Submission Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        task_id = result.get('id')
        print(f"Task ID: {task_id}")
        print(f"Full response: {json.dumps(result, indent=2)}")
        
        # Check status immediately
        print(f"\nChecking status...")
        status_response = requests.get(
            f"https://scraper-api.decodo.com/v2/task/{task_id}",
            auth=(username, password),
            timeout=10
        )
        
        print(f"Status Check Status: {status_response.status_code}")
        if status_response.status_code == 200:
            status_result = status_response.json()
            print(f"Status: {json.dumps(status_result, indent=2)}")
        else:
            print(f"Status check failed: {status_response.text}")
            
        # Wait a bit and check again
        print(f"\nWaiting 30 seconds and checking again...")
        time.sleep(30)
        
        status_response2 = requests.get(
            f"https://scraper-api.decodo.com/v2/task/{task_id}",
            auth=(username, password),
            timeout=10
        )
        
        if status_response2.status_code == 200:
            status_result2 = status_response2.json()
            print(f"Status after 30s: {json.dumps(status_result2, indent=2)}")
            
            if status_result2.get('status') == 'done':
                print(f"\nTask completed! Getting results...")
                result_response = requests.get(
                    f"https://scraper-api.decodo.com/v2/task/{task_id}/results",
                    auth=(username, password),
                    timeout=30
                )
                
                if result_response.status_code == 200:
                    print("Results obtained successfully!")
                    with open('task_result.json', 'w') as f:
                        json.dump(result_response.json(), f, indent=2)
                    print("Results saved to task_result.json")
                else:
                    print(f"Results fetch failed: {result_response.status_code} - {result_response.text}")
        else:
            print(f"Second status check failed: {status_response2.text}")
    
    else:
        print(f"Task submission failed: {response.text}")

if __name__ == "__main__":
    debug_single_task()