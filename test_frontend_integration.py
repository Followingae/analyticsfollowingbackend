"""
Frontend Integration Test Script
Tests all endpoints that the frontend will use
"""

import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_endpoint(session, endpoint, description):
    """Test a single endpoint"""
    print(f"\n🧪 Testing: {description}")
    print(f"   Endpoint: {endpoint}")
    
    try:
        start_time = datetime.now()
        async with session.get(f"{BASE_URL}{endpoint}") as response:
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Status: {response.status}")
                print(f"   ⏱️  Response Time: {response_time:.2f}s")
                
                # Show custom headers
                custom_headers = {k: v for k, v in response.headers.items() if k.startswith('X-')}
                if custom_headers:
                    print(f"   📋 Custom Headers: {custom_headers}")
                
                # Show data sample
                if isinstance(data, dict):
                    keys = list(data.keys())[:5]  # First 5 keys
                    print(f"   📊 Data Keys: {keys}")
                    
                    # Show specific important fields
                    if 'profile' in data:
                        profile = data['profile']
                        print(f"   👤 Profile: {profile.get('username', 'N/A')} - {profile.get('followers', 0):,} followers")
                    elif 'username' in data:
                        print(f"   👤 User: {data.get('username', 'N/A')} - {data.get('followers', 0):,} followers")
                    elif 'status' in data:
                        print(f"   🔍 Status: {data.get('status', 'N/A')}")
                
                return True
            else:
                print(f"   ❌ Status: {response.status}")
                error_text = await response.text()
                print(f"   📝 Error: {error_text[:200]}...")
                return False
                
    except Exception as e:
        print(f"   💥 Exception: {str(e)}")
        return False

async def run_frontend_integration_tests():
    """Run all frontend integration tests"""
    print("🚀 Frontend Integration Test Suite")
    print("=" * 50)
    
    # Test endpoints that the frontend will use
    test_cases = [
        # Core endpoints
        ("/", "Root endpoint"),
        ("/health", "Health check"),
        ("/api", "API info"),
        
        # API endpoints
        ("/api/v1/status", "API status"),
        ("/api/v1/config", "API configuration"),
        
        # Profile analysis endpoints
        ("/api/v1/instagram/profile/mkbhd/basic", "Basic profile (mkbhd)"),
        ("/api/v1/analytics/summary/mkbhd", "Analytics summary (mkbhd)"),
        ("/api/v1/instagram/profile/mkbhd", "Full profile analysis (mkbhd)"),
        
        # Utility endpoints
        ("/api/v1/search/suggestions/mk", "Username suggestions"),
        ("/api/v1/test-connection", "Decodo connection test"),
        
        # Alternative profiles for testing
        ("/api/v1/analytics/summary/cristiano", "Analytics summary (cristiano)"),
        ("/api/v1/instagram/profile/kyliejenner/basic", "Basic profile (kyliejenner)"),
    ]
    
    results = []
    timeout = aiohttp.ClientTimeout(total=60)  # 60 second timeout
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for endpoint, description in test_cases:
            success = await test_endpoint(session, endpoint, description)
            results.append((endpoint, description, success))
            
            # Small delay between requests
            await asyncio.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = sum(1 for _, _, success in results if success)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
    
    if passed < total:
        print("\n❌ Failed Tests:")
        for endpoint, description, success in results:
            if not success:
                print(f"   • {description}: {endpoint}")
    
    print(f"\n🎯 Frontend Integration Status: {'✅ READY' if passed >= total * 0.8 else '⚠️ NEEDS ATTENTION'}")
    
    return passed, total

async def test_cors():
    """Test CORS configuration"""
    print("\n🌐 Testing CORS Configuration")
    print("-" * 30)
    
    try:
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        async with aiohttp.ClientSession() as session:
            # Test preflight request
            async with session.options(f"{BASE_URL}/api/v1/health", headers=headers) as response:
                print(f"Preflight Status: {response.status}")
                cors_headers = {k: v for k, v in response.headers.items() if k.startswith('Access-Control')}
                print(f"CORS Headers: {cors_headers}")
                
                if response.status in [200, 204] and 'Access-Control-Allow-Origin' in response.headers:
                    print("✅ CORS properly configured for localhost:3000")
                    return True
                else:
                    print("❌ CORS configuration issues detected")
                    return False
                    
    except Exception as e:
        print(f"💥 CORS test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting Frontend Integration Tests...")
    print(f"Target: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Run main tests
        passed, total = asyncio.run(run_frontend_integration_tests())
        
        # Test CORS
        cors_ok = asyncio.run(test_cors())
        
        print(f"\n🏁 Final Results:")
        print(f"   API Tests: {passed}/{total}")
        print(f"   CORS Test: {'✅' if cors_ok else '❌'}")
        print(f"   Overall: {'🎉 READY FOR FRONTEND' if passed >= total * 0.8 and cors_ok else '⚠️ NEEDS FIXES'}")
        
    except KeyboardInterrupt:
        print("\n\n⛔ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n💥 Test suite failed: {str(e)}")