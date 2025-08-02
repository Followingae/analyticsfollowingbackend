#!/usr/bin/env python3
"""
Comprehensive Database Connectivity Test
Tests all aspects of database connectivity with detailed logging
"""
import asyncio
import asyncpg
import json
import time
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.insert(0, os.path.abspath('.'))

from app.core.config import settings
from app.database.connection import get_db, init_database
from app.database.unified_models import Profile, User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import uuid

def log_step(step_num, description, status="INFO", details=None):
    """Log each step with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"\n[{timestamp}] STEP {step_num}: {description}")
    print(f"[{timestamp}] STATUS: {status}")
    if details:
        print(f"[{timestamp}] DETAILS: {details}")
    print("-" * 80)

async def test_database_connectivity():
    """Comprehensive database connectivity test"""
    print("=" * 80)
    print("      COMPREHENSIVE DATABASE CONNECTIVITY TEST")
    print("=" * 80)
    
    username = input("\nEnter username to test database operations: ").strip()
    if not username:
        print("No username provided. Using 'testuser'")
        username = "testuser"
    
    test_results = {
        "username": username,
        "start_time": time.time(),
        "tests_passed": [],
        "tests_failed": [],
        "timings": {}
    }
    
    # TEST 1: Raw AsyncPG Connection
    log_step(1, "Testing raw AsyncPG connection", "RUNNING")
    step_start = time.time()
    
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        connection_time = time.time() - step_start
        test_results["timings"]["raw_connection"] = connection_time
        
        log_step(1, "Raw AsyncPG connection", "SUCCESS", f"Connected in {connection_time:.3f}s")
        print(f"    Connection info: {conn.get_server_version()}")
        
        # Test basic query
        result = await conn.fetchval("SELECT version()")
        print(f"    PostgreSQL version: {result}")
        
        await conn.close()
        test_results["tests_passed"].append("raw_asyncpg_connection")
        
    except Exception as e:
        connection_time = time.time() - step_start
        test_results["timings"]["raw_connection"] = connection_time
        log_step(1, "Raw AsyncPG connection", "ERROR", f"Failed after {connection_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"raw_asyncpg_connection: {e}")
    
    # TEST 2: SQLAlchemy Engine Connection
    log_step(2, "Testing SQLAlchemy engine connection", "RUNNING")
    step_start = time.time()
    
    try:
        await init_database()
        engine_time = time.time() - step_start
        test_results["timings"]["sqlalchemy_engine"] = engine_time
        
        log_step(2, "SQLAlchemy engine connection", "SUCCESS", f"Initialized in {engine_time:.3f}s")
        test_results["tests_passed"].append("sqlalchemy_engine")
        
    except Exception as e:
        engine_time = time.time() - step_start
        test_results["timings"]["sqlalchemy_engine"] = engine_time
        log_step(2, "SQLAlchemy engine connection", "ERROR", f"Failed after {engine_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"sqlalchemy_engine: {e}")
    
    # TEST 3: Database Session Creation
    log_step(3, "Testing database session creation", "RUNNING")
    step_start = time.time()
    
    try:
        async with get_db() as db:
            session_time = time.time() - step_start
            test_results["timings"]["session_creation"] = session_time
            
            log_step(3, "Database session creation", "SUCCESS", f"Session created in {session_time:.3f}s")
            print(f"    Session type: {type(db)}")
            print(f"    Session bind: {db.bind}")
            test_results["tests_passed"].append("session_creation")
            
    except Exception as e:
        session_time = time.time() - step_start
        test_results["timings"]["session_creation"] = session_time
        log_step(3, "Database session creation", "ERROR", f"Failed after {session_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"session_creation: {e}")
    
    # TEST 4: Table Existence Check
    log_step(4, "Testing table existence", "RUNNING")
    step_start = time.time()
    
    try:
        async with get_db() as db:
            tables_to_check = ['profiles', 'users', 'user_profile_access', 'user_searches']
            existing_tables = []
            
            for table in tables_to_check:
                result = await db.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                    )
                """))
                exists = result.scalar()
                if exists:
                    existing_tables.append(table)
            
            table_time = time.time() - step_start
            test_results["timings"]["table_check"] = table_time
            
            log_step(4, "Table existence check", "SUCCESS", f"Checked {len(tables_to_check)} tables in {table_time:.3f}s")
            print(f"    Existing tables: {existing_tables}")
            print(f"    Missing tables: {[t for t in tables_to_check if t not in existing_tables]}")
            test_results["tests_passed"].append("table_existence")
            test_results["existing_tables"] = existing_tables
            
    except Exception as e:
        table_time = time.time() - step_start
        test_results["timings"]["table_check"] = table_time
        log_step(4, "Table existence check", "ERROR", f"Failed after {table_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"table_existence: {e}")
    
    # TEST 5: Profile Schema Verification
    log_step(5, "Testing profiles table schema", "RUNNING")
    step_start = time.time()
    
    try:
        async with get_db() as db:
            columns_result = await db.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'profiles' AND table_schema = 'public'
                ORDER BY ordinal_position
            """))
            columns = columns_result.fetchall()
            
            schema_time = time.time() - step_start
            test_results["timings"]["schema_check"] = schema_time
            
            if columns:
                log_step(5, "Profiles table schema", "SUCCESS", f"Found {len(columns)} columns in {schema_time:.3f}s")
                
                required_fields = ['username', 'instagram_user_id', 'followers_count', 'following_count', 'posts_count', 'biography', 'raw_data']
                existing_columns = [col[0] for col in columns]
                missing_fields = [field for field in required_fields if field not in existing_columns]
                
                print(f"    Total columns: {len(columns)}")
                print(f"    Sample columns: {existing_columns[:10]}")
                if missing_fields:
                    print(f"    Missing required fields: {missing_fields}")
                else:
                    print(f"    All required fields present!")
                
                test_results["tests_passed"].append("schema_verification")
                test_results["profiles_columns"] = existing_columns
                test_results["missing_fields"] = missing_fields
            else:
                log_step(5, "Profiles table schema", "WARNING", "Profiles table exists but no columns found")
                
    except Exception as e:
        schema_time = time.time() - step_start
        test_results["timings"]["schema_check"] = schema_time
        log_step(5, "Profiles table schema", "ERROR", f"Failed after {schema_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"schema_verification: {e}")
    
    # TEST 6: Database Read Operations
    log_step(6, f"Testing database read for username: {username}", "RUNNING")
    step_start = time.time()
    
    try:
        async with get_db() as db:
            # Check if profile exists
            result = await db.execute(
                select(Profile).where(Profile.username == username.lower())
            )
            existing_profile = result.scalar_one_or_none()
            
            read_time = time.time() - step_start
            test_results["timings"]["database_read"] = read_time
            
            if existing_profile:
                log_step(6, "Database read operation", "SUCCESS", f"Found existing profile in {read_time:.3f}s")
                print(f"    Profile ID: {existing_profile.id}")
                print(f"    Full name: {existing_profile.full_name}")
                print(f"    Followers: {getattr(existing_profile, 'followers_count', 'N/A')}")
                print(f"    Created: {existing_profile.created_at}")
                test_results["profile_exists"] = True
                test_results["profile_data"] = {
                    "id": str(existing_profile.id),
                    "username": existing_profile.username,
                    "full_name": existing_profile.full_name,
                    "followers": getattr(existing_profile, 'followers_count', None)
                }
            else:
                log_step(6, "Database read operation", "SUCCESS", f"No existing profile found in {read_time:.3f}s")
                print(f"    Username '{username}' not found in database")
                print(f"    This means a Decodo API call would be needed")
                test_results["profile_exists"] = False
            
            test_results["tests_passed"].append("database_read")
            
    except Exception as e:
        read_time = time.time() - step_start
        test_results["timings"]["database_read"] = read_time
        log_step(6, "Database read operation", "ERROR", f"Failed after {read_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"database_read: {e}")
    
    # TEST 7: Database Write Operations (Test Insert)
    log_step(7, "Testing database write operations", "RUNNING")
    step_start = time.time()
    
    try:
        test_username = f"test_user_{int(time.time())}"
        test_data = {
            'username': test_username,
            'instagram_user_id': f"test_id_{int(time.time())}",
            'full_name': 'Test User',
            'biography': 'Test biography',
            'followers_count': 1000,
            'following_count': 500,
            'posts_count': 50,
            'is_verified': False,
            'is_private': False,
            'is_business_account': False,
            'raw_data': {'test': 'data'}
        }
        
        async with get_db() as db:
            # Try to create a test profile
            new_profile = Profile(**test_data)
            db.add(new_profile)
            await db.commit()
            await db.refresh(new_profile)
            
            write_time = time.time() - step_start
            test_results["timings"]["database_write"] = write_time
            
            log_step(7, "Database write operation", "SUCCESS", f"Created test profile in {write_time:.3f}s")
            print(f"    Test profile ID: {new_profile.id}")
            print(f"    Test username: {new_profile.username}")
            
            # Clean up - delete the test profile
            await db.delete(new_profile)
            await db.commit()
            print(f"    Test profile cleaned up")
            
            test_results["tests_passed"].append("database_write")
            
    except Exception as e:
        write_time = time.time() - step_start
        test_results["timings"]["database_write"] = write_time
        log_step(7, "Database write operation", "ERROR", f"Failed after {write_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"database_write: {e}")
        
        # Log specific error details for write failures
        print(f"    Error type: {type(e).__name__}")
        print(f"    Error details: {str(e)}")
        if hasattr(e, 'orig'):
            print(f"    Original error: {e.orig}")
    
    # TEST 8: Connection Pool Stress Test
    log_step(8, "Testing connection pool under stress", "RUNNING")
    step_start = time.time()
    
    try:
        async def test_connection():
            async with get_db() as db:
                result = await db.execute(text("SELECT 1"))
                return result.scalar()
        
        # Test multiple concurrent connections
        tasks = [test_connection() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        pool_time = time.time() - step_start
        test_results["timings"]["connection_pool"] = pool_time
        
        successful_connections = len([r for r in results if r == 1])
        failed_connections = len([r for r in results if isinstance(r, Exception)])
        
        if failed_connections == 0:
            log_step(8, "Connection pool stress test", "SUCCESS", f"All 5 connections succeeded in {pool_time:.3f}s")
            test_results["tests_passed"].append("connection_pool")
        else:
            log_step(8, "Connection pool stress test", "WARNING", f"{successful_connections}/5 connections succeeded in {pool_time:.3f}s")
            print(f"    Failed connections: {failed_connections}")
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"      Connection {i+1}: {result}")
        
    except Exception as e:
        pool_time = time.time() - step_start
        test_results["timings"]["connection_pool"] = pool_time
        log_step(8, "Connection pool stress test", "ERROR", f"Failed after {pool_time:.3f}s: {e}")
        test_results["tests_failed"].append(f"connection_pool: {e}")
    
    # FINAL SUMMARY
    total_time = time.time() - test_results["start_time"]
    test_results["total_time"] = total_time
    
    log_step("FINAL", "Database connectivity test summary", "SUMMARY")
    print(f"    Username tested: {username}")
    print(f"    Total test time: {total_time:.2f}s")
    print(f"    Tests passed: {len(test_results['tests_passed'])}")
    print(f"    Tests failed: {len(test_results['tests_failed'])}")
    print(f"    Passed tests: {', '.join(test_results['tests_passed'])}")
    
    if test_results["tests_failed"]:
        print(f"\n    FAILED TESTS:")
        for i, failure in enumerate(test_results["tests_failed"], 1):
            print(f"      {i}. {failure}")
    
    # Performance summary
    print(f"\n    PERFORMANCE SUMMARY:")
    for operation, timing in test_results["timings"].items():
        print(f"      {operation}: {timing:.3f}s")
    
    # Database readiness assessment
    critical_tests = ["raw_asyncpg_connection", "sqlalchemy_engine", "session_creation", "database_read"]
    critical_passed = [test for test in critical_tests if test in test_results["tests_passed"]]
    
    if len(critical_passed) == len(critical_tests):
        print(f"\n    ✅ DATABASE IS READY FOR PRODUCTION")
        print(f"    ✅ Profile lookup for '{username}': {'EXISTS' if test_results.get('profile_exists') else 'NEEDS DECODO CALL'}")
        database_ready = True
    else:
        print(f"\n    ❌ DATABASE HAS ISSUES")
        print(f"    ❌ Critical tests failed: {[test for test in critical_tests if test not in test_results['tests_passed']]}")
        database_ready = False
    
    return database_ready, test_results

if __name__ == "__main__":
    print("Starting comprehensive database connectivity test...")
    print("This will test all aspects of database connectivity and performance.")
    print()
    
    # Check if user wants to continue
    confirm = input("Continue with the test? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Test cancelled.")
        exit()
    
    print("\n" + "=" * 80)
    database_ready, results = asyncio.run(test_database_connectivity())
    print("=" * 80)
    
    if database_ready:
        print("\n🎉 DATABASE CONNECTIVITY TEST PASSED!")
        print("   Your database is ready for production use!")
        if results.get("profile_exists"):
            print(f"   The profile exists - no Decodo call needed!")
        else:
            print(f"   The profile doesn't exist - Decodo call will be needed.")
    else:
        print("\n💥 DATABASE CONNECTIVITY TEST FAILED!")
        print("   Fix the database issues before proceeding.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    exit(0 if database_ready else 1)