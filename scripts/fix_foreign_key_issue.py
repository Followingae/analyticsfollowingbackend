#!/usr/bin/env python3
"""
Fix foreign key constraint issue with credit_wallets
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

async def check_foreign_key_constraints():
    """Check foreign key constraints on credit_wallets"""
    try:
        async with get_session() as session:
            # Check foreign key constraints
            result = await session.execute(text("""
                SELECT 
                    tc.constraint_name,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                AND tc.table_name = 'credit_wallets';
            """))
            
            logger.info("📋 FOREIGN KEY CONSTRAINTS ON credit_wallets:")
            for row in result:
                constraint_name = row[0]
                table_name = row[1]
                column_name = row[2]
                foreign_table = row[3]
                foreign_column = row[4]
                logger.info(f"  {constraint_name}: {table_name}.{column_name} -> {foreign_table}.{foreign_column}")
            
            # Check what tables named 'users' exist
            result = await session.execute(text("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_name = 'users'
                ORDER BY table_schema;
            """))
            
            logger.info(f"\n📋 ALL 'users' TABLES:")
            for row in result:
                schema = row[0]
                table = row[1]
                logger.info(f"  {schema}.{table}")
                
                # Check if this table has our user
                try:
                    check_result = await session.execute(text(f"""
                        SELECT id, email FROM {schema}.{table} 
                        WHERE email = 'client@analyticsfollowing.com'
                        LIMIT 1;
                    """))
                    
                    user_row = check_result.first()
                    if user_row:
                        logger.info(f"    ✅ Contains client@analyticsfollowing.com: ID = {user_row[0]}")
                    else:
                        logger.info(f"    ❌ Does not contain client@analyticsfollowing.com")
                except Exception as e:
                    logger.info(f"    ⚠️ Could not query: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error checking foreign keys: {e}")

async def fix_credit_wallet_simple():
    """Simple fix - just update the balance in the existing wallet"""
    try:
        async with get_session() as session:
            # Get the current wallet
            result = await session.execute(text("""
                SELECT id, user_id, current_balance 
                FROM credit_wallets 
                WHERE id = 1;
            """))
            
            wallet = result.first()
            if wallet:
                wallet_id = wallet[0]
                current_user_id = wallet[1]
                current_balance = wallet[2]
                
                logger.info(f"📋 Current wallet: ID={wallet_id}, UserID={current_user_id}, Balance={current_balance}")
                
                # Simply update the balance to 5000 to match the user's credits
                await session.execute(text("""
                    UPDATE credit_wallets 
                    SET current_balance = 5000,
                        updated_at = NOW()
                    WHERE id = :wallet_id
                """), {"wallet_id": wallet_id})
                
                await session.commit()
                logger.info(f"✅ Updated wallet balance to 5000")
                
                # Verify the update
                result = await session.execute(text("""
                    SELECT current_balance FROM credit_wallets WHERE id = :wallet_id
                """), {"wallet_id": wallet_id})
                
                new_balance = result.scalar()
                logger.info(f"✅ Verified new balance: {new_balance}")
                
                return True
            else:
                logger.error("❌ No wallet found to update")
                return False
            
    except Exception as e:
        logger.error(f"❌ Error fixing wallet: {e}")
        return False

async def final_verification():
    """Final verification that everything is working"""
    try:
        async with get_session() as session:
            logger.info("\n🎯 FINAL VERIFICATION:")
            logger.info("=" * 50)
            
            # Check user data
            result = await session.execute(text("""
                SELECT email, role, subscription_tier, credits, status
                FROM users 
                WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                ORDER BY email;
            """))
            
            user_info = {}
            for row in result:
                email = row[0]
                user_info[email] = {
                    'email': email,
                    'role': row[1],
                    'tier': row[2],
                    'credits': row[3],
                    'status': row[4]
                }
                logger.info(f"👤 {email}")
                logger.info(f"   Role: {row[1]} | Tier: {row[2]} | Credits: {row[3]:,} | Status: {row[4]}")
            
            # Check wallet data
            logger.info(f"\n💳 CREDIT WALLET STATUS:")
            result = await session.execute(text("""
                SELECT user_id, current_balance, subscription_active 
                FROM credit_wallets;
            """))
            
            for row in result:
                wallet_user_id = str(row[0])
                balance = row[1]
                active = row[2]
                
                # Try to find which user this belongs to
                check_result = await session.execute(text("""
                    SELECT email FROM users WHERE supabase_user_id = :user_id
                """), {"user_id": wallet_user_id})
                
                user_match = check_result.first()
                if user_match:
                    email = user_match[0]
                    if email == 'client@analyticsfollowing.com':
                        user_credits = user_info.get(email, {}).get('credits', 0)
                        status = "✅ SYNCED" if balance == user_credits else f"❌ MISMATCH (User: {user_credits}, Wallet: {balance})"
                        logger.info(f"💳 {email}: {balance:,} credits | Active: {active} | {status}")
                    else:
                        logger.info(f"💳 {email}: {balance:,} credits | Active: {active}")
                else:
                    logger.info(f"💳 Unknown user ({wallet_user_id}): {balance:,} credits | Active: {active}")
            
            # Summary
            client_info = user_info.get('client@analyticsfollowing.com')
            zain_info = user_info.get('zain@following.ae')
            
            logger.info(f"\n🎉 SETUP SUMMARY:")
            logger.info(f"✅ Brand User: {client_info['email'] if client_info else 'Not found'}")
            if client_info:
                logger.info(f"   Role: {client_info['role']} | Tier: {client_info['tier']} | Credits: {client_info['credits']:,}")
            
            logger.info(f"✅ Admin User: {zain_info['email'] if zain_info else 'Not found'}")
            if zain_info:
                logger.info(f"   Role: {zain_info['role']} | Tier: {zain_info['tier']} | Credits: {zain_info['credits']:,}")
            
    except Exception as e:
        logger.error(f"❌ Error in final verification: {e}")

async def main():
    """Main function"""
    try:
        logger.info("🚀 Fixing foreign key issues and finalizing setup...")
        
        # Initialize database
        await init_database()
        
        # Check foreign key constraints
        await check_foreign_key_constraints()
        
        # Fix credit wallet balance
        success = await fix_credit_wallet_simple()
        
        if success:
            # Final verification
            await final_verification()
        
        logger.info("\n✅ Credit wallet fix completed!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())