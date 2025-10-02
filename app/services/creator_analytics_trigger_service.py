"""
Creator Analytics Trigger Service - Complete Creator Analytics Pipeline
Triggers the FULL Creator Analytics module with all rules and flows
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.unified_models import Profile, Post
from app.database.comprehensive_service import ComprehensiveDataService
from app.scrapers.apify_instagram_client import ApifyInstagramClient
from app.services.unified_background_processor import unified_background_processor
from app.core.config import settings

logger = logging.getLogger(__name__)


class CreatorAnalyticsTriggerService:
    """
    Triggers FULL Creator Analytics with complete rules:
    1. Check if FULL CREATOR ANALYTICS exists in database
    2. Only serve from database if profile has:
       - followers_count > 0
       - posts_count > 0
       - ai_profile_analyzed_at not null
       - posts stored in database
    3. If incomplete, trigger fresh Apify + CDN + AI pipeline
    4. Store complete results in database (same as individual creator search)
    """

    def __init__(self):
        self.comprehensive_service = ComprehensiveDataService()
        self.cache_ttl = timedelta(hours=24)  # Same as creator search

    async def trigger_full_creator_analytics(
        self,
        username: str,
        db: AsyncSession,
        force_refresh: bool = False
    ) -> Tuple[Optional[Profile], Dict[str, Any]]:
        """
        Trigger FULL creator analytics with complete rules

        Args:
            username: Instagram username
            db: Database session
            force_refresh: Force fresh fetch even if data exists

        Returns:
            Tuple of (Profile object, metadata dict)
        """
        try:
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"🚀 FULL CREATOR ANALYTICS TRIGGERED: {username}")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Step 1: Check if profile exists and has FULL ANALYTICS
            profile_query = select(Profile).where(Profile.username == username)
            profile_result = await db.execute(profile_query)
            existing_profile = profile_result.scalar_one_or_none()

            has_full_analytics = False
            reason_incomplete = None

            if existing_profile and not force_refresh:
                # Check FULL ANALYTICS criteria
                has_basic_data = (
                    existing_profile.followers_count and existing_profile.followers_count > 0 and
                    existing_profile.posts_count and existing_profile.posts_count > 0 and
                    existing_profile.biography  # Should have biography
                )

                has_ai_analysis = existing_profile.ai_profile_analyzed_at is not None

                # Check if posts are stored
                posts_count_query = select(func.count(Post.id)).where(Post.profile_id == existing_profile.id)
                posts_count_result = await db.execute(posts_count_query)
                stored_posts_count = posts_count_result.scalar()
                has_posts = stored_posts_count > 0

                # Check if data is fresh (within cache TTL)
                is_fresh = False
                if existing_profile.last_refreshed:
                    age = datetime.now(timezone.utc) - existing_profile.last_refreshed
                    is_fresh = age < self.cache_ttl

                # Determine if we have FULL ANALYTICS
                has_full_analytics = has_basic_data and has_ai_analysis and has_posts and is_fresh

                # Log reasons if incomplete
                if not has_full_analytics:
                    reasons = []
                    if not has_basic_data:
                        reasons.append(f"Missing basic data (followers={existing_profile.followers_count}, posts_count={existing_profile.posts_count})")
                    if not has_ai_analysis:
                        reasons.append("Missing AI analysis")
                    if not has_posts:
                        reasons.append(f"No posts stored ({stored_posts_count} posts)")
                    if not is_fresh:
                        age_hours = (datetime.now(timezone.utc) - existing_profile.last_refreshed).total_seconds() / 3600
                        reasons.append(f"Data stale ({age_hours:.1f}h old)")
                    reason_incomplete = ", ".join(reasons)

            # Step 2: Decide whether to use database or fetch fresh
            if has_full_analytics:
                logger.info(f"✅ USING DATABASE: Profile {username} has FULL CREATOR ANALYTICS")
                logger.info(f"   Followers: {existing_profile.followers_count:,}")
                logger.info(f"   Posts Count: {existing_profile.posts_count}")
                logger.info(f"   AI Analysis: ✅")
                logger.info(f"   Stored Posts: {stored_posts_count}")

                return existing_profile, {
                    "source": "database",
                    "is_full_analytics": True,
                    "profile_age_hours": (datetime.now(timezone.utc) - existing_profile.last_refreshed).total_seconds() / 3600 if existing_profile.last_refreshed else None
                }

            # Step 3: Fetch fresh data from Apify
            logger.info(f"🔄 FETCHING FRESH DATA: {username}")
            if existing_profile:
                logger.info(f"   Reason: {reason_incomplete}")
            else:
                logger.info(f"   Reason: Profile not in database")

            logger.info(f"[1/4] 📡 Fetching from Apify...")
            async with ApifyInstagramClient(settings.APIFY_API_TOKEN) as apify_client:
                apify_data = await apify_client.get_instagram_profile_comprehensive(username)

            if not apify_data:
                logger.error(f"❌ Apify returned no data for {username}")
                # Return existing profile if available, otherwise None
                return existing_profile, {
                    "source": "database_fallback",
                    "is_full_analytics": False,
                    "error": "Apify fetch failed",
                    "reason": reason_incomplete if existing_profile else "Profile not found"
                }

            # Step 4: Store complete profile + posts in database
            logger.info(f"[2/4] 💾 Storing profile + posts in database...")
            profile, is_new = await self.comprehensive_service.store_complete_profile(
                db, username, apify_data
            )

            if not profile:
                logger.error(f"❌ Failed to store profile {username}")
                return existing_profile, {
                    "source": "database_fallback",
                    "is_full_analytics": False,
                    "error": "Profile storage failed"
                }

            logger.info(f"✅ Profile stored: {profile.followers_count:,} followers, {profile.posts_count} posts")

            # CRITICAL: Commit database transaction BEFORE long AI processing
            # This releases the connection back to the pool immediately
            logger.info(f"[3/4] 💾 Committing profile data to database...")
            await db.commit()
            await db.refresh(profile)
            profile_id = str(profile.id)
            logger.info(f"✅ Database transaction committed - connection released")

            # Step 5: Trigger CDN + AI pipeline in background (NO database session held)
            logger.info(f"[4/4] 🚀 Starting UNIFIED background processing (CDN → AI ALL 10 MODELS)...")
            logger.info(f"      Background processing will continue asynchronously...")

            # Run AI processing WITHOUT blocking - it will update the database when complete
            try:
                # Fire and forget - AI processing runs in background
                import asyncio
                asyncio.create_task(
                    unified_background_processor.process_profile_complete_pipeline(
                        profile_id=profile_id,
                        username=username
                    )
                )
                logger.info(f"✅ Background AI processing task created for {username}")

            except Exception as processing_error:
                logger.error(f"❌ Failed to create background processing task: {processing_error}")
                import traceback
                logger.error(traceback.format_exc())
                # Don't fail - profile is already stored

            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"✅ FULL CREATOR ANALYTICS COMPLETE: {username}")
            logger.info(f"   Followers: {profile.followers_count:,}")
            logger.info(f"   Posts: {profile.posts_count}")
            logger.info(f"   AI Analyzed: {profile.ai_profile_analyzed_at is not None}")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            return profile, {
                "source": "apify_fresh",
                "is_full_analytics": True,
                "is_new_profile": is_new,
                "followers_count": profile.followers_count,
                "posts_count": profile.posts_count,
                "ai_analyzed": profile.ai_profile_analyzed_at is not None
            }

        except Exception as e:
            logger.error(f"❌ Full creator analytics failed for {username}: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Return existing profile if available
            if existing_profile:
                return existing_profile, {
                    "source": "database_fallback",
                    "is_full_analytics": False,
                    "error": str(e)
                }

            return None, {
                "source": "failed",
                "is_full_analytics": False,
                "error": str(e)
            }


# Global service instance
creator_analytics_trigger_service = CreatorAnalyticsTriggerService()
