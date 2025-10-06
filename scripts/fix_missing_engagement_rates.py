#!/usr/bin/env python3
"""
Fix missing engagement rates for posts in the database.
This script calculates and updates engagement_rate for posts that have likes/comments but missing rate.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.database.unified_models import Post, Profile
from app.core.config import settings

# Get database URL from settings
engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_missing_engagement_rates():
    """Calculate and update missing engagement rates"""
    async with async_session_maker() as db:
        try:
            # Find posts with missing engagement rates
            query = (
                select(Post, Profile.followers_count)
                .join(Profile, Post.profile_id == Profile.id)
                .where(
                    and_(
                        Post.engagement_rate.is_(None),
                        Post.likes_count.isnot(None),
                        Post.comments_count.isnot(None),
                        Profile.followers_count > 0
                    )
                )
            )

            result = await db.execute(query)
            posts_to_fix = result.all()

            logger.info(f"Found {len(posts_to_fix)} posts with missing engagement rates")

            fixed_count = 0
            for post, followers_count in posts_to_fix:
                # Calculate engagement rate: (likes + comments) / followers * 100
                engagement_rate = round(
                    ((post.likes_count + post.comments_count) / followers_count * 100),
                    4
                )

                # Update the post
                await db.execute(
                    update(Post)
                    .where(Post.id == post.id)
                    .values(engagement_rate=engagement_rate)
                )

                fixed_count += 1
                logger.info(
                    f"Fixed post {post.id}: {post.likes_count} likes, "
                    f"{post.comments_count} comments, {followers_count} followers "
                    f"= {engagement_rate}% engagement"
                )

            await db.commit()
            logger.info(f"✅ Successfully fixed {fixed_count} posts with missing engagement rates")

            # Verify the Nike Launch campaign post specifically
            nike_post_id = '6cb1a682-243e-410e-b10b-4868e6f58923'
            nike_post = await db.execute(
                select(Post).where(Post.id == nike_post_id)
            )
            nike_post = nike_post.scalar_one_or_none()

            if nike_post:
                logger.info(
                    f"✅ Nike Launch campaign post engagement rate: {nike_post.engagement_rate}%"
                )

        except Exception as e:
            logger.error(f"❌ Error fixing engagement rates: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(fix_missing_engagement_rates())