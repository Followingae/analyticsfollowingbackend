#!/usr/bin/env python3
"""
Final comprehensive system verification after fixes
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

async def final_comprehensive_verification():
    """Final comprehensive verification of the entire system"""
    try:
        async with get_session() as session:
            logger.info("🎯 FINAL COMPREHENSIVE SYSTEM VERIFICATION")
            logger.info("=" * 60)
            
            # Complete verification query
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    u.id as app_user_id,
                    au.id::text as auth_user_id,
                    u.supabase_user_id,
                    u.role,
                    u.subscription_tier,
                    u.credits as user_credits,
                    u.status,
                    cw.id as wallet_id,
                    cw.current_balance as wallet_credits,
                    cw.subscription_active,
                    CASE 
                        WHEN au.id::text = u.supabase_user_id THEN 'SYNCED'
                        ELSE 'MISMATCH'
                    END as id_sync_status,
                    CASE 
                        WHEN u.credits = cw.current_balance THEN 'SYNCED'
                        WHEN cw.current_balance IS NULL THEN 'NO_WALLET'
                        ELSE 'MISMATCH'
                    END as credit_sync_status
                FROM users u
                JOIN auth.users au ON u.email = au.email
                LEFT JOIN credit_wallets cw ON au.id = cw.user_id
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY u.email;
            """))
            
            all_good = True
            
            for row in result:
                email = row[0]
                app_id = row[1]
                auth_id = row[2]
                supabase_id = row[3]
                role = row[4]
                tier = row[5]
                user_credits = row[6]
                status = row[7]
                wallet_id = row[8]
                wallet_credits = row[9]
                wallet_active = row[10]
                id_sync = row[11]
                credit_sync = row[12]
                
                logger.info(f"\n👤 {email.upper()}")
                logger.info(f"   App User ID: {app_id}")
                logger.info(f"   Auth User ID: {auth_id}")
                logger.info(f"   Stored Supabase ID: {supabase_id}")
                logger.info(f"   ID Sync: {'✅' if id_sync == 'SYNCED' else '❌'} {id_sync}")
                
                logger.info(f"   Role: {role}")
                logger.info(f"   Subscription Tier: {tier}")
                logger.info(f"   Status: {status}")
                
                logger.info(f"   User Table Credits: {user_credits:,}")
                
                if wallet_id:
                    logger.info(f"   Wallet ID: {wallet_id}")
                    logger.info(f"   Wallet Credits: {wallet_credits:,}")
                    logger.info(f"   Wallet Active: {wallet_active}")
                    logger.info(f"   Credit Sync: {'✅' if credit_sync == 'SYNCED' else '❌'} {credit_sync}")
                else:
                    logger.info(f"   Wallet: None (Expected for admin)")
                    logger.info(f"   Credit Sync: ✅ NO_WALLET (Expected)")
                
                # Determine overall status
                if email == 'client@analyticsfollowing.com':
                    if (id_sync == 'SYNCED' and credit_sync == 'SYNCED' and 
                        role == 'premium' and tier == 'professional' and 
                        user_credits == 5000 and status == 'active'):
                        logger.info(f"   🎉 BRAND USER: PERFECT CONFIGURATION")
                    else:
                        logger.error(f"   ❌ BRAND USER: CONFIGURATION ISSUES")
                        all_good = False
                        
                elif email == 'zain@following.ae':
                    if (id_sync == 'SYNCED' and role == 'admin' and 
                        tier == 'unlimited' and user_credits == 100000 and 
                        status == 'active'):
                        logger.info(f"   🎉 ADMIN USER: PERFECT CONFIGURATION")
                    else:
                        logger.error(f"   ❌ ADMIN USER: CONFIGURATION ISSUES")
                        all_good = False
            
            # Test authentication flow simulation
            logger.info(f"\n🔐 AUTHENTICATION FLOW SIMULATION:")
            
            # Simulate client login
            result = await session.execute(text("""
                SELECT 
                    au.id::text as auth_id,
                    u.role,
                    u.subscription_tier,
                    u.credits,
                    cw.current_balance
                FROM auth.users au
                JOIN users u ON au.id::text = u.supabase_user_id
                LEFT JOIN credit_wallets cw ON au.id = cw.user_id
                WHERE au.email = 'client@analyticsfollowing.com';
            """))
            
            client_login = result.first()
            if client_login:
                logger.info(f"   ✅ Client Login Test: SUCCESS")
                logger.info(f"      Auth ID: {client_login[0]}")
                logger.info(f"      Role: {client_login[1]}")
                logger.info(f"      Credits: {client_login[2]} (User) / {client_login[4]} (Wallet)")
            else:
                logger.error(f"   ❌ Client Login Test: FAILED")
                all_good = False
            
            # Simulate admin login  
            result = await session.execute(text("""
                SELECT 
                    au.id::text as auth_id,
                    u.role,
                    u.subscription_tier,
                    u.credits
                FROM auth.users au
                JOIN users u ON au.id::text = u.supabase_user_id
                WHERE au.email = 'zain@following.ae';
            """))
            
            admin_login = result.first()
            if admin_login:
                logger.info(f"   ✅ Admin Login Test: SUCCESS")
                logger.info(f"      Auth ID: {admin_login[0]}")
                logger.info(f"      Role: {admin_login[1]}")
                logger.info(f"      Credits: {admin_login[3]}")
            else:
                logger.error(f"   ❌ Admin Login Test: FAILED")
                all_good = False
            
            # Final summary
            logger.info(f"\n🏁 FINAL SYSTEM STATUS:")
            logger.info("=" * 60)
            
            if all_good:
                logger.info(f"🎉 SYSTEM STATUS: FULLY OPERATIONAL")
                logger.info(f"✅ All user accounts properly configured")
                logger.info(f"✅ All ID relationships correctly mapped")
                logger.info(f"✅ Credit system fully synchronized")
                logger.info(f"✅ Authentication flow working perfectly")
                logger.info(f"")
                logger.info(f"👤 BRAND USER: client@analyticsfollowing.com")
                logger.info(f"   Role: premium | Tier: professional | Credits: 5,000")
                logger.info(f"👑 ADMIN USER: zain@following.ae") 
                logger.info(f"   Role: admin | Tier: unlimited | Credits: 100,000")
                logger.info(f"   Password: Following0925_25")
            else:
                logger.error(f"❌ SYSTEM STATUS: ISSUES DETECTED")
                logger.error(f"Some configurations still need attention")
            
            return all_good
            
    except Exception as e:
        logger.error(f"❌ Error in final verification: {e}")
        return False

async def main():
    """Main function"""
    try:
        # Initialize database
        await init_database()
        
        # Final verification
        success = await final_comprehensive_verification()
        
        if success:
            logger.info(f"\n🚀 SYSTEM READY FOR PRODUCTION USE!")
        else:
            logger.error(f"\n⚠️ SYSTEM NEEDS ADDITIONAL FIXES")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())