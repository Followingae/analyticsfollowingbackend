"""
Create real Supabase users in your actual Supabase project
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings


async def create_supabase_users():
    """Create real users in your Supabase authentication"""
    try:
        print("="*80)
        print("CREATING REAL SUPABASE USERS")  
        print("="*80)
        print(f"Supabase URL: {settings.SUPABASE_URL}")
        print(f"Using service role key...")
        
        # Create Supabase client with service role (can create users)
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Demo users to create
        demo_users = [
            {
                "email": "admin@analyticsfollowing.com",
                "password": "Admin123!@#",
                "user_metadata": {
                    "full_name": "Analytics Admin",
                    "role": "admin"
                }
            },
            {
                "email": "premium@analyticsfollowing.com", 
                "password": "Premium123!@#",
                "user_metadata": {
                    "full_name": "Premium User",
                    "role": "premium"
                }
            },
            {
                "email": "free@analyticsfollowing.com",
                "password": "Free123!@#", 
                "user_metadata": {
                    "full_name": "Free User",
                    "role": "free"
                }
            }
        ]
        
        print("Creating users in Supabase...")
        created_users = []
        
        for user_data in demo_users:
            try:
                print(f"\nCreating user: {user_data['email']}")
                
                # Create user with Supabase Auth
                response = supabase.auth.admin.create_user({
                    "email": user_data["email"],
                    "password": user_data["password"],
                    "user_metadata": user_data["user_metadata"],
                    "email_confirm": True  # Auto-confirm email
                })
                
                if response.user:
                    print(f"✅ User created successfully!")
                    print(f"   User ID: {response.user.id}")
                    print(f"   Email: {response.user.email}")
                    print(f"   Role: {user_data['user_metadata']['role']}")
                    
                    created_users.append({
                        "email": user_data["email"],
                        "password": user_data["password"],
                        "role": user_data["user_metadata"]["role"],
                        "user_id": response.user.id
                    })
                else:
                    print(f"❌ Failed to create user: {user_data['email']}")
                    
            except Exception as e:
                print(f"❌ Error creating user {user_data['email']}: {str(e)}")
                # User might already exist, that's okay
                if "already registered" in str(e).lower():
                    print(f"   User already exists, that's fine!")
                    created_users.append({
                        "email": user_data["email"],
                        "password": user_data["password"],
                        "role": user_data["user_metadata"]["role"],
                        "user_id": "existing"
                    })
        
        print(f"\n" + "="*80)
        print("SUPABASE USERS READY!")
        print("="*80)
        
        print(f"\n🎯 LOGIN CREDENTIALS:")
        for user in created_users:
            print(f"\n{user['role'].upper()} USER:")
            print(f"  Email: {user['email']}")
            print(f"  Password: {user['password']}")
            print(f"  Role: {user['role']}")
        
        print(f"\n🚀 HOW TO USE:")
        print(f"1. These users are now in your Supabase Authentication tab")
        print(f"2. Use POST /api/v1/auth/login with email/password")
        print(f"3. All Instagram endpoints now require authentication")
        
        print(f"\n📋 TEST LOGIN:")
        print(f"curl -X POST \"http://127.0.0.1:8000/api/v1/auth/login\" \\")
        print(f"  -H \"Content-Type: application/json\" \\")
        print(f"  -d '{{\"email\":\"admin@analyticsfollowing.com\",\"password\":\"Admin123!@#\"}}'")
        
        return created_users
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_supabase_users())