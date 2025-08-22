#!/usr/bin/env python3
"""
Simple User Setup Script - Create essential tables and assign roles
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

async def create_essential_tables():
    """Create essential tables for user management"""
    try:
        async with get_session() as session:
            # Create user_roles table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    role_name VARCHAR(50) UNIQUE NOT NULL,
                    role_level INTEGER NOT NULL, 
                    description TEXT,
                    is_admin_role BOOLEAN DEFAULT false,
                    permissions_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            
            # Insert default roles
            await session.execute(text("""
                INSERT INTO user_roles (role_name, role_level, description, is_admin_role) VALUES 
                ('brand_free', 0, 'Free brand user with basic access', false),
                ('brand_standard', 1, 'Standard brand user with more features', false),
                ('brand_premium', 2, 'Premium brand user with advanced features', false),
                ('brand_enterprise', 3, 'Enterprise brand user with full features', false),
                ('admin', 4, 'Administrator with system access', true),
                ('super_admin', 5, 'Super administrator with full control', true)
                ON CONFLICT (role_name) DO NOTHING;
            """))
            
            # Check if users table exists, if not create a simple version
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    role_id UUID REFERENCES user_roles(id),
                    subscription_tier VARCHAR(50) DEFAULT 'free',
                    credits_balance INTEGER DEFAULT 1000,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            
            # Create credit_wallets table for brand users
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS credit_wallets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'free',
                    credits_balance INTEGER NOT NULL DEFAULT 0,
                    monthly_allowance INTEGER NOT NULL DEFAULT 1000,
                    billing_cycle_start DATE DEFAULT CURRENT_DATE,
                    billing_cycle_end DATE DEFAULT (CURRENT_DATE + INTERVAL '1 month'),
                    auto_recharge BOOLEAN DEFAULT false,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            
            await session.commit()
            logger.info("✅ Essential tables created successfully")
            
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise

async def get_auth_users():
    """Get users from Supabase auth.users"""
    try:
        async with get_session() as session:
            result = await session.execute(text("""
                SELECT id, email, created_at 
                FROM auth.users 
                ORDER BY created_at ASC
            """))
            
            users = []
            for row in result:
                users.append({
                    'id': str(row[0]),
                    'email': row[1],
                    'created_at': row[2]
                })
            
            return users
            
    except Exception as e:
        logger.error(f"❌ Error getting auth users: {e}")
        return []

async def assign_user_role_simple(user_id: str, role_name: str, subscription_tier: str = None):
    """Simple role assignment"""
    try:
        async with get_session() as session:
            # Get role ID
            result = await session.execute(text("""
                SELECT id, role_level FROM user_roles WHERE role_name = :role_name
            """), {"role_name": role_name})
            
            role_data = result.first()
            if not role_data:
                logger.error(f"❌ Role '{role_name}' not found")
                return False
            
            role_id, role_level = role_data
            
            # Insert/update user
            await session.execute(text("""
                INSERT INTO users (id, role_id, subscription_tier, credits_balance)
                VALUES (:user_id, :role_id, :subscription_tier, :credits)
                ON CONFLICT (id) DO UPDATE SET
                    role_id = :role_id,
                    subscription_tier = COALESCE(:subscription_tier, users.subscription_tier),
                    credits_balance = :credits,
                    updated_at = NOW()
            """), {
                "user_id": user_id,
                "role_id": role_id,
                "subscription_tier": subscription_tier or ("unlimited" if role_level >= 4 else "free"),
                "credits": 100000 if role_level >= 4 else 5000
            })
            
            # Create credit wallet for brand users
            if role_level < 4 and subscription_tier:
                credits_amount = 5000 if subscription_tier == "professional" else 1000
                await session.execute(text("""
                    INSERT INTO credit_wallets (user_id, subscription_tier, credits_balance, monthly_allowance)
                    VALUES (:user_id, :subscription_tier, :credits, :allowance)
                    ON CONFLICT (user_id) DO UPDATE SET
                        subscription_tier = :subscription_tier,
                        credits_balance = :credits,
                        monthly_allowance = :allowance,
                        updated_at = NOW()
                """), {
                    "user_id": user_id,
                    "subscription_tier": subscription_tier,
                    "credits": credits_amount,
                    "allowance": credits_amount
                })
            
            await session.commit()
            logger.info(f"✅ Assigned role '{role_name}' to user {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error assigning role: {e}")
        return False

async def create_superadmin_account(email: str, password: str):
    """Create superadmin account"""
    try:
        supabase = get_supabase()
        
        # Create user in Supabase Auth
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "role": "super_admin",
                "created_by": "system"
            }
        })
        
        if response.user:
            user_id = response.user.id
            logger.info(f"✅ Created Supabase auth user: {email} (ID: {user_id})")
            
            # Assign super_admin role
            await assign_user_role_simple(user_id, "super_admin")
            return user_id
        else:
            logger.error(f"❌ Failed to create Supabase user")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error creating superadmin: {e}")
        return None

async def main():
    """Main setup function"""
    try:
        logger.info("🚀 Starting simple user setup...")
        
        # Initialize database
        await init_database()
        
        # Create essential tables
        await create_essential_tables()
        
        # Get existing auth users
        auth_users = await get_auth_users()
        logger.info(f"📋 Found {len(auth_users)} auth users:")
        for user in auth_users:
            logger.info(f"  - {user['email']} (ID: {user['id']})")
        
        # Assign brand role to first existing user if any
        if auth_users:
            first_user = auth_users[0]
            logger.info(f"🎯 Assigning brand_premium role to: {first_user['email']}")
            await assign_user_role_simple(first_user['id'], "brand_premium", "professional")
        
        # Create superadmin account
        logger.info("👑 Creating superadmin account: zain@following.ae")
        superadmin_id = await create_superadmin_account("zain@following.ae", "Following0925_25")
        
        # Show final status
        logger.info("📋 Final setup complete!")
        final_auth_users = await get_auth_users()
        
        async with get_session() as session:
            for user in final_auth_users:
                result = await session.execute(text("""
                    SELECT ur.role_name, u.subscription_tier, u.credits_balance
                    FROM users u 
                    JOIN user_roles ur ON u.role_id = ur.id 
                    WHERE u.id = :user_id
                """), {"user_id": user['id']})
                
                user_data = result.first()
                if user_data:
                    role_name, subscription_tier, credits = user_data
                    logger.info(f"✅ {user['email']} | Role: {role_name} | Tier: {subscription_tier} | Credits: {credits}")
                else:
                    logger.info(f"⚠️ {user['email']} | No role assigned")
        
        logger.info("✅ User setup completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())