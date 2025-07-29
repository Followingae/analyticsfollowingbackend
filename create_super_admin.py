"""
Create a super admin account for development and testing
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from app.services.auth_service import auth_service
from app.models.auth import UserCreate, UserRole


async def create_super_admin():
    """Create a super admin account"""
    try:
        print("Creating super admin account...")
        
        # Initialize auth service
        await auth_service.initialize()
        
        # Create super admin user
        admin_user = UserCreate(
            email="admin@analyticsfollowing.com",
            password="SuperAdmin123!",  # Change this to a secure password
            full_name="System Administrator",
            role=UserRole.ADMIN
        )
        
        # Register the user
        result = await auth_service.register_user(admin_user)
        
        print("✅ Super admin account created successfully!")
        print(f"Email: {admin_user.email}")
        print(f"Password: {admin_user.password}")
        print(f"Role: {admin_user.role.value}")
        print(f"User ID: {result.id}")
        
        # Test login
        print("\nTesting login...")
        login_result = await auth_service.login_user(admin_user.email, admin_user.password)
        print(f"✅ Login successful!")
        print(f"Access Token: {login_result.access_token[:50]}...")
        print(f"Token Type: {login_result.token_type}")
        
        print(f"\n🎯 Use these credentials to access authenticated endpoints")
        
    except Exception as e:
        print(f"Error creating super admin: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_super_admin())