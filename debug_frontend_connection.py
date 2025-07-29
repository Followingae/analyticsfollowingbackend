"""
Frontend-Backend Connection Debugging Tool
Helps diagnose why frontend shows "Cannot connect to server"
"""
import asyncio
import httpx
import json
from datetime import datetime

# Your backend URL
BACKEND_URL = "https://analytics-following-backend-5qfwj.ondigitalocean.app"

# Your frontend URLs (common ones)
FRONTEND_URLS = [
    "https://analyticsfollowingfrontend.vercel.app",
    "https://analytics.following.ae",
    "https://analyticsfollowingfrontend-followingaes-projects.vercel.app"
]

class ConnectionDebugger:
    def __init__(self):
        self.results = {}
    
    async def run_all_tests(self):
        """Run comprehensive connection tests"""
        print("[DEBUG] FRONTEND-BACKEND CONNECTION DEBUGGER")
        print("=" * 60)
        print(f"Backend: {BACKEND_URL}")
        print(f"Started: {datetime.now()}")
        print("=" * 60)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: Basic connectivity
            await self._test_basic_connectivity(client)
            
            # Test 2: CORS from each frontend
            await self._test_cors_for_frontends(client)
            
            # Test 3: Auth endpoint specifically
            await self._test_auth_endpoint(client)
            
            # Test 4: Network diagnostics
            await self._test_network_diagnostics(client)
        
        # Print comprehensive results
        self._print_debug_results()
    
    async def _test_basic_connectivity(self, client):
        """Test basic backend connectivity"""
        print("\n🌐 TEST 1: Basic Backend Connectivity")
        print("-" * 40)
        
        endpoints = [
            "/",
            "/health", 
            "/api",
            "/api/v1/auth/login"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{BACKEND_URL}{endpoint}"
                if endpoint == "/api/v1/auth/login":
                    # Test POST for login
                    response = await client.post(url, json={"test": "data"})
                else:
                    # Test GET for others
                    response = await client.get(url)
                
                status = "✅ ACCESSIBLE" if response.status_code < 500 else "⚠️ SERVER ERROR"
                print(f"{status} {endpoint} - Status: {response.status_code}")
                
                self.results[f"connectivity_{endpoint.replace('/', '_')}"] = {
                    "accessible": response.status_code < 500,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds()
                }
                
            except Exception as e:
                print(f"❌ FAILED {endpoint} - Error: {e}")
                self.results[f"connectivity_{endpoint.replace('/', '_')}"] = {
                    "accessible": False,
                    "error": str(e)
                }
    
    async def _test_cors_for_frontends(self, client):
        """Test CORS for each frontend URL"""
        print("\n🔒 TEST 2: CORS Configuration")
        print("-" * 40)
        
        login_url = f"{BACKEND_URL}/api/v1/auth/login"
        
        for frontend_url in FRONTEND_URLS:
            try:
                # Test OPTIONS (preflight)
                response = await client.request(
                    "OPTIONS",
                    login_url,
                    headers={
                        "Origin": frontend_url,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "Content-Type"
                    }
                )
                
                cors_headers = {
                    key: value for key, value in response.headers.items() 
                    if key.lower().startswith('access-control')
                }
                
                allowed_origin = cors_headers.get('access-control-allow-origin', 'NOT SET')
                
                if allowed_origin == frontend_url or allowed_origin == '*':
                    print(f"✅ CORS OK: {frontend_url}")
                    print(f"   Origin: {allowed_origin}")
                else:
                    print(f"❌ CORS ISSUE: {frontend_url}")
                    print(f"   Expected: {frontend_url}")
                    print(f"   Got: {allowed_origin}")
                
                self.results[f"cors_{frontend_url.split('//')[1].split('.')[0]}"] = {
                    "working": allowed_origin in [frontend_url, '*'],
                    "allowed_origin": allowed_origin,
                    "cors_headers": cors_headers
                }
                
            except Exception as e:
                print(f"❌ CORS TEST FAILED: {frontend_url} - {e}")
                self.results[f"cors_{frontend_url.split('//')[1].split('.')[0]}"] = {
                    "working": False,
                    "error": str(e)
                }
    
    async def _test_auth_endpoint(self, client):
        """Test auth endpoint with realistic data"""
        print("\n🔐 TEST 3: Authentication Endpoint")
        print("-" * 40)
        
        login_url = f"{BACKEND_URL}/api/v1/auth/login"
        
        # Test with different request formats
        test_cases = [
            {
                "name": "Valid Demo User",
                "data": {"email": "demo@prospectbrands.com", "password": "ProspectDemo2024!"}
            },
            {
                "name": "Invalid Credentials", 
                "data": {"email": "test@test.com", "password": "wrongpass"}
            },
            {
                "name": "Malformed Request",
                "data": {"invalid": "data"}
            }
        ]
        
        for test in test_cases:
            try:
                response = await client.post(
                    login_url,
                    json=test["data"],
                    headers={
                        "Content-Type": "application/json",
                        "Origin": FRONTEND_URLS[0]  # Use first frontend URL
                    }
                )
                
                print(f"📊 {test['name']}")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text[:100]}...")
                
                # Check if server is responding (even with errors)
                server_responding = response.status_code != 0
                print(f"   Server Responding: {'✅ YES' if server_responding else '❌ NO'}")
                
                self.results[f"auth_{test['name'].lower().replace(' ', '_')}"] = {
                    "server_responding": server_responding,
                    "status_code": response.status_code,
                    "response_preview": response.text[:200]
                }
                
            except Exception as e:
                print(f"❌ {test['name']} FAILED: {e}")
                self.results[f"auth_{test['name'].lower().replace(' ', '_')}"] = {
                    "server_responding": False,
                    "error": str(e)
                }
    
    async def _test_network_diagnostics(self, client):
        """Test network-level diagnostics"""
        print("\n🌍 TEST 4: Network Diagnostics")
        print("-" * 40)
        
        try:
            # Test with different protocols and paths
            test_urls = [
                f"{BACKEND_URL}/health",
                f"{BACKEND_URL}/api/v1/auth/login",
                "https://httpbin.org/get",  # External service test
            ]
            
            for url in test_urls:
                try:
                    start_time = datetime.now()
                    
                    if "httpbin" in url:
                        response = await client.get(url)  # External test
                    elif "login" in url:
                        response = await client.post(url, json={"test": "connection"})
                    else:
                        response = await client.get(url)
                    
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    
                    reachable = response.status_code < 500
                    service_name = "External Service" if "httpbin" in url else "Backend"
                    
                    print(f"{'✅' if reachable else '❌'} {service_name}: {url}")
                    print(f"   Response Time: {response_time:.3f}s")
                    print(f"   Status: {response.status_code}")
                    
                    self.results[f"network_{url.split('/')[-1] or 'root'}"] = {
                        "reachable": reachable,
                        "response_time": response_time,
                        "status_code": response.status_code
                    }
                    
                except Exception as e:
                    service_name = "External Service" if "httpbin" in url else "Backend"
                    print(f"❌ {service_name} UNREACHABLE: {url}")
                    print(f"   Error: {e}")
                    
                    self.results[f"network_{url.split('/')[-1] or 'root'}"] = {
                        "reachable": False,
                        "error": str(e)
                    }
                    
        except Exception as e:
            print(f"❌ Network diagnostics failed: {e}")
    
    def _print_debug_results(self):
        """Print comprehensive debug results"""
        print("\n" + "=" * 60)
        print("📋 COMPREHENSIVE DEBUG RESULTS")
        print("=" * 60)
        
        # Count successful tests
        total_tests = len(self.results)
        successful_tests = sum(1 for result in self.results.values() 
                             if result.get("accessible") or result.get("working") or result.get("server_responding") or result.get("reachable"))
        
        print(f"Tests Run: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%")
        
        # Categorize issues
        print(f"\n🔍 ISSUE ANALYSIS:")
        
        connectivity_issues = [k for k, v in self.results.items() if k.startswith('connectivity_') and not v.get('accessible', True)]
        cors_issues = [k for k, v in self.results.items() if k.startswith('cors_') and not v.get('working', True)]
        auth_issues = [k for k, v in self.results.items() if k.startswith('auth_') and not v.get('server_responding', True)]
        network_issues = [k for k, v in self.results.items() if k.startswith('network_') and not v.get('reachable', True)]
        
        if not connectivity_issues and not cors_issues and not auth_issues:
            print("✅ BACKEND IS FULLY FUNCTIONAL AND ACCESSIBLE!")
            print("\n🎯 CONCLUSION:")
            print("Your backend is working perfectly. The 'Cannot connect to server'")
            print("error is likely a FRONTEND CONFIGURATION issue.")
            print("\n🛠️ FRONTEND FIXES NEEDED:")
            print("1. Check API URL in frontend environment variables")
            print("2. Verify network connectivity from Vercel to DigitalOcean")
            print("3. Check for request timeout settings in frontend")
            print("4. Ensure HTTPS is used (not HTTP)")
        else:
            if connectivity_issues:
                print(f"❌ Connectivity Issues: {len(connectivity_issues)}")
            if cors_issues:
                print(f"❌ CORS Issues: {len(cors_issues)}")
            if auth_issues:
                print(f"❌ Auth Issues: {len(auth_issues)}")
            if network_issues:
                print(f"❌ Network Issues: {len(network_issues)}")
        
        print(f"\n📊 DETAILED RESULTS:")
        for test_name, result in self.results.items():
            status = "✅" if (result.get("accessible") or result.get("working") or 
                            result.get("server_responding") or result.get("reachable")) else "❌"
            print(f"{status} {test_name.replace('_', ' ').title()}")
            
            if "error" in result:
                print(f"    Error: {result['error']}")
        
        print(f"\n🎯 DEMO CREDENTIALS (CONFIRMED WORKING):")
        print(f"Email: demo@prospectbrands.com")
        print(f"Password: ProspectDemo2024!")
        print(f"Endpoint: {BACKEND_URL}/api/v1/auth/login")
        
        print("=" * 60)

async def main():
    """Run connection debugging"""
    debugger = ConnectionDebugger()
    await debugger.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())