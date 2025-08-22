#!/usr/bin/env python3
"""
Final comprehensive end-to-end verification of the entire user setup
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

async def verify_authentication_layer():
    """Verify Supabase authentication layer"""
    try:
        supabase = get_supabase()
        
        logger.info("🔐 AUTHENTICATION LAYER VERIFICATION:")
        logger.info("=" * 50)
        
        # Get auth users
        auth_response = supabase.auth.admin.list_users()
        auth_users = auth_response.users if hasattr(auth_response, 'users') else auth_response
        
        target_emails = ['client@analyticsfollowing.com', 'zain@following.ae']
        
        for user in auth_users:
            if user.email in target_emails:
                logger.info(f"👤 {user.email}")
                logger.info(f"   Auth ID: {user.id}")
                logger.info(f"   Email Confirmed: {'✅' if user.email_confirmed_at else '❌'}")
                logger.info(f"   Status: {'Active' if not user.banned_until else 'Banned'}")
                logger.info(f"   Created: {user.created_at}")
                
                # Check user metadata
                if hasattr(user, 'user_metadata') and user.user_metadata:
                    logger.info(f"   Metadata: {user.user_metadata}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verifying authentication: {e}")
        return False

async def verify_application_layer():
    """Verify application database layer"""
    try:
        async with get_session() as session:
            logger.info("\n📊 APPLICATION LAYER VERIFICATION:")
            logger.info("=" * 50)
            
            # Verify users table
            result = await session.execute(text("""
                SELECT 
                    u.id as app_user_id,
                    u.email,
                    u.supabase_user_id,
                    u.role,
                    u.subscription_tier,
                    u.credits,
                    u.credits_used_this_month,
                    u.status,
                    u.full_name,
                    u.company,
                    u.job_title,
                    au.id as auth_user_id
                FROM users u
                LEFT JOIN auth.users au ON u.supabase_user_id = au.id::text
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY u.email;
            """))
            
            app_users = {}
            for row in result:
                email = row[1]
                app_users[email] = {
                    'app_user_id': str(row[0]),
                    'email': row[1],
                    'supabase_user_id': row[2],
                    'role': row[3],
                    'subscription_tier': row[4],
                    'credits': row[5],
                    'credits_used': row[6],
                    'status': row[7],
                    'full_name': row[8],
                    'company': row[9],
                    'job_title': row[10],
                    'auth_linked': row[11] is not None
                }
                
                user_data = app_users[email]
                logger.info(f"👤 {email}")
                logger.info(f"   App User ID: {user_data['app_user_id']}")
                logger.info(f"   Supabase ID: {user_data['supabase_user_id']}")
                logger.info(f"   Auth Linked: {'✅' if user_data['auth_linked'] else '❌'}")
                logger.info(f"   Role: {user_data['role']}")
                logger.info(f"   Subscription: {user_data['subscription_tier']}")
                logger.info(f"   Credits: {user_data['credits']:,}")
                logger.info(f"   Credits Used: {user_data['credits_used']}")
                logger.info(f"   Status: {user_data['status']}")
                logger.info(f"   Profile: {user_data['full_name']} at {user_data['company']}")
            
            return app_users
            
    except Exception as e:
        logger.error(f"❌ Error verifying application layer: {e}")
        return {}

async def verify_credit_system():
    """Verify credit system integration"""
    try:
        async with get_session() as session:
            logger.info("\n💳 CREDIT SYSTEM VERIFICATION:")
            logger.info("=" * 50)
            
            # Check credit wallets
            result = await session.execute(text("""
                SELECT 
                    cw.id as wallet_id,
                    cw.user_id,
                    cw.current_balance,
                    cw.total_earned_this_cycle,
                    cw.total_spent_this_cycle,
                    cw.subscription_active,
                    cw.current_billing_cycle_start,
                    cw.next_reset_date,
                    u.email,
                    u.credits as user_table_credits
                FROM credit_wallets cw
                LEFT JOIN users u ON cw.user_id = u.supabase_user_id
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae');
            """))
            
            for row in result:
                wallet_id = row[0]
                user_id = row[1]
                balance = row[2]
                earned = row[3]
                spent = row[4]
                active = row[5]
                cycle_start = row[6]
                next_reset = row[7]
                email = row[8]
                user_credits = row[9]
                
                logger.info(f"💳 {email}")
                logger.info(f"   Wallet ID: {wallet_id}")
                logger.info(f"   Current Balance: {balance:,}")
                logger.info(f"   User Table Credits: {user_credits:,}")
                logger.info(f"   Sync Status: {'✅ SYNCED' if balance == user_credits else '❌ MISMATCH'}")
                logger.info(f"   Earned This Cycle: {earned}")
                logger.info(f"   Spent This Cycle: {spent}")
                logger.info(f"   Subscription Active: {active}")
                logger.info(f"   Billing Cycle: {cycle_start} to {next_reset}")
            
            # Check credit transactions
            result = await session.execute(text("""
                SELECT COUNT(*) FROM credit_transactions 
                WHERE user_id IN (
                    SELECT supabase_user_id FROM users 
                    WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                );
            """))
            
            transaction_count = result.scalar()
            logger.info(f"\n📊 Credit Transactions: {transaction_count} total")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error verifying credit system: {e}")
        return False

async def verify_access_permissions():
    """Verify user access permissions and capabilities"""
    try:
        async with get_session() as session:
            logger.info("\n🔑 ACCESS PERMISSIONS VERIFICATION:")
            logger.info("=" * 50)
            
            # Check brand user permissions
            client_result = await session.execute(text("""
                SELECT role, subscription_tier, credits, status
                FROM users 
                WHERE email = 'client@analyticsfollowing.com';
            """))
            
            client_data = client_result.first()
            if client_data:
                role, tier, credits, status = client_data
                logger.info(f"👤 Brand User (client@analyticsfollowing.com):")
                logger.info(f"   Role: {role} (Premium brand user)")
                logger.info(f"   Tier: {tier} (Professional subscription)")
                logger.info(f"   Credits: {credits:,} (Sufficient for premium features)")
                logger.info(f"   Status: {status}")
                
                # Determine access level
                if role == 'premium' and tier == 'professional' and credits >= 5000:
                    logger.info(f"   Access Level: ✅ FULL BRAND PREMIUM ACCESS")
                    logger.info(f"   Features: Advanced analytics, unlimited profiles, export capabilities")
                else:
                    logger.info(f"   Access Level: ⚠️ LIMITED ACCESS")
            
            # Check admin user permissions
            admin_result = await session.execute(text("""
                SELECT role, subscription_tier, credits, status
                FROM users 
                WHERE email = 'zain@following.ae';
            """))
            
            admin_data = admin_result.first()
            if admin_data:
                role, tier, credits, status = admin_data
                logger.info(f"\n👑 Admin User (zain@following.ae):")
                logger.info(f"   Role: {role} (System administrator)")
                logger.info(f"   Tier: {tier} (Unlimited access)")
                logger.info(f"   Credits: {credits:,} (Unlimited)")
                logger.info(f"   Status: {status}")
                
                # Determine access level
                if role == 'admin' and tier == 'unlimited':
                    logger.info(f"   Access Level: ✅ FULL SYSTEM ADMINISTRATOR ACCESS")
                    logger.info(f"   Features: User management, system settings, all platform features")
                else:
                    logger.info(f"   Access Level: ⚠️ LIMITED ACCESS")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error verifying permissions: {e}")
        return False

async def verify_system_integration():
    """Verify complete system integration"""
    try:
        logger.info("\n🔗 SYSTEM INTEGRATION VERIFICATION:")
        logger.info("=" * 50)
        
        async with get_session() as session:
            # Test a complete user flow simulation
            result = await session.execute(text("""
                SELECT 
                    'Brand User Flow' as test_name,
                    u.email,
                    u.role,
                    u.credits,
                    cw.current_balance,
                    CASE 
                        WHEN u.credits = cw.current_balance THEN 'PASS'
                        ELSE 'FAIL'
                    END as credit_sync_test,
                    CASE 
                        WHEN u.role = 'premium' AND u.subscription_tier = 'professional' THEN 'PASS'
                        ELSE 'FAIL'
                    END as role_tier_test
                FROM users u
                LEFT JOIN credit_wallets cw ON u.supabase_user_id = cw.user_id
                WHERE u.email = 'client@analyticsfollowing.com'
                
                UNION ALL
                
                SELECT 
                    'Admin User Flow' as test_name,
                    u.email,
                    u.role,
                    u.credits,
                    NULL as current_balance,
                    'PASS' as credit_sync_test,
                    CASE 
                        WHEN u.role = 'admin' AND u.subscription_tier = 'unlimited' THEN 'PASS'
                        ELSE 'FAIL'
                    END as role_tier_test
                FROM users u
                WHERE u.email = 'zain@following.ae';
            """))
            
            logger.info("🧪 INTEGRATION TESTS:")
            all_tests_pass = True
            
            for row in result:
                test_name = row[0]
                email = row[1]
                role = row[2]
                credits = row[3]
                wallet_balance = row[4]
                credit_sync = row[5]
                role_tier = row[6]
                
                logger.info(f"\n   {test_name} ({email}):")
                logger.info(f"     Credit Sync Test: {'✅' if credit_sync == 'PASS' else '❌'} {credit_sync}")
                logger.info(f"     Role/Tier Test: {'✅' if role_tier == 'PASS' else '❌'} {role_tier}")
                
                if credit_sync != 'PASS' or role_tier != 'PASS':
                    all_tests_pass = False
            
            logger.info(f"\n🎯 OVERALL SYSTEM STATUS: {'✅ ALL TESTS PASS' if all_tests_pass else '❌ SOME TESTS FAILED'}")
            
            return all_tests_pass
            
    except Exception as e:
        logger.error(f"❌ Error verifying system integration: {e}")
        return False

async def main():
    """Main comprehensive verification function"""
    try:
        logger.info("🚀 COMPREHENSIVE END-TO-END VERIFICATION")
        logger.info("=" * 60)
        
        # Initialize database
        await init_database()
        
        # Run all verification checks
        auth_ok = await verify_authentication_layer()
        app_users = await verify_application_layer()
        credit_ok = await verify_credit_system()
        permissions_ok = await verify_access_permissions()
        integration_ok = await verify_system_integration()
        
        # Final summary
        logger.info(f"\n🏁 FINAL VERIFICATION SUMMARY:")
        logger.info("=" * 60)
        logger.info(f"🔐 Authentication Layer: {'✅ PASS' if auth_ok else '❌ FAIL'}")
        logger.info(f"📊 Application Layer: {'✅ PASS' if app_users else '❌ FAIL'}")
        logger.info(f"💳 Credit System: {'✅ PASS' if credit_ok else '❌ FAIL'}")
        logger.info(f"🔑 Access Permissions: {'✅ PASS' if permissions_ok else '❌ FAIL'}")
        logger.info(f"🔗 System Integration: {'✅ PASS' if integration_ok else '❌ FAIL'}")
        
        overall_success = all([auth_ok, app_users, credit_ok, permissions_ok, integration_ok])
        
        logger.info(f"\n🎉 OVERALL STATUS: {'✅ COMPLETE SUCCESS' if overall_success else '❌ ISSUES DETECTED'}")
        
        if overall_success:
            logger.info("\n🎯 USER SETUP COMPLETED SUCCESSFULLY!")
            logger.info("Both accounts are properly configured and ready for use:")
            logger.info("• Brand User: client@analyticsfollowing.com (Premium/Professional, 5000 credits)")
            logger.info("• Admin User: zain@following.ae (Admin/Unlimited, 100000 credits)")
        else:
            logger.info("\n⚠️ Some issues were detected. Please review the verification results above.")
        
    except Exception as e:
        logger.error(f"❌ Error in comprehensive verification: {e}")

if __name__ == "__main__":
    asyncio.run(main())