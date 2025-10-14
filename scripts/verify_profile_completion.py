#!/usr/bin/env python3
"""
Verify Profile Completion Status Script
Checks APIFY + CDN + AI completion status for specific profiles
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_session
from app.database.unified_models import Profile, Post

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_profile_completion(username: str, db: AsyncSession) -> dict:
    """Verify complete processing status for a profile"""
    try:
        # Get profile data
        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            return {
                'username': username,
                'exists': False,
                'error': 'Profile not found'
            }

        # Check basic profile data
        has_followers = profile.followers_count and profile.followers_count > 0
        has_posts_count = profile.posts_count and profile.posts_count > 0
        has_biography = profile.biography is not None

        # Check AI analysis completion
        has_ai_analysis = profile.ai_profile_analyzed_at is not None

        # Check posts in database
        posts_query = select(func.count(Post.id)).where(Post.profile_id == profile.id)
        posts_result = await db.execute(posts_query)
        posts_in_db = posts_result.scalar() or 0

        # Check posts with AI analysis
        ai_posts_query = select(func.count(Post.id)).where(
            Post.profile_id == profile.id,
            Post.ai_analyzed_at.isnot(None)
        )
        ai_posts_result = await db.execute(ai_posts_query)
        ai_analyzed_posts = ai_posts_result.scalar() or 0

        # Check posts with CDN thumbnails
        cdn_posts_query = select(func.count(Post.id)).where(
            Post.profile_id == profile.id,
            Post.cdn_thumbnail_url.isnot(None)
        )
        cdn_posts_result = await db.execute(cdn_posts_query)
        cdn_processed_posts = cdn_posts_result.scalar() or 0

        # Determine completion status
        apify_complete = has_followers and has_posts_count and has_biography
        posts_stored = posts_in_db >= 12  # Should have at least 12 posts
        ai_complete = has_ai_analysis and ai_analyzed_posts >= 12
        cdn_complete = cdn_processed_posts >= 12

        overall_complete = apify_complete and posts_stored and ai_complete and cdn_complete

        return {
            'username': username,
            'exists': True,
            'profile_id': str(profile.id),
            'overall_complete': overall_complete,
            'apify_data': {
                'complete': apify_complete,
                'followers_count': profile.followers_count,
                'posts_count': profile.posts_count,
                'has_biography': has_biography,
                'created_at': profile.created_at.isoformat() if profile.created_at else None
            },
            'posts_data': {
                'total_posts_in_db': posts_in_db,
                'posts_stored_complete': posts_stored
            },
            'ai_analysis': {
                'complete': ai_complete,
                'profile_analyzed': has_ai_analysis,
                'ai_analyzed_at': profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
                'posts_with_ai': ai_analyzed_posts,
                'ai_posts_complete': ai_analyzed_posts >= 12
            },
            'cdn_processing': {
                'complete': cdn_complete,
                'posts_with_cdn': cdn_processed_posts,
                'cdn_posts_complete': cdn_processed_posts >= 12
            }
        }

    except Exception as e:
        logger.error(f"Error verifying {username}: {e}")
        return {
            'username': username,
            'exists': False,
            'error': str(e)
        }

async def main():
    """Main verification script"""
    print("=" * 60)
    print("PROFILE COMPLETION VERIFICATION")
    print("=" * 60)

    # Profiles to check
    test_profiles = [
        'athlecult',
        'migrationology',
        '_om__sarah_',
        '15smeals',
        '24ndubai'
    ]

    async with get_session() as db:
        for username in test_profiles:
            print(f"\n🔍 Checking: @{username}")
            print("-" * 40)

            result = await verify_profile_completion(username, db)

            if not result['exists']:
                print(f"❌ Profile not found: {result.get('error', 'Unknown error')}")
                continue

            # Print results
            print(f"✅ Profile ID: {result['profile_id']}")
            print(f"🎯 Overall Complete: {'✅ YES' if result['overall_complete'] else '❌ NO'}")

            # APIFY Data
            apify = result['apify_data']
            print(f"\n📊 APIFY DATA: {'✅' if apify['complete'] else '❌'}")
            print(f"   - Followers: {apify['followers_count']:,}")
            print(f"   - Posts Count: {apify['posts_count']:,}")
            print(f"   - Biography: {'✅' if apify['has_biography'] else '❌'}")

            # Posts Data
            posts = result['posts_data']
            print(f"\n📝 POSTS STORAGE: {'✅' if posts['posts_stored_complete'] else '❌'}")
            print(f"   - Posts in DB: {posts['total_posts_in_db']}")
            print(f"   - Minimum 12: {'✅' if posts['posts_stored_complete'] else '❌'}")

            # AI Analysis
            ai = result['ai_analysis']
            print(f"\n🤖 AI ANALYSIS: {'✅' if ai['complete'] else '❌'}")
            print(f"   - Profile AI: {'✅' if ai['profile_analyzed'] else '❌'}")
            print(f"   - Posts with AI: {ai['posts_with_ai']}")
            print(f"   - AI Complete: {'✅' if ai['ai_posts_complete'] else '❌'}")

            # CDN Processing
            cdn = result['cdn_processing']
            print(f"\n🖼️ CDN PROCESSING: {'✅' if cdn['complete'] else '❌'}")
            print(f"   - Posts with CDN: {cdn['posts_with_cdn']}")
            print(f"   - CDN Complete: {'✅' if cdn['cdn_posts_complete'] else '❌'}")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())