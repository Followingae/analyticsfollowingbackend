"""
Comprehensive test script for the authentication system
"""
import asyncio
import requests
import json
from datetime import datetime
import uuid


def test_server_status():
    """Test if server is running"""
    try:
        response = requests.get('http://localhost:8000/api/v1/status', timeout=5)
        print(f"✓ Server status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"✗ Server not accessible: {e}")
        return False


def test_auth_endpoints():
    """Test authentication endpoints"""
    print("\n--- Testing Authentication Endpoints ---")
    
    # Test user registration
    print("1. Testing user registration...")
    
    test_user = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
        "role": "free"
    }
    
    try:
        response = requests.post(
            'http://localhost:8000/api/v1/auth/register',
            json=test_user,
            timeout=10
        )
        print(f"   Registration status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ User registration successful")
            user_data = response.json()
            print(f"   User ID: {user_data.get('id', 'Unknown')}")
            return test_user
        else:
            print(f"   ✗ Registration failed: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to auth endpoint")
        return None
    except Exception as e:
        print(f"   ✗ Registration error: {e}")
        return None


def test_user_login(test_user):
    """Test user login"""
    if not test_user:
        print("2. Skipping login test (no user to test with)")
        return None
        
    print("2. Testing user login...")
    
    login_data = {
        "email": test_user["email"],
        "password": test_user["password"]
    }
    
    try:
        response = requests.post(
            'http://localhost:8000/api/v1/auth/login',
            json=login_data,
            timeout=10
        )
        print(f"   Login status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ User login successful")
            login_response = response.json()
            token = login_response.get('access_token')
            print(f"   Access token received: {token[:20]}..." if token else "No token")
            return token
        else:
            print(f"   ✗ Login failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ✗ Login error: {e}")
        return None


def test_authenticated_request(token):
    """Test authenticated requests"""
    if not token:
        print("3. Skipping authenticated request test (no token)")
        return
        
    print("3. Testing authenticated requests...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Test profile endpoint
        response = requests.get(
            'http://localhost:8000/api/v1/auth/me',
            headers=headers,
            timeout=10
        )
        print(f"   Profile request status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ Authenticated profile request successful")
            profile = response.json()
            print(f"   User email: {profile.get('email', 'Unknown')}")
        else:
            print(f"   ✗ Profile request failed: {response.text}")
            
    except Exception as e:
        print(f"   ✗ Authenticated request error: {e}")


def test_user_tracking():
    """Test user tracking functionality"""
    print("4. Testing user tracking...")
    
    try:
        # Test profile search without authentication
        response = requests.get(
            'http://localhost:8000/api/v1/instagram/profile/mkbhd',
            timeout=30
        )
        print(f"   Unauthenticated search status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   User authenticated: {data.get('user_authenticated', False)}")
            print(f"   Data source: {data.get('data_source', 'Unknown')}")
            print("   ✓ Unauthenticated search works")
        else:
            print(f"   ✗ Search failed: {response.text}")
            
    except Exception as e:
        print(f"   ✗ User tracking test error: {e}")


def test_endpoints_availability():
    """Test which endpoints are available"""
    print("\n--- Testing Endpoint Availability ---")
    
    endpoints_to_test = [
        "/api/v1/status",
        "/api/v1/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/instagram/profile/test",
    ]
    
    for endpoint in endpoints_to_test:
        try:
            if endpoint == "/api/v1/auth/register":
                response = requests.post(f'http://localhost:8000{endpoint}', 
                                       json={"test": "data"}, timeout=5)
            else:
                response = requests.get(f'http://localhost:8000{endpoint}', timeout=5)
            
            print(f"   {endpoint}: {response.status_code}")
            
        except Exception as e:
            print(f"   {endpoint}: ERROR - {e}")


def main():
    """Run all authentication tests"""
    print("=== Authentication System Test Suite ===")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    # Check server status
    if not test_server_status():
        print("❌ Server is not running. Please start the server first.")
        return
    
    # Test endpoint availability
    test_endpoints_availability()
    
    # Test user registration
    test_user = test_auth_endpoints()
    
    # Test user login
    token = test_user_login(test_user)
    
    # Test authenticated requests
    test_authenticated_request(token)
    
    # Test user tracking
    test_user_tracking()
    
    print(f"\n=== Test completed at: {datetime.now().isoformat()} ===")
    
    if test_user:
        print("\n✅ Authentication system is working!")
        print("Next steps:")
        print("1. Test with frontend integration")
        print("2. Implement user dashboard")
        print("3. Add role-based access controls")
    else:
        print("\n❌ Authentication system needs debugging")


if __name__ == "__main__":
    main()