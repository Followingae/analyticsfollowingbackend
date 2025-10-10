#!/usr/bin/env python3
"""
EMERGENCY FIX: Call the admin endpoint to grant access to saharuuuuuuuu
"""

import requests
import json

def fix_access():
    """Call the emergency fix endpoint"""

    # Login as admin first to get auth token
    login_response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={
            "email": "zain@following.ae",
            "password": "Following0925_25"
        }
    )

    if login_response.status_code != 200:
        print(f"ERROR Login failed: {login_response.status_code}")
        print(login_response.text)
        return

    auth_token = login_response.json().get("access_token")
    print("LOGIN successful, got auth token")

    # Call the emergency fix endpoint
    fix_response = requests.post(
        "http://localhost:8000/api/v1/admin/system/fix/missing-access-record",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        params={
            "username": "saharuuuuuuuu",
            "user_email": "client@analyticsfollowing.com"
        }
    )

    print(f"Status: {fix_response.status_code}")
    print(f"Response: {json.dumps(fix_response.json(), indent=2)}")

if __name__ == "__main__":
    fix_access()