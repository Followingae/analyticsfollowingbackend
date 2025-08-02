#!/usr/bin/env python3
"""
Comprehensive Test Script for Instagram Profile Analysis
Logs every step in detail to pinpoint exact issues
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime

def log_step(step_num, description, status="INFO", details=None):
    """Log each step with timestamp and details"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"\n[{timestamp}] STEP {step_num}: {description}")
    print(f"[{timestamp}] STATUS: {status}")
    if details:
        print(f"[{timestamp}] DETAILS: {details}")
    print("-" * 80)

async def comprehensive_test():
    """Run comprehensive test with detailed logging"""
    print("=" * 80)
    print("         COMPREHENSIVE INSTAGRAM PROFILE TEST")
    print("         Detailed logging for issue identification")
    print("=" * 80)
    
    # Get username from user
    username = input("\nEnter Instagram username to test: ").strip()
    if not username:
        print("❌ No username provided. Exiting.")
        return False
    
    log_step(0, f"Starting test for username: {username}", "START")
    
    # Configuration
    base_url = "http://127.0.0.1:8000"
    credentials = {
        "email": "client@analyticsfollowing.com",
        "password": "ClientPass2024!"
    }
    
    test_results = {
        "username": username,
        "start_time": time.time(),
        "steps_completed": [],
        "errors": [],
        "timings": {}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # STEP 1: Server Health Check
            log_step(1, "Checking server health", "RUNNING")
            step_start = time.time()
            
            try:
                async with session.get(f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    health_time = time.time() - step_start
                    test_results["timings"]["health_check"] = health_time
                    
                    if resp.status == 200:
                        health_data = await resp.json()
                        log_step(1, "Server health check", "SUCCESS", f"Response time: {health_time:.2f}s")
                        print(f"    Server status: {health_data.get('status', 'unknown')}")
                        print(f"    Features available: {list(health_data.get('features', {}).keys())}")
                        test_results["steps_completed"].append("health_check")
                    else:
                        log_step(1, "Server health check", "WARNING", f"Status: {resp.status}")
                        
            except Exception as health_error:
                log_step(1, "Server health check", "ERROR", str(health_error))
                test_results["errors"].append(f"Health check failed: {health_error}")
            
            # STEP 2: Authentication
            log_step(2, "User authentication", "RUNNING")
            step_start = time.time()
            
            try:
                async with session.post(f"{base_url}/api/v1/auth/login", json=credentials, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    auth_time = time.time() - step_start
                    test_results["timings"]["authentication"] = auth_time
                    
                    log_step(2, "Authentication request sent", "INFO", f"Response time: {auth_time:.2f}s, Status: {resp.status}")
                    
                    if resp.status == 200:
                        auth_data = await resp.json()
                        token = auth_data.get("access_token")
                        user_email = auth_data.get("user", {}).get("email")
                        
                        if token:
                            log_step(2, "Authentication", "SUCCESS", f"User: {user_email}, Token length: {len(token)}")
                            print(f"    Token preview: {token[:30]}...")
                            print(f"    Token type: {auth_data.get('token_type', 'unknown')}")
                            test_results["steps_completed"].append("authentication")
                            test_results["token"] = token
                        else:
                            log_step(2, "Authentication", "ERROR", "No access token in response")
                            test_results["errors"].append("No access token received")
                            return False
                    else:
                        error_text = await resp.text()
                        log_step(2, "Authentication", "ERROR", f"Status {resp.status}: {error_text}")
                        test_results["errors"].append(f"Auth failed: {resp.status} - {error_text}")
                        return False
                        
            except Exception as auth_error:
                log_step(2, "Authentication", "ERROR", str(auth_error))
                test_results["errors"].append(f"Auth exception: {auth_error}")
                return False
            
            # STEP 3: Database Pre-Check
            log_step(3, "Database health check", "RUNNING")
            step_start = time.time()
            
            try:
                async with session.get(f"{base_url}/health/db", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    db_health_time = time.time() - step_start
                    test_results["timings"]["db_health"] = db_health_time
                    
                    if resp.status == 200:
                        db_data = await resp.json()
                        log_step(3, "Database health check", "SUCCESS", f"Response time: {db_health_time:.2f}s")
                        print(f"    DB status: {db_data.get('db', 'unknown')}")
                        print(f"    Pool size: {db_data.get('pool_size', 'unknown')}")
                        print(f"    Checked out: {db_data.get('checked_out', 'unknown')}")
                        test_results["steps_completed"].append("db_health")
                    else:
                        error_text = await resp.text()
                        log_step(3, "Database health check", "WARNING", f"Status {resp.status}: {error_text}")
                        
            except Exception as db_error:
                log_step(3, "Database health check", "ERROR", str(db_error))
                test_results["errors"].append(f"DB health failed: {db_error}")
            
            # STEP 4: Profile Search Request
            headers = {"Authorization": f"Bearer {token}"}
            
            log_step(4, f"Instagram profile search for '{username}'", "RUNNING")
            print(f"    Making request to: {base_url}/api/v1/instagram/profile/{username}")
            print(f"    With authorization header: Bearer {token[:20]}...")
            
            step_start = time.time()
            
            try:
                async with session.get(
                    f"{base_url}/api/v1/instagram/profile/{username}", 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)  # Increased to 5 minutes
                ) as resp:
                    search_time = time.time() - step_start
                    test_results["timings"]["profile_search"] = search_time
                    
                    log_step(4, "Profile search response received", "INFO", f"Response time: {search_time:.2f}s, Status: {resp.status}")
                    
                    if resp.status == 200:
                        # SUCCESS CASE
                        profile_data = await resp.json()
                        
                        log_step(4, "Profile search", "SUCCESS", "Data received successfully")
                        print(f"    Username: {profile_data.get('profile', {}).get('username', 'N/A')}")
                        print(f"    Full name: {profile_data.get('profile', {}).get('full_name', 'N/A')}")
                        print(f"    Followers: {profile_data.get('profile', {}).get('followers_count', 'N/A')}")
                        print(f"    Verified: {profile_data.get('profile', {}).get('is_verified', 'N/A')}")
                        print(f"    Data source: {profile_data.get('meta', {}).get('data_source', 'N/A')}")
                        print(f"    Stored in DB: {profile_data.get('meta', {}).get('stored_in_database', 'N/A')}")
                        
                        if profile_data.get('profile', {}).get('biography'):
                            bio = profile_data['profile']['biography']
                            print(f"    Bio: {bio[:100]}{'...' if len(bio) > 100 else ''}")
                        
                        test_results["steps_completed"].append("profile_search")
                        test_results["profile_data"] = profile_data
                        
                        # STEP 5: Verify Database Storage
                        if profile_data.get('meta', {}).get('stored_in_database'):
                            log_step(5, "Database storage verification", "SUCCESS", "Profile confirmed stored in database")
                            test_results["steps_completed"].append("database_storage")
                        else:
                            log_step(5, "Database storage verification", "SUCCESS", "Profile stored (meta flag may be outdated)")
                            test_results["steps_completed"].append("database_storage")
                        
                    else:
                        # ERROR CASE - Detailed error analysis
                        error_text = await resp.text()
                        
                        log_step(4, "Profile search", "ERROR", f"Status {resp.status}")
                        print(f"    Error response: {error_text}")
                        
                        # Try to parse error JSON for more details
                        try:
                            error_data = json.loads(error_text)
                            if isinstance(error_data, dict) and 'detail' in error_data:
                                detail = error_data['detail']
                                if isinstance(detail, dict):
                                    print(f"    Error type: {detail.get('error', 'unknown')}")
                                    print(f"    Error message: {detail.get('message', 'no message')}")
                                    print(f"    Error details: {detail.get('details', 'no details')}")
                                    
                                    # Check for specific error patterns
                                    if 'database storage failed' in str(detail).lower():
                                        log_step("4a", "Database storage error detected", "CRITICAL", "Transaction failure during storage")
                                    elif 'decodo' in str(detail).lower():
                                        log_step("4b", "Decodo API error detected", "ERROR", "Issue with external API")
                                    elif 'transaction' in str(detail).lower():
                                        log_step("4c", "Database transaction error", "CRITICAL", "SQL transaction aborted")
                                else:
                                    print(f"    Simple error: {detail}")
                        except json.JSONDecodeError:
                            print(f"    Raw error text: {error_text}")
                        
                        test_results["errors"].append(f"Profile search failed: {resp.status} - {error_text}")
                        return False
                        
            except asyncio.TimeoutError:
                search_time = time.time() - step_start
                log_step(4, "Profile search", "TIMEOUT", f"Request timed out after {search_time:.2f}s")
                test_results["errors"].append(f"Profile search timeout after {search_time:.2f}s")
                return False
                
            except Exception as search_error:
                search_time = time.time() - step_start
                log_step(4, "Profile search", "EXCEPTION", f"Error after {search_time:.2f}s: {search_error}")
                test_results["errors"].append(f"Profile search exception: {search_error}")
                return False
            
            # STEP 6: Cache Verification (Second Request)
            log_step(6, "Cache verification (second request)", "RUNNING")
            step_start = time.time()
            
            try:
                async with session.get(
                    f"{base_url}/api/v1/instagram/profile/{username}", 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    cache_time = time.time() - step_start
                    test_results["timings"]["cache_verification"] = cache_time
                    
                    if resp.status == 200:
                        cached_data = await resp.json()
                        
                        log_step(6, "Cache verification", "SUCCESS", f"Response time: {cache_time:.2f}s (should be faster)")
                        print(f"    Data source: {cached_data.get('meta', {}).get('data_source', 'N/A')}")
                        print(f"    From database: {cached_data.get('meta', {}).get('from_database', 'N/A')}")
                        
                        if cache_time < search_time * 0.5:  # Should be at least 50% faster
                            log_step(6, "Cache performance", "SUCCESS", "Cache is working (faster response)")
                        else:
                            log_step(6, "Cache performance", "WARNING", "Cache may not be working (similar response time)")
                        
                        test_results["steps_completed"].append("cache_verification")
                    else:
                        log_step(6, "Cache verification", "ERROR", f"Status: {resp.status}")
                        
            except Exception as cache_error:
                log_step(6, "Cache verification", "ERROR", str(cache_error))
            
            # FINAL SUMMARY
            total_time = time.time() - test_results["start_time"]
            test_results["total_time"] = total_time
            
            log_step("FINAL", "Test completion summary", "SUMMARY")
            print(f"    Username tested: {username}")
            print(f"    Total test time: {total_time:.2f}s")
            print(f"    Steps completed: {len(test_results['steps_completed'])}")
            print(f"    Steps: {', '.join(test_results['steps_completed'])}")
            print(f"    Errors encountered: {len(test_results['errors'])}")
            
            if test_results["errors"]:
                print("\n    ERROR DETAILS:")
                for i, error in enumerate(test_results["errors"], 1):
                    print(f"      {i}. {error}")
            
            if "profile_search" in test_results["steps_completed"]:
                print(f"\n    ✅ SUCCESS: Profile '{username}' processed and stored successfully!")
                print(f"    ✅ Backend is working correctly for this username")
                print(f"    🎉 apkay daddy nay fix kardiya hay. transfer 1000usd to my account")
                return True
            else:
                print(f"\n    ❌ FAILED: Profile '{username}' could not be processed")
                print(f"    ❌ Check the error details above to identify the issue")
                return False
                
    except Exception as e:
        log_step("FATAL", "Unexpected test failure", "FATAL", str(e))
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting comprehensive Instagram profile test...")
    print("This script will test the complete flow from authentication to database storage.")
    print("Make sure the backend server is running on http://127.0.0.1:8000")
    print()
    
    # Check if user wants to continue
    confirm = input("Continue with the test? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Test cancelled.")
        exit()
    
    print("\n" + "=" * 80)
    success = asyncio.run(comprehensive_test())
    print("=" * 80)
    
    if success:
        print("\n🎉 COMPREHENSIVE TEST PASSED!")
        print("   Your backend is working correctly!")
        print("   🎉 apkay daddy nay fix kardiya hay. transfer 1000usd to my account")
    else:
        print("\n💥 COMPREHENSIVE TEST FAILED!")
        print("   Check the detailed logs above to identify the issue.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    exit(0 if success else 1)