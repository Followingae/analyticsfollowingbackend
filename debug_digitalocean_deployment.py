"""
Debug DigitalOcean deployment issues
"""
import requests
import time

def test_backend_thoroughly():
    """Test backend thoroughly to find exact issue"""
    print("COMPREHENSIVE BACKEND TESTING")
    print("=" * 50)
    
    backend_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    # Test all endpoints with timing
    endpoints = [
        {"path": "/", "timeout": 5, "name": "Root"},
        {"path": "/health", "timeout": 5, "name": "Health"}, 
        {"path": "/api", "timeout": 5, "name": "API Info"},
        {"path": "/api/v1/auth/login", "timeout": 30, "name": "Auth", "method": "POST", "data": {
            "email": "zzain.ali@outlook.com", 
            "password": "BarakatDemo2024!"
        }}
    ]
    
    for endpoint in endpoints:
        print(f"\n[TEST] {endpoint['name']}: {endpoint['path']}")
        print(f"  Timeout: {endpoint['timeout']}s")
        
        start_time = time.time()
        
        try:
            if endpoint.get('method') == 'POST':
                response = requests.post(
                    f"{backend_url}{endpoint['path']}", 
                    json=endpoint.get('data', {}),
                    timeout=endpoint['timeout']
                )
            else:
                response = requests.get(
                    f"{backend_url}{endpoint['path']}", 
                    timeout=endpoint['timeout']
                )
            
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            print(f"  Status: {response.status_code} ({duration}s)")
            
            if response.status_code == 200:
                print("  [SUCCESS] Working")
                if len(response.text) < 200:
                    print(f"  Response: {response.text}")
                else:
                    print(f"  Response: {response.text[:100]}...")
            elif response.status_code == 504:
                print("  [ERROR] Gateway timeout - App not responding")
                print("  This means:")
                print("    - App is deployed but not starting properly")
                print("    - Database connection hanging")
                print("    - App initialization failing")
            elif response.status_code == 502:
                print("  [ERROR] Bad gateway - App crashed")
            else:
                print(f"  [ERROR] Unexpected status")
                print(f"  Response: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            print(f"  [TIMEOUT] Request timed out after {duration}s")
            print("  This suggests the app is hanging during processing")
            
        except requests.exceptions.ConnectionError:
            print("  [ERROR] Connection refused - App not running")
            
        except Exception as e:
            print(f"  [ERROR] Request failed: {e}")

def check_app_startup():
    """Check if app is starting up properly"""
    print(f"\n{'='*50}")
    print("APP STARTUP DIAGNOSIS")
    print(f"{'='*50}")
    
    print("\nPOSSIBLE ISSUES:")
    print("1. DATABASE CONNECTION HANGING:")
    print("   - Supabase database URL incorrect")
    print("   - Database credentials expired")
    print("   - Network connectivity issues")
    
    print("\n2. APP INITIALIZATION FAILING:")
    print("   - Missing environment variables")
    print("   - Python dependencies missing")
    print("   - Code errors during startup")
    
    print("\n3. DIGITALOCEAN PLATFORM ISSUES:")
    print("   - Resource limits exceeded")
    print("   - App platform issues")
    print("   - Build/deployment problems")
    
    print("\nDEBUGGING STEPS:")
    print("1. Check DigitalOcean App Logs:")
    print("   - Go to DigitalOcean Dashboard")
    print("   - Apps → Your App → Runtime Logs")
    print("   - Look for startup errors")
    
    print("\n2. Verify Environment Variables:")
    print("   - Ensure all required vars are set")
    print("   - Check for typos in DATABASE_URL")
    print("   - Verify Supabase credentials")
    
    print("\n3. Test Database Connection:")
    print("   - Try connecting to your database directly")
    print("   - Check if Supabase is accessible")
    
    print("\n4. Restart App:")
    print("   - Force restart the DigitalOcean app")
    print("   - Or redeploy from latest commit")

def display_immediate_actions():
    """Display immediate actions to take"""
    print(f"\n{'='*50}")
    print("IMMEDIATE ACTIONS TO TAKE")
    print(f"{'='*50}")
    
    print("\n1. CHECK DIGITALOCEAN LOGS RIGHT NOW:")
    print("   Go to: https://cloud.digitalocean.com/apps")
    print("   Your App → Runtime Logs")
    print("   Look for errors during app startup")
    
    print("\n2. RESTART YOUR DIGITALOCEAN APP:")
    print("   In DigitalOcean dashboard:")
    print("   Apps → Your App → Settings → General")
    print("   Click 'Restart App'")
    
    print("\n3. CHECK DATABASE CONNECTION:")
    print("   Your DATABASE_URL might be wrong")
    print("   Test it separately or check Supabase dashboard")
    
    print("\n4. TEMPORARY WORKAROUND:")
    print("   If nothing else works, we can:")
    print("   - Deploy a simpler version without database")
    print("   - Use mock data temporarily")
    print("   - Debug step by step")
    
    print("\nWHAT TO LOOK FOR IN LOGS:")
    print("- 'Database connection failed'")
    print("- 'Module not found' errors") 
    print("- 'Environment variable not set'")
    print("- Any Python tracebacks")
    
    print(f"\n{'='*50}")
    print("Your app works partially (root/health) but auth fails.")
    print("This suggests a database connection issue during auth.")
    print("Check the logs first - that will tell us exactly what's wrong!")
    print(f"{'='*50}")

def main():
    """Main debug function"""
    test_backend_thoroughly()
    check_app_startup()
    display_immediate_actions()

if __name__ == "__main__":
    main()