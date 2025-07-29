"""
Test the fixed auth service
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from app.services.auth_service_fixed import auth_service_fixed
from app.models.auth import LoginRequest

async def test_fixed_auth_service():
    """Test the fixed auth service"""
    print("TESTING FIXED AUTH SERVICE")
    print("=" * 35)
    
    try:
        # Initialize
        print("[INIT] Initializing fixed auth service...")
        success = await auth_service_fixed.initialize()
        
        if success:
            print("[SUCCESS] Auth service initialized")
            
            # Test login
            print("[TEST] Testing login with demo credentials...")
            login_request = LoginRequest(
                email="zzain.ali@outlook.com",
                password="BarakatDemo2024!"
            )
            
            try:
                result = await auth_service_fixed.login_user(login_request)
                print("[SUCCESS] Login successful!")
                print(f"Access token: {result.access_token[:50]}...")
                print(f"User: {result.user.email}")
                return True
            except Exception as login_error:
                print(f"[ERROR] Login failed: {login_error}")
                return False
        else:
            print("[ERROR] Auth service initialization failed")
            return False
            
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

async def main():
    """Main test function"""
    success = await test_fixed_auth_service()
    
    if success:
        print("\\n[SUCCESS] Fixed auth service works!")
        print("You can now replace the original auth service with this fixed version")
    else:
        print("\\n[ERROR] Fixed auth service still has issues")

if __name__ == "__main__":
    asyncio.run(main())