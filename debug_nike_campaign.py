#!/usr/bin/env python3

import asyncio
import sys
sys.path.append('.')

from app.database.database import get_database_session
from app.models.campaigns import Campaign
from app.models.campaign_posts import CampaignPost
from app.models.posts import Post
from app.models.profiles import Profile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def check_nike_campaign():
    async with get_database_session() as db:
        # Find Nike campaign
        result = await db.execute(
            select(Campaign).where(Campaign.name.ilike('%nike%'))
        )
        campaigns = result.scalars().all()

        print(f"Found {len(campaigns)} Nike campaigns:")
        for campaign in campaigns:
            print(f"   Campaign: {campaign.name}")
            print(f"   ID: {campaign.id}")

            # Get campaign posts with profiles
            posts_result = await db.execute(
                select(CampaignPost)
                .options(selectinload(CampaignPost.post).selectinload(Post.profile))
                .where(CampaignPost.campaign_id == campaign.id)
                .limit(10)
            )
            campaign_posts = posts_result.scalars().all()

            print(f"   Campaign has {len(campaign_posts)} posts:")
            for cp in campaign_posts:
                post = cp.post
                profile = post.profile if post else None

                if profile:
                    has_ai = "YES" if profile.ai_profile_analyzed_at else "NO"
                    print(f"     - Profile: {profile.username}")
                    print(f"       Followers: {profile.followers_count}")
                    print(f"       Post likes: {post.likes_count}")
                    print(f"       AI Category: {post.ai_content_category}")
                    print(f"       Profile AI Complete: {has_ai}")
                    print(f"       ---")
                else:
                    post_id = post.id if post else "None"
                    print(f"     - Missing profile for post {post_id}")

if __name__ == "__main__":
    asyncio.run(check_nike_campaign())