#!/usr/bin/env python3
"""
Direct fix script for the 4 incomplete campaign profiles
"""

import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import get_session
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fix_profile(username: str):
    """Fix a single profile by triggering full creator analytics"""
    try:
        logger.info(f"Starting repair for {username}...")

        async with get_session() as db:
            # Trigger full creator analytics with force refresh
            profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                username=username,
                db=db,
                force_refresh=True  # Force refresh to ensure we get new data
            )

            if profile and profile.followers_count > 0:
                logger.info(f"SUCCESS: {username} - {profile.followers_count:,} followers, {profile.posts_count} posts")
                return True
            else:
                logger.error(f"FAILED: {username} - Still has 0 followers")
                return False

    except Exception as e:
        logger.error(f"ERROR fixing {username}: {e}")
        return False

async def main():
    """Fix all 4 incomplete campaign profiles"""
    profiles_to_fix = [
        "barakatme",
        "marrysweet884",
        "nabil.al.nahhas",
        "yolo_dxb"
    ]

    print("=" * 60)
    print("FIXING INCOMPLETE CAMPAIGN PROFILES")
    print("=" * 60)

    success_count = 0

    for username in profiles_to_fix:
        print(f"\nProcessing: {username}")
        success = await fix_profile(username)
        if success:
            success_count += 1

        # Small delay between profiles
        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print(f"REPAIR COMPLETE: {success_count}/{len(profiles_to_fix)} profiles fixed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())