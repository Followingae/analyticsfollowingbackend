#!/usr/bin/env python3
"""
RESTORE MISSING ACCESS RECORDS
Fixes critical issue where users were charged for profile unlocks but access records weren't created.

This script:
1. Identifies credit transactions for profile_analysis actions
2. Checks if corresponding access records exist
3. Creates missing access records for users who were charged
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from uuid import UUID

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select, and_, text
from app.database.connection import get_session, init_database
from app.database.unified_models import (
    CreditTransaction, Profile, User, UnlockedInfluencer, 
    UserProfileAccess, CreditWallet
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def find_missing_access_records():
    """Find credit transactions for profile analysis that are missing access records"""
    logger.info("🔍 Searching for missing access records...")
    
    missing_records = []
    
    async with get_session() as db:
        # Find all credit transactions for profile_analysis actions where credits were spent
        transaction_query = select(CreditTransaction).where(
            and_(
                CreditTransaction.action_type == "profile_analysis",
                CreditTransaction.amount < 0,  # Negative amount means spending
                CreditTransaction.reference_id.isnot(None)
            )
        ).order_by(CreditTransaction.created_at.desc())
        
        transaction_result = await db.execute(transaction_query)
        transactions = transaction_result.scalars().all()
        
        logger.info(f"Found {len(transactions)} profile_analysis credit transactions")
        
        for transaction in transactions:
            try:
                # Get the wallet to find user_id
                wallet_query = select(CreditWallet).where(CreditWallet.id == transaction.wallet_id)
                wallet_result = await db.execute(wallet_query)
                wallet = wallet_result.scalar_one_or_none()
                
                if not wallet:
                    logger.warning(f"No wallet found for transaction {transaction.id}")
                    continue
                
                user_id = wallet.user_id
                username = transaction.reference_id
                
                # Check if unlocked_influencers record exists
                unlock_query = select(UnlockedInfluencer).where(
                    and_(
                        UnlockedInfluencer.user_id == user_id,
                        UnlockedInfluencer.username == username
                    )
                )
                unlock_result = await db.execute(unlock_query)
                unlocked_record = unlock_result.scalar_one_or_none()
                
                # Get database user ID for user_profile_access check
                db_user_query = select(User.id).where(User.supabase_user_id == str(user_id))
                db_user_result = await db.execute(db_user_query)
                database_user_id = db_user_result.scalar_one_or_none()
                
                # Get profile by username
                profile_query = select(Profile).where(Profile.username == username)
                profile_result = await db.execute(profile_query)
                profile = profile_result.scalar_one_or_none()
                
                # Check if user_profile_access record exists
                access_record = None
                if database_user_id and profile:
                    access_query = select(UserProfileAccess).where(
                        and_(
                            UserProfileAccess.user_id == database_user_id,
                            UserProfileAccess.profile_id == profile.id
                        )
                    )
                    access_result = await db.execute(access_query)
                    access_record = access_result.scalar_one_or_none()
                
                # Check if records are missing
                is_missing = not unlocked_record or not access_record
                
                if is_missing:
                    missing_records.append({
                        'transaction_id': transaction.id,
                        'user_id': user_id,
                        'database_user_id': database_user_id,
                        'username': username,
                        'profile_id': profile.id if profile else None,
                        'profile_name': profile.full_name if profile else None,
                        'credits_spent': abs(transaction.amount),
                        'transaction_date': transaction.created_at,
                        'missing_unlocked': not unlocked_record,
                        'missing_access': not access_record,
                        'profile_exists': profile is not None,
                        'db_user_exists': database_user_id is not None
                    })
                    
                    logger.warning(f"❌ MISSING ACCESS for user {user_id} -> {username}")
                    logger.warning(f"   Transaction: {transaction.id}, Credits: {abs(transaction.amount)}")
                    logger.warning(f"   Missing unlocked_influencers: {not unlocked_record}")
                    logger.warning(f"   Missing user_profile_access: {not access_record}")
                else:
                    logger.info(f"✅ Access records OK for user {user_id} -> {username}")
                    
            except Exception as e:
                logger.error(f"Error checking transaction {transaction.id}: {e}")
                
        logger.info(f"🎯 Found {len(missing_records)} transactions with missing access records")
        return missing_records

async def restore_access_record(record):
    """Restore access records for a single transaction"""
    try:
        user_id = record['user_id']
        database_user_id = record['database_user_id']
        username = record['username']
        profile_id = record['profile_id']
        credits_spent = record['credits_spent']
        transaction_id = record['transaction_id']
        
        if not profile_id:
            logger.error(f"Cannot restore access for {username} - profile not found")
            return False
            
        if not database_user_id:
            logger.error(f"Cannot restore access for user {user_id} - database user not found")
            return False
        
        async with get_session() as db:
            current_time = datetime.now(timezone.utc)
            records_created = 0
            
            # Create unlocked_influencers record if missing
            if record['missing_unlocked']:
                unlocked_influencer = UnlockedInfluencer(
                    user_id=user_id,  # Supabase UUID
                    profile_id=profile_id,
                    username=username,
                    unlocked_at=current_time,
                    credits_spent=credits_spent,
                    transaction_id=transaction_id
                )
                db.add(unlocked_influencer)
                records_created += 1
                logger.info(f"   📝 Creating unlocked_influencers record")
            
            # Create user_profile_access record if missing
            if record['missing_access']:
                from datetime import timedelta
                expires_at = current_time + timedelta(days=30)
                
                profile_access = UserProfileAccess(
                    user_id=database_user_id,  # Database UUID
                    profile_id=profile_id,
                    granted_at=current_time,
                    expires_at=expires_at
                )
                db.add(profile_access)
                records_created += 1
                logger.info(f"   📝 Creating user_profile_access record")
            
            if records_created > 0:
                await db.commit()
                logger.info(f"✅ RESTORED access for user {user_id} -> {username} ({records_created} records)")
                return True
            else:
                logger.info(f"⚠️  No records needed for user {user_id} -> {username}")
                return True
                
    except Exception as e:
        logger.error(f"❌ Failed to restore access record: {e}")
        return False

async def main():
    """Main restoration process"""
    logger.info("🚀 STARTING ACCESS RECORD RESTORATION")
    logger.info("=====================================")
    
    # Initialize database
    logger.info("🔧 Initializing database connection...")
    await init_database()
    
    # Find missing records
    missing_records = await find_missing_access_records()
    
    if not missing_records:
        logger.info("🎉 No missing access records found - all users have proper access!")
        return
    
    logger.info(f"\n📋 RESTORATION SUMMARY:")
    logger.info(f"   Missing Records: {len(missing_records)}")
    
    for record in missing_records:
        logger.info(f"   • User {record['user_id']} -> {record['username']}")
        logger.info(f"     Credits: {record['credits_spent']}, Date: {record['transaction_date']}")
        logger.info(f"     Missing: unlocked={record['missing_unlocked']}, access={record['missing_access']}")
    
    # Confirm restoration
    logger.info(f"\nWARNING: About to restore access for {len(missing_records)} users.")
    logger.info("This will create missing access records for users who were charged credits.")
    logger.info("Proceeding with automatic restoration...")
    
    # Auto-proceed for system restoration
    
    # Restore records
    logger.info("\nRESTORING ACCESS RECORDS...")
    success_count = 0
    
    for record in missing_records:
        logger.info(f"\nRestoring: {record['username']} (Transaction {record['transaction_id']})")
        if await restore_access_record(record):
            success_count += 1
    
    logger.info(f"\nRESTORATION COMPLETE!")
    logger.info(f"   Successful: {success_count}/{len(missing_records)}")
    logger.info("=====================================")

if __name__ == "__main__":
    asyncio.run(main())