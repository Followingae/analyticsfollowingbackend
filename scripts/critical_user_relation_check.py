#!/usr/bin/env python3
"""
CRITICAL: Comprehensive check of ALL user relations and data consistency
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

async def check_all_user_relations():
    """Check ALL user relations comprehensively"""
    try:
        async with get_session() as session:
            logger.info("🔍 COMPREHENSIVE USER RELATION CHECK")
            logger.info("=" * 60)
            
            # 1. Check auth.users table
            logger.info("\n1️⃣ AUTH.USERS TABLE:")
            result = await session.execute(text("""
                SELECT id, email, created_at, email_confirmed_at IS NOT NULL as confirmed
                FROM auth.users 
                WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY email;
            """))
            
            auth_users = {}
            for row in result:
                auth_id = str(row[0])
                email = row[1]
                created = row[2]
                confirmed = row[3]
                auth_users[email] = {
                    'auth_id': auth_id,
                    'email': email,
                    'created': created,
                    'confirmed': confirmed
                }
                logger.info(f"   {email}: Auth ID = {auth_id}")
                logger.info(f"   Created: {created}, Confirmed: {confirmed}")
            
            # 2. Check public.users table
            logger.info("\n2️⃣ PUBLIC.USERS TABLE:")
            result = await session.execute(text("""
                SELECT id, email, supabase_user_id, role, subscription_tier, credits, status
                FROM users 
                WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY email;
            """))
            
            app_users = {}
            for row in result:
                app_id = str(row[0])
                email = row[1]
                supabase_id = row[2]
                role = row[3]
                tier = row[4]
                credits = row[5]
                status = row[6]
                app_users[email] = {
                    'app_id': app_id,
                    'email': email,
                    'supabase_id': supabase_id,
                    'role': role,
                    'tier': tier,
                    'credits': credits,
                    'status': status
                }
                logger.info(f"   {email}: App ID = {app_id}")
                logger.info(f"   Supabase ID: {supabase_id}")
                logger.info(f"   Role: {role}, Tier: {tier}, Credits: {credits}, Status: {status}")
            
            # 3. Check ID mapping consistency
            logger.info("\n3️⃣ ID MAPPING CONSISTENCY:")
            for email in ['client@analyticsfollowing.com', 'zain@following.ae']:
                if email in auth_users and email in app_users:
                    auth_id = auth_users[email]['auth_id']
                    supabase_id = app_users[email]['supabase_id']
                    
                    if auth_id == supabase_id:
                        logger.info(f"   ✅ {email}: IDs MATCH")
                    else:
                        logger.error(f"   ❌ {email}: ID MISMATCH!")
                        logger.error(f"      Auth ID: {auth_id}")
                        logger.error(f"      Supabase ID in users: {supabase_id}")
                else:
                    logger.warning(f"   ⚠️ {email}: Missing from one of the tables")
            
            # 4. Check credit_wallets table
            logger.info("\n4️⃣ CREDIT_WALLETS TABLE:")
            result = await session.execute(text("""
                SELECT id, user_id, current_balance, subscription_active
                FROM credit_wallets;
            """))
            
            wallet_users = {}
            for row in result:
                wallet_id = row[0]
                user_id = str(row[1])
                balance = row[2]
                active = row[3]
                
                # Find which user this wallet belongs to
                owner_email = None
                for email, data in auth_users.items():
                    if data['auth_id'] == user_id:
                        owner_email = email
                        break
                
                if not owner_email:
                    for email, data in app_users.items():
                        if data['supabase_id'] == user_id:
                            owner_email = email
                            break
                
                logger.info(f"   Wallet {wallet_id}: User ID = {user_id}")
                logger.info(f"   Owner: {owner_email or 'UNKNOWN'}")
                logger.info(f"   Balance: {balance}, Active: {active}")
                
                if owner_email:
                    wallet_users[owner_email] = {
                        'wallet_id': wallet_id,
                        'user_id': user_id,
                        'balance': balance,
                        'active': active
                    }
            
            # 5. Check user_profiles table
            logger.info("\n5️⃣ USER_PROFILES TABLE:")
            result = await session.execute(text("""
                SELECT user_id, full_name, company, job_title
                FROM user_profiles;
            """))
            
            for row in result:
                profile_user_id = str(row[0])
                name = row[1]
                company = row[2]
                title = row[3]
                
                # Find which user this profile belongs to
                owner_email = None
                for email, data in auth_users.items():
                    if data['auth_id'] == profile_user_id:
                        owner_email = email
                        break
                
                if not owner_email:
                    for email, data in app_users.items():
                        if data['app_id'] == profile_user_id:
                            owner_email = email
                            break
                
                logger.info(f"   Profile User ID: {profile_user_id}")
                logger.info(f"   Owner: {owner_email or 'UNKNOWN'}")
                logger.info(f"   Name: {name}, Company: {company}, Title: {title}")
            
            # 6. CRITICAL ANALYSIS
            logger.info("\n🚨 CRITICAL ANALYSIS:")
            logger.info("=" * 60)
            
            client_auth = auth_users.get('client@analyticsfollowing.com')
            client_app = app_users.get('client@analyticsfollowing.com')
            client_wallet = wallet_users.get('client@analyticsfollowing.com')
            
            if client_auth and client_app:
                logger.info(f"📧 CLIENT@ANALYTICSFOLLOWING.COM:")
                logger.info(f"   Auth Table ID: {client_auth['auth_id']}")
                logger.info(f"   App Table ID: {client_app['app_id']}")
                logger.info(f"   App Table Supabase ID: {client_app['supabase_id']}")
                
                if client_auth['auth_id'] != client_app['supabase_id']:
                    logger.error(f"   ❌ CRITICAL MISMATCH: Auth ID ≠ Supabase ID in users table")
                    logger.error(f"   This means the wrong user data is being fetched!")
                
                if client_wallet:
                    logger.info(f"   Wallet User ID: {client_wallet['user_id']}")
                    logger.info(f"   Wallet Balance: {client_wallet['balance']}")
                    
                    if client_wallet['user_id'] == client_auth['auth_id']:
                        logger.info(f"   ✅ Wallet correctly linked to Auth ID")
                    elif client_wallet['user_id'] == client_app['supabase_id']:
                        logger.info(f"   ⚠️ Wallet linked to stored Supabase ID (may be incorrect)")
                    else:
                        logger.error(f"   ❌ Wallet linked to unknown ID")
            
            return auth_users, app_users, wallet_users
            
    except Exception as e:
        logger.error(f"❌ Error in comprehensive check: {e}")
        return {}, {}, {}

async def fix_id_inconsistencies(auth_users, app_users, wallet_users):
    """Fix ID inconsistencies"""
    try:
        async with get_session() as session:
            logger.info("\n🔧 FIXING ID INCONSISTENCIES:")
            logger.info("=" * 60)
            
            client_auth = auth_users.get('client@analyticsfollowing.com')
            client_app = app_users.get('client@analyticsfollowing.com')
            
            if client_auth and client_app:
                correct_auth_id = client_auth['auth_id']
                stored_supabase_id = client_app['supabase_id']
                
                if correct_auth_id != stored_supabase_id:
                    logger.info(f"🔧 Updating supabase_user_id in users table:")
                    logger.info(f"   From: {stored_supabase_id}")
                    logger.info(f"   To: {correct_auth_id}")
                    
                    await session.execute(text("""
                        UPDATE users 
                        SET supabase_user_id = :correct_id,
                            updated_at = NOW()
                        WHERE email = 'client@analyticsfollowing.com'
                    """), {"correct_id": correct_auth_id})
                    
                    logger.info("✅ Updated users.supabase_user_id")
                
                # Check if wallet needs updating
                client_wallet = wallet_users.get('client@analyticsfollowing.com')
                if client_wallet and client_wallet['user_id'] != correct_auth_id:
                    logger.info(f"🔧 Updating credit_wallets.user_id:")
                    logger.info(f"   From: {client_wallet['user_id']}")
                    logger.info(f"   To: {correct_auth_id}")
                    
                    await session.execute(text("""
                        UPDATE credit_wallets 
                        SET user_id = :correct_id,
                            updated_at = NOW()
                        WHERE id = :wallet_id
                    """), {
                        "correct_id": correct_auth_id,
                        "wallet_id": client_wallet['wallet_id']
                    })
                    
                    logger.info("✅ Updated credit_wallets.user_id")
                
                await session.commit()
                logger.info("✅ All ID inconsistencies fixed!")
            
    except Exception as e:
        logger.error(f"❌ Error fixing inconsistencies: {e}")
        await session.rollback()

async def final_verification():
    """Final verification after fixes"""
    try:
        async with get_session() as session:
            logger.info("\n✅ FINAL VERIFICATION:")
            logger.info("=" * 60)
            
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    au.id as auth_id,
                    u.supabase_user_id,
                    u.role,
                    u.credits as user_credits,
                    cw.current_balance as wallet_credits,
                    CASE 
                        WHEN au.id = u.supabase_user_id THEN 'SYNCED'
                        ELSE 'MISMATCH'
                    END as id_sync,
                    CASE 
                        WHEN u.credits = cw.current_balance THEN 'SYNCED'
                        ELSE 'MISMATCH'
                    END as credit_sync
                FROM users u
                JOIN auth.users au ON u.email = au.email
                LEFT JOIN credit_wallets cw ON au.id = cw.user_id
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY u.email;
            """))
            
            for row in result:
                email = row[0]
                auth_id = row[1]
                supabase_id = row[2]
                role = row[3]
                user_credits = row[4]
                wallet_credits = row[5]
                id_sync = row[6]
                credit_sync = row[7]
                
                logger.info(f"📧 {email}:")
                logger.info(f"   Role: {role}")
                logger.info(f"   Auth ID: {auth_id}")
                logger.info(f"   Stored Supabase ID: {supabase_id}")
                logger.info(f"   ID Sync: {'✅' if id_sync == 'SYNCED' else '❌'} {id_sync}")
                logger.info(f"   User Credits: {user_credits}")
                logger.info(f"   Wallet Credits: {wallet_credits}")
                logger.info(f"   Credit Sync: {'✅' if credit_sync == 'SYNCED' else '❌'} {credit_sync}")
                
                if id_sync == 'SYNCED' and credit_sync == 'SYNCED':
                    logger.info(f"   🎉 {email}: FULLY SYNCHRONIZED")
                else:
                    logger.error(f"   ❌ {email}: STILL HAS ISSUES")
            
    except Exception as e:
        logger.error(f"❌ Error in final verification: {e}")

async def main():
    """Main function"""
    try:
        logger.info("🚨 CRITICAL USER RELATION AUDIT")
        logger.info("Checking ALL user relations for data consistency issues...")
        
        # Initialize database
        await init_database()
        
        # Comprehensive check
        auth_users, app_users, wallet_users = await check_all_user_relations()
        
        # Fix inconsistencies
        await fix_id_inconsistencies(auth_users, app_users, wallet_users)
        
        # Final verification
        await final_verification()
        
        logger.info("\n✅ CRITICAL AUDIT COMPLETE!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())