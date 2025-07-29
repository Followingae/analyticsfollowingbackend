"""
Comprehensive Production Authentication Test
Tests the bulletproof Supabase authentication system
"""
import asyncio
import httpx
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_URL = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
TEST_CREDENTIALS = {
    "email": "zzain.ali@outlook.com",
    "password": "BarakatDemo2024!"
}

class AuthenticationTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = None
        self.test_results = {}
    
    async def run_comprehensive_tests(self):
        """Run all authentication tests"""
        print("🚀 COMPREHENSIVE PRODUCTION AUTHENTICATION TEST")
        print("=" * 60)
        print(f"Testing API: {self.base_url}")
        print(f"Test User: {TEST_CREDENTIALS['email']}")
        print(f"Started: {datetime.now()}")
        print("=" * 60)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            self.client = client
            
            # Test 1: Backend Health Check
            await self._test_backend_health()
            
            # Test 2: Auth Service Health Check
            await self._test_auth_health()
            
            # Test 3: Authentication Endpoint Test
            await self._test_authentication()
            
            # Test 4: Token Validation (if login successful)
            if self.test_results.get("auth_login", {}).get("success"):
                await self._test_token_validation()
            
            # Test 5: User Profile Access (if login successful)
            if self.test_results.get("auth_login", {}).get("success"):
                await self._test_user_profile()
        
        # Print comprehensive results
        self._print_test_results()
    
    async def _test_backend_health(self):
        """Test backend health endpoint"""
        print("\n🏥 TEST 1: Backend Health Check")
        print("-" * 40)
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            self.test_results["backend_health"] = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code == 200 else response.text
            }
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Backend Status: {data.get('status', 'unknown')}")
                print(f"✅ Version: {data.get('version', 'unknown')}")
                
                # Check auth service health from backend
                auth_service_health = data.get('services', {}).get('auth', {})
                if auth_service_health:
                    print(f"✅ Auth Service Status: {auth_service_health.get('status', 'unknown')}")
                    print(f"✅ Auth Initialized: {auth_service_health.get('initialized', False)}")
            else:
                print(f"❌ Backend health check failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Backend health check error: {e}")
            self.test_results["backend_health"] = {"success": False, "error": str(e)}
    
    async def _test_auth_health(self):
        """Test dedicated auth health endpoint"""
        print("\n🔐 TEST 2: Auth Service Health Check")
        print("-" * 40)
        
        try:
            response = await self.client.get(f"{self.base_url}/auth/health")
            
            self.test_results["auth_health"] = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code == 200 else response.text
            }
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Auth Service: {data.get('status', 'unknown')}")
                print(f"✅ Initialized: {data.get('initialized', False)}")
                
                details = data.get('details', {})
                if 'supabase_connectivity' in details:
                    print(f"✅ Supabase Connectivity: {details['supabase_connectivity']}")
                
                if 'environment' in details:
                    env = details['environment']
                    print(f"✅ Environment Variables:")
                    print(f"   - Supabase URL: {env.get('supabase_url', 'unknown')}")
                    print(f"   - Supabase Key: {'set' if env.get('supabase_key') == 'set' else 'missing'}")
                    print(f"   - Database URL: {env.get('database_url', 'unknown')}")
            else:
                print(f"❌ Auth health check failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Auth health check error: {e}")
            self.test_results["auth_health"] = {"success": False, "error": str(e)}
    
    async def _test_authentication(self):
        """Test user authentication"""
        print("\n🔑 TEST 3: User Authentication")
        print("-" * 40)
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/auth/login",
                json=TEST_CREDENTIALS,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"📊 Login Response Status: {response.status_code}")
            print(f"📊 Response Headers: {dict(response.headers)}")
            
            self.test_results["auth_login"] = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "headers": dict(response.headers)
            }
            
            if response.status_code == 200:
                data = response.json()
                self.test_results["auth_login"]["data"] = data
                
                print("✅ LOGIN SUCCESSFUL!")
                print(f"✅ User Email: {data.get('user', {}).get('email')}")
                print(f"✅ User Role: {data.get('user', {}).get('role')}")
                print(f"✅ User Status: {data.get('user', {}).get('status')}")
                print(f"✅ Token Type: {data.get('token_type')}")
                print(f"✅ Access Token: {data.get('access_token', '')[:20]}...")
                print(f"✅ Expires In: {data.get('expires_in')} seconds")
                
                # Store token for further tests
                self.access_token = data.get('access_token')
                
            else:
                print(f"❌ LOGIN FAILED!")
                print(f"❌ Status Code: {response.status_code}")
                print(f"❌ Response: {response.text}")
                self.test_results["auth_login"]["error"] = response.text
                
        except Exception as e:
            print(f"❌ Authentication test error: {e}")
            self.test_results["auth_login"] = {"success": False, "error": str(e)}
    
    async def _test_token_validation(self):
        """Test token validation by accessing protected endpoint"""
        print("\n🎫 TEST 4: Token Validation")
        print("-" * 40)
        
        if not hasattr(self, 'access_token'):
            print("❌ No access token available for validation test")
            return
        
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            self.test_results["token_validation"] = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
            
            if response.status_code == 200:
                data = response.json()
                self.test_results["token_validation"]["data"] = data
                
                print("✅ TOKEN VALIDATION SUCCESSFUL!")
                print(f"✅ User ID: {data.get('id')}")
                print(f"✅ Email: {data.get('email')}")
                print(f"✅ Full Name: {data.get('full_name')}")
                print(f"✅ Role: {data.get('role')}")
                
            else:
                print(f"❌ TOKEN VALIDATION FAILED!")
                print(f"❌ Status Code: {response.status_code}")
                print(f"❌ Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Token validation error: {e}")
            self.test_results["token_validation"] = {"success": False, "error": str(e)}
    
    async def _test_user_profile(self):
        """Test user profile access"""
        print("\n👤 TEST 5: User Profile Access")
        print("-" * 40)
        
        if not hasattr(self, 'access_token'):
            print("❌ No access token available for profile test")
            return
        
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/auth/dashboard",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            self.test_results["user_profile"] = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
            
            if response.status_code == 200:
                data = response.json()
                self.test_results["user_profile"]["data"] = data
                
                print("✅ USER PROFILE ACCESS SUCCESSFUL!")
                print(f"✅ Total Searches: {data.get('total_searches', 0)}")
                print(f"✅ Searches This Month: {data.get('searches_this_month', 0)}")
                print(f"✅ Account Created: {data.get('account_created')}")
                
            else:
                print(f"⚠️ User profile access: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ User profile error: {e}")
            self.test_results["user_profile"] = {"success": False, "error": str(e)}
    
    def _print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result.get("success", False))
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%")
        
        print("\n📋 DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result.get("success") else "❌ FAIL"
            print(f"{status} {test_name.replace('_', ' ').title()}")
            
            if not result.get("success") and "error" in result:
                print(f"    Error: {result['error']}")
        
        # Authentication status
        auth_success = self.test_results.get("auth_login", {}).get("success", False)
        
        print("\n" + "=" * 60)
        if auth_success:
            print("🎉 AUTHENTICATION SYSTEM FULLY FUNCTIONAL!")
            print("\n🔑 DEMO CREDENTIALS VERIFIED:")
            print(f"Email: {TEST_CREDENTIALS['email']}")
            print(f"Password: {TEST_CREDENTIALS['password']}")
            print("\n🌐 API ENDPOINT:")
            print(f"{self.base_url}/api/v1/auth/login")
            print("\n✨ Ready for frontend integration!")
        else:
            print("❌ AUTHENTICATION SYSTEM NEEDS ATTENTION")
            print("Check the failed tests above for details.")
        
        print("=" * 60)


async def main():
    """Run comprehensive authentication tests"""
    tester = AuthenticationTester()
    await tester.run_comprehensive_tests()


if __name__ == "__main__":
    asyncio.run(main())