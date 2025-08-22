#!/usr/bin/env python3
"""
Check which user is currently logged in
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

async def check_current_session():
    """Check current user session"""
    try:
        supabase = get_supabase()
        
        logger.info("🔍 CHECKING CURRENT LOGGED-IN USER")
        logger.info("=" * 50)
        
        # Get current session from Supabase
        try:
            # This will show us active sessions if any
            response = supabase.auth.admin.list_users()
            users = response.users if hasattr(response, 'users') else response
            
            logger.info("📋 ALL USERS IN SUPABASE AUTH:")
            for user in users:
                if user.email in ['client@analyticsfollowing.com', 'zain@following.ae']:
                    logger.info(f"   {user.email}")
                    logger.info(f"   Auth UUID: {user.id}")
                    logger.info(f"   Created: {user.created_at}")
                    logger.info(f"   Last Sign In: {getattr(user, 'last_sign_in_at', 'N/A')}")
                    logger.info(f"   Email Confirmed: {user.email_confirmed_at is not None}")
                    
        except Exception as e:
            logger.error(f"❌ Error getting Supabase users: {e}")
        
        # Check database user mapping
        async with get_session() as session:
            logger.info(f"\n📊 DATABASE USER MAPPING:")
            
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    u.id as app_user_id,
                    au.id::text as auth_user_id,
                    u.supabase_user_id,
                    u.role,
                    u.subscription_tier,
                    u.credits,
                    u.status,
                    u.last_login,
                    u.last_activity
                FROM users u
                JOIN auth.users au ON u.email = au.email
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY COALESCE(u.last_activity, u.last_login) DESC NULLS LAST;
            """))
            
            for row in result:
                email = row[0]
                app_id = row[1]
                auth_id = row[2]
                supabase_id = row[3]
                role = row[4]
                tier = row[5]
                credits = row[6]
                status = row[7]
                last_login = row[8]
                last_activity = row[9]
                
                logger.info(f"\n👤 {email}")
                logger.info(f"   App User ID: {app_id}")
                logger.info(f"   Auth User ID: {auth_id}")
                logger.info(f"   Stored Supabase ID: {supabase_id}")
                logger.info(f"   Role: {role} | Tier: {tier} | Credits: {credits:,}")
                logger.info(f"   Status: {status}")
                logger.info(f"   Last Login: {last_login or 'Never'}")
                logger.info(f"   Last Activity: {last_activity or 'Never'}")
                
                # Determine if this looks like the currently active user
                if last_activity or last_login:
                    logger.info(f"   🟢 RECENTLY ACTIVE USER")
                else:
                    logger.info(f"   ⚪ NO RECENT ACTIVITY")
            
            # Check for any active sessions or recent activity
            logger.info(f"\n🔐 SESSION ANALYSIS:")
            
            # Based on the logs you showed, let's identify who's making requests
            logger.info(f"From your logs, I can see:")
            logger.info(f"- Auth service sync for: client@analyticsfollowing.com")
            logger.info(f"- Supabase ID in logs: 99b1001b-69a0-4d75-9730-3177ba42c642")
            logger.info(f"- User making API calls to /api/v1/auth/dashboard and /api/v1/credits/balance")
            
            # Verify this Supabase ID
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    u.id as app_user_id,
                    u.supabase_user_id,
                    u.role,
                    u.credits
                FROM users u
                WHERE u.supabase_user_id = '99b1001b-69a0-4d75-9730-3177ba42c642';
            """))
            
            user_row = result.first()
            if user_row:
                logger.info(f"\n✅ IDENTIFIED CURRENT USER:")
                logger.info(f"   Email: {user_row[0]}")
                logger.info(f"   App User ID: {user_row[1]}")
                logger.info(f"   Supabase User ID: {user_row[2]}")
                logger.info(f"   Role: {user_row[3]}")
                logger.info(f"   Credits: {user_row[4]:,}")
                logger.info(f"\n🎯 CONCLUSION: {user_row[0]} is currently logged in")
            else:
                logger.error(f"❌ Could not find user with Supabase ID from logs")
                
    except Exception as e:
        logger.error(f"❌ Error checking current session: {e}")

async def main():
    """Main function"""
    try:
        # Initialize database
        await init_database()
        
        # Check current session
        await check_current_session()
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())