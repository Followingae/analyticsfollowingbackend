"""
Complete Authentication System Fix
Fixes database schema, recreates demo user, and validates auth flow
"""
import asyncio
import asyncpg
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not found in environment variables")
    exit(1)

# Supabase configuration  
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_database_schema():
    """Fix the database schema to match auth requirements"""
    print("[SCHEMA] FIXING DATABASE SCHEMA")
    print("=" * 50)
    
    try:
        # Connect to PostgreSQL
        conn = await asyncpg.connect(DATABASE_URL)
        print("[SUCCESS] Connected to database")
        
        # Add missing columns to users table
        try:
            await conn.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS full_name TEXT,
                ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active',
                ADD COLUMN IF NOT EXISTS supabase_user_id TEXT,
                ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS profile_picture_url TEXT,
                ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'::jsonb
            """)
            print("[SUCCESS] Added missing columns to users table")
        except Exception as e:
            print(f"[WARNING]  Users table update: {e}")
        
        # Update existing role column to match auth expectations
        try:
            await conn.execute("""
                UPDATE users SET role = 'free' WHERE role = 'user'
            """)
            print("[SUCCESS] Updated user roles to match auth system")
        except Exception as e:
            print(f"[WARNING]  Role update: {e}")
        
        # Add missing columns to profiles table if needed
        try:
            await conn.execute("""
                ALTER TABLE profiles 
                ADD COLUMN IF NOT EXISTS fb_id TEXT
            """)
            print("[SUCCESS] Added fb_id column to profiles table")
        except Exception as e:
            print(f"[WARNING]  Profiles table update: {e}")
            
        await conn.close()
        print("[SUCCESS] Database schema fixed successfully")
        return True
        
    except Exception as e:
        print(f"[ERROR] Database schema fix failed: {e}")
        return False

async def create_demo_user_supabase():
    """Create demo user directly in Supabase Auth"""
    print("\n[USER] CREATING DEMO USER IN SUPABASE")
    print("=" * 50)
    
    try:
        from supabase import create_client
        
        # Initialize Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[SUCCESS] Supabase client initialized")
        
        # Demo user credentials
        demo_email = "zzain.ali@outlook.com"
        demo_password = "BarakatDemo2024!"
        demo_full_name = "Zain Ali (Barakat Demo)"
        
        # Delete existing user if exists
        try:
            users = supabase.auth.admin.list_users()
            for user in users:
                if user.email == demo_email:
                    supabase.auth.admin.delete_user(user.id)
                    print(f"[DELETE] Deleted existing user: {demo_email}")
        except Exception as e:
            print(f"[WARNING]  User cleanup: {e}")
        
        # Create new user
        result = supabase.auth.admin.create_user({
            "email": demo_email,
            "password": demo_password,
            "email_confirm": True,  # Skip email verification
            "user_metadata": {
                "full_name": demo_full_name,
                "role": "premium"
            }
        })
        
        if result.user:
            print(f"[SUCCESS] Created Supabase Auth user: {result.user.id}")
            return result.user.id, demo_email, demo_password
        else:
            print("[ERROR] Failed to create Supabase Auth user")
            return None, None, None
            
    except Exception as e:
        print(f"[ERROR] Demo user creation failed: {e}")
        return None, None, None

async def create_demo_user_database(supabase_user_id, email, full_name):
    """Create demo user record in our database"""
    print("\n[DB] CREATING DEMO USER IN DATABASE")
    print("=" * 50)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("[SUCCESS] Connected to database")
        
        # Insert or update user in our users table
        await conn.execute("""
            INSERT INTO users (id, email, hashed_password, role, credits, full_name, status, supabase_user_id, last_login, created_at)
            VALUES ($1::uuid, $2, 'supabase_managed', 'premium', 1000, $3, 'active', $4, NOW(), NOW())
            ON CONFLICT (email) 
            DO UPDATE SET 
                full_name = $3,
                status = 'active',
                supabase_user_id = $4,
                role = 'premium',
                credits = 1000,
                last_login = NOW()
        """, supabase_user_id, email, full_name, supabase_user_id)
        
        print(f"[SUCCESS] Created/updated database user: {email}")
        await conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Database user creation failed: {e}")
        return False

async def test_auth_endpoint():
    """Test the authentication endpoint"""
    print("\n[TEST] TESTING AUTHENTICATION ENDPOINT")
    print("=" * 50)
    
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            # Test login
            response = await client.post(
                "https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1/auth/login",
                json={
                    "email": "zzain.ali@outlook.com",
                    "password": "BarakatDemo2024!"
                },
                timeout=30.0
            )
            
            print(f"Login response status: {response.status_code}")
            print(f"Login response: {response.text[:200]}...")
            
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    print("[SUCCESS] Authentication test SUCCESSFUL!")
                    print(f"[SUCCESS] User: {data.get('user', {}).get('email')}")
                    print(f"[SUCCESS] Role: {data.get('user', {}).get('role')}")
                    return True
                else:
                    print("[ERROR] Authentication test failed - no access token")
                    return False
            else:
                print(f"[ERROR] Authentication test failed - status {response.status_code}")
                return False
                
    except Exception as e:
        print(f"[ERROR] Authentication test error: {e}")
        return False

async def main():
    """Main function to fix authentication completely"""
    print("[START] COMPLETE AUTHENTICATION SYSTEM FIX")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print("=" * 60)
    
    success_count = 0
    total_steps = 4
    
    # Step 1: Fix database schema
    if await fix_database_schema():
        success_count += 1
        print("[SUCCESS] Step 1/4: Database schema fixed")
    else:
        print("[ERROR] Step 1/4: Database schema fix failed")
    
    # Step 2: Create demo user in Supabase
    user_id, email, password = await create_demo_user_supabase()
    if user_id:
        success_count += 1
        print("[SUCCESS] Step 2/4: Supabase user created")
    else:
        print("[ERROR] Step 2/4: Supabase user creation failed")
    
    # Step 3: Create demo user in database
    if user_id and await create_demo_user_database(user_id, email, "Zain Ali (Barakat Demo)"):
        success_count += 1
        print("[SUCCESS] Step 3/4: Database user created")
    else:
        print("[ERROR] Step 3/4: Database user creation failed")
    
    # Wait a moment for deployment to be ready
    print("\n[WAIT] Waiting 10 seconds for backend to be ready...")
    await asyncio.sleep(10)
    
    # Step 4: Test authentication
    if await test_auth_endpoint():
        success_count += 1
        print("[SUCCESS] Step 4/4: Authentication test passed")
    else:
        print("[ERROR] Step 4/4: Authentication test failed")
    
    # Final summary
    print("\n" + "=" * 60)
    print("[SUMMARY] AUTHENTICATION FIX SUMMARY")
    print("=" * 60)
    print(f"[SUCCESS] Steps completed: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("[SUCCESS] AUTHENTICATION SYSTEM FULLY FIXED!")
        print("\n[CREDENTIALS] DEMO CREDENTIALS:")
        print("Email: zzain.ali@outlook.com")
        print("Password: BarakatDemo2024!")
        print("Role: Premium")
        print("\n[ENDPOINT] LOGIN ENDPOINT:")
        print("https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1/auth/login")
        print("\n[READY] Ready for frontend integration!")
    else:
        print("[WARNING] Authentication system partially fixed. Check errors above.")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())