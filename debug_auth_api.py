"""
Debug auth service during API requests
"""
import asyncio
import sys
import os
import requests
import json
sys.path.append(os.getcwd())

from app.services.auth_service import auth_service
from app.models.auth import LoginRequest

async def debug_auth_vs_api():
    """Debug difference between direct auth service and API"""
    print("=" * 80)
    print("AUTH SERVICE VS API DEBUG")
    print("=" * 80)
    
    base_url = "http://127.0.0.1:8000"
    test_credentials = {
        "email": "admin@analyticsfollowing.com",
        "password": "Admin123!@#"
    }
    
    try:
        # 1. Test direct auth service
        print("1. Testing direct auth service...")
        await auth_service.initialize()
        
        login_data = LoginRequest(
            email=test_credentials["email"],
            password=test_credentials["password"]
        )
        
        direct_response = await auth_service.login_user(login_data)
        print(f"SUCCESS: Direct auth service login successful!")
        print(f"   Access token: {direct_response.access_token[:50]}...")
        print(f"   User: {direct_response.user.email}")
        print(f"   Role: {direct_response.user.role}")
        
        # 2. Test API endpoint
        print("\n2. Testing API endpoint...")
        try:
            api_response = requests.post(
                f"{base_url}/api/v1/auth/login",
                json=test_credentials,
                timeout=10
            )
            
            if api_response.status_code == 200:
                api_data = api_response.json()
                print(f"SUCCESS: API login successful!")
                print(f"   Access token: {api_data.get('access_token', '')[:50]}...")
                print(f"   User: {api_data.get('user', {}).get('email')}")
                print(f"   Role: {api_data.get('user', {}).get('role')}")
            else:
                print(f"FAILED: API login failed: {api_response.status_code}")
                print(f"   Error: {api_response.text}")
                print(f"   Headers: {api_response.headers}")
                
        except requests.exceptions.ConnectionError:
            print("FAILED: Cannot connect to API server")
            print("   Server might not be running")
        
    except Exception as e:
        print(f"FAILED: Debug test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_auth_vs_api())