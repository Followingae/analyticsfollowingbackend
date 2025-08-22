#!/usr/bin/env python3
"""
Final User Setup Script - Working with actual table structure
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database.connection import init_database, get_session, get_supabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_current_users():
    """Get current users with correct column names"""
    try:
        async with get_session() as session:
            result = await session.execute(text("""
                SELECT id, email, role, subscription_tier, credits, status
                FROM users 
                ORDER BY created_at ASC;
            """))
            
            users = []
            for row in result:
                user_data = {
                    'id': str(row[0]),
                    'email': row[1],
                    'role': row[2],
                    'subscription_tier': row[3],
                    'credits': row[4],
                    'status': row[5]
                }
                users.append(user_data)
            
            return users
            
    except Exception as e:
        logger.error(f"❌ Error getting users: {e}")
        return []

async def update_user_to_brand_premium(user_id: str):
    """Update user to brand premium with professional tier"""
    try:
        async with get_session() as session:
            await session.execute(text("""
                UPDATE users 
                SET role = 'brand_premium', 
                    subscription_tier = 'professional', 
                    credits = 5000,
                    status = 'active',
                    updated_at = NOW()
                WHERE id = :user_id
            """), {"user_id": user_id})
            
            await session.commit()
            logger.info(f"✅ Updated user {user_id} to brand_premium with professional tier (5000 credits)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error updating user: {e}")
        return False

async def create_superadmin_user_record(user_id: str, email: str):
    """Create user record for existing auth user"""
    try:
        async with get_session() as session:
            await session.execute(text("""
                INSERT INTO users (
                    id, email, role, status, credits, subscription_tier,
                    full_name, preferences, notification_preferences,
                    created_at, updated_at
                )
                VALUES (
                    :user_id, :email, 'super_admin', 'active', 100000, 'unlimited',
                    'System Administrator', '{}', 
                    '{"email_notifications": true, "security_alerts": true}',
                    NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    role = 'super_admin',
                    subscription_tier = 'unlimited',
                    credits = 100000,
                    status = 'active',
                    updated_at = NOW()
            """), {
                "user_id": user_id,
                "email": email
            })
            
            await session.commit()
            logger.info(f"✅ Created/updated superadmin user record for {email}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating superadmin record: {e}")
        return False

async def main():
    """Main setup function"""
    try:
        logger.info("🚀 Starting final user setup...")
        
        # Initialize database
        await init_database()
        
        # Get current users
        current_users = await get_current_users()
        logger.info(f"📋 Found {len(current_users)} users:")
        for user in current_users:
            logger.info(f"  - {user['email']} | Role: {user['role']} | Tier: {user['subscription_tier']} | Credits: {user['credits']}")
        
        # Update first user to brand_premium if exists
        if current_users:
            first_user = current_users[0]
            if first_user['role'] != 'brand_premium':
                logger.info(f"🎯 Updating {first_user['email']} to brand_premium with professional tier")
                await update_user_to_brand_premium(first_user['id'])
            else:
                logger.info(f"✅ {first_user['email']} already has brand_premium role")
        
        # Check if we need to create user record for zain@following.ae
        zain_exists = any(user['email'] == 'zain@following.ae' for user in current_users)
        
        if not zain_exists:
            # Get zain's auth user ID
            async with get_session() as session:
                result = await session.execute(text("""
                    SELECT id FROM auth.users WHERE email = 'zain@following.ae'
                """))
                
                auth_user = result.first()
                if auth_user:
                    zain_user_id = str(auth_user[0])
                    logger.info(f"👑 Creating superadmin user record for zain@following.ae (ID: {zain_user_id})")
                    await create_superadmin_user_record(zain_user_id, "zain@following.ae")
                else:
                    logger.warning("⚠️ Auth user for zain@following.ae not found")
        else:
            # Update existing zain user to superadmin
            zain_user = next(user for user in current_users if user['email'] == 'zain@following.ae')
            if zain_user['role'] != 'super_admin':
                logger.info(f"👑 Updating existing zain@following.ae to super_admin")
                async with get_session() as session:
                    await session.execute(text("""
                        UPDATE users 
                        SET role = 'super_admin', 
                            subscription_tier = 'unlimited', 
                            credits = 100000,
                            status = 'active',
                            updated_at = NOW()
                        WHERE id = :user_id
                    """), {"user_id": zain_user['id']})
                    await session.commit()
                    logger.info("✅ Updated zain@following.ae to super_admin")
            else:
                logger.info("✅ zain@following.ae already has super_admin role")
        
        # Show final status
        logger.info("📋 Final user status:")
        final_users = await get_current_users()
        for user in final_users:
            logger.info(f"✅ {user['email']} | Role: {user['role']} | Tier: {user['subscription_tier']} | Credits: {user['credits']} | Status: {user['status']}")
        
        logger.info("✅ User setup completed successfully!")
        logger.info(f"🎉 Summary:")
        logger.info(f"  - Brand user (professional tier): {final_users[0]['email'] if final_users else 'None'}")
        logger.info(f"  - Superadmin: zain@following.ae")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())