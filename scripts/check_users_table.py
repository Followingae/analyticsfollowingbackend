#!/usr/bin/env python3
"""
Check the current users table structure and manage users
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

async def check_users_table_structure():
    """Check the current users table structure"""
    try:
        async with get_session() as session:
            # Get table structure
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            
            logger.info("📋 Current users table structure:")
            for row in result:
                logger.info(f"  - {row[0]} | {row[1]} | Nullable: {row[2]} | Default: {row[3]}")
            
            # Check current users data
            result = await session.execute(text("""
                SELECT id, email, role, subscription_tier, credits_balance, is_active
                FROM users 
                ORDER BY created_at ASC;
            """))
            
            logger.info("📋 Current users:")
            users = []
            for row in result:
                user_data = {
                    'id': str(row[0]),
                    'email': row[1],
                    'role': row[2],
                    'subscription_tier': row[3],
                    'credits_balance': row[4],
                    'is_active': row[5]
                }
                users.append(user_data)
                logger.info(f"  - {user_data['email']} | Role: {user_data['role']} | Tier: {user_data['subscription_tier']} | Credits: {user_data['credits_balance']}")
            
            return users
            
    except Exception as e:
        logger.error(f"❌ Error checking users table: {e}")
        return []

async def update_user_role_and_tier(user_id: str, role: str, subscription_tier: str, credits_balance: int):
    """Update user role and subscription tier"""
    try:
        async with get_session() as session:
            await session.execute(text("""
                UPDATE users 
                SET role = :role, 
                    subscription_tier = :subscription_tier, 
                    credits_balance = :credits_balance,
                    updated_at = NOW()
                WHERE id = :user_id
            """), {
                "user_id": user_id,
                "role": role,
                "subscription_tier": subscription_tier,
                "credits_balance": credits_balance
            })
            
            await session.commit()
            logger.info(f"✅ Updated user {user_id} to role: {role}, tier: {subscription_tier}, credits: {credits_balance}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error updating user: {e}")
        return False

async def create_user_record(user_id: str, email: str, role: str, subscription_tier: str, credits_balance: int):
    """Create a new user record"""
    try:
        async with get_session() as session:
            await session.execute(text("""
                INSERT INTO users (id, email, role, subscription_tier, credits_balance, is_active, created_at, updated_at)
                VALUES (:user_id, :email, :role, :subscription_tier, :credits_balance, true, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    role = :role,
                    subscription_tier = :subscription_tier,
                    credits_balance = :credits_balance,
                    updated_at = NOW()
            """), {
                "user_id": user_id,
                "email": email,
                "role": role,
                "subscription_tier": subscription_tier,
                "credits_balance": credits_balance
            })
            
            await session.commit()
            logger.info(f"✅ Created/updated user record for {email}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating user record: {e}")
        return False

async def main():
    """Main function"""
    try:
        logger.info("🚀 Starting user management...")
        
        # Initialize database
        await init_database()
        
        # Check current table structure and users
        current_users = await check_users_table_structure()
        
        # If we have existing users, update the first one to brand_premium
        if current_users:
            first_user = current_users[0]
            logger.info(f"🎯 Updating first user {first_user['email']} to brand_premium with professional tier")
            await update_user_role_and_tier(
                first_user['id'], 
                "brand_premium", 
                "professional", 
                5000
            )
        
        # Check if zain@following.ae already exists in users table
        zain_exists = any(user['email'] == 'zain@following.ae' for user in current_users)
        
        if not zain_exists:
            # We know from the previous run that zain@following.ae auth user already exists
            # Get the auth user ID for zain@following.ae
            async with get_session() as session:
                result = await session.execute(text("""
                    SELECT id FROM auth.users WHERE email = 'zain@following.ae'
                """))
                
                auth_user = result.first()
                if auth_user:
                    zain_user_id = str(auth_user[0])
                    logger.info(f"📋 Found existing auth user for zain@following.ae: {zain_user_id}")
                    
                    # Create user record
                    await create_user_record(
                        zain_user_id,
                        "zain@following.ae",
                        "super_admin",
                        "unlimited",
                        100000
                    )
                else:
                    logger.warning("⚠️ Auth user for zain@following.ae not found")
        else:
            # Update existing zain user to super_admin
            zain_user = next(user for user in current_users if user['email'] == 'zain@following.ae')
            logger.info(f"🎯 Updating existing zain@following.ae to super_admin")
            await update_user_role_and_tier(
                zain_user['id'],
                "super_admin",
                "unlimited",
                100000
            )
        
        # Show final status
        logger.info("📋 Final user status:")
        final_users = await check_users_table_structure()
        
        logger.info("✅ User management completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())