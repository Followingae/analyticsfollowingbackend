"""
Superadmin Analytics Completeness Service - Enterprise Grade Creator Analytics Management

Provides comprehensive analytics completeness management for superadmin users.
Identifies incomplete profiles and triggers full creator analytics pipeline to ensure
100% completeness matching the ola.alnomairi benchmark.

Key Features:
✅ Complete profile analysis against benchmark criteria
✅ Batch repair operations with rate limiting
✅ Real-time progress tracking and monitoring
✅ Integration with bulletproof creator search pipeline
✅ Comprehensive error handling and recovery
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, update, insert
from enum import Enum
import json

from app.database.unified_models import Profile, Post
from app.database.connection import get_session
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class CompletenessStatus(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    PROCESSING = "processing"
    FAILED = "failed"


class RepairStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProfileCompletenessAnalysis:
    """Detailed analysis of a profile's completeness status"""
    profile_id: UUID
    username: str
    is_complete: bool
    completeness_score: float  # 0.0 to 1.0
    missing_components: List[str]

    # Basic Data Components
    has_basic_data: bool
    followers_count: Optional[int]
    posts_count: Optional[int]
    has_biography: bool
    has_full_name: bool

    # Posts Data Components
    stored_posts_count: int
    has_minimum_posts: bool  # >= 12 posts

    # AI Analysis Components
    ai_analyzed_posts_count: int
    has_profile_ai_analysis: bool
    ai_profile_analyzed_at: Optional[datetime]
    has_ai_aggregation: bool

    # CDN Processing Components
    cdn_processed_posts_count: int
    has_cdn_thumbnails: bool  # >= 12 posts with CDN

    # Timestamps
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    analyzed_at: datetime


@dataclass
class BatchRepairOperation:
    """Batch repair operation tracking"""
    operation_id: UUID
    started_by: str  # Admin user email
    total_profiles: int
    completed_profiles: int
    failed_profiles: int
    status: RepairStatus
    error_details: Optional[Dict[str, Any]]
    started_at: datetime
    completed_at: Optional[datetime]
    estimated_completion: Optional[datetime]


@dataclass
class SystemCompletenessStats:
    """System-wide completeness statistics"""
    total_profiles: int
    complete_profiles: int
    incomplete_profiles: int
    completeness_percentage: float
    profiles_processing: int
    profiles_failed: int
    last_scan_at: Optional[datetime]
    avg_completeness_score: float


class SuperadminAnalyticsCompletenessService:
    """
    Superadmin Analytics Completeness Service

    Provides comprehensive analytics completeness management including:
    - Profile completeness analysis against benchmark criteria
    - Batch repair operations with bulletproof creator search
    - Real-time monitoring and progress tracking
    - System-wide statistics and health monitoring
    """

    def __init__(self):
        self.batch_size = 100  # Process profiles in batches
        self.max_concurrent_repairs = 5  # Limit concurrent repairs
        self.hourly_repair_limit = 100  # Max repairs per hour
        self.completeness_threshold = 1.0  # 100% complete required

    async def scan_all_profiles_completeness(
        self,
        db: AsyncSession,
        limit: Optional[int] = None,
        username_filter: Optional[str] = None,
        include_complete: bool = False
    ) -> Dict[str, Any]:
        """
        Scan ALL profiles for completeness against ola.alnomairi benchmark

        Returns comprehensive analysis of profile completeness across the system
        """
        try:
            start_time = datetime.now(timezone.utc)
            logger.info("🔍 Starting comprehensive profile completeness scan...")

            # Build comprehensive completeness query
            completeness_query = text("""
                WITH profile_completeness AS (
                    SELECT
                        p.id,
                        p.username,
                        p.full_name,
                        p.biography,
                        p.followers_count,
                        p.posts_count,
                        p.ai_profile_analyzed_at,
                        p.ai_content_distribution,
                        p.ai_language_distribution,
                        p.ai_content_quality_score,
                        p.created_at,
                        p.updated_at,

                        -- Posts data analysis
                        COUNT(posts.id) as stored_posts_count,
                        COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as ai_analyzed_posts_count,
                        COUNT(CASE WHEN posts.cdn_thumbnail_url IS NOT NULL THEN 1 END) as cdn_processed_posts_count,

                        -- Completeness criteria checks
                        CASE WHEN p.followers_count > 0 AND p.posts_count > 0 AND p.biography IS NOT NULL AND p.full_name IS NOT NULL THEN 1 ELSE 0 END as has_basic_data,
                        CASE WHEN COUNT(posts.id) >= 12 THEN 1 ELSE 0 END as has_minimum_posts,
                        CASE WHEN COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) >= 12 THEN 1 ELSE 0 END as has_ai_posts,
                        CASE WHEN p.ai_profile_analyzed_at IS NOT NULL THEN 1 ELSE 0 END as has_profile_ai,
                        CASE WHEN COUNT(CASE WHEN posts.cdn_thumbnail_url IS NOT NULL THEN 1 END) >= 12 THEN 1 ELSE 0 END as has_cdn_posts,
                        CASE WHEN p.ai_content_distribution IS NOT NULL AND p.ai_language_distribution IS NOT NULL THEN 1 ELSE 0 END as has_ai_aggregation

                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    WHERE 1=1
                        {username_filter_clause}
                    GROUP BY p.id, p.username, p.full_name, p.biography, p.followers_count, p.posts_count,
                             p.ai_profile_analyzed_at, p.ai_content_distribution, p.ai_language_distribution,
                             p.ai_content_quality_score, p.created_at, p.updated_at
                    {limit_clause}
                )
                SELECT
                    *,
                    -- Calculate completeness score (all 6 criteria must be met)
                    (has_basic_data + has_minimum_posts + has_ai_posts + has_profile_ai + has_cdn_posts + has_ai_aggregation) / 6.0 as completeness_score,
                    -- Determine if profile is complete (all criteria = 1)
                    CASE WHEN (has_basic_data + has_minimum_posts + has_ai_posts + has_profile_ai + has_cdn_posts + has_ai_aggregation) = 6 THEN 1 ELSE 0 END as is_complete
                FROM profile_completeness
                {complete_filter_clause}
                ORDER BY completeness_score ASC, followers_count DESC
            """.format(
                username_filter_clause=f"AND p.username ILIKE '%{username_filter}%'" if username_filter else "",
                limit_clause=f"LIMIT {limit}" if limit else "",
                complete_filter_clause="" if include_complete else "WHERE (has_basic_data + has_minimum_posts + has_ai_posts + has_profile_ai + has_cdn_posts + has_ai_aggregation) < 6"
            ))

            result = await db.execute(completeness_query)
            rows = result.fetchall()

            # Process results into structured data
            analyses = []
            for row in rows:
                # Determine missing components
                missing_components = []
                if not row.has_basic_data:
                    missing_components.append("basic_data")
                if not row.has_minimum_posts:
                    missing_components.append("minimum_posts")
                if not row.has_ai_posts:
                    missing_components.append("ai_analysis")
                if not row.has_profile_ai:
                    missing_components.append("profile_ai")
                if not row.has_cdn_posts:
                    missing_components.append("cdn_processing")
                if not row.has_ai_aggregation:
                    missing_components.append("ai_aggregation")

                analysis = ProfileCompletenessAnalysis(
                    profile_id=row.id,
                    username=row.username,
                    is_complete=bool(row.is_complete),
                    completeness_score=float(row.completeness_score),
                    missing_components=missing_components,
                    has_basic_data=bool(row.has_basic_data),
                    followers_count=row.followers_count,
                    posts_count=row.posts_count,
                    has_biography=bool(row.biography),
                    has_full_name=bool(row.full_name),
                    stored_posts_count=row.stored_posts_count,
                    has_minimum_posts=bool(row.has_minimum_posts),
                    ai_analyzed_posts_count=row.ai_analyzed_posts_count,
                    has_profile_ai_analysis=bool(row.has_profile_ai),
                    ai_profile_analyzed_at=row.ai_profile_analyzed_at,
                    has_ai_aggregation=bool(row.has_ai_aggregation),
                    cdn_processed_posts_count=row.cdn_processed_posts_count,
                    has_cdn_thumbnails=bool(row.has_cdn_posts),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    analyzed_at=datetime.now(timezone.utc)
                )
                analyses.append(analysis)

            # Calculate summary statistics
            total_profiles = len(analyses)
            complete_profiles = len([a for a in analyses if a.is_complete])
            incomplete_profiles = total_profiles - complete_profiles
            avg_score = sum(a.completeness_score for a in analyses) / total_profiles if total_profiles > 0 else 0.0

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            completion_pct = (complete_profiles/total_profiles*100) if total_profiles > 0 else 0.0
            logger.info(f"✅ Completeness scan complete: {total_profiles} profiles, {complete_profiles} complete ({completion_pct:.1f}%)")

            # Convert UUID objects to strings for JSON serialization
            def analysis_to_dict(analysis: ProfileCompletenessAnalysis) -> Dict[str, Any]:
                result = asdict(analysis)
                result["profile_id"] = str(analysis.profile_id)  # Convert UUID to string
                return result

            return {
                "success": True,
                "scan_timestamp": start_time.isoformat(),
                "execution_time_seconds": execution_time,
                "summary": {
                    "total_profiles": total_profiles,
                    "complete_profiles": complete_profiles,
                    "incomplete_profiles": incomplete_profiles,
                    "completeness_percentage": (complete_profiles / total_profiles * 100) if total_profiles > 0 else 0,
                    "average_completeness_score": avg_score
                },
                "profiles": [analysis_to_dict(analysis) for analysis in analyses],
                "incomplete_profiles": [analysis_to_dict(a) for a in analyses if not a.is_complete]
            }

        except Exception as e:
            import traceback
            logger.error(f"❌ Completeness scan failed: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            raise Exception(f"Profile completeness scan failed: {str(e)}")

    async def repair_incomplete_profiles(
        self,
        db: AsyncSession,
        admin_email: str,
        profile_ids: Optional[List[UUID]] = None,
        max_profiles: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Repair incomplete profiles using bulletproof creator search pipeline

        Args:
            db: Database session
            admin_email: Email of admin triggering repair
            profile_ids: Specific profile IDs to repair (None for all incomplete)
            max_profiles: Maximum profiles to repair in this operation
            dry_run: If True, only simulate repair without execution
        """
        try:
            start_time = datetime.now(timezone.utc)
            operation_id = uuid4()

            logger.info(f"🔧 Starting profile repair operation {operation_id} by {admin_email}")

            # Get incomplete profiles to repair
            if profile_ids:
                # Repair specific profiles
                profile_query = select(Profile).where(Profile.id.in_(profile_ids))
                result = await db.execute(profile_query)
                profiles_to_repair = result.scalars().all()
            else:
                # Get all incomplete profiles
                scan_result = await self.scan_all_profiles_completeness(
                    db=db,
                    include_complete=False,
                    limit=max_profiles
                )

                incomplete_profile_ids = [
                    UUID(p["profile_id"]) if isinstance(p["profile_id"], str) else p["profile_id"]
                    for p in scan_result["incomplete_profiles"]
                ]

                if not incomplete_profile_ids:
                    return {
                        "success": True,
                        "message": "No incomplete profiles found",
                        "operation_id": str(operation_id),
                        "profiles_repaired": 0
                    }

                profile_query = select(Profile).where(Profile.id.in_(incomplete_profile_ids))
                result = await db.execute(profile_query)
                profiles_to_repair = result.scalars().all()

            total_profiles = len(profiles_to_repair)

            if dry_run:
                logger.info(f"🔍 DRY RUN: Would repair {total_profiles} profiles")
                return {
                    "success": True,
                    "dry_run": True,
                    "operation_id": str(operation_id),
                    "profiles_to_repair": total_profiles,
                    "profiles": [{"username": p.username, "profile_id": str(p.id)} for p in profiles_to_repair]
                }

            # Create repair operation record
            await self._create_repair_operation_record(
                db=db,
                operation_id=operation_id,
                admin_email=admin_email,
                total_profiles=total_profiles
            )

            # Execute repairs with rate limiting
            successful_repairs = 0
            failed_repairs = 0
            repair_results = []

            # Process in batches with concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent_repairs)

            async def repair_single_profile(profile: Profile) -> Dict[str, Any]:
                async with semaphore:
                    try:
                        logger.info(f"🔄 Repairing profile @{profile.username} ({profile.id})")

                        # Use creator analytics trigger service for complete analytics
                        async with get_session() as repair_db:
                            repaired_profile, analytics_data = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                                username=profile.username,
                                db=repair_db,
                                force_refresh=True,  # Force complete re-analysis
                                is_background_discovery=True  # Mark as background analytics to prevent discovery loops
                            )

                        if repaired_profile and analytics_data.get("success", False):
                            return {
                                "profile_id": str(profile.id),
                                "username": profile.username,
                                "status": "success",
                                "message": "Profile repair completed successfully"
                            }
                        else:
                            return {
                                "profile_id": str(profile.id),
                                "username": profile.username,
                                "status": "failed",
                                "error": analytics_data.get("error", "Creator analytics failed")
                            }

                    except Exception as e:
                        logger.error(f"❌ Profile repair failed for @{profile.username}: {e}")
                        return {
                            "profile_id": str(profile.id),
                            "username": profile.username,
                            "status": "failed",
                            "error": str(e)
                        }

            # Execute repairs concurrently
            repair_tasks = [repair_single_profile(profile) for profile in profiles_to_repair]
            repair_results = await asyncio.gather(*repair_tasks, return_exceptions=True)

            # Process results
            for result in repair_results:
                if isinstance(result, Exception):
                    failed_repairs += 1
                    logger.error(f"❌ Repair task exception: {result}")
                elif result["status"] == "success":
                    successful_repairs += 1
                else:
                    failed_repairs += 1

            # Update repair operation record
            await self._update_repair_operation_record(
                db=db,
                operation_id=operation_id,
                status=RepairStatus.COMPLETED,
                completed_profiles=successful_repairs,
                failed_profiles=failed_repairs
            )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            logger.info(f"✅ Repair operation {operation_id} completed: {successful_repairs}/{total_profiles} successful")

            return {
                "success": True,
                "operation_id": str(operation_id),
                "execution_time_seconds": execution_time,
                "summary": {
                    "total_profiles": total_profiles,
                    "successful_repairs": successful_repairs,
                    "failed_repairs": failed_repairs,
                    "success_rate": (successful_repairs / total_profiles * 100) if total_profiles > 0 else 0
                },
                "repair_results": [r for r in repair_results if not isinstance(r, Exception)]
            }

        except Exception as e:
            logger.error(f"❌ Profile repair operation failed: {e}")
            # Update operation record with failure
            try:
                await self._update_repair_operation_record(
                    db=db,
                    operation_id=operation_id,
                    status=RepairStatus.FAILED,
                    error_details={"error": str(e)}
                )
            except:
                pass
            raise Exception(f"Profile repair operation failed: {str(e)}")

    async def get_completeness_dashboard(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for analytics completeness
        """
        try:
            logger.info("📊 Generating completeness dashboard...")

            # Get system-wide statistics
            stats_query = text("""
                WITH completeness_stats AS (
                    SELECT
                        COUNT(*) as total_profiles,
                        COUNT(CASE WHEN (
                            p.followers_count > 0 AND p.posts_count > 0 AND p.biography IS NOT NULL AND p.full_name IS NOT NULL AND
                            p.ai_profile_analyzed_at IS NOT NULL AND
                            p.ai_content_distribution IS NOT NULL AND
                            (SELECT COUNT(*) FROM posts WHERE profile_id = p.id) >= 12 AND
                            (SELECT COUNT(*) FROM posts WHERE profile_id = p.id AND ai_analyzed_at IS NOT NULL) >= 12 AND
                            (SELECT COUNT(*) FROM posts WHERE profile_id = p.id AND cdn_thumbnail_url IS NOT NULL) >= 12
                        ) THEN 1 END) as complete_profiles,
                        AVG(CASE WHEN p.followers_count > 0 THEN p.followers_count ELSE 0 END) as avg_followers,
                        MAX(p.updated_at) as last_profile_update
                    FROM profiles p
                ),
                recent_activity AS (
                    SELECT
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as profiles_created_24h,
                        COUNT(CASE WHEN updated_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as profiles_updated_24h
                    FROM profiles
                )
                SELECT
                    cs.*,
                    ra.*,
                    CASE WHEN cs.total_profiles > 0
                        THEN (cs.complete_profiles::float / cs.total_profiles * 100)
                        ELSE 0
                    END as completeness_percentage
                FROM completeness_stats cs, recent_activity ra
            """)

            result = await db.execute(stats_query)
            stats_row = result.fetchone()

            # Get recent repair operations
            repair_ops_query = text("""
                SELECT operation_id, started_by, total_profiles, completed_profiles,
                       failed_profiles, status, started_at, completed_at
                FROM superadmin_repair_operations
                ORDER BY started_at DESC
                LIMIT 10
            """)

            try:
                repair_result = await db.execute(repair_ops_query)
                recent_operations = [dict(row._mapping) for row in repair_result.fetchall()]
            except:
                # Table might not exist yet
                recent_operations = []

            # Get profiles by completeness score distribution
            distribution_query = text("""
                WITH profile_scores AS (
                    SELECT
                        p.username,
                        p.followers_count,
                        (
                            (CASE WHEN p.followers_count > 0 AND p.posts_count > 0 AND p.biography IS NOT NULL AND p.full_name IS NOT NULL THEN 1 ELSE 0 END) +
                            (CASE WHEN (SELECT COUNT(*) FROM posts WHERE profile_id = p.id) >= 12 THEN 1 ELSE 0 END) +
                            (CASE WHEN (SELECT COUNT(*) FROM posts WHERE profile_id = p.id AND ai_analyzed_at IS NOT NULL) >= 12 THEN 1 ELSE 0 END) +
                            (CASE WHEN p.ai_profile_analyzed_at IS NOT NULL THEN 1 ELSE 0 END) +
                            (CASE WHEN (SELECT COUNT(*) FROM posts WHERE profile_id = p.id AND cdn_thumbnail_url IS NOT NULL) >= 12 THEN 1 ELSE 0 END) +
                            (CASE WHEN p.ai_content_distribution IS NOT NULL THEN 1 ELSE 0 END)
                        ) / 6.0 as completeness_score
                    FROM profiles p
                )
                SELECT
                    CASE
                        WHEN completeness_score = 1.0 THEN 'Complete (100%)'
                        WHEN completeness_score >= 0.8 THEN 'Nearly Complete (80-99%)'
                        WHEN completeness_score >= 0.5 THEN 'Partially Complete (50-79%)'
                        WHEN completeness_score >= 0.2 THEN 'Minimal Data (20-49%)'
                        ELSE 'Incomplete (0-19%)'
                    END as completeness_category,
                    COUNT(*) as profile_count,
                    AVG(followers_count) as avg_followers
                FROM profile_scores
                GROUP BY completeness_category
                ORDER BY MIN(completeness_score) DESC
            """)

            distribution_result = await db.execute(distribution_query)
            distribution_data = [dict(row._mapping) for row in distribution_result.fetchall()]

            dashboard_data = {
                "success": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "system_stats": {
                    "total_profiles": stats_row.total_profiles,
                    "complete_profiles": stats_row.complete_profiles,
                    "incomplete_profiles": stats_row.total_profiles - stats_row.complete_profiles,
                    "completeness_percentage": float(stats_row.completeness_percentage or 0),
                    "avg_followers": float(stats_row.avg_followers or 0),
                    "last_profile_update": stats_row.last_profile_update.isoformat() if stats_row.last_profile_update else None,
                    "profiles_created_24h": stats_row.profiles_created_24h,
                    "profiles_updated_24h": stats_row.profiles_updated_24h
                },
                "completeness_distribution": distribution_data,
                "recent_repair_operations": recent_operations,
                "system_health": {
                    "status": "healthy" if stats_row.completeness_percentage > 80 else "needs_attention",
                    "recommendations": self._generate_health_recommendations(stats_row)
                }
            }

            return dashboard_data

        except Exception as e:
            logger.error(f"❌ Dashboard generation failed: {e}")
            raise Exception(f"Dashboard generation failed: {str(e)}")

    async def validate_single_profile(
        self,
        db: AsyncSession,
        username: str
    ) -> Dict[str, Any]:
        """
        Validate completeness of a single profile with detailed analysis
        """
        try:
            logger.info(f"🔍 Validating profile completeness for @{username}")

            # Get single profile analysis
            scan_result = await self.scan_all_profiles_completeness(
                db=db,
                username_filter=username,
                include_complete=True,
                limit=1
            )

            if not scan_result["profiles"]:
                raise Exception(f"Profile @{username} not found in database")

            profile_analysis = scan_result["profiles"][0]

            # Get detailed post analysis
            posts_query = text("""
                SELECT
                    COUNT(*) as total_posts,
                    COUNT(CASE WHEN ai_analyzed_at IS NOT NULL THEN 1 END) as ai_analyzed_posts,
                    COUNT(CASE WHEN cdn_thumbnail_url IS NOT NULL THEN 1 END) as cdn_processed_posts,
                    MIN(created_at) as oldest_post,
                    MAX(created_at) as newest_post,
                    AVG(likes_count) as avg_likes,
                    AVG(comments_count) as avg_comments
                FROM posts p
                JOIN profiles pr ON pr.id = p.profile_id
                WHERE pr.username = :username
            """)

            posts_result = await db.execute(posts_query, {"username": username})
            posts_data = posts_result.fetchone()

            return {
                "success": True,
                "username": username,
                "profile_analysis": profile_analysis,
                "posts_analysis": {
                    "total_posts": posts_data.total_posts,
                    "ai_analyzed_posts": posts_data.ai_analyzed_posts,
                    "cdn_processed_posts": posts_data.cdn_processed_posts,
                    "oldest_post": posts_data.oldest_post.isoformat() if posts_data.oldest_post else None,
                    "newest_post": posts_data.newest_post.isoformat() if posts_data.newest_post else None,
                    "avg_likes": float(posts_data.avg_likes or 0),
                    "avg_comments": float(posts_data.avg_comments or 0)
                },
                "recommendations": self._generate_profile_recommendations(profile_analysis),
                "validated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Profile validation failed for @{username}: {e}")
            raise Exception(f"Profile validation failed: {str(e)}")

    # Helper Methods

    async def _create_repair_operation_record(
        self,
        db: AsyncSession,
        operation_id: UUID,
        admin_email: str,
        total_profiles: int
    ):
        """Create repair operation tracking record"""
        try:
            insert_query = text("""
                INSERT INTO superadmin_repair_operations
                (operation_id, started_by, total_profiles, completed_profiles, failed_profiles,
                 status, started_at, estimated_completion)
                VALUES
                (:operation_id, :started_by, :total_profiles, 0, 0,
                 :status, :started_at, :estimated_completion)
            """)

            estimated_completion = datetime.now(timezone.utc) + timedelta(
                minutes=total_profiles * 3  # Estimate 3 minutes per profile
            )

            await db.execute(insert_query, {
                "operation_id": str(operation_id),
                "started_by": admin_email,
                "total_profiles": total_profiles,
                "status": RepairStatus.PROCESSING.value,
                "started_at": datetime.now(timezone.utc),
                "estimated_completion": estimated_completion
            })
            await db.commit()

        except Exception as e:
            logger.error(f"Failed to create repair operation record: {e}")
            # Continue without tracking if table doesn't exist
            pass

    async def _update_repair_operation_record(
        self,
        db: AsyncSession,
        operation_id: UUID,
        status: RepairStatus,
        completed_profiles: int = 0,
        failed_profiles: int = 0,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """Update repair operation tracking record"""
        try:
            update_query = text("""
                UPDATE superadmin_repair_operations
                SET status = :status,
                    completed_profiles = :completed_profiles,
                    failed_profiles = :failed_profiles,
                    completed_at = :completed_at,
                    error_details = :error_details
                WHERE operation_id = :operation_id
            """)

            await db.execute(update_query, {
                "operation_id": str(operation_id),
                "status": status.value,
                "completed_profiles": completed_profiles,
                "failed_profiles": failed_profiles,
                "completed_at": datetime.now(timezone.utc) if status in [RepairStatus.COMPLETED, RepairStatus.FAILED] else None,
                "error_details": json.dumps(error_details) if error_details else None
            })
            await db.commit()

        except Exception as e:
            logger.error(f"Failed to update repair operation record: {e}")
            # Continue without tracking if table doesn't exist
            pass

    def _generate_health_recommendations(self, stats_row) -> List[str]:
        """Generate system health recommendations"""
        recommendations = []

        completeness_pct = float(stats_row.completeness_percentage or 0)

        if completeness_pct < 50:
            recommendations.append("URGENT: Less than 50% of profiles are complete. Run mass repair operation.")
        elif completeness_pct < 80:
            recommendations.append("ATTENTION: Profile completeness below 80%. Consider repair operation.")

        if stats_row.profiles_updated_24h < 5:
            recommendations.append("Low activity: Consider running discovery to find new profiles.")

        if not recommendations:
            recommendations.append("System healthy: All metrics within acceptable ranges.")

        return recommendations

    def _generate_profile_recommendations(self, profile_analysis: Dict[str, Any]) -> List[str]:
        """Generate profile-specific recommendations"""
        recommendations = []

        missing = profile_analysis.get("missing_components", [])

        if "basic_data" in missing:
            recommendations.append("Profile needs basic data refresh from Instagram API")
        if "minimum_posts" in missing:
            recommendations.append("Profile needs more posts data (minimum 12 required)")
        if "ai_analysis" in missing:
            recommendations.append("Posts need AI analysis processing")
        if "profile_ai" in missing:
            recommendations.append("Profile-level AI analysis required")
        if "cdn_processing" in missing:
            recommendations.append("Posts need CDN thumbnail processing")
        if "ai_aggregation" in missing:
            recommendations.append("Profile needs AI aggregation data")

        if not missing:
            recommendations.append("Profile is 100% complete - no action needed")

        return recommendations


# Global service instance
superadmin_analytics_completeness_service = SuperadminAnalyticsCompletenessService()