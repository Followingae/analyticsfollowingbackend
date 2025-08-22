#!/usr/bin/env python3
"""
User Management Script for Analytics Following Backend
Handles user role assignments and account creation
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database.connection import init_database, get_session, get_supabase
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_migration_status():
    """Check if the comprehensive user segregation migration has been applied"""
    try:
        async with get_session() as session:
            # Check if user_roles table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'user_roles'
                );
            """))
            user_roles_exists = result.scalar()
            
            if not user_roles_exists:
                logger.error("❌ Migration not applied! user_roles table does not exist")
                return False
            
            # Check if roles are initialized
            result = await session.execute(text("SELECT COUNT(*) FROM user_roles"))
            role_count = result.scalar()
            
            logger.info(f"✅ Migration status: user_roles table exists with {role_count} roles")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error checking migration status: {e}")
        return False

async def apply_migration_if_needed():
    """Apply the comprehensive user segregation migration if not already applied"""
    try:
        migration_applied = await check_migration_status()
        if migration_applied:
            logger.info("✅ Migration already applied")
            return True
            
        logger.info("🚀 Applying comprehensive user segregation migration...")
        
        # Read and execute the migration file
        migration_file = Path(__file__).parent.parent / "migrations" / "comprehensive_user_segregation_schema.sql"
        
        if not migration_file.exists():
            logger.error(f"❌ Migration file not found: {migration_file}")
            return False
            
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        async with get_session() as session:
            # Execute the migration in chunks (split by --;)
            sql_statements = [stmt.strip() for stmt in migration_sql.split('--;') if stmt.strip()]
            
            for i, statement in enumerate(sql_statements):
                if statement and not statement.startswith('--'):
                    try:
                        await session.execute(text(statement))
                        logger.info(f"✅ Executed statement {i+1}/{len(sql_statements)}")
                    except Exception as e:
                        logger.warning(f"⚠️ Statement {i+1} failed (might be expected): {e}")
            
            await session.commit()
            logger.info("✅ Migration applied successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error applying migration: {e}")
        return False

async def get_current_users():
    """Get all current users from auth.users"""
    try:
        async with get_session() as session:
            result = await session.execute(text("""
                SELECT 
                    au.id, 
                    au.email, 
                    au.created_at,
                    ur.role_name,
                    ur.role_level
                FROM auth.users au
                LEFT JOIN users u ON au.id = u.id
                LEFT JOIN user_roles ur ON u.role_id = ur.id
                ORDER BY au.created_at DESC
            """))
            
            users = []
            for row in result:
                users.append({
                    'id': str(row[0]),
                    'email': row[1],
                    'created_at': row[2],
                    'role_name': row[3] or 'No role assigned',
                    'role_level': row[4] or 'N/A'
                })
            
            return users
            
    except Exception as e:
        logger.error(f"❌ Error getting users: {e}")
        return []

async def create_superadmin_account(email: str, password: str):
    """Create a superadmin account using Supabase Auth"""
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
            
            # Assign super_admin role in our system
            await assign_user_role(user_id, "super_admin")
            
            return user_id
        else:
            logger.error(f"❌ Failed to create Supabase user: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error creating superadmin account: {e}")
        return None

async def assign_user_role(user_id: str, role_name: str, subscription_tier: str = None):
    """Assign a role to a user and create necessary records"""
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
            
            # Create or update user record
            await session.execute(text("""
                INSERT INTO users (id, role_id, subscription_tier, credits_balance, created_at, updated_at)
                VALUES (:user_id, :role_id, :subscription_tier, :credits, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    role_id = :role_id,
                    subscription_tier = COALESCE(:subscription_tier, users.subscription_tier),
                    updated_at = NOW()
            """), {
                "user_id": user_id,
                "role_id": role_id,
                "subscription_tier": subscription_tier or ("unlimited" if role_level >= 4 else "free"),
                "credits": 100000 if role_level >= 4 else 5000  # Admin gets unlimited, brand gets 5000
            })
            
            # Create user profile if it doesn't exist
            await session.execute(text("""
                INSERT INTO user_profiles (id, user_id, created_at, updated_at)
                VALUES (gen_random_uuid(), :user_id, NOW(), NOW())
                ON CONFLICT (user_id) DO NOTHING
            """), {"user_id": user_id})
            
            # For brand users, create credit wallet
            if role_level < 4 and subscription_tier:
                await session.execute(text("""
                    INSERT INTO credit_wallets (user_id, subscription_tier, credits_balance, monthly_allowance, created_at, updated_at)
                    VALUES (:user_id, :subscription_tier, :credits, :allowance, NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        subscription_tier = :subscription_tier,
                        credits_balance = :credits,
                        monthly_allowance = :allowance,
                        updated_at = NOW()
                """), {
                    "user_id": user_id,
                    "subscription_tier": subscription_tier,
                    "credits": 5000 if subscription_tier == "professional" else 1000,
                    "allowance": 5000 if subscription_tier == "professional" else 1000
                })
            
            await session.commit()
            logger.info(f"✅ Assigned role '{role_name}' to user {user_id}")
            if subscription_tier:
                logger.info(f"✅ Set subscription tier to '{subscription_tier}'")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error assigning role: {e}")
        return False

async def main():
    """Main function to set up users"""
    try:
        logger.info("🚀 Starting user management setup...")
        
        # Initialize database
        await init_database()
        
        # Apply migration if needed
        migration_success = await apply_migration_if_needed()
        if not migration_success:
            logger.error("❌ Failed to apply migration. Exiting.")
            return
        
        # Get current users
        current_users = await get_current_users()
        logger.info(f"📋 Found {len(current_users)} existing users:")
        for user in current_users:
            logger.info(f"  - {user['email']} | Role: {user['role_name']} | ID: {user['id']}")
        
        # If there are existing users, assign brand role to the first one
        if current_users:
            first_user = current_users[0]
            logger.info(f"🎯 Assigning brand_premium role to existing user: {first_user['email']}")
            await assign_user_role(first_user['id'], "brand_premium", "professional")
        
        # Create superadmin account
        logger.info("👑 Creating superadmin account: zain@following.ae")
        superadmin_id = await create_superadmin_account("zain@following.ae", "Following0925_25")
        
        if superadmin_id:
            logger.info("✅ Superadmin account created successfully")
        else:
            logger.error("❌ Failed to create superadmin account")
        
        # Final status check
        logger.info("📋 Final user status:")
        final_users = await get_current_users()
        for user in final_users:
            logger.info(f"  - {user['email']} | Role: {user['role_name']} | Level: {user['role_level']}")
        
        logger.info("✅ User management setup completed!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())