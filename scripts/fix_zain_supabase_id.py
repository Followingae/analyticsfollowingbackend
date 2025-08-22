#!/usr/bin/env python3
"""
Fix Zain's missing supabase_user_id
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

async def fix_zain_supabase_id():
    """Fix Zain's missing supabase_user_id"""
    try:
        async with get_session() as session:
            logger.info("🔧 FIXING ZAIN'S MISSING SUPABASE_USER_ID")
            logger.info("=" * 50)
            
            # Get Zain's auth ID
            result = await session.execute(text("""
                SELECT id FROM auth.users WHERE email = 'zain@following.ae'
            """))
            
            auth_id = result.scalar()
            if not auth_id:
                logger.error("❌ Zain not found in auth.users")
                return
            
            auth_id_str = str(auth_id)
            logger.info(f"📋 Zain's Auth ID: {auth_id_str}")
            
            # Update users table
            await session.execute(text("""
                UPDATE users 
                SET supabase_user_id = :auth_id,
                    updated_at = NOW()
                WHERE email = 'zain@following.ae'
            """), {"auth_id": auth_id_str})
            
            await session.commit()
            logger.info("✅ Updated Zain's supabase_user_id")
            
            # Verify the fix
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    au.id::text as auth_id,
                    u.supabase_user_id,
                    u.role,
                    u.credits,
                    CASE 
                        WHEN au.id::text = u.supabase_user_id THEN 'SYNCED'
                        ELSE 'MISMATCH'
                    END as sync_status
                FROM users u
                JOIN auth.users au ON u.email = au.email
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY u.email;
            """))
            
            logger.info("\n✅ VERIFICATION RESULTS:")
            for row in result:
                email = row[0]
                auth_id = row[1]
                supabase_id = row[2]
                role = row[3]
                credits = row[4]
                sync_status = row[5]
                
                logger.info(f"📧 {email}:")
                logger.info(f"   Auth ID: {auth_id}")
                logger.info(f"   Supabase ID: {supabase_id}")
                logger.info(f"   Role: {role}, Credits: {credits:,}")
                logger.info(f"   Status: {'✅' if sync_status == 'SYNCED' else '❌'} {sync_status}")
            
            logger.info("\n🎉 ALL ACCOUNTS NOW PROPERLY SYNCHRONIZED!")
            
    except Exception as e:
        logger.error(f"❌ Error fixing Zain's ID: {e}")

async def main():
    """Main function"""
    try:
        # Initialize database
        await init_database()
        
        # Fix Zain's supabase_user_id
        await fix_zain_supabase_id()
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())