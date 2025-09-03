#!/usr/bin/env python3
"""
CRITICAL UNLOCK FIX - Simple Insert Approach
Creates the missing unlock records for users who were charged.
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

async def create_missing_unlocks():
    """Create missing unlock records for profiles that were charged but not unlocked"""
    logger.info("🚀 CREATING MISSING UNLOCK RECORDS")
    logger.info("==================================")
    
    # Initialize database
    await init_database()
    
    # Specific unlock records to create (based on previous analysis)
    unlock_data = [
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': '331bceda-ea76-41f0-96d4-45980dac0807', 'username': 'sharjahlive', 'credits': 25, 'tx_id': 33},
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': '04fe8706-93f5-4564-b363-d6367c176e98', 'username': 'moweeezy', 'credits': 25, 'tx_id': 31},
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': '778b2631-a820-479a-812b-789ecd61e9d2', 'username': 'lukadoncic', 'credits': 25, 'tx_id': 28},
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': 'd50b27ed-567e-4db3-99b8-52a49557009e', 'username': 'wemby', 'credits': 25, 'tx_id': 22},
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': 'd62a8790-8472-412a-ab03-5623e25e45ff', 'username': 'deals.food', 'credits': 25, 'tx_id': 21},
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': '722a6827-245d-457a-a572-e4c6df7e8c4f', 'username': 'shaq', 'credits': 25, 'tx_id': 18},
        {'user_id': '99b1001b-69a0-4d75-9730-3177ba42c642', 'profile_id': 'd4a444d3-1baa-4cd6-b19e-71d08bc189a3', 'username': 'tony.keyrouz', 'credits': 25, 'tx_id': 14},
    ]
    
    logger.info(f"Creating unlock records for {len(unlock_data)} profiles...")
    current_time = datetime.now(timezone.utc)
    
    success_count = 0
    async with get_session() as db:
        for unlock in unlock_data:
            try:
                # Create individual transactions to avoid rollback cascade
                insert_query = """
                INSERT INTO unlocked_influencers (user_id, profile_id, username, unlocked_at, credits_spent, transaction_id)
                VALUES (:user_id, :profile_id, :username, :unlocked_at, :credits_spent, :transaction_id);
                """
                
                await db.execute(text(insert_query), {
                    'user_id': unlock['user_id'],
                    'profile_id': unlock['profile_id'],
                    'username': unlock['username'],
                    'unlocked_at': current_time,
                    'credits_spent': unlock['credits'],
                    'transaction_id': unlock['tx_id']
                })
                
                await db.commit()
                logger.info(f"✅ Created unlock: {unlock['username']}")
                success_count += 1
                
            except Exception as e:
                await db.rollback()
                if "duplicate key value" in str(e).lower():
                    logger.info(f"⚠️  Already exists: {unlock['username']}")
                    success_count += 1
                else:
                    logger.error(f"❌ Failed to create unlock for {unlock['username']}: {e}")
    
    logger.info(f"\n🎉 RESTORATION SUMMARY")
    logger.info(f"   Successfully processed: {success_count}/{len(unlock_data)} profiles")
    
    # Verify the unlocks were created
    async with get_session() as db:
        verify_query = """
        SELECT username, unlocked_at FROM unlocked_influencers 
        WHERE user_id = :user_id 
        ORDER BY unlocked_at DESC;
        """
        result = await db.execute(text(verify_query), {'user_id': unlock_data[0]['user_id']})
        unlocks = result.fetchall()
        
        logger.info(f"\n📊 VERIFICATION - User has {len(unlocks)} total unlocks:")
        for unlock in unlocks:
            logger.info(f"   • {unlock.username} (unlocked: {unlock.unlocked_at})")

if __name__ == "__main__":
    asyncio.run(create_missing_unlocks())