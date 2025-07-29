"""
Test dashboard endpoint
"""
import requests
import json

def test_dashboard():
    """Test dashboard endpoint"""
    try:
        # 1. Login
        print("1. Logging in...")
        login_response = requests.post(
            "http://127.0.0.1:8000/api/v1/auth/login",
            json={
                "email": "client@analyticsfollowing.com",
                "password": "ClientPass2024!"
            },
            timeout=10
        )
        
        if login_response.status_code == 200:
            login_data = login_response.json()
            access_token = login_data["access_token"]
            print("SUCCESS: Login successful!")
            
            # 2. Test dashboard
            print("\n2. Testing dashboard...")
            dashboard_response = requests.get(
                "http://127.0.0.1:8000/api/v1/auth/dashboard",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if dashboard_response.status_code == 200:
                dashboard_data = dashboard_response.json()
                print("SUCCESS: Dashboard working!")
                print(f"   Total searches: {dashboard_data.get('total_searches')}")
                print(f"   Searches this month: {dashboard_data.get('searches_this_month')}")
                print(f"   Account created: {dashboard_data.get('account_created')}")
                print(f"   Recent searches: {len(dashboard_data.get('recent_searches', []))}")
            else:
                print(f"FAILED: Dashboard failed: {dashboard_response.status_code}")
                print(f"   Error: {dashboard_response.text}")
        else:
            print(f"FAILED: Login failed: {login_response.status_code}")
            print(f"   Error: {login_response.text}")
            
    except Exception as e:
        print(f"FAILED: Test failed: {e}")

if __name__ == "__main__":
    test_dashboard()