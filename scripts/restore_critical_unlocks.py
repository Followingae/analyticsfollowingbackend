#!/usr/bin/env python3
"""
CRITICAL UNLOCK RESTORATION - Direct SQL Approach
Bypasses SQLAlchemy model issues to directly restore unlocked_influencers records.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from uuid import UUID

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.database.connection import get_session, init_database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def restore_critical_unlocks():
    """Directly restore unlocked_influencers records using raw SQL"""
    logger.info("🚀 CRITICAL UNLOCK RESTORATION")
    logger.info("==============================")
    
    # Initialize database
    await init_database()
    
    async with get_session() as db:
        # Step 1: Find all profile_analysis transactions that need access records
        logger.info("1. Finding transactions that need unlock records...")
        
        find_query = """
        SELECT 
            ct.id as transaction_id,
            ct.reference_id as username,
            ct.amount as credits_spent,
            ct.created_at as transaction_date,
            cw.user_id as supabase_user_id,
            p.id as profile_id
        FROM credit_transactions ct
        JOIN credit_wallets cw ON ct.wallet_id = cw.id
        LEFT JOIN profiles p ON p.username = ct.reference_id
        WHERE 
            ct.action_type = 'profile_analysis'
            AND ct.amount < 0
            AND ct.reference_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM unlocked_influencers ui 
                WHERE ui.user_id = cw.user_id 
                AND ui.username = ct.reference_id
            )
            AND p.id IS NOT NULL  -- Only for profiles that exist
        ORDER BY ct.created_at DESC;
        """
        
        result = await db.execute(text(find_query))
        missing_unlocks = result.fetchall()
        
        logger.info(f"Found {len(missing_unlocks)} transactions needing unlock restoration")
        
        if not missing_unlocks:
            logger.info("✅ No missing unlock records found!")
            return
        
        # Step 2: Show what will be restored
        logger.info("\n📋 RESTORATION PLAN:")
        unique_profiles = set()
        for unlock in missing_unlocks:
            unique_profiles.add(unlock.username)
            logger.info(f"   • User {unlock.supabase_user_id} -> {unlock.username}")
            logger.info(f"     Credits: {abs(unlock.credits_spent)}, Date: {unlock.transaction_date}")
        
        logger.info(f"\nUnique profiles to unlock: {len(unique_profiles)}")
        logger.info(f"Total unlock records to create: {len(missing_unlocks)}")
        
        # Step 3: Create unlock records using direct SQL insert
        logger.info("\n🔧 CREATING UNLOCK RECORDS...")
        current_time = datetime.now(timezone.utc)
        
        insert_query = """
        INSERT INTO unlocked_influencers (
            user_id, profile_id, username, unlocked_at, 
            credits_spent, transaction_id
        ) VALUES (:user_id, :profile_id, :username, :unlocked_at, :credits_spent, :transaction_id)
        ON CONFLICT (user_id, username) DO NOTHING;
        """
        
        success_count = 0
        for unlock in missing_unlocks:
            try:
                await db.execute(
                    text(insert_query),
                    {
                        "user_id": unlock.supabase_user_id,      # user_id (Supabase UUID)
                        "profile_id": unlock.profile_id,         # profile_id
                        "username": unlock.username,             # username
                        "unlocked_at": current_time,             # unlocked_at
                        "credits_spent": abs(unlock.credits_spent),  # credits_spent (positive)
                        "transaction_id": unlock.transaction_id  # transaction_id
                    }
                )
                success_count += 1
                logger.info(f"   ✅ Created unlock: {unlock.username}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to create unlock for {unlock.username}: {e}")
        
        # Step 4: Commit all changes
        if success_count > 0:
            await db.commit()
            logger.info(f"\n🎉 RESTORATION COMPLETE!")
            logger.info(f"   Successfully restored: {success_count}/{len(missing_unlocks)} unlock records")
            
            # Verify restoration
            verify_query = """
            SELECT COUNT(*) as total_unlocks,
                   COUNT(DISTINCT username) as unique_profiles
            FROM unlocked_influencers 
            WHERE user_id = :user_id;
            """
            
            # Get the main user ID from the first unlock
            if missing_unlocks:
                user_id = missing_unlocks[0].supabase_user_id
                verify_result = await db.execute(text(verify_query), {"user_id": user_id})
                verification = verify_result.fetchone()
                
                logger.info(f"\n📊 VERIFICATION FOR USER {user_id}:")
                logger.info(f"   Total unlocks: {verification.total_unlocks}")
                logger.info(f"   Unique profiles: {verification.unique_profiles}")
        else:
            logger.info("❌ No records were successfully created")
    
    logger.info("==============================")

if __name__ == "__main__":
    asyncio.run(restore_critical_unlocks())