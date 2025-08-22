#!/usr/bin/env python3
"""
Test Total Plan Credits Implementation
Tests the new Total Plan Credits calculation and API endpoint
"""
import asyncio
import sys
import os
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.credit_wallet_service import credit_wallet_service
from app.database.connection import init_database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_total_plan_credits():
    """Test the total plan credits implementation"""
    
    # Test users
    test_users = [
        {"email": "zain@following.ae", "name": "Zain (Superadmin)"},
        {"email": "client@analyticsfollowing.com", "name": "Client (Brand User)"}
    ]
    
    try:
        # Initialize database
        await init_database()
        logger.info("✅ Database initialized")
        
        # Apply migration first
        logger.info("🔄 Applying Total Plan Credits migration...")
        from app.database.connection import get_session
        from sqlalchemy import text
        
        async with get_session() as session:
            # Read and execute migration
            migration_path = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'add_total_plan_credits_tracking.sql')
            if os.path.exists(migration_path):
                with open(migration_path, 'r') as f:
                    migration_sql = f.read()
                
                # Split by statements and execute
                statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
                for stmt in statements:
                    if stmt and not stmt.startswith('--'):
                        try:
                            await session.execute(text(stmt))
                        except Exception as e:
                            if "already exists" not in str(e).lower():
                                logger.warning(f"Migration statement failed: {e}")
                
                await session.commit()
                logger.info("✅ Migration applied")
            else:
                logger.warning("Migration file not found")
        
        # Test each user
        for user_info in test_users:
            logger.info(f"\n🧪 Testing {user_info['name']} ({user_info['email']})")
            
            # Get user ID from database
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": user_info['email']}
                )
                user_row = result.fetchone()
                
                if not user_row:
                    logger.error(f"❌ User not found: {user_info['email']}")
                    continue
                
                user_id = UUID(str(user_row[0]))
                logger.info(f"📋 User ID: {user_id}")
            
            # Test wallet balance
            try:
                balance = await credit_wallet_service.get_wallet_balance(user_id)
                logger.info(f"💰 Current Balance: {balance.balance} credits")
            except Exception as e:
                logger.error(f"❌ Error getting balance: {e}")
                continue
            
            # Test total plan credits (new functionality)
            try:
                total_plan = await credit_wallet_service.get_total_plan_credits(user_id)
                if total_plan:
                    logger.info(f"🎯 TOTAL PLAN CREDITS BREAKDOWN:")
                    logger.info(f"   📦 Package Credits: {total_plan.package_credits}")
                    logger.info(f"   💳 Purchased Credits: {total_plan.purchased_credits}")
                    logger.info(f"   🎁 Bonus Credits: {total_plan.bonus_credits}")
                    logger.info(f"   ➕ TOTAL PLAN CREDITS: {total_plan.total_plan_credits}")
                    logger.info(f"   📅 Monthly Allowance: {total_plan.monthly_allowance}")
                    logger.info(f"   📋 Package: {total_plan.package_name}")
                    logger.info(f"   💰 Current Spendable: {total_plan.current_balance}")
                else:
                    logger.warning(f"⚠️ No total plan credits data found")
            except Exception as e:
                logger.error(f"❌ Error getting total plan credits: {e}")
            
            # Test enhanced wallet summary
            try:
                summary = await credit_wallet_service.get_wallet_summary(user_id)
                if summary:
                    logger.info(f"📊 Enhanced Wallet Summary:")
                    logger.info(f"   Total Plan Credits: {summary.total_plan_credits}")
                    logger.info(f"   Package Credits: {summary.package_credits_balance}")
                    logger.info(f"   Purchased Credits: {summary.purchased_credits_balance}")
                    logger.info(f"   Bonus Credits: {summary.bonus_credits_balance}")
                    logger.info(f"   Monthly Allowance: {summary.monthly_allowance}")
                    logger.info(f"   Package Name: {summary.package_name}")
                else:
                    logger.warning(f"⚠️ No wallet summary found")
            except Exception as e:
                logger.error(f"❌ Error getting wallet summary: {e}")
        
        logger.info("\n✅ Total Plan Credits implementation test completed!")
        
        # Show API endpoint info
        logger.info("\n🔗 NEW API ENDPOINT:")
        logger.info("GET /api/v1/credits/total-plan-credits")
        logger.info("Returns comprehensive Total Plan Credits breakdown")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_total_plan_credits())