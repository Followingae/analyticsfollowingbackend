#!/usr/bin/env python3
"""
Fix user ID mismatch between users table and credit_wallets table
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

async def analyze_user_id_mismatch():
    """Analyze the user ID mismatch between tables"""
    try:
        async with get_session() as session:
            # Get current user data
            logger.info("📋 USERS TABLE DATA:")
            result = await session.execute(text("""
                SELECT id, email, supabase_user_id 
                FROM users 
                WHERE email = 'client@analyticsfollowing.com';
            """))
            
            user_data = result.first()
            if user_data:
                user_id = str(user_data[0])
                email = user_data[1]
                supabase_id = user_data[2]
                logger.info(f"  Email: {email}")
                logger.info(f"  User ID: {user_id}")
                logger.info(f"  Supabase ID: {supabase_id}")
            
            # Get current credit_wallet data
            logger.info("\n💳 CREDIT_WALLETS TABLE DATA:")
            result = await session.execute(text("""
                SELECT id, user_id, current_balance
                FROM credit_wallets;
            """))
            
            wallet_data = []
            for row in result:
                wallet_id = row[0]
                wallet_user_id = str(row[1])
                balance = row[2]
                wallet_data.append({
                    'id': wallet_id,
                    'user_id': wallet_user_id,
                    'balance': balance
                })
                logger.info(f"  Wallet ID: {wallet_id}, User ID: {wallet_user_id}, Balance: {balance}")
            
            # Check which wallet belongs to client@analyticsfollowing.com
            logger.info("\n🔍 ANALYZING MISMATCH:")
            client_wallet = None
            if wallet_data:
                wallet_user_id = wallet_data[0]['user_id']
                
                # Check if this wallet_user_id exists in users table
                result = await session.execute(text("""
                    SELECT email FROM users WHERE id = :wallet_user_id
                """), {"wallet_user_id": wallet_user_id})
                
                wallet_owner = result.first()
                if wallet_owner:
                    logger.info(f"  Wallet {wallet_data[0]['id']} belongs to: {wallet_owner[0]}")
                    if wallet_owner[0] == 'client@analyticsfollowing.com':
                        client_wallet = wallet_data[0]
                else:
                    logger.info(f"  Wallet {wallet_data[0]['id']} user_id {wallet_user_id} not found in users table")
                    
                    # Check if it matches supabase_user_id
                    result = await session.execute(text("""
                        SELECT email FROM users WHERE supabase_user_id = :wallet_user_id
                    """), {"wallet_user_id": wallet_user_id})
                    
                    supabase_match = result.first()
                    if supabase_match:
                        logger.info(f"  But wallet user_id matches supabase_user_id for: {supabase_match[0]}")
                        if supabase_match[0] == 'client@analyticsfollowing.com':
                            client_wallet = wallet_data[0]
            
            return user_data, wallet_data, client_wallet
            
    except Exception as e:
        logger.error(f"❌ Error analyzing mismatch: {e}")
        return None, [], None

async def fix_credit_wallet_user_id(user_data, client_wallet):
    """Fix the credit_wallet user_id to match the correct user"""
    try:
        async with get_session() as session:
            current_user_id = str(user_data[0])
            email = user_data[1]
            
            if client_wallet:
                # Update the existing wallet to use the correct user_id
                logger.info(f"🔧 Updating credit_wallet {client_wallet['id']} user_id to {current_user_id}")
                
                await session.execute(text("""
                    UPDATE credit_wallets 
                    SET user_id = :new_user_id,
                        current_balance = 5000,
                        updated_at = NOW()
                    WHERE id = :wallet_id
                """), {
                    "new_user_id": current_user_id,
                    "wallet_id": client_wallet['id']
                })
                
                logger.info(f"✅ Updated wallet {client_wallet['id']} to user_id {current_user_id} with 5000 credits")
            else:
                # Create new wallet for the client
                logger.info(f"🔧 Creating new credit_wallet for {email}")
                
                await session.execute(text("""
                    INSERT INTO credit_wallets (
                        user_id, current_balance, subscription_active, 
                        created_at, updated_at
                    )
                    VALUES (:user_id, 5000, true, NOW(), NOW())
                """), {"user_id": current_user_id})
                
                logger.info(f"✅ Created new wallet for {email} with 5000 credits")
            
            await session.commit()
            
    except Exception as e:
        logger.error(f"❌ Error fixing credit wallet: {e}")

async def final_comprehensive_check():
    """Final comprehensive check of everything"""
    try:
        async with get_session() as session:
            logger.info("\n🎯 FINAL COMPREHENSIVE VERIFICATION:")
            logger.info("=" * 60)
            
            # Check both users
            result = await session.execute(text("""
                SELECT 
                    u.email,
                    u.role,
                    u.subscription_tier,
                    u.credits as user_credits,
                    u.status,
                    cw.current_balance as wallet_credits,
                    cw.subscription_active as wallet_active,
                    CASE 
                        WHEN u.credits = cw.current_balance THEN 'SYNCED'
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
                tier = row[2]
                user_credits = row[3]
                status = row[4]
                wallet_credits = row[5]
                wallet_active = row[6]
                sync_status = row[7]
                
                logger.info(f"\n📧 {email}")
                logger.info(f"   Role: {role}")
                logger.info(f"   Subscription Tier: {tier}")
                logger.info(f"   Status: {status}")
                logger.info(f"   User Table Credits: {user_credits:,}")
                
                if wallet_credits is not None:
                    logger.info(f"   Wallet Credits: {wallet_credits:,}")
                    logger.info(f"   Wallet Active: {wallet_active}")
                    logger.info(f"   Sync Status: {'✅' if sync_status == 'SYNCED' else '❌'} {sync_status}")
                    
                    if email == 'client@analyticsfollowing.com':
                        if sync_status == 'SYNCED' and user_credits == 5000:
                            logger.info(f"   🎉 PERFECT! Brand user properly configured with 5000 credits")
                        else:
                            logger.warning(f"   ⚠️ ISSUE: Credits not synced properly")
                else:
                    if email == 'zain@following.ae':
                        logger.info(f"   Wallet: None (Expected for admin)")
                        logger.info(f"   🎉 PERFECT! Admin user properly configured")
                    else:
                        logger.warning(f"   ⚠️ ISSUE: No wallet found for brand user")
            
            logger.info(f"\n🏁 COMPREHENSIVE VERIFICATION COMPLETE!")
            
    except Exception as e:
        logger.error(f"❌ Error in final verification: {e}")

async def main():
    """Main function to fix user ID mismatch"""
    try:
        logger.info("🚀 Fixing user ID mismatch between users and credit_wallets...")
        
        # Initialize database
        await init_database()
        
        # Analyze the mismatch
        user_data, wallet_data, client_wallet = await analyze_user_id_mismatch()
        
        if user_data:
            # Fix the credit wallet
            await fix_credit_wallet_user_id(user_data, client_wallet)
            
            # Final verification
            await final_comprehensive_check()
        else:
            logger.error("❌ Could not retrieve user data")
        
        logger.info("\n✅ User ID mismatch fix completed!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())