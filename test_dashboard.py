"""
Test Dashboard Functionality
"""
import asyncio
import httpx
import json

async def test_dashboard():
    base_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login first
        print("=== TESTING LOGIN ===")
        try:
            login_response = await client.post(
                f"{base_url}/api/v1/auth/login",
                json={"email": "demo@prospectbrands.com", "password": "ProspectDemo2024!"},
                headers={"Content-Type": "application/json"}
            )
            
            if login_response.status_code == 200:
                login_data = login_response.json()
                token = login_data.get("access_token")
                print("LOGIN SUCCESS!")
                print(f"User: {login_data.get('user', {}).get('email')}")
                print(f"Role: {login_data.get('user', {}).get('role')}")
                print(f"Token: {token[:20]}...")
                
                # Test dashboard
                print("\n=== TESTING DASHBOARD ===")
                dashboard_response = await client.get(
                    f"{base_url}/api/v1/auth/dashboard",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                print(f"Dashboard Status: {dashboard_response.status_code}")
                if dashboard_response.status_code == 200:
                    dashboard_data = dashboard_response.json()
                    print("DASHBOARD SUCCESS!")
                    print(f"Total Searches: {dashboard_data.get('total_searches')}")
                    print(f"Searches This Month: {dashboard_data.get('searches_this_month')}")
                    print(f"Favorite Profiles: {dashboard_data.get('favorite_profiles')}")
                    print(f"Recent Searches: {len(dashboard_data.get('recent_searches', []))}")
                    print(f"Account Created: {dashboard_data.get('account_created')}")
                    return True
                else:
                    print(f"DASHBOARD FAILED: {dashboard_response.text}")
                    return False
            else:
                print(f"LOGIN FAILED: {login_response.text}")
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_dashboard())
    print(f"\n=== RESULT ===")
    if success:
        print("DASHBOARD IS WORKING!")
    else:
        print("DASHBOARD NEEDS FIXING")