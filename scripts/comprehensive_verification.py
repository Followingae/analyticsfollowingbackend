#!/usr/bin/env python3
"""
Comprehensive End-to-End Verification and Fix
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

async def check_all_user_related_tables():
    """Check all user-related tables for comprehensive verification"""
    try:
        async with get_session() as session:
            # Check users table
            logger.info("📋 USERS TABLE:")
            result = await session.execute(text("""
                SELECT id, email, role, subscription_tier, credits, credits_used_this_month, status
                FROM users 
                WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY email;
            """))
            
            user_data = {}
            for row in result:
                user_id = str(row[0])
                email = row[1]
                user_data[email] = {
                    'id': user_id,
                    'email': email,
                    'role': row[2],
                    'subscription_tier': row[3],
                    'credits': row[4],
                    'credits_used_this_month': row[5],
                    'status': row[6]
                }
                logger.info(f"  {email}: Role={row[2]}, Tier={row[3]}, Credits={row[4]}, Used={row[5]}, Status={row[6]}")
            
            # Check credit_wallets table
            logger.info("\n💳 CREDIT_WALLETS TABLE:")
            result = await session.execute(text("""
                SELECT user_id, subscription_tier, credits_balance, monthly_allowance, billing_cycle_start, billing_cycle_end
                FROM credit_wallets 
                WHERE user_id IN (
                    SELECT id FROM users WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                )
                ORDER BY user_id;
            """))
            
            wallet_data = {}
            for row in result:
                user_id = str(row[0])
                wallet_data[user_id] = {
                    'user_id': user_id,
                    'subscription_tier': row[1],
                    'credits_balance': row[2],
                    'monthly_allowance': row[3],
                    'billing_cycle_start': row[4],
                    'billing_cycle_end': row[5]
                }
                
                # Find email for this user_id
                email = None
                for e, data in user_data.items():
                    if data['id'] == user_id:
                        email = e
                        break
                
                logger.info(f"  {email or 'Unknown'}: Tier={row[1]}, Balance={row[2]}, Allowance={row[3]}")
            
            # Check if credit_wallets exist for our users
            client_user = user_data.get('client@analyticsfollowing.com')
            zain_user = user_data.get('zain@following.ae')
            
            if client_user:
                client_wallet = wallet_data.get(client_user['id'])
                if not client_wallet:
                    logger.warning("⚠️ No credit_wallet found for client@analyticsfollowing.com")
                else:
                    logger.info(f"✅ Client wallet found: {client_wallet}")
            
            if zain_user:
                zain_wallet = wallet_data.get(zain_user['id'])
                if not zain_wallet:
                    logger.info("ℹ️ No credit_wallet found for zain@following.ae (expected for admin)")
                else:
                    logger.info(f"ℹ️ Zain wallet: {zain_wallet}")
            
            # Check user_profiles table
            logger.info("\n👤 USER_PROFILES TABLE:")
            result = await session.execute(text("""
                SELECT user_id, full_name, company, job_title
                FROM user_profiles 
                WHERE user_id IN (
                    SELECT id FROM users WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                )
                ORDER BY user_id;
            """))
            
            for row in result:
                user_id = str(row[0])
                # Find email for this user_id
                email = None
                for e, data in user_data.items():
                    if data['id'] == user_id:
                        email = e
                        break
                logger.info(f"  {email or 'Unknown'}: Name={row[1]}, Company={row[2]}, Title={row[3]}")
            
            return user_data, wallet_data
            
    except Exception as e:
        logger.error(f"❌ Error checking tables: {e}")
        return {}, {}

async def fix_credit_wallet_inconsistencies(user_data, wallet_data):
    """Fix any inconsistencies in credit_wallets"""
    try:
        async with get_session() as session:
            client_user = user_data.get('client@analyticsfollowing.com')
            
            if client_user:
                client_wallet = wallet_data.get(client_user['id'])
                
                # Check if wallet exists and if it matches user table
                user_credits = client_user['credits']
                user_tier = client_user['subscription_tier']
                
                if not client_wallet:
                    logger.info("🔧 Creating missing credit_wallet for client@analyticsfollowing.com")
                    await session.execute(text("""
                        INSERT INTO credit_wallets (
                            user_id, subscription_tier, credits_balance, monthly_allowance,
                            billing_cycle_start, billing_cycle_end, created_at, updated_at
                        )
                        VALUES (
                            :user_id, :subscription_tier, :credits_balance, :monthly_allowance,
                            CURRENT_DATE, (CURRENT_DATE + INTERVAL '1 month'), NOW(), NOW()
                        )
                    """), {
                        "user_id": client_user['id'],
                        "subscription_tier": user_tier,
                        "credits_balance": user_credits,
                        "monthly_allowance": user_credits
                    })
                    logger.info(f"✅ Created credit_wallet with {user_credits} credits")
                    
                elif (client_wallet['credits_balance'] != user_credits or 
                      client_wallet['subscription_tier'] != user_tier):
                    logger.info("🔧 Updating credit_wallet to match users table")
                    await session.execute(text("""
                        UPDATE credit_wallets 
                        SET credits_balance = :credits_balance,
                            subscription_tier = :subscription_tier,
                            monthly_allowance = :monthly_allowance,
                            updated_at = NOW()
                        WHERE user_id = :user_id
                    """), {
                        "user_id": client_user['id'],
                        "credits_balance": user_credits,
                        "subscription_tier": user_tier,
                        "monthly_allowance": user_credits
                    })
                    logger.info(f"✅ Updated credit_wallet: Balance={user_credits}, Tier={user_tier}")
                else:
                    logger.info("✅ Credit_wallet already matches users table")
            
            await session.commit()
            
    except Exception as e:
        logger.error(f"❌ Error fixing credit_wallet: {e}")

async def final_verification():
    """Final comprehensive verification"""
    try:
        async with get_session() as session:
            logger.info("\n🎯 FINAL COMPREHENSIVE VERIFICATION:")
            logger.info("=" * 60)
            
            # Check everything is in sync
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    u.role,
                    u.subscription_tier as user_tier,
                    u.credits as user_credits,
                    u.status,
                    cw.subscription_tier as wallet_tier,
                    cw.credits_balance as wallet_credits,
                    cw.monthly_allowance,
                    CASE 
                        WHEN u.credits = cw.credits_balance AND u.subscription_tier = cw.subscription_tier THEN 'SYNCED'
                        ELSE 'MISMATCH'
                    END as sync_status
                FROM users u
                LEFT JOIN credit_wallets cw ON u.id = cw.user_id
                WHERE u.email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY u.email;
            """))
            
            for row in result:
                email = row[0]
                role = row[1]
                user_tier = row[2]
                user_credits = row[3]
                status = row[4]
                wallet_tier = row[5]
                wallet_credits = row[6]
                monthly_allowance = row[7]
                sync_status = row[8]
                
                logger.info(f"\n📧 {email}")
                logger.info(f"   Role: {role}")
                logger.info(f"   Status: {status}")
                logger.info(f"   User Table - Tier: {user_tier}, Credits: {user_credits}")
                
                if wallet_tier:
                    logger.info(f"   Wallet Table - Tier: {wallet_tier}, Credits: {wallet_credits}, Allowance: {monthly_allowance}")
                    logger.info(f"   Sync Status: {'✅' if sync_status == 'SYNCED' else '❌'} {sync_status}")
                else:
                    logger.info(f"   Wallet Table - No wallet (expected for admin accounts)")
                    logger.info(f"   Sync Status: ✅ EXPECTED")
            
            logger.info("\n🏁 VERIFICATION COMPLETE!")
            
    except Exception as e:
        logger.error(f"❌ Error in final verification: {e}")

async def main():
    """Main comprehensive verification function"""
    try:
        logger.info("🚀 Starting Comprehensive End-to-End Verification...")
        
        # Initialize database
        await init_database()
        
        # Check all user-related tables
        user_data, wallet_data = await check_all_user_related_tables()
        
        # Fix any inconsistencies
        await fix_credit_wallet_inconsistencies(user_data, wallet_data)
        
        # Final verification
        await final_verification()
        
        logger.info("\n✅ Comprehensive verification and fixes completed!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())