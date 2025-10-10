#!/usr/bin/env python3

import asyncio
import sys
sys.path.append('.')

from app.database.connection import get_session as get_database_session
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from app.database.unified_models import Profile
from sqlalchemy import select

async def debug_creator_analytics():
    """Debug Creator Analytics for ahmed.othman"""
    username = "ahmed.othman"

    async with get_database_session() as db:
        print(f"🔍 Debugging Creator Analytics for: {username}")

        # Check current profile state
        result = await db.execute(
            select(Profile).where(Profile.username == username)
        )
        profile = result.scalar_one_or_none()

        if profile:
            print(f"📊 Current Profile State:")
            print(f"   - ID: {profile.id}")
            print(f"   - Followers: {profile.followers_count}")
            print(f"   - Following: {profile.following_count}")
            print(f"   - Posts: {profile.posts_count}")
            print(f"   - AI Analyzed: {'YES' if profile.ai_profile_analyzed_at else 'NO'}")
            print(f"   - Biography: {profile.biography[:50] if profile.biography else 'None'}...")
            print(f"   - Last Refreshed: {profile.last_refreshed}")
            print(f"   - Created: {profile.created_at}")
            print()
        else:
            print(f"❌ Profile {username} not found in database")
            return

        # Trigger Creator Analytics
        print(f"🚀 Triggering Creator Analytics...")
        try:
            updated_profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                username=username,
                db=db,
                force_refresh=True  # Force refresh to see what happens
            )

            print(f"✅ Creator Analytics completed:")
            print(f"   - Source: {metadata.get('source')}")
            print(f"   - Success: {metadata.get('is_full_analytics', False)}")
            if updated_profile:
                print(f"   - Followers: {updated_profile.followers_count:,}")
                print(f"   - Posts: {updated_profile.posts_count}")
                print(f"   - AI Analyzed: {'YES' if updated_profile.ai_profile_analyzed_at else 'NO'}")

            if 'error' in metadata:
                print(f"❌ Error: {metadata['error']}")

        except Exception as e:
            print(f"❌ Creator Analytics failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_creator_analytics())