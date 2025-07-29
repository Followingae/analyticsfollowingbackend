"""
Test what User ID is returned from JWT token
"""
import asyncio
import httpx
import json

async def test_token_user_id():
    base_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login first
        login_response = await client.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": "demo@prospectbrands.com", "password": "ProspectDemo2024!"},
            headers={"Content-Type": "application/json"}
        )
        
        if login_response.status_code == 200:
            login_data = login_response.json()
            token = login_data.get("access_token")
            user_from_login = login_data.get("user", {})
            
            print("LOGIN USER DATA:")
            print(f"  ID: {user_from_login.get('id')}")
            print(f"  Email: {user_from_login.get('email')}")
            print(f"  Role: {user_from_login.get('role')}")
            
            # Test /me endpoint to see what user ID is returned from token
            me_response = await client.get(
                f"{base_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if me_response.status_code == 200:
                me_data = me_response.json()
                print("\n/ME ENDPOINT USER DATA:")
                print(f"  ID: {me_data.get('id')}")
                print(f"  Email: {me_data.get('email')}")
                print(f"  Role: {me_data.get('role')}")
                
                # Compare IDs
                login_id = user_from_login.get('id')
                me_id = me_data.get('id')
                
                print(f"\nID COMPARISON:")
                print(f"  Login ID: {login_id}")
                print(f"  /me ID: {me_id}")
                print(f"  IDs Match: {login_id == me_id}")
                
                # Expected database user ID (from our previous check)
                expected_db_id = "7d3e66b3-cf04-42e6-980e-4aa8ce662be6"
                print(f"  Expected DB ID: {expected_db_id}")
                print(f"  Login ID matches DB: {login_id == expected_db_id}")
                print(f"  /me ID matches DB: {me_id == expected_db_id}")
                
            else:
                print(f"/me endpoint failed: {me_response.text}")
        else:
            print(f"Login failed: {login_response.text}")

if __name__ == "__main__":
    asyncio.run(test_token_user_id())