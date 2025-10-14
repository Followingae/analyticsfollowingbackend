"""
Profile Completeness Repair Service - Database Integrity Management

Standalone service to identify and repair incomplete profiles in the database.
A profile is INCOMPLETE if it's missing any critical data components:
- Basic data (followers_count, posts_count, biography)
- AI analysis (ai_profile_analyzed_at)
- Posts data (stored posts in database)

This service operates independently and uses existing CreatorAnalyticsTriggerService
to ensure zero interference with current analytics systems.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from dataclasses import dataclass

from app.database.unified_models import Profile, Post
from app.database.connection import get_session
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProfileCompletenessStatus:
    """Status of a profile's completeness"""
    profile_id: UUID
    username: str
    is_complete: bool
    missing_components: List[str]
    followers_count: Optional[int]
    posts_count: Optional[int]
    has_biography: bool
    has_ai_analysis: bool
    stored_posts_count: int


@dataclass
class RepairResults:
    """Results of a repair operation"""
    total_profiles_checked: int
    incomplete_profiles_found: int
    repair_attempted: int
    repair_successful: int
    repair_failed: int
    failed_profiles: List[Dict[str, Any]]
    execution_time_seconds: float


class ProfileCompletenessRepairService:
    """
    Profile Completeness Repair Service

    Identifies and repairs incomplete profiles in the database.
    Uses existing Creator Analytics system to ensure profiles are 100% complete.
    """

    def __init__(self):
        self.batch_size = 50  # Process profiles in batches
        self.max_concurrent_repairs = 3  # Limit concurrent repairs to avoid overload

    async def scan_profile_completeness(
        self,
        db: AsyncSession,
        limit: Optional[int] = None,
        username_filter: Optional[str] = None
    ) -> List[ProfileCompletenessStatus]:
        """
        Scan database for profile completeness status

        Args:
            db: Database session
            limit: Maximum profiles to check (None for all)
            username_filter: Filter by username pattern (SQL LIKE)

        Returns:
            List of profile completeness statuses
        """
        try:
            logger.info("🔍 Starting profile completeness scan...")

            # Build query for profiles with posts count
            query = text("""
                SELECT
                    p.id,
                    p.username,
                    p.followers_count,
                    p.posts_count,
                    p.biography,
                    p.ai_profile_analyzed_at,
                    COUNT(posts.id) as stored_posts_count
                FROM profiles p
                LEFT JOIN posts ON posts.profile_id = p.id
                WHERE 1=1
            """)

            # Add username filter if provided
            if username_filter:
                query = text(f"""
                    SELECT
                        p.id,
                        p.username,
                        p.followers_count,
                        p.posts_count,
                        p.biography,
                        p.ai_profile_analyzed_at,
                        COUNT(posts.id) as stored_posts_count
                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    WHERE p.username LIKE :username_filter
                """)

            query = text(str(query) + """
                GROUP BY p.id, p.username, p.followers_count, p.posts_count, p.biography, p.ai_profile_analyzed_at
                ORDER BY p.created_at DESC
            """)

            if limit:
                query = text(str(query) + f" LIMIT {limit}")

            # Execute query
            params = {}
            if username_filter:
                params['username_filter'] = f"%{username_filter}%"

            result = await db.execute(query, params)
            rows = result.fetchall()

            logger.info(f"📊 Found {len(rows)} profiles to analyze")

            # Analyze each profile for completeness
            statuses = []
            for row in rows:
                status = self._analyze_profile_completeness(row)
                statuses.append(status)

            # Summary stats
            incomplete_count = sum(1 for s in statuses if not s.is_complete)
            logger.info(f"📈 Completeness Summary:")
            logger.info(f"   Total Profiles: {len(statuses)}")
            logger.info(f"   Complete: {len(statuses) - incomplete_count}")
            logger.info(f"   Incomplete: {incomplete_count}")

            return statuses

        except Exception as e:
            logger.error(f"❌ Profile completeness scan failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _analyze_profile_completeness(self, row) -> ProfileCompletenessStatus:
        """Analyze a single profile row for completeness"""
        missing_components = []

        # Check basic data
        has_followers = row.followers_count and row.followers_count > 0
        has_posts_count = row.posts_count and row.posts_count > 0
        has_biography = bool(row.biography and row.biography.strip())

        if not has_followers:
            missing_components.append("followers_count")
        if not has_posts_count:
            missing_components.append("posts_count")
        if not has_biography:
            missing_components.append("biography")

        # Check AI analysis
        has_ai_analysis = row.ai_profile_analyzed_at is not None
        if not has_ai_analysis:
            missing_components.append("ai_analysis")

        # Check stored posts
        stored_posts_count = row.stored_posts_count or 0
        if stored_posts_count == 0:
            missing_components.append("stored_posts")

        is_complete = len(missing_components) == 0

        return ProfileCompletenessStatus(
            profile_id=row.id,
            username=row.username,
            is_complete=is_complete,
            missing_components=missing_components,
            followers_count=row.followers_count,
            posts_count=row.posts_count,
            has_biography=has_biography,
            has_ai_analysis=has_ai_analysis,
            stored_posts_count=stored_posts_count
        )

    async def repair_incomplete_profiles(
        self,
        db: AsyncSession,
        incomplete_profiles: List[ProfileCompletenessStatus],
        force_repair: bool = False,
        dry_run: bool = False
    ) -> RepairResults:
        """
        Repair incomplete profiles using Creator Analytics

        Args:
            db: Database session
            incomplete_profiles: List of incomplete profile statuses
            force_repair: Force repair even if profile seems partially complete
            dry_run: Only simulate repair without actual execution

        Returns:
            Repair operation results
        """
        start_time = datetime.now(timezone.utc)

        try:
            logger.info(f"🔧 Starting profile repair operation...")
            logger.info(f"   Profiles to repair: {len(incomplete_profiles)}")
            logger.info(f"   Dry run: {dry_run}")
            logger.info(f"   Force repair: {force_repair}")

            if dry_run:
                logger.info("🔍 DRY RUN - No actual repairs will be performed")

            repair_attempted = 0
            repair_successful = 0
            repair_failed = 0
            failed_profiles = []

            # Process profiles in batches with concurrency control
            for i in range(0, len(incomplete_profiles), self.batch_size):
                batch = incomplete_profiles[i:i + self.batch_size]
                logger.info(f"📦 Processing batch {i//self.batch_size + 1}: {len(batch)} profiles")

                # Process batch with concurrency limit
                semaphore = asyncio.Semaphore(self.max_concurrent_repairs)
                tasks = []

                for profile_status in batch:
                    if dry_run:
                        # Simulate repair for dry run
                        logger.info(f"🔍 [DRY RUN] Would repair @{profile_status.username} - Missing: {', '.join(profile_status.missing_components)}")
                        repair_attempted += 1
                        repair_successful += 1
                    else:
                        task = self._repair_single_profile_with_semaphore(
                            semaphore, profile_status, db
                        )
                        tasks.append(task)

                if not dry_run and tasks:
                    # Execute repairs with concurrency control
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for profile_status, result in zip(batch, results):
                        repair_attempted += 1

                        if isinstance(result, Exception):
                            repair_failed += 1
                            failed_profiles.append({
                                "username": profile_status.username,
                                "profile_id": str(profile_status.profile_id),
                                "error": str(result),
                                "missing_components": profile_status.missing_components
                            })
                            logger.error(f"❌ Repair failed for @{profile_status.username}: {result}")
                        elif result:
                            repair_successful += 1
                            logger.info(f"✅ Successfully repaired @{profile_status.username}")
                        else:
                            repair_failed += 1
                            failed_profiles.append({
                                "username": profile_status.username,
                                "profile_id": str(profile_status.profile_id),
                                "error": "Repair returned False",
                                "missing_components": profile_status.missing_components
                            })
                            logger.warning(f"⚠️ Repair returned False for @{profile_status.username}")

                # Small delay between batches to avoid overwhelming system
                if not dry_run and i + self.batch_size < len(incomplete_profiles):
                    await asyncio.sleep(2)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            results = RepairResults(
                total_profiles_checked=len(incomplete_profiles),
                incomplete_profiles_found=len(incomplete_profiles),
                repair_attempted=repair_attempted,
                repair_successful=repair_successful,
                repair_failed=repair_failed,
                failed_profiles=failed_profiles,
                execution_time_seconds=execution_time
            )

            logger.info(f"🎯 Repair Operation Complete:")
            logger.info(f"   Attempted: {repair_attempted}")
            logger.info(f"   Successful: {repair_successful}")
            logger.info(f"   Failed: {repair_failed}")
            logger.info(f"   Execution Time: {execution_time:.2f}s")

            return results

        except Exception as e:
            logger.error(f"❌ Profile repair operation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def _repair_single_profile_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        profile_status: ProfileCompletenessStatus,
        db: AsyncSession
    ) -> bool:
        """Repair a single profile with concurrency control"""
        async with semaphore:
            return await self._repair_single_profile(profile_status, db)

    async def _repair_single_profile(
        self,
        profile_status: ProfileCompletenessStatus,
        db: AsyncSession
    ) -> bool:
        """
        Repair a single incomplete profile using Creator Analytics

        Returns:
            True if repair was successful, False otherwise
        """
        try:
            logger.info(f"🔧 Repairing @{profile_status.username}...")
            logger.info(f"   Missing: {', '.join(profile_status.missing_components)}")

            # Use existing Creator Analytics system with force_refresh=True
            profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                username=profile_status.username,
                db=db,
                force_refresh=True  # Force fresh analytics to ensure completeness
            )

            if profile and metadata.get("is_full_analytics", False):
                logger.info(f"✅ Successfully repaired @{profile_status.username}")
                logger.info(f"   Followers: {profile.followers_count:,}")
                logger.info(f"   Posts: {profile.posts_count}")
                logger.info(f"   AI Analysis: {'✅' if profile.ai_profile_analyzed_at else '❌'}")
                return True
            else:
                logger.warning(f"⚠️ Repair incomplete for @{profile_status.username}")
                logger.warning(f"   Metadata: {metadata}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to repair @{profile_status.username}: {e}")
            return False

    async def run_full_repair_scan(
        self,
        db: AsyncSession,
        limit: Optional[int] = None,
        username_filter: Optional[str] = None,
        dry_run: bool = False,
        force_repair: bool = False
    ) -> Dict[str, Any]:
        """
        Run complete repair scan and repair operation

        Returns:
            Complete operation results including scan and repair data
        """
        try:
            logger.info("🚀 Starting FULL Profile Completeness Repair Operation")
            logger.info("=" * 60)

            # Step 1: Scan for incomplete profiles
            logger.info("📊 Step 1: Scanning profile completeness...")
            statuses = await self.scan_profile_completeness(
                db=db,
                limit=limit,
                username_filter=username_filter
            )

            # Filter for incomplete profiles only
            incomplete_profiles = [s for s in statuses if not s.is_complete]

            if not incomplete_profiles:
                logger.info("🎉 All profiles are complete! No repairs needed.")
                return {
                    "scan_results": {
                        "total_profiles": len(statuses),
                        "complete_profiles": len(statuses),
                        "incomplete_profiles": 0
                    },
                    "repair_results": None,
                    "message": "No incomplete profiles found"
                }

            # Step 2: Repair incomplete profiles
            logger.info(f"🔧 Step 2: Repairing {len(incomplete_profiles)} incomplete profiles...")
            repair_results = await self.repair_incomplete_profiles(
                db=db,
                incomplete_profiles=incomplete_profiles,
                force_repair=force_repair,
                dry_run=dry_run
            )

            logger.info("=" * 60)
            logger.info("✅ FULL Profile Completeness Repair Operation Complete")

            return {
                "scan_results": {
                    "total_profiles": len(statuses),
                    "complete_profiles": len(statuses) - len(incomplete_profiles),
                    "incomplete_profiles": len(incomplete_profiles)
                },
                "repair_results": repair_results,
                "incomplete_profiles_details": [
                    {
                        "username": p.username,
                        "missing_components": p.missing_components,
                        "followers_count": p.followers_count,
                        "stored_posts_count": p.stored_posts_count
                    }
                    for p in incomplete_profiles
                ]
            }

        except Exception as e:
            logger.error(f"❌ Full repair scan failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise


# Global service instance
profile_completeness_repair_service = ProfileCompletenessRepairService()