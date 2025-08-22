#!/usr/bin/env python3
"""
Check credit_wallets table structure and fix the issue
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

async def check_credit_wallets_structure():
    """Check the actual structure of credit_wallets table"""
    try:
        async with get_session() as session:
            # Check if credit_wallets table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'credit_wallets'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                logger.warning("⚠️ credit_wallets table does not exist")
                return False
            
            # Get table structure
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'credit_wallets' AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            
            logger.info("📋 credit_wallets table structure:")
            columns = []
            for row in result:
                column_name = row[0]
                columns.append(column_name)
                logger.info(f"  - {row[0]} | {row[1]} | Nullable: {row[2]} | Default: {row[3]}")
            
            # Check current data
            if columns:
                # Build a safe SELECT query with only existing columns
                basic_columns = ['id', 'user_id', 'credits_balance'] if 'credits_balance' in columns else ['id', 'user_id']
                if 'current_balance' in columns:
                    basic_columns.append('current_balance')
                if 'monthly_limit' in columns:
                    basic_columns.append('monthly_limit')
                if 'monthly_allowance' in columns:
                    basic_columns.append('monthly_allowance')
                
                select_query = f"SELECT {', '.join(basic_columns)} FROM credit_wallets"
                
                result = await session.execute(text(select_query))
                
                logger.info("\n📋 Current credit_wallets data:")
                for row in result:
                    logger.info(f"  Row: {dict(zip(basic_columns, row))}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error checking credit_wallets structure: {e}")
        return False

async def check_all_credit_related_tables():
    """Check all credit-related tables"""
    try:
        async with get_session() as session:
            # Check for credit-related tables
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND (table_name LIKE '%credit%' OR table_name LIKE '%wallet%')
                ORDER BY table_name;
            """))
            
            credit_tables = [row[0] for row in result]
            logger.info(f"📋 Credit-related tables found: {credit_tables}")
            
            # Check specific credit-related data for our users
            logger.info("\n💳 Checking credit data for our users:")
            
            # Get user IDs first
            result = await session.execute(text("""
                SELECT id, email, credits, subscription_tier
                FROM users 
                WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae');
            """))
            
            user_data = {}
            for row in result:
                user_id = str(row[0])
                email = row[1]
                credits = row[2]
                tier = row[3]
                user_data[email] = {'id': user_id, 'credits': credits, 'tier': tier}
                logger.info(f"  {email}: ID={user_id}, Credits={credits}, Tier={tier}")
            
            # Check each credit table for our users
            for table in credit_tables:
                try:
                    result = await session.execute(text(f"""
                        SELECT * FROM {table} 
                        WHERE user_id IN (
                            SELECT id FROM users 
                            WHERE email IN ('client@analyticsfollowing.com', 'zain@following.ae')
                        );
                    """))
                    
                    rows = result.fetchall()
                    if rows:
                        logger.info(f"\n📊 {table} data:")
                        for row in rows:
                            logger.info(f"  {dict(zip(result.keys(), row))}")
                    else:
                        logger.info(f"\n📊 {table}: No data for our users")
                        
                except Exception as table_error:
                    logger.warning(f"⚠️ Could not query {table}: {table_error}")
            
            return user_data
            
    except Exception as e:
        logger.error(f"❌ Error checking credit tables: {e}")
        return {}

async def fix_credit_wallet_for_client(user_data):
    """Fix or create credit_wallet entry for client"""
    try:
        async with get_session() as session:
            client_data = user_data.get('client@analyticsfollowing.com')
            if not client_data:
                logger.warning("⚠️ No client data found")
                return
            
            user_id = client_data['id']
            credits = client_data['credits']
            tier = client_data['tier']
            
            # First check if credit_wallets table has the structure we expect
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'credit_wallets' AND table_schema = 'public';
            """))
            
            columns = [row[0] for row in result]
            logger.info(f"📋 Available columns in credit_wallets: {columns}")
            
            # Build appropriate INSERT/UPDATE based on available columns
            if 'current_balance' in columns:
                # Use current_balance instead of credits_balance
                await session.execute(text("""
                    INSERT INTO credit_wallets (user_id, current_balance)
                    VALUES (:user_id, :credits)
                    ON CONFLICT (user_id) DO UPDATE SET
                        current_balance = :credits,
                        updated_at = NOW()
                """), {
                    "user_id": user_id,
                    "credits": credits
                })
                logger.info(f"✅ Updated credit_wallets.current_balance to {credits} for client")
                
            elif 'credits_balance' in columns:
                # Use credits_balance
                await session.execute(text("""
                    INSERT INTO credit_wallets (user_id, credits_balance)
                    VALUES (:user_id, :credits)
                    ON CONFLICT (user_id) DO UPDATE SET
                        credits_balance = :credits,
                        updated_at = NOW()
                """), {
                    "user_id": user_id,
                    "credits": credits
                })
                logger.info(f"✅ Updated credit_wallets.credits_balance to {credits} for client")
            
            await session.commit()
            
    except Exception as e:
        logger.error(f"❌ Error fixing credit wallet: {e}")

async def main():
    """Main function"""
    try:
        logger.info("🚀 Checking credit_wallets structure and fixing issues...")
        
        # Initialize database
        await init_database()
        
        # Check credit_wallets structure
        table_exists = await check_credit_wallets_structure()
        
        # Check all credit-related data
        user_data = await check_all_credit_related_tables()
        
        # Fix credit wallet for client if needed
        if table_exists and user_data:
            await fix_credit_wallet_for_client(user_data)
        
        # Final verification
        logger.info("\n🎯 FINAL STATUS CHECK:")
        async with get_session() as session:
            result = await session.execute(text("""
                SELECT u.email, u.credits as user_credits, cw.current_balance as wallet_balance
                FROM users u
                LEFT JOIN credit_wallets cw ON u.id = cw.user_id
                WHERE u.email = 'client@analyticsfollowing.com';
            """))
            
            for row in result:
                logger.info(f"✅ {row[0]}: User credits={row[1]}, Wallet balance={row[2]}")
        
        logger.info("✅ Credit wallet verification and fix completed!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())