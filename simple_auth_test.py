"""
Simple Authentication Test without emojis (Windows-compatible)
"""
import asyncio
import httpx
import json

async def test_auth_simple():
    base_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Health check
        print("=== TESTING BACKEND HEALTH ===")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Health Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Backend Status: {data.get('status')}")
                print(f"Auth Service: {data.get('services', {}).get('auth', {}).get('status')}")
        except Exception as e:
            print(f"Health check failed: {e}")
        
        # Test 2: Auth health
        print("\n=== TESTING AUTH SERVICE ===")
        try:
            response = await client.get(f"{base_url}/api/v1/auth/health")
            print(f"Auth Health Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Auth Status: {data.get('status')}")
                print(f"Initialized: {data.get('initialized')}")
        except Exception as e:
            print(f"Auth health check failed: {e}")
        
        # Test 3: Login attempt
        print("\n=== TESTING AUTHENTICATION ===")
        test_users = [
            {"email": "zzain.ali@outlook.com", "password": "BarakatDemo2024!"},
            {"email": "demo@prospectbrands.com", "password": "ProspectDemo2024!"}
        ]
        
        for user in test_users:
            print(f"\nTesting user: {user['email']}")
            try:
                response = await client.post(
                    f"{base_url}/api/v1/auth/login",
                    json=user,
                    headers={"Content-Type": "application/json"}
                )
                print(f"Login Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print("SUCCESS! Login worked!")
                    print(f"User: {data.get('user', {}).get('email')}")
                    print(f"Role: {data.get('user', {}).get('role')}")
                    print(f"Token: {data.get('access_token', '')[:20]}...")
                    return True
                else:
                    print(f"FAILED: {response.text}")
            except Exception as e:
                print(f"Login error: {e}")
        
        return False

if __name__ == "__main__":
    success = asyncio.run(test_auth_simple())
    print(f"\n=== FINAL RESULT ===")
    if success:
        print("AUTHENTICATION WORKING!")
    else:
        print("AUTHENTICATION NEEDS FIXING")