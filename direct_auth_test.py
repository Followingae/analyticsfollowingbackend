"""
Direct test of auth service initialization
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from app.services.auth_service import auth_service
from app.models.auth import LoginRequest

async def test_auth_service_direct():
    """Test auth service directly"""
    print("=" * 80)
    print("DIRECT AUTH SERVICE TEST")
    print("=" * 80)
    
    try:
        # Initialize auth service
        print("1. Initializing auth service...")
        init_success = await auth_service.initialize()
        print(f"   Auth service initialized: {init_success}")
        
        if init_success:
            # Test login
            print("\n2. Testing login...")
            login_data = LoginRequest(
                email="admin@analyticsfollowing.com",
                password="Admin123!@#"
            )
            
            try:
                login_response = await auth_service.login_user(login_data)
                print(f"SUCCESS: Login successful!")
                print(f"   Access token: {login_response.access_token[:50]}...")
                print(f"   User: {login_response.user.email}")
                print(f"   Role: {login_response.user.role}")
                
                # Test token validation
                print("\n3. Testing token validation...")
                user = await auth_service.get_current_user(login_response.access_token)
                print(f"SUCCESS: Token validation successful!")
                print(f"   User ID: {user.id}")
                print(f"   Email: {user.email}")
                print(f"   Role: {user.role}")
                
            except Exception as login_error:
                print(f"FAILED: Login error: {login_error}")
                
        else:
            print("FAILED: Auth service initialization failed")
            
    except Exception as e:
        print(f"FAILED: Direct test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_auth_service_direct())