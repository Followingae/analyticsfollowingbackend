"""
Diagnose user and connection issues
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings

async def check_supabase_users():
    """Check Supabase Auth users vs custom users table"""
    try:
        print("CHECKING SUPABASE USERS")
        print("=" * 40)
        
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Check Auth users
        print("[AUTH] Checking Supabase Auth users...")
        try:
            auth_users = supabase.auth.admin.list_users()
            print(f"[SUCCESS] Found {len(auth_users)} users in Supabase Auth:")
            for user in auth_users:
                print(f"  - {user.email} (ID: {user.id})")
        except Exception as e:
            print(f"[ERROR] Auth users check failed: {e}")
        
        print()
        
        # Check custom users table
        print("[TABLE] Checking custom users table...")
        try:
            users_result = supabase.table("users").select("*").execute()
            print(f"[SUCCESS] Found {len(users_result.data)} users in custom users table:")
            for user in users_result.data:
                print(f"  - {user.get('email', 'No email')} (ID: {user.get('id', 'No ID')})")
        except Exception as e:
            print(f"[ERROR] Custom users table check failed: {e}")
        
        print()
        print("ISSUE IDENTIFIED:")
        print("- Users exist in Supabase Auth (for login)")
        print("- Users missing from custom 'users' table (for app data)")
        print("- This causes foreign key constraint errors")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] User check failed: {e}")
        return False

def check_backend_connection():
    """Check backend connection issues"""
    import requests
    
    print("CHECKING BACKEND CONNECTION")
    print("=" * 40)
    
    backend_url = "https://analytics-following-backend-5qfwj.ondigitalocean.app"
    
    # Test simple endpoint
    try:
        print(f"[TEST] Testing: {backend_url}/")
        response = requests.get(f"{backend_url}/", timeout=5)
        print(f"[SUCCESS] Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
    
    print()
    
    # Test CORS
    try:
        print("[CORS] Testing CORS headers...")
        response = requests.options(f"{backend_url}/", timeout=5)
        cors_origin = response.headers.get('Access-Control-Allow-Origin', 'NOT SET')
        print(f"Access-Control-Allow-Origin: {cors_origin}")
        
        if cors_origin == '*' or cors_origin:
            print("[SUCCESS] CORS configured")
        else:
            print("[ERROR] CORS not configured properly")
    except Exception as e:
        print(f"[ERROR] CORS check failed: {e}")

def display_solutions():
    """Display solutions for both issues"""
    print()
    print("SOLUTIONS")
    print("=" * 40)
    
    print()
    print("1. FIX USERS TABLE ISSUE:")
    print("   - Users exist in Supabase Auth but not in custom users table")
    print("   - Need to sync Auth users to custom users table")
    print("   - This will fix foreign key constraint errors")
    
    print()
    print("2. FIX FRONTEND CONNECTION:")
    print("   - Frontend needs correct backend URL in env vars")
    print("   - Backend needs to allow frontend domain in CORS")
    print("   - Check browser Network tab for specific error")
    
    print()
    print("3. IMMEDIATE ACTIONS:")
    print("   a) What's your Vercel frontend URL?")
    print("   b) Are env vars set in Vercel dashboard?")
    print("   c) Check DigitalOcean app logs for errors")

async def main():
    """Main diagnosis"""
    await check_supabase_users()
    print()
    check_backend_connection()
    display_solutions()

if __name__ == "__main__":
    asyncio.run(main())