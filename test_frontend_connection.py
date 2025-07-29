"""
Test frontend connection with your specific URLs
"""
import requests
import json

def test_cors_for_your_frontends():
    """Test CORS for your specific frontend URLs"""
    print("TESTING CORS FOR YOUR FRONTEND URLs")
    print("=" * 50)
    
    backend_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    frontend_urls = [
        "https://analyticsfollowingfrontend.vercel.app",
        "https://analytics.following.ae",
        "https://analyticsfollowingfrontend-followingaes-projects.vercel.app"
    ]
    
    for frontend_url in frontend_urls:
        print(f"\\n[TEST] Testing CORS for: {frontend_url}")
        
        try:
            # Simulate browser preflight request
            headers = {
                'Origin': frontend_url,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
            
            response = requests.options(f"{backend_url}/api/v1/auth/login", headers=headers, timeout=10)
            
            print(f"  Status: {response.status_code}")
            
            cors_headers = {
                'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
            }
            
            print("  CORS Headers:")
            for header, value in cors_headers.items():
                print(f"    {header}: {value}")
            
            if cors_headers['Access-Control-Allow-Origin']:
                print("  [SUCCESS] CORS configured")
            else:
                print("  [ERROR] CORS missing")
                
        except Exception as e:
            print(f"  [ERROR] CORS test failed: {e}")

def test_backend_endpoints():
    """Test all backend endpoints"""
    print("\\nTESTING BACKEND ENDPOINTS")
    print("=" * 35)
    
    backend_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    endpoints = [
        {"path": "/", "method": "GET", "name": "Root"},
        {"path": "/health", "method": "GET", "name": "Health"},
        {"path": "/api/v1/auth/login", "method": "POST", "name": "Auth", "data": {
            "email": "zzain.ali@outlook.com",
            "password": "BarakatDemo2024!"
        }}
    ]
    
    for endpoint in endpoints:
        print(f"\\n[TEST] {endpoint['name']}: {endpoint['path']}")
        
        try:
            if endpoint['method'] == 'GET':
                response = requests.get(f"{backend_url}{endpoint['path']}", timeout=15)
            else:
                response = requests.post(
                    f"{backend_url}{endpoint['path']}", 
                    json=endpoint.get('data', {}),
                    timeout=15
                )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print("  [SUCCESS] Working")
                if endpoint['name'] == 'Auth':
                    print("  [SUCCESS] Demo login successful!")
            elif response.status_code == 504:
                print("  [ERROR] Timeout - Backend/Database issue")
            else:
                print(f"  [ERROR] Failed: {response.text[:100]}...")
                
        except requests.exceptions.Timeout:
            print("  [ERROR] Request timeout")
        except Exception as e:
            print(f"  [ERROR] Request failed: {e}")

def display_frontend_setup_guide():
    """Display frontend setup guide"""
    print(f"\\n{'='*60}")
    print("FRONTEND SETUP GUIDE")
    print(f"{'='*60}")
    
    print("\\n1. VERCEL ENVIRONMENT VARIABLES:")
    print("   Go to: https://vercel.com/dashboard")
    print("   Your Project > Settings > Environment Variables")
    print("   Add these:")
    print("   NEXT_PUBLIC_API_URL=https://analytics-following-backend-5qfwj.ondigitalocean.app")
    print("   NEXT_PUBLIC_API_BASE_URL=https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1")
    
    print("\\n2. REDEPLOY FRONTEND:")
    print("   After adding env vars, go to Deployments tab")
    print("   Click 'Redeploy' on latest deployment")
    
    print("\\n3. CHECK BROWSER NETWORK TAB:")
    print("   Open browser developer tools")
    print("   Go to Network tab")
    print("   Try to login and see the actual error")
    
    print("\\n4. COMMON ISSUES:")
    print("   - Environment variables not set")
    print("   - Frontend not redeployed after env var changes")
    print("   - Frontend code using wrong API URL")
    print("   - Browser cache (try incognito mode)")
    
    print("\\n5. DIGITALOCEAN BACKEND FIX:")
    print("   Your auth endpoint is timing out (504)")
    print("   Go to DigitalOcean Apps dashboard")
    print("   Check Runtime Logs for database connection errors")
    print("   Ensure environment variables are set")
    print("   Restart the app")
    
    print("\\nDEMO CREDENTIALS:")
    print("Email: zzain.ali@outlook.com")
    print("Password: BarakatDemo2024!")
    
    print(f"\\n{'='*60}")

def main():
    """Main test function"""
    test_cors_for_your_frontends()
    test_backend_endpoints()
    display_frontend_setup_guide()

if __name__ == "__main__":
    main()