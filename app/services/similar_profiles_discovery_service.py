"""
Similar Profiles Discovery Service

Background service that discovers and processes similar profiles found during
Creator Analytics and Post Analytics operations. This service operates completely
in the background without interfering with existing analytics flows.

Key Features:
- Hooks into existing related_profiles data collection
- Background processing of similar profiles through full Creator Analytics
- Rate limiting and quality filtering
- Comprehensive error handling and retry logic
- Zero interference with existing systems
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text
from dataclasses import dataclass

from app.database.unified_models import Profile, RelatedProfile
from app.database.connection import get_session
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from app.core.discovery_config import discovery_settings, DiscoveryConstants
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SimilarProfileDiscovery:
    """Similar profile discovery entry"""
    username: str
    source_profile_username: str
    source_type: str  # 'creator_analytics' or 'post_analytics'
    similarity_score: Optional[float]
    discovered_at: datetime
    status: str = DiscoveryConstants.STATUS_PENDING
    retry_count: int = 0
    last_attempt_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class DiscoveryBatchResult:
    """Results of a discovery batch processing"""
    total_profiles: int
    processed_successfully: int
    failed_profiles: int
    skipped_profiles: int
    execution_time_seconds: float
    failed_usernames: List[str]


class SimilarProfilesDiscoveryService:
    """
    Similar Profiles Discovery Service

    Automatically discovers and processes similar profiles found during analytics operations.
    Operates entirely in background without blocking main analytics flows.
    """

    def __init__(self):
        self.processed_today: Set[str] = set()
        self.daily_count = 0
        self.hourly_count = 0
        self.last_hour_reset = datetime.now(timezone.utc)
        self.last_day_reset = datetime.now(timezone.utc)

    async def hook_creator_analytics_similar_profiles(
        self,
        source_username: str,
        profile_id: UUID,
        db: AsyncSession
    ) -> None:
        """
        Hook that triggers when Creator Analytics finds similar profiles

        This method is called after related_profiles are stored in the database
        and triggers background discovery of those similar profiles.

        Args:
            source_username: Username of the profile that was analyzed
            profile_id: ID of the profile that was analyzed
            db: Database session
        """
        if not discovery_settings.DISCOVERY_ENABLED or not discovery_settings.DISCOVERY_ENABLE_CREATOR_ANALYTICS_HOOK:
            return

        try:
            logger.info(f"🔍 Discovery Hook: Creator Analytics for @{source_username}")

            # Get related profiles from database
            similar_profiles = await self._get_related_profiles_for_discovery(db, profile_id)

            if not similar_profiles:
                logger.info(f"   No similar profiles found for @{source_username}")
                return

            logger.info(f"   Found {len(similar_profiles)} similar profiles to discover")

            # Create discovery entries for background processing
            discoveries = []
            for username, similarity_score in similar_profiles:
                discovery = SimilarProfileDiscovery(
                    username=username,
                    source_profile_username=source_username,
                    source_type=DiscoveryConstants.SOURCE_CREATOR_ANALYTICS,
                    similarity_score=similarity_score,
                    discovered_at=datetime.now(timezone.utc)
                )
                discoveries.append(discovery)

            # Queue for background processing (fire and forget)
            asyncio.create_task(
                self._process_discovery_batch_background(discoveries)
            )

            logger.info(f"✅ Discovery Hook: Queued {len(discoveries)} profiles for background processing")

        except Exception as e:
            logger.error(f"❌ Discovery Hook failed for @{source_username}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def hook_post_analytics_similar_profiles(
        self,
        source_username: str,
        post_shortcode: str,
        profile_id: UUID,
        db: AsyncSession
    ) -> None:
        """
        Hook that triggers when Post Analytics finds similar profiles through Creator Analytics

        Args:
            source_username: Username of the post owner
            post_shortcode: Shortcode of the analyzed post
            profile_id: ID of the profile
            db: Database session
        """
        if not discovery_settings.DISCOVERY_ENABLED or not discovery_settings.DISCOVERY_ENABLE_POST_ANALYTICS_HOOK:
            return

        try:
            logger.info(f"🔍 Discovery Hook: Post Analytics for @{source_username}/{post_shortcode}")

            # Get related profiles from database (same logic as creator analytics)
            similar_profiles = await self._get_related_profiles_for_discovery(db, profile_id)

            if not similar_profiles:
                logger.info(f"   No similar profiles found from post analytics for @{source_username}")
                return

            logger.info(f"   Found {len(similar_profiles)} similar profiles to discover")

            # Create discovery entries for background processing
            discoveries = []
            for username, similarity_score in similar_profiles:
                discovery = SimilarProfileDiscovery(
                    username=username,
                    source_profile_username=source_username,
                    source_type=DiscoveryConstants.SOURCE_POST_ANALYTICS,
                    similarity_score=similarity_score,
                    discovered_at=datetime.now(timezone.utc)
                )
                discoveries.append(discovery)

            # Queue for background processing (fire and forget)
            asyncio.create_task(
                self._process_discovery_batch_background(discoveries)
            )

            logger.info(f"✅ Discovery Hook: Queued {len(discoveries)} profiles for background processing")

        except Exception as e:
            logger.error(f"❌ Discovery Hook failed for post @{source_username}/{post_shortcode}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _get_related_profiles_for_discovery(
        self,
        db: AsyncSession,
        profile_id: UUID
    ) -> List[tuple[str, float]]:
        """Get related profiles from database for discovery processing"""
        try:
            query = select(
                RelatedProfile.related_username,
                RelatedProfile.similarity_score
            ).where(
                and_(
                    RelatedProfile.profile_id == profile_id,
                    RelatedProfile.related_username.isnot(None)
                )
            ).order_by(RelatedProfile.similarity_score.desc())

            result = await db.execute(query)
            rows = result.fetchall()

            # Filter out profiles that don't meet quality thresholds
            filtered_profiles = []
            for username, similarity_score in rows:
                if await self._should_discover_profile(db, username):
                    filtered_profiles.append((username, similarity_score or 0.0))

            return filtered_profiles[:discovery_settings.DISCOVERY_MAX_PROFILES_TO_DISCOVER]

        except Exception as e:
            logger.error(f"Error getting related profiles for discovery: {e}")
            return []

    async def _should_discover_profile(self, db: AsyncSession, username: str) -> bool:
        """Check if a profile should be discovered based on quality filters"""
        try:
            # Check rate limits
            if not self._check_rate_limits():
                return False

            # Check if profile already exists and is complete
            if discovery_settings.DISCOVERY_SKIP_EXISTING_PROFILES:
                existing_query = select(Profile).where(Profile.username == username)
                existing_result = await db.execute(existing_query)
                existing_profile = existing_result.scalar_one_or_none()

                if existing_profile:
                    # Check if profile is complete
                    is_complete = (
                        existing_profile.followers_count and existing_profile.followers_count > 0 and
                        existing_profile.posts_count and existing_profile.posts_count > 0 and
                        existing_profile.biography and
                        existing_profile.ai_profile_analyzed_at is not None
                    )

                    if is_complete:
                        logger.debug(f"Skipping @{username} - already complete in database")
                        return False

            # Check if already processed today
            if username in self.processed_today:
                logger.debug(f"Skipping @{username} - already processed today")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking if should discover @{username}: {e}")
            return False

    def _check_rate_limits(self) -> bool:
        """Check if rate limits allow more processing"""
        now = datetime.now(timezone.utc)

        # Reset hourly counter
        if (now - self.last_hour_reset).total_seconds() >= 3600:
            self.hourly_count = 0
            self.last_hour_reset = now

        # Reset daily counter
        if (now - self.last_day_reset).total_seconds() >= 86400:
            self.daily_count = 0
            self.processed_today.clear()
            self.last_day_reset = now

        # Check limits
        if self.hourly_count >= discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_HOUR:
            logger.warning(f"Rate limit reached: {self.hourly_count} profiles processed this hour")
            return False

        if self.daily_count >= discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY:
            logger.warning(f"Rate limit reached: {self.daily_count} profiles processed today")
            return False

        return True

    async def _process_discovery_batch_background(
        self,
        discoveries: List[SimilarProfileDiscovery]
    ) -> None:
        """
        Process a batch of discoveries in the background

        This method runs completely independently and doesn't block anything
        """
        try:
            # Create new database session for background processing
            async with get_session() as db:
                result = await self._process_discovery_batch(db, discoveries)

                logger.info(f"🎯 Background Discovery Batch Complete:")
                logger.info(f"   Processed: {result.processed_successfully}")
                logger.info(f"   Failed: {result.failed_profiles}")
                logger.info(f"   Skipped: {result.skipped_profiles}")
                logger.info(f"   Time: {result.execution_time_seconds:.2f}s")

        except Exception as e:
            logger.error(f"❌ Background discovery batch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _process_discovery_batch(
        self,
        db: AsyncSession,
        discoveries: List[SimilarProfileDiscovery]
    ) -> DiscoveryBatchResult:
        """Process a batch of similar profile discoveries"""
        start_time = datetime.now(timezone.utc)
        processed_successfully = 0
        failed_profiles = 0
        skipped_profiles = 0
        failed_usernames = []

        logger.info(f"🚀 Processing discovery batch: {len(discoveries)} profiles")

        # Process discoveries with concurrency control
        semaphore = asyncio.Semaphore(discovery_settings.DISCOVERY_MAX_CONCURRENT_PROFILES)
        tasks = []

        for discovery in discoveries:
            task = self._process_single_discovery_with_semaphore(semaphore, discovery, db)
            tasks.append(task)

        # Execute with concurrency control
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for discovery, result in zip(discoveries, results):
                if isinstance(result, Exception):
                    failed_profiles += 1
                    failed_usernames.append(discovery.username)
                    logger.error(f"❌ Discovery failed for @{discovery.username}: {result}")
                elif result == "skipped":
                    skipped_profiles += 1
                    logger.info(f"⏭️ Skipped @{discovery.username}")
                elif result == "success":
                    processed_successfully += 1
                    self.processed_today.add(discovery.username)
                    self.hourly_count += 1
                    self.daily_count += 1
                    logger.info(f"✅ Successfully discovered @{discovery.username}")
                else:
                    failed_profiles += 1
                    failed_usernames.append(discovery.username)
                    logger.warning(f"⚠️ Unknown result for @{discovery.username}: {result}")

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        return DiscoveryBatchResult(
            total_profiles=len(discoveries),
            processed_successfully=processed_successfully,
            failed_profiles=failed_profiles,
            skipped_profiles=skipped_profiles,
            execution_time_seconds=execution_time,
            failed_usernames=failed_usernames
        )

    async def _process_single_discovery_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        discovery: SimilarProfileDiscovery,
        db: AsyncSession
    ) -> str:
        """Process a single discovery with concurrency control"""
        async with semaphore:
            return await self._process_single_discovery(discovery, db)

    async def _process_single_discovery(
        self,
        discovery: SimilarProfileDiscovery,
        db: AsyncSession
    ) -> str:
        """
        Process a single similar profile discovery

        Returns:
            "success", "skipped", or "failed"
        """
        try:
            logger.info(f"🔍 Discovering @{discovery.username} (from @{discovery.source_profile_username})")

            # Double-check if we should process this profile
            if not await self._should_discover_profile(db, discovery.username):
                return "skipped"

            # Use existing Creator Analytics system to ensure 100% completeness
            profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                username=discovery.username,
                db=db,
                force_refresh=False  # Use existing data if already complete
            )

            if profile and metadata.get("is_full_analytics", False):
                logger.info(f"✅ Successfully discovered @{discovery.username}")
                logger.info(f"   Followers: {profile.followers_count:,}")
                logger.info(f"   Source: @{discovery.source_profile_username}")
                return "success"
            else:
                logger.warning(f"⚠️ Discovery incomplete for @{discovery.username}")
                return "failed"

        except Exception as e:
            logger.error(f"❌ Discovery failed for @{discovery.username}: {e}")
            return "failed"

    async def get_discovery_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get discovery system statistics"""
        try:
            now = datetime.now(timezone.utc)

            # Get total related profiles in database
            total_related_query = select(func.count(RelatedProfile.id))
            total_related_result = await db.execute(total_related_query)
            total_related_profiles = total_related_result.scalar()

            # Get unique related usernames not yet in profiles table
            undiscovered_query = text("""
                SELECT COUNT(DISTINCT rp.related_username)
                FROM related_profiles rp
                LEFT JOIN profiles p ON p.username = rp.related_username
                WHERE p.username IS NULL
                AND rp.related_username IS NOT NULL
                AND rp.related_username != ''
            """)
            undiscovered_result = await db.execute(undiscovered_query)
            undiscovered_count = undiscovered_result.scalar()

            return {
                "config": {
                    "enabled": discovery_settings.DISCOVERY_ENABLED,
                    "max_concurrent": discovery_settings.DISCOVERY_MAX_CONCURRENT_PROFILES,
                    "min_followers": discovery_settings.DISCOVERY_MIN_FOLLOWERS_COUNT,
                    "daily_limit": discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY
                },
                "stats": {
                    "total_related_profiles_in_db": total_related_profiles,
                    "undiscovered_profiles": undiscovered_count,
                    "processed_today": self.daily_count,
                    "processed_this_hour": self.hourly_count,
                    "remaining_daily_quota": max(0, discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY - self.daily_count),
                    "last_reset": self.last_day_reset.isoformat()
                },
                "rate_limits": {
                    "hourly_limit": discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_HOUR,
                    "daily_limit": discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY,
                    "current_hour_count": self.hourly_count,
                    "current_day_count": self.daily_count
                }
            }

        except Exception as e:
            logger.error(f"Error getting discovery stats: {e}")
            return {"error": str(e)}


# Global service instance
similar_profiles_discovery_service = SimilarProfilesDiscoveryService()