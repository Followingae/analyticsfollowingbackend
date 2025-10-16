"""
Trigger CDN Processing for Post Thumbnails
Manually enqueue and process post thumbnails for a profile
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def trigger_post_cdn_processing(username: str = 'latifalshamsi'):
    """Trigger CDN processing for all posts of a profile"""
    from app.database.connection import init_database, get_session
    from sqlalchemy import text
    from app.services.cdn_image_service import cdn_image_service

    await init_database()

    logger.info(f"🚀 Triggering CDN processing for @{username} posts...")

    async with get_session() as db:
        # Get profile ID
        profile_query = text("""
            SELECT id FROM profiles WHERE username = :username
        """)
        result = await db.execute(profile_query, {'username': username})
        profile_row = result.fetchone()

        if not profile_row:
            logger.error(f"❌ Profile @{username} not found!")
            return

        profile_id = str(profile_row[0])
        logger.info(f"✅ Found profile: {profile_id}")

        # Get posts data
        posts_query = text("""
            SELECT
                id,
                instagram_post_id,
                shortcode,
                display_url,
                cdn_thumbnail_url
            FROM posts
            WHERE profile_id = :profile_id
            AND display_url IS NOT NULL
            ORDER BY created_at DESC
        """)
        posts_result = await db.execute(posts_query, {'profile_id': profile_id})
        posts = posts_result.fetchall()

        logger.info(f"📊 Found {len(posts)} posts with display URLs")

        # Prepare Apify-like data structure for CDN service
        apify_data = {
            'profile_pic_url_hd': None,  # We only want to process posts
            'posts': []
        }

        # Use CDN service to enqueue posts
        cdn_image_service.set_db_session(db)

        jobs_created = 0

        # Enqueue each post individually
        from uuid import UUID
        for i, post in enumerate(posts, 1):
            post_id = post[0]
            instagram_post_id = post[1]
            shortcode = post[2]
            display_url = post[3]
            cdn_thumbnail_url = post[4]

            if cdn_thumbnail_url:
                logger.info(f"⏭️  Post {i}/{len(posts)} ({shortcode}): Already has CDN URL, skipping")
                continue

            logger.info(f"🖼️  Post {i}/{len(posts)}: {shortcode}")
            logger.info(f"   Display URL: {display_url[:80]}...")

            try:
                # Enqueue this post
                asset_id = await cdn_image_service._enqueue_asset(
                    source_type='post_thumbnail',
                    source_id=UUID(profile_id),
                    media_id=instagram_post_id,
                    source_url=display_url,
                    priority=5
                )

                if asset_id:
                    jobs_created += 1
                    logger.info(f"   ✅ Enqueued (Job created)")
                else:
                    logger.warning(f"   ⚠️  Failed to enqueue")

            except Exception as e:
                logger.error(f"   ❌ Error: {e}")

        await db.commit()

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ ENQUEUE COMPLETE!")
        logger.info(f"   Jobs Created: {jobs_created}")
        logger.info(f"   Total Posts: {len(posts)}")
        logger.info(f"{'='*60}\n")

        # Now process the jobs using our synchronous processor
        if jobs_created > 0:
            logger.info("🔄 Now processing CDN jobs...")
            from process_stuck_cdn_jobs import reset_and_process_stuck_jobs
            await reset_and_process_stuck_jobs()

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else 'latifalshamsi'
    asyncio.run(trigger_post_cdn_processing(username))
