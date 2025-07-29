"""
Simple test to create and verify users in Supabase
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings

def create_users():
    """Create users in Supabase without Unicode characters"""
    try:
        print("Connecting to Supabase...")
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Test user to create (try admin user)
        user_data = {
            "email": "admin@analyticsfollowing.com",
            "password": "Admin123!@#",
            "user_metadata": {
                "full_name": "Analytics Admin",
                "role": "admin"
            }
        }
        
        print(f"Creating user: {user_data['email']}")
        
        try:
            # Create user with Supabase Auth
            response = supabase.auth.admin.create_user({
                "email": user_data["email"],
                "password": user_data["password"],
                "user_metadata": user_data["user_metadata"],
                "email_confirm": True  # Auto-confirm email
            })
            
            if response.user:
                print("SUCCESS: User created successfully!")
                print(f"   User ID: {response.user.id}")
                print(f"   Email: {response.user.email}")
                print(f"   Role: {user_data['user_metadata']['role']}")
                
                # Test login immediately
                print("\nTesting login...")
                login_response = supabase.auth.sign_in_with_password({
                    "email": user_data["email"],
                    "password": user_data["password"]
                })
                
                if login_response.user:
                    print("SUCCESS: Login test successful!")
                    print(f"   User ID: {login_response.user.id}")
                    print(f"   Email: {login_response.user.email}")
                    return True
                else:
                    print("FAILED: Login test failed")
                    return False
            else:
                print("FAILED: User creation failed")
                return False
                
        except Exception as e:
            error_str = str(e)
            print(f"Error creating user: {error_str}")
            
            # User might already exist
            if "already registered" in error_str.lower() or "user_already_exists" in error_str.lower() or "already been registered" in error_str.lower():
                print("User already exists, testing login...")
                try:
                    login_response = supabase.auth.sign_in_with_password({
                        "email": user_data["email"],
                        "password": user_data["password"]
                    })
                    
                    if login_response.user:
                        print("SUCCESS: Existing user login successful!")
                        print(f"   User ID: {login_response.user.id}")
                        print(f"   Email: {login_response.user.email}")
                        return True
                    else:
                        print("FAILED: Existing user login failed")
                        return False
                except Exception as login_error:
                    print(f"FAILED: Login error: {login_error}")
                    return False
            else:
                print(f"FAILED: Unknown error: {error_str}")
                return False
        
    except Exception as e:
        print(f"FAILED: Connection error: {e}")
        return False

if __name__ == "__main__":
    success = create_users()
    if success:
        print("\nUser is ready for authentication tests!")
    else:
        print("\nUser creation/verification failed!")