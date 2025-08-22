#!/usr/bin/env python3
"""
Check table constraints and fix user setup
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database.connection import init_database, get_session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_constraints():
    """Check table constraints"""
    try:
        async with get_session() as session:
            # Check role constraints
            result = await session.execute(text("""
                SELECT conname, conkey, consrc 
                FROM pg_constraint 
                WHERE conrelid = 'users'::regclass 
                AND contype = 'c';
            """))
            
            logger.info("📋 Table constraints:")
            for row in result:
                logger.info(f"  - {row[0]}: {row[2] if row[2] else 'No source available'}")
            
            # Check if there are ENUM types for role
            result = await session.execute(text("""
                SELECT enumlabel FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'user_role'
                )
                ORDER BY enumsortorder;
            """))
            
            roles = [row[0] for row in result]
            if roles:
                logger.info(f"📋 Valid roles (ENUM): {roles}")
            else:
                logger.info("📋 No ENUM type found for roles")
            
            # Check current user data to see what roles are actually being used
            result = await session.execute(text("""
                SELECT DISTINCT role FROM users;
            """))
            
            current_roles = [row[0] for row in result]
            logger.info(f"📋 Currently used roles: {current_roles}")
            
    except Exception as e:
        logger.error(f"❌ Error checking constraints: {e}")

async def update_user_with_valid_role(user_id: str, role: str, subscription_tier: str, credits: int):
    """Update user with proper values for all required fields"""
    try:
        async with get_session() as session:
            await session.execute(text("""
                UPDATE users 
                SET role = :role, 
                    subscription_tier = :subscription_tier, 
                    credits = :credits,
                    credits_used_this_month = 0,
                    status = 'active',
                    updated_at = NOW()
                WHERE id = :user_id
            """), {
                "user_id": user_id,
                "role": role,
                "subscription_tier": subscription_tier,
                "credits": credits
            })
            
            await session.commit()
            logger.info(f"✅ Updated user {user_id} to role: {role}, tier: {subscription_tier}, credits: {credits}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error updating user: {e}")
        return False

async def create_superadmin_with_all_fields(user_id: str, email: str):
    """Create superadmin user record with all required fields"""
    try:
        async with get_session() as session:
            await session.execute(text("""
                INSERT INTO users (
                    id, email, role, status, credits, credits_used_this_month,
                    subscription_tier, full_name, preferences, notification_preferences,
                    created_at, updated_at
                )
                VALUES (
                    :user_id, :email, 'admin', 'active', 100000, 0,
                    'unlimited', 'System Administrator', '{}', 
                    '{"email_notifications": true, "security_alerts": true}',
                    NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    role = 'admin',
                    subscription_tier = 'unlimited',
                    credits = 100000,
                    credits_used_this_month = 0,
                    status = 'active',
                    updated_at = NOW()
            """), {
                "user_id": user_id,
                "email": email
            })
            
            await session.commit()
            logger.info(f"✅ Created/updated admin user record for {email}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating admin record: {e}")
        return False

async def main():
    """Main function"""
    try:
        logger.info("🚀 Checking constraints and fixing user setup...")
        
        # Initialize database
        await init_database()
        
        # Check constraints
        await check_constraints()
        
        # Get current users
        async with get_session() as session:
            result = await session.execute(text("""
                SELECT id, email, role, subscription_tier, credits
                FROM users 
                ORDER BY created_at ASC;
            """))
            
            current_users = []
            for row in result:
                user_data = {
                    'id': str(row[0]),
                    'email': row[1],
                    'role': row[2],
                    'subscription_tier': row[3],
                    'credits': row[4]
                }
                current_users.append(user_data)
        
        logger.info(f"📋 Current users:")
        for user in current_users:
            logger.info(f"  - {user['email']} | Role: {user['role']} | Tier: {user['subscription_tier']} | Credits: {user['credits']}")
        
        # Update first user to premium (using existing valid role)
        if current_users:
            first_user = current_users[0]
            if first_user['role'] == 'free':
                logger.info(f"🎯 Updating {first_user['email']} to premium role with professional tier")
                await update_user_with_valid_role(
                    first_user['id'], 
                    'premium',  # Use 'premium' instead of 'brand_premium'
                    'professional', 
                    5000
                )
        
        # Handle zain@following.ae
        zain_exists = any(user['email'] == 'zain@following.ae' for user in current_users)
        
        if not zain_exists:
            # Get zain's auth user ID and create admin record
            async with get_session() as session:
                result = await session.execute(text("""
                    SELECT id FROM auth.users WHERE email = 'zain@following.ae'
                """))
                
                auth_user = result.first()
                if auth_user:
                    zain_user_id = str(auth_user[0])
                    logger.info(f"👑 Creating admin user record for zain@following.ae")
                    await create_superadmin_with_all_fields(zain_user_id, "zain@following.ae")
        else:
            # Update existing zain user
            zain_user = next(user for user in current_users if user['email'] == 'zain@following.ae')
            logger.info(f"👑 Updating zain@following.ae to admin role")
            await update_user_with_valid_role(
                zain_user['id'],
                'admin',  # Use 'admin' instead of 'super_admin'
                'unlimited',
                100000
            )
        
        # Show final status
        logger.info("📋 Final user status:")
        async with get_session() as session:
            result = await session.execute(text("""
                SELECT email, role, subscription_tier, credits, status
                FROM users 
                ORDER BY created_at ASC;
            """))
            
            for row in result:
                logger.info(f"✅ {row[0]} | Role: {row[1]} | Tier: {row[2]} | Credits: {row[3]} | Status: {row[4]}")
        
        logger.info("✅ User setup completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())