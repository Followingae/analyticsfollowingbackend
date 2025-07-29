"""
Test connection to DigitalOcean backend
"""
import requests
import json

def test_digitalocean_backends():
    """Test common DigitalOcean backend URLs"""
    print("TESTING DIGITALOCEAN BACKEND CONNECTIONS")
    print("=" * 50)
    
    # Common DigitalOcean app URL patterns
    possible_urls = [
        "https://analytics-following-backend.ondigitalocean.app",
        "https://analyticsfollowingbackend.ondigitalocean.app", 
        "https://barakat-backend.ondigitalocean.app",
        "https://following-analytics.ondigitalocean.app",
        "https://backend.ondigitalocean.app"
    ]
    
    working_backends = []
    
    for url in possible_urls:
        try:
            print(f"\n[TEST] {url}")
            response = requests.get(f"{url}/", timeout=10)
            
            if response.status_code == 200:
                print(f"[SUCCESS] Backend found! Status: {response.status_code}")
                print(f"Response: {response.text[:100]}...")
                working_backends.append(url)
                
                # Test health endpoint
                try:
                    health = requests.get(f"{url}/health", timeout=5)
                    print(f"[HEALTH] {health.status_code}: {health.text[:50]}...")
                except:
                    print("[HEALTH] No health endpoint")
                
                # Test auth endpoint
                try:
                    auth_test = {
                        "email": "zzain.ali@outlook.com",
                        "password": "BarakatDemo2024!"
                    }
                    auth = requests.post(f"{url}/api/v1/auth/login", json=auth_test, timeout=10)
                    print(f"[AUTH] Login test: {auth.status_code}")
                    if auth.status_code != 200:
                        print(f"[AUTH] Error: {auth.text[:100]}...")
                except Exception as e:
                    print(f"[AUTH] Auth test failed: {e}")
                    
            else:
                print(f"[FAIL] Status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("[FAIL] Connection refused")
        except requests.exceptions.Timeout:
            print("[FAIL] Timeout")
        except Exception as e:
            print(f"[ERROR] {e}")
    
    print(f"\n{'='*50}")
    if working_backends:
        print("WORKING BACKENDS FOUND:")
        for backend in working_backends:
            print(f"  ✓ {backend}")
        
        print(f"\nUSE THIS IN YOUR FRONTEND:")
        print(f"NEXT_PUBLIC_API_URL={working_backends[0]}")
        print(f"NEXT_PUBLIC_API_BASE_URL={working_backends[0]}/api/v1")
    else:
        print("NO WORKING BACKENDS FOUND!")
        print("\nCHECK:")
        print("1. Is your DigitalOcean app deployed and running?")
        print("2. Check DigitalOcean Apps dashboard")
        print("3. Verify the correct URL from DigitalOcean")

if __name__ == "__main__":
    test_digitalocean_backends()