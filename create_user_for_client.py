"""
Create a user for the client in Supabase
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings

def create_client_user():
    """Create a user for the client"""
    try:
        print("Creating user in Supabase...")
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Client user credentials
        user_data = {
            "email": "client@analyticsfollowing.com",
            "password": "ClientPass2024!",
            "user_metadata": {
                "full_name": "Client User",
                "role": "premium"
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
                    
                    print("\n" + "=" * 60)
                    print("CLIENT USER CREDENTIALS")
                    print("=" * 60)
                    print(f"Email: {user_data['email']}")
                    print(f"Password: {user_data['password']}")
                    print(f"Role: {user_data['user_metadata']['role']}")
                    print("=" * 60)
                    print("\nUSAGE:")
                    print("1. Use these credentials to login via API")
                    print("2. Premium role gives access to advanced features")
                    print("3. All Instagram endpoints require authentication")
                    
                    return True
                else:
                    print("FAILED: Login test failed")
                    return False
            else:
                print("FAILED: User creation failed")
                return False
                
        except Exception as e:
            error_str = str(e)
            print(f"Error: {error_str}")
            
            # User might already exist
            if "already registered" in error_str.lower() or "already been registered" in error_str.lower():
                print("User already exists, testing login...")
                try:
                    login_response = supabase.auth.sign_in_with_password({
                        "email": user_data["email"],
                        "password": user_data["password"]
                    })
                    
                    if login_response.user:
                        print("SUCCESS: Existing user login successful!")
                        
                        print("\n" + "=" * 60)
                        print("CLIENT USER CREDENTIALS (EXISTING)")
                        print("=" * 60)
                        print(f"Email: {user_data['email']}")
                        print(f"Password: {user_data['password']}")
                        print(f"Role: {user_data['user_metadata']['role']}")
                        print("=" * 60)
                        
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
    success = create_client_user()
    if not success:
        print("\nUser creation failed!")