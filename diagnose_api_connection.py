"""
Diagnose API connection issues for frontend
"""
import asyncio
import sys
import os
import requests
from datetime import datetime
sys.path.append(os.getcwd())

from app.core.config import settings

def check_local_api():
    """Check if API is running locally"""
    try:
        print("[CHECK] Testing local API connection...")
        response = requests.get("http://localhost:8000/", timeout=5)
        print(f"[SUCCESS] Local API responding: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print("[ERROR] Local API not running on localhost:8000")
        return False
    except Exception as e:
        print(f"[ERROR] Local API error: {e}")
        return False

def check_deployed_api():
    """Check common deployment endpoints"""
    print("[CHECK] Testing potential deployed API endpoints...")
    
    # Common deployment URLs
    possible_urls = [
        "https://analyticsfollowingbackend.vercel.app",
        "https://analytics-following-backend.vercel.app", 
        "https://analytics-backend.vercel.app",
        "https://barakat-backend.vercel.app"
    ]
    
    for url in possible_urls:
        try:
            print(f"[TEST] Trying: {url}")
            response = requests.get(f"{url}/", timeout=10)
            print(f"[SUCCESS] Found deployed API at: {url} (Status: {response.status_code})")
            
            # Test health endpoint
            try:
                health_response = requests.get(f"{url}/health", timeout=5)
                print(f"[SUCCESS] Health check: {health_response.status_code}")
            except:
                print("[INFO] No health endpoint")
            
            return url
        except requests.exceptions.ConnectionError:
            print(f"[FAIL] Not accessible: {url}")
        except requests.exceptions.Timeout:
            print(f"[TIMEOUT] Slow response: {url}")
        except Exception as e:
            print(f"[ERROR] Error testing {url}: {e}")
    
    print("[ERROR] No deployed API found")
    return None

def test_auth_endpoint(base_url):
    """Test authentication endpoints"""
    try:
        print(f"[TEST] Testing auth endpoint: {base_url}/auth/login")
        
        # Test with demo credentials
        auth_data = {
            "email": "zzain.ali@outlook.com",
            "password": "BarakatDemo2024!"
        }
        
        response = requests.post(f"{base_url}/auth/login", json=auth_data, timeout=10)
        print(f"[AUTH] Login test response: {response.status_code}")
        
        if response.status_code == 200:
            print("[SUCCESS] Auth endpoint working!")
            return True
        else:
            print(f"[ERROR] Auth failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Auth test failed: {e}")
        return False

def check_cors_headers(base_url):
    """Check CORS configuration"""
    try:
        print(f"[TEST] Checking CORS headers...")
        response = requests.options(f"{base_url}/", timeout=5)
        
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
        }
        
        print("[CORS] Headers:")
        for header, value in cors_headers.items():
            print(f"  {header}: {value}")
        
        if cors_headers['Access-Control-Allow-Origin']:
            print("[SUCCESS] CORS configured")
        else:
            print("[WARNING] CORS headers missing")
            
    except Exception as e:
        print(f"[ERROR] CORS check failed: {e}")

def display_diagnosis_results():
    """Display diagnosis results and solutions"""
    print("\n" + "=" * 80)
    print("API CONNECTION DIAGNOSIS")
    print("=" * 80)
    
    print("\nCOMMON ISSUES & SOLUTIONS:")
    print("\n1. BACKEND NOT DEPLOYED:")
    print("   - Your backend needs to be deployed to a platform like:")
    print("     * Vercel: npx vercel --prod")
    print("     * Railway: railway up")
    print("     * Render: Connect GitHub repo")
    print("     * DigitalOcean App Platform")
    
    print("\n2. CORS CONFIGURATION:")
    print("   - Frontend domain needs to be allowed in backend CORS")
    print("   - Check middleware/frontend_headers.py")
    print("   - Add your frontend domain to allowed origins")
    
    print("\n3. API BASE URL CONFIGURATION:")
    print("   - Frontend needs correct API base URL")
    print("   - Should point to deployed backend, not localhost")
    print("   - Check frontend environment variables")
    
    print("\n4. ENVIRONMENT VARIABLES:")
    print("   - Ensure all env vars are set in deployment platform")
    print("   - Database URL, Supabase keys, etc.")
    
    print("\nNEXT STEPS:")
    print("1. Deploy backend to production platform")
    print("2. Update frontend API base URL")
    print("3. Configure CORS for frontend domain")
    print("4. Test API endpoints manually")
    
    print("=" * 80)

def main():
    """Main diagnosis function"""
    print("API CONNECTION DIAGNOSIS STARTING...")
    print(f"Time: {datetime.now()}")
    print()
    
    # Check local API
    local_running = check_local_api()
    print()
    
    # Check for deployed API
    deployed_url = check_deployed_api()
    print()
    
    if deployed_url:
        # Test auth endpoint
        test_auth_endpoint(deployed_url)
        print()
        
        # Check CORS
        check_cors_headers(deployed_url)
        print()
    
    # Display diagnosis
    display_diagnosis_results()
    
    if not local_running and not deployed_url:
        print("\n[CRITICAL] No accessible API found!")
        print("Your backend needs to be deployed for the frontend to work.")
    elif deployed_url:
        print(f"\n[SUCCESS] Use this API URL in your frontend: {deployed_url}")

if __name__ == "__main__":
    main()