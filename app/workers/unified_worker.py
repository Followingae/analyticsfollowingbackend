"""
Unified Background Worker - Industry Standard Implementation
Processes jobs from fast handoff API with complete isolation and reliability
"""
import os
import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from celery import Celery
from sqlalchemy import text

from app.core.job_queue import JobStatus
from app.database.optimized_pools import optimized_pools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

# Redis configuration for Celery
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')

# Create Celery app with optimized configuration
celery_app = Celery(
    'unified_worker',
    broker=redis_url,
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=['app.workers.unified_worker']
)

# Celery configuration optimized for background processing
celery_app.conf.update(
    # Task routing for different queue types
    task_routes={
        'app.workers.unified_worker.process_profile_analysis': {'queue': 'high_priority'},
        'app.workers.unified_worker.process_profile_analysis_background': {'queue': 'normal_priority'},
        'app.workers.unified_worker.process_post_analysis': {'queue': 'post_analytics'},
        'app.workers.unified_worker.process_batch_post_analysis': {'queue': 'bulk_processing'},
        'app.workers.unified_worker.process_bulk_analysis': {'queue': 'bulk_processing'},
        'app.workers.unified_worker.process_creator_search': {'queue': 'high_priority'},
        'app.workers.unified_worker.process_discovery_unlock': {'queue': 'high_priority'},
        'app.workers.unified_worker.process_bulk_unlock': {'queue': 'bulk_processing'},
        'app.workers.unified_worker.process_campaign_export': {'queue': 'bulk_processing'},
        'app.workers.unified_worker.process_post_analytics_campaign': {'queue': 'post_analytics'},
    },

    # Worker optimization
    worker_prefetch_multiplier=1,  # Prevent worker overload
    worker_max_tasks_per_child=100,  # Restart workers periodically
    task_acks_late=True,  # Acknowledge only after completion
    worker_disable_rate_limits=False,

    # Task configuration
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_expires=3600,  # 1 hour

    # Reliability settings
    task_reject_on_worker_lost=True,
    task_ignore_result=False,

    # Queue configuration
    task_default_queue='normal_priority',
    task_default_exchange='tasks',
    task_default_exchange_type='direct',
    task_default_routing_key='normal_priority',

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# ============================================================================
# JOB PROCESSING INFRASTRUCTURE
# ============================================================================

class JobProcessor:
    """Base class for job processing with reliability patterns"""

    def __init__(self):
        # Services will be imported dynamically when needed to avoid import errors
        self._analytics_service = None
        self._post_service = None
        self._credit_service = None

    @property
    def analytics_service(self):
        if self._analytics_service is None:
            from app.services.creator_analytics_trigger_service import CreatorAnalyticsTriggerService
            self._analytics_service = CreatorAnalyticsTriggerService()
        return self._analytics_service

    @property
    def post_service(self):
        if self._post_service is None:
            from app.services.post_analytics_service import PostAnalyticsService
            self._post_service = PostAnalyticsService()
        return self._post_service

    @property
    def credit_service(self):
        if self._credit_service is None:
            from app.services.credit_wallet_service import CreditWalletService
            self._credit_service = CreditWalletService()
        return self._credit_service

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress_percent: Optional[int] = None,
        progress_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update job status in database"""
        try:
            async with optimized_pools.get_background_session() as session:
                update_data = {
                    'job_id': job_id,
                    'status': status.value,
                    'updated_at': datetime.now(timezone.utc)
                }

                if progress_percent is not None:
                    update_data['progress_percent'] = progress_percent
                if progress_message:
                    update_data['progress_message'] = progress_message
                if result:
                    update_data['result'] = json.dumps(result)
                if error_details:
                    update_data['error_details'] = json.dumps(error_details)
                if status == JobStatus.PROCESSING:
                    update_data['started_at'] = datetime.now(timezone.utc)
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    update_data['completed_at'] = datetime.now(timezone.utc)

                # Build dynamic UPDATE query
                set_clause = ', '.join([f"{key} = :{key}" for key in update_data.keys() if key != 'job_id'])

                await session.execute(text(f"""
                    UPDATE job_queue SET {set_clause}
                    WHERE id = :job_id
                """).execution_options(prepare=False), update_data)

                await session.commit()
                logger.info(f"Updated job {job_id} status to {status.value}")

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")

    async def create_completion_notification(
        self,
        job_id: str,
        job_type: str,
        user_id: str,
        result: dict
    ) -> None:
        """Create a server notification when a job completes successfully."""
        try:
            from app.services.notification_service import NotificationService
            from uuid import UUID as _UUID

            # Resolve user email from auth.users
            user_email = None
            async with optimized_pools.get_background_session() as db:
                email_r = await db.execute(
                    text("SELECT email FROM auth.users WHERE id = CAST(:uid AS uuid)")
                    .execution_options(prepare=False),
                    {'uid': user_id}
                )
                row = email_r.fetchone()
                user_email = row[0] if row else 'unknown@user'

            # Determine notification title/message based on job type
            username = result.get('username') or result.get('profile', {}).get('username', '')

            if job_type in ('creator_search', 'profile_analysis'):
                async with optimized_pools.get_background_session() as db:
                    await NotificationService.notify_analytics_completed(
                        db, _UUID(user_id), user_email, username
                    )
            elif job_type in ('post_analysis', 'batch_post_analysis'):
                title = "Post analytics ready"
                posts_count = result.get('data', {}).get('summary', {}).get('successful', '')
                message = f"Post analytics have been processed{f' ({posts_count} posts)' if posts_count else ''}."
                async with optimized_pools.get_background_session() as db:
                    await NotificationService.create(
                        db,
                        user_id=_UUID(user_id),
                        user_email=user_email,
                        notification_type="analytics_completed",
                        title=title,
                        message=message,
                        action_url=f"/creator-analytics/{username}" if username else None,
                        reference_type="post_analytics",
                        metadata={"username": username, "job_type": job_type},
                    )
            elif job_type == 'discovery_unlock':
                title = f"Profile unlocked: @{username}" if username else "Profile unlocked"
                async with optimized_pools.get_background_session() as db:
                    await NotificationService.create(
                        db,
                        user_id=_UUID(user_id),
                        user_email=user_email,
                        notification_type="analytics_completed",
                        title=title,
                        message=f"@{username} has been unlocked and analytics are ready to view.",
                        action_url=f"/creator-analytics/{username}" if username else None,
                        reference_type="profile",
                        metadata={"username": username, "job_type": job_type},
                    )
            elif job_type in ('bulk_analysis', 'bulk_unlock'):
                count = result.get('successful_analyses') or result.get('successful_unlocks') or 0
                title = f"Bulk {'analysis' if job_type == 'bulk_analysis' else 'unlock'} complete: {count} profiles"
                async with optimized_pools.get_background_session() as db:
                    await NotificationService.create(
                        db,
                        user_id=_UUID(user_id),
                        user_email=user_email,
                        notification_type="analytics_completed",
                        title=title,
                        message=f"Bulk operation completed with {count} successful profiles.",
                        reference_type="bulk_operation",
                        metadata={"count": count, "job_type": job_type},
                    )
            else:
                async with optimized_pools.get_background_session() as db:
                    await NotificationService.create(
                        db,
                        user_id=_UUID(user_id),
                        user_email=user_email,
                        notification_type="analytics_completed",
                        title="Background task completed",
                        message=f"Your {job_type.replace('_', ' ')} job has finished.",
                        metadata={"job_type": job_type},
                    )

            logger.info(f"[NOTIFICATION] Created completion notification for job {job_id} ({job_type})")

        except Exception as e:
            # Never let notification failure break job completion
            logger.warning(f"[NOTIFICATION] Failed to create notification for job {job_id}: {e}")

    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details from database"""
        try:
            async with optimized_pools.get_background_session() as session:
                result = await session.execute(text("""
                    SELECT id, user_id, job_type, params, status, priority, created_at
                    FROM job_queue WHERE id = :job_id
                """).execution_options(prepare=False), {'job_id': job_id})

                job_data = result.fetchone()
                if not job_data:
                    return None

                return {
                    'id': job_data.id,
                    'user_id': job_data.user_id,
                    'job_type': job_data.job_type,
                    'params': job_data.params if isinstance(job_data.params, dict) else (json.loads(job_data.params) if job_data.params else {}),
                    'status': job_data.status,
                    'priority': job_data.priority,
                    'created_at': job_data.created_at
                }

        except Exception as e:
            logger.error(f"Failed to get job details for {job_id}: {e}")
            return None

    async def deduct_credits(self, user_id: str, amount: int, description: str) -> bool:
        """Deduct credits from user wallet"""
        try:
            return await self.credit_service.spend_credits(
                user_id=user_id,
                amount=amount,
                description=description
            )
        except Exception as e:
            logger.error(f"Failed to deduct {amount} credits from user {user_id}: {e}")
            return False

# Global job processor instance
job_processor = JobProcessor()

# ============================================================================
# CELERY TASKS - PROFILE ANALYSIS
# ============================================================================

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_profile_analysis(self, job_id: str):
    """Process profile analysis job with comprehensive error handling"""

    try:
        logger.info(f"Starting profile analysis job {job_id}")

        # Run async processing in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_profile_analysis_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Profile analysis job {job_id} failed: {e}")

        # Update job status to failed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'task_retry': self.request.retries}
                )
            )
        finally:
            loop.close()

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = min(300, 60 * (2 ** self.request.retries))  # Max 5 minutes
            logger.info(f"Retrying job {job_id} in {retry_delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay)

        raise

async def _process_profile_analysis_async(job_id: str) -> Dict[str, Any]:
    """Async implementation of profile analysis"""

    # Get job details
    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    username = params.get('username')
    credit_cost = params.get('credit_cost', 25)
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    logger.info(f"Processing profile analysis for {username} (job: {job_id})")

    # Update status to processing
    await job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting analysis for {username}"
    )

    try:
        # STEP 1: Deduct credits (fail fast if insufficient)
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=10,
            progress_message="Validating credits"
        )

        credit_deducted = await job_processor.deduct_credits(
            user_id,
            credit_cost,
            f"Profile analysis for {username}"
        )

        if not credit_deducted:
            raise Exception("Failed to deduct credits - insufficient balance")

        # STEP 2: Run comprehensive analysis
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=20,
            progress_message="Triggering comprehensive analytics"
        )

        # Check if this is a repair operation to prevent recursive discovery
        is_repair = params.get('repair_operation', False)
        is_admin_operation = params.get('operation_id') is not None

        # Get database session for the analytics call
        async with optimized_pools.get_background_session() as db:
            profile, analytics_result = await job_processor.analytics_service.trigger_full_creator_analytics(
                username=username,
                db=db,
                force_refresh=True,
                is_background_discovery=(is_repair or is_admin_operation)  # PREVENT RECURSIVE DISCOVERY for admin operations
            )

        if not analytics_result.get('is_full_analytics'):
            raise Exception(f"Analytics failed: {analytics_result.get('error', 'Incomplete analytics')}")

        # STEP 3: Wait for completion with progress updates
        profile_id = profile.id if profile else None
        completion_result = await _wait_for_analytics_completion(
            job_id, profile_id, username, progress_start=30
        )

        # STEP 4: Prepare final result
        final_result = {
            'profile_id': profile_id,
            'username': username,
            'analytics_completed': True,
            'credit_cost': credit_cost,
            'completion_time': datetime.now(timezone.utc).isoformat(),
            **completion_result
        }

        # Update job as completed
        await job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Analysis completed successfully",
            result=final_result
        )

        # Notify user of completion
        await job_processor.create_completion_notification(
            job_id, 'profile_analysis', user_id, final_result
        )

        logger.info(f"Profile analysis completed for {username} (job: {job_id})")
        return final_result

    except Exception as e:
        logger.error(f"Profile analysis failed for {username}: {e}")

        # Refund credits on failure
        try:
            await job_processor.credit_service.add_credits(
                user_id,
                credit_cost,
                f"Refund for failed analysis of {username}"
            )
        except Exception as refund_error:
            logger.error(f"Failed to refund credits: {refund_error}")

        # Update job as failed
        await job_processor.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_details={
                'error': str(e),
                'username': username,
                'credits_refunded': True
            }
        )

        raise

async def _wait_for_analytics_completion(
    job_id: str,
    profile_id: str,
    username: str,
    progress_start: int = 30,
    max_wait_seconds: int = 300
) -> Dict[str, Any]:
    """Wait for analytics completion with progress updates"""

    start_time = datetime.now(timezone.utc)
    last_progress = progress_start

    while (datetime.now(timezone.utc) - start_time).total_seconds() < max_wait_seconds:
        try:
            # Check completion status
            async with optimized_pools.get_background_session() as session:
                result = await session.execute(text("""
                    SELECT
                        ai_profile_analyzed_at,
                        posts_count,
                        (SELECT COUNT(*) FROM posts WHERE profile_id = p.id AND ai_analyzed_at IS NOT NULL) as ai_posts_count
                    FROM profiles p WHERE p.id = :profile_id
                """).execution_options(prepare=False), {'profile_id': profile_id})

                profile_data = result.fetchone()

            if profile_data and profile_data.ai_profile_analyzed_at:
                # Analytics completed
                return {
                    'ai_posts_analyzed': profile_data.ai_posts_count,
                    'total_posts': profile_data.posts_count,
                    'analysis_completion_time': profile_data.ai_profile_analyzed_at.isoformat()
                }

            # Update progress based on elapsed time
            elapsed_percent = min(60, int((datetime.now(timezone.utc) - start_time).total_seconds() / max_wait_seconds * 70))
            current_progress = progress_start + elapsed_percent

            if current_progress > last_progress + 5:  # Update every 5% progress
                await job_processor.update_job_status(
                    job_id,
                    JobStatus.PROCESSING,
                    progress_percent=current_progress,
                    progress_message=f"Processing {username} - AI analysis in progress"
                )
                last_progress = current_progress

            # Wait before next check
            await asyncio.sleep(10)

        except Exception as e:
            logger.warning(f"Error checking analytics completion: {e}")
            await asyncio.sleep(5)

    # Timeout reached
    raise Exception(f"Analytics completion timeout for {username} after {max_wait_seconds} seconds")

# ============================================================================
# IMD CREATOR ANALYTICS (auto-triggered on influencer add)
# ============================================================================

async def _update_imd_progress(
    influencer_db_id: str,
    status: str,
    progress: int,
    message: Optional[str] = None,
    error: Optional[str] = None
):
    """Mirror job progress to the IMD record for real-time frontend polling."""
    try:
        async with optimized_pools.get_background_session() as session:
            await session.execute(
                text("""
                    UPDATE influencer_database
                    SET analytics_status = :status,
                        analytics_progress = :progress,
                        analytics_progress_message = :message,
                        analytics_error = :error,
                        updated_at = NOW()
                    WHERE id = CAST(:id AS uuid)
                """).execution_options(prepare=False),
                {"status": status, "progress": progress, "message": message, "error": error, "id": influencer_db_id}
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update IMD progress for {influencer_db_id}: {e}")


async def _sync_analytics_to_imd(influencer_db_id: str, username: str):
    """After analytics complete, copy profile data into the IMD record."""
    try:
        async with optimized_pools.get_background_session() as session:
            # Get profile data
            profile_result = await session.execute(
                text("""
                    SELECT
                        p.full_name, p.biography,
                        COALESCE(p.cdn_avatar_url, p.profile_pic_url_hd, p.profile_pic_url) AS profile_image_url,
                        p.is_verified, p.is_private,
                        p.followers_count, p.following_count, p.posts_count,
                        p.engagement_rate, p.category,
                        p.ai_avg_sentiment_score, p.ai_top_3_categories,
                        p.ai_content_distribution,
                        p.ai_language_distribution, p.ai_audience_quality,
                        p.ai_content_quality_score
                    FROM profiles p WHERE p.username = :u
                """).execution_options(prepare=False),
                {"u": username}
            )
            profile = profile_result.mappings().fetchone()
            if not profile:
                logger.warning(f"No profile found for @{username} after analytics")
                return

            profile = dict(profile)

            # Calculate post averages
            stats_result = await session.execute(
                text("""
                    SELECT
                        CAST(COALESCE(AVG(likes_count), 0) AS bigint) AS avg_likes,
                        CAST(COALESCE(AVG(comments_count), 0) AS bigint) AS avg_comments,
                        CAST(COALESCE(AVG(CASE WHEN is_video THEN video_view_count ELSE 0 END), 0) AS bigint) AS avg_views
                    FROM posts WHERE profile_id = (SELECT id FROM profiles WHERE username = :u)
                """).execution_options(prepare=False),
                {"u": username}
            )
            stats = stats_result.mappings().fetchone()

            # Map AI fields — derive categories from ai_content_distribution (always populated)
            ai_categories = []
            categories = []
            content_dist = profile.get("ai_content_distribution")
            if content_dist and isinstance(content_dist, dict):
                # Sort by percentage descending, take top categories
                sorted_cats = sorted(content_dist.items(), key=lambda x: x[1], reverse=True)
                ai_categories = [cat for cat, _ in sorted_cats if cat != "general"]
                categories = ai_categories[:3]
            elif profile.get("category"):
                categories = [profile["category"]]

            aq = profile.get("ai_audience_quality")
            audience_quality_score = aq.get("authenticity_score") if aq and isinstance(aq, dict) else None

            lang_dist = profile.get("ai_language_distribution")

            # Update IMD record with synced data
            await session.execute(
                text("""
                    UPDATE influencer_database SET
                        full_name = :full_name,
                        biography = :biography,
                        profile_image_url = :profile_image_url,
                        is_verified = :is_verified,
                        is_private = :is_private,
                        followers_count = :followers_count,
                        following_count = :following_count,
                        posts_count = :posts_count,
                        engagement_rate = :engagement_rate,
                        avg_likes = :avg_likes,
                        avg_comments = :avg_comments,
                        avg_views = :avg_views,
                        categories = CAST(:categories AS text[]),
                        ai_content_categories = CAST(:ai_content_categories AS text[]),
                        ai_sentiment_score = :ai_sentiment_score,
                        ai_audience_quality_score = :ai_audience_quality_score,
                        language_distribution = CAST(:language_distribution AS jsonb),
                        analytics_status = 'completed',
                        analytics_progress = 100,
                        analytics_progress_message = 'Analytics complete',
                        analytics_completed_at = NOW(),
                        last_analytics_refresh = NOW(),
                        updated_at = NOW()
                    WHERE id = CAST(:id AS uuid)
                """).execution_options(prepare=False),
                {
                    "id": influencer_db_id,
                    "full_name": profile.get("full_name"),
                    "biography": profile.get("biography"),
                    "profile_image_url": profile.get("profile_image_url"),
                    "is_verified": profile.get("is_verified", False),
                    "is_private": profile.get("is_private", False),
                    "followers_count": profile.get("followers_count", 0),
                    "following_count": profile.get("following_count", 0),
                    "posts_count": profile.get("posts_count", 0),
                    "engagement_rate": profile.get("engagement_rate", 0),
                    "avg_likes": stats["avg_likes"] if stats else 0,
                    "avg_comments": stats["avg_comments"] if stats else 0,
                    "avg_views": stats["avg_views"] if stats else 0,
                    "categories": categories,
                    "ai_content_categories": ai_categories,
                    "ai_sentiment_score": profile.get("ai_avg_sentiment_score"),
                    "ai_audience_quality_score": audience_quality_score,
                    "language_distribution": json.dumps(lang_dist) if lang_dist else None,
                }
            )
            await session.commit()
            logger.info(f"Synced analytics data to IMD record for @{username}")

    except Exception as e:
        logger.error(f"Failed to sync analytics to IMD for @{username}: {e}")
        raise


async def _process_imd_analytics_async(job_id: str) -> Dict[str, Any]:
    """
    Process IMD creator analytics job.
    Uses the SAME pipeline as _process_creator_search_async:
      1. Fetch from Apify
      2. Store profile + posts
      3. Await CDN + AI pipeline (NOT fire-and-forget)
      4. Sync results to influencer_database record
    No credit deduction (admin operation).
    Mirrors progress to influencer_database record for real-time polling.
    """
    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    username = params.get('username')
    influencer_db_id = params.get('influencer_db_id')

    logger.info(f"[IMD-ANALYTICS] Starting analytics for @{username} (job: {job_id}, imd: {influencer_db_id})")

    await job_processor.update_job_status(
        job_id, JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting analytics for @{username}"
    )
    await _update_imd_progress(influencer_db_id, 'processing', 0, "Starting analytics...")

    try:
        # STEP 1: Fetch from Apify (same as creator search)
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=10,
            progress_message=f"Fetching Instagram data for @{username}"
        )
        await _update_imd_progress(influencer_db_id, 'processing', 10, "Fetching from Instagram...")

        from app.scrapers.apify_instagram_client import ApifyInstagramClient
        from app.core.config import settings

        async with ApifyInstagramClient(settings.APIFY_API_TOKEN) as apify_client:
            apify_data = await apify_client.get_instagram_profile_comprehensive(username)

        if not apify_data:
            raise Exception(f"Apify returned no data for @{username}")

        # STEP 2: Store profile + posts (same as creator search)
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=25,
            progress_message=f"Storing profile data for @{username}"
        )
        await _update_imd_progress(influencer_db_id, 'processing', 25, "Storing profile data...")

        from app.database.comprehensive_service import ComprehensiveDataService
        comprehensive_service = ComprehensiveDataService()

        async with optimized_pools.get_background_session() as db:
            profile, is_new = await comprehensive_service.store_complete_profile(
                db, username, apify_data
            )
            await db.commit()
            profile_id = str(profile.id)

        logger.info(f"[IMD-ANALYTICS] Profile stored: {profile_id} (new: {is_new})")

        # STEP 3: Run CDN + AI pipeline — AWAIT it (same as creator search)
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=35,
            progress_message=f"Running CDN + AI pipeline for @{username}"
        )
        await _update_imd_progress(influencer_db_id, 'processing', 35, "Processing CDN + AI analysis...")

        from app.services.unified_background_processor import unified_background_processor

        pipeline_results = await unified_background_processor.process_profile_complete_pipeline(
            profile_id=profile_id,
            username=username
        )

        if not pipeline_results.get('overall_success'):
            logger.warning(f"[IMD-ANALYTICS] Pipeline completed with issues for @{username}: {pipeline_results.get('errors', [])}")

        # STEP 4: Sync analytics data to IMD record
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=90,
            progress_message=f"Syncing data to database for @{username}"
        )
        await _update_imd_progress(influencer_db_id, 'processing', 90, "Syncing data to database...")
        await _sync_analytics_to_imd(influencer_db_id, username)

        # STEP 5: Mark job completed
        final_result = {
            'username': username,
            'influencer_db_id': influencer_db_id,
            'analytics_completed': True,
            'completion_time': datetime.now(timezone.utc).isoformat(),
            'pipeline_success': pipeline_results.get('overall_success', False),
            'cdn_images': pipeline_results.get('results', {}).get('cdn_results', {}).get('processed_images', 0),
            'ai_models': pipeline_results.get('results', {}).get('ai_results', {}).get('completed_models', 0),
        }

        await job_processor.update_job_status(
            job_id, JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Analytics completed successfully",
            result=final_result
        )

        logger.info(f"[IMD-ANALYTICS] Completed for @{username} (job: {job_id})")
        return final_result

    except Exception as e:
        logger.error(f"[IMD-ANALYTICS] Failed for @{username}: {e}")

        await _update_imd_progress(
            influencer_db_id, 'failed', 0,
            error=str(e)[:500]
        )

        await job_processor.update_job_status(
            job_id, JobStatus.FAILED,
            error_details={'error': str(e), 'username': username, 'influencer_db_id': influencer_db_id}
        )
        raise


async def cleanup_stale_imd_analytics():
    """Mark stuck IMD analytics jobs as failed. Called periodically by the worker."""
    try:
        async with optimized_pools.get_background_session() as session:
            result = await session.execute(text("""
                UPDATE influencer_database
                SET analytics_status = 'failed',
                    analytics_error = 'Job timed out after 15 minutes',
                    updated_at = NOW()
                WHERE analytics_status IN ('processing', 'queued')
                  AND analytics_queued_at < NOW() - INTERVAL '15 minutes'
                  AND analytics_completed_at IS NULL
                RETURNING id, username
            """).execution_options(prepare=False))
            rows = result.fetchall()
            await session.commit()
            if rows:
                logger.info(f"[IMD-CLEANUP] Marked {len(rows)} stale IMD analytics jobs as failed")
                for row in rows:
                    logger.info(f"  - @{row.username} ({row.id})")
    except Exception as e:
        logger.error(f"[IMD-CLEANUP] Failed: {e}")

# ============================================================================
# CELERY TASKS - CREATOR SEARCH (async 202 endpoint)
# ============================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def process_creator_search(self, job_id: str):
    """Process creator search job — full Apify + CDN + AI pipeline, stores response for retrieval"""
    try:
        logger.info(f"Starting creator search job {job_id}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_process_creator_search_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Creator search job {job_id} failed: {e}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'task_retry': self.request.retries}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            retry_delay = min(300, 60 * (2 ** self.request.retries))
            raise self.retry(countdown=retry_delay)
        raise


async def _process_creator_search_async(job_id: str) -> Dict[str, Any]:
    """
    Async implementation of creator search.
    Does the full pipeline that was previously blocking the API endpoint:
    1. Fetch from Apify
    2. Store profile + posts
    3. Run CDN + AI pipeline
    4. Build the full response dict
    5. Auto-unlock profile for the requesting user
    6. Store response in job result for frontend retrieval
    """
    from app.services.creator_search_response_builder import build_new_profile_response

    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    username = params.get('username')
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries
    user_email = params.get('user_email', '')

    logger.info(f"[CREATOR-SEARCH] Processing {username} (job: {job_id})")

    await job_processor.update_job_status(
        job_id, JobStatus.PROCESSING,
        progress_percent=5,
        progress_message=f"Fetching Instagram data for @{username}"
    )

    try:
        # STEP 1: Fetch from Apify
        from app.scrapers.apify_instagram_client import ApifyInstagramClient
        from app.core.config import settings

        async with ApifyInstagramClient(settings.APIFY_API_TOKEN) as apify_client:
            apify_data = await apify_client.get_instagram_profile_comprehensive(username)

        if not apify_data:
            raise Exception(f"Apify returned no data for {username}")

        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=20,
            progress_message=f"Storing profile data for @{username}"
        )

        # STEP 2: Store profile + posts
        from app.database.comprehensive_service import ComprehensiveDataService
        comprehensive_service = ComprehensiveDataService()

        async with optimized_pools.get_background_session() as db:
            profile, is_new = await comprehensive_service.store_complete_profile(
                db, username, apify_data
            )
            await db.commit()
            profile_id = str(profile.id)

        logger.info(f"[CREATOR-SEARCH] Profile stored: {profile_id} (new: {is_new})")

        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=30,
            progress_message=f"Running CDN + AI pipeline for @{username}"
        )

        # STEP 3: Run CDN + AI pipeline
        from app.services.unified_background_processor import unified_background_processor

        pipeline_results = await unified_background_processor.process_profile_complete_pipeline(
            profile_id=profile_id,
            username=username
        )

        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=85,
            progress_message=f"Building response for @{username}"
        )

        # STEP 4: Build the full response dict
        from app.database.unified_models import Profile, Post
        from sqlalchemy import select, text as sa_text

        async with optimized_pools.get_background_session() as db:
            # Refresh profile
            profile_q = select(Profile).where(Profile.id == profile_id)
            profile_r = await db.execute(profile_q)
            profile = profile_r.scalar_one_or_none()

            if not profile:
                raise Exception(f"Profile {username} not found after pipeline")

            # Get posts
            posts_q = select(Post).where(
                Post.profile_id == profile.id
            ).order_by(Post.created_at.desc()).limit(50)
            posts_r = await db.execute(posts_q)
            posts = posts_r.scalars().all()

            # Get CDN URLs
            cdn_q = sa_text("""
                SELECT media_id, cdn_url_512
                FROM cdn_image_assets
                WHERE source_id = :profile_id
                AND source_type = 'post_thumbnail'
                AND cdn_url_512 IS NOT NULL
            """)
            cdn_r = await db.execute(cdn_q, {'profile_id': profile_id})
            posts_cdn_urls = {str(row[0]): row[1] for row in cdn_r.fetchall()}

            avatar_q = sa_text("""
                SELECT cdn_url_512
                FROM cdn_image_assets
                WHERE source_id = :profile_id
                AND source_type = 'profile_avatar'
                AND cdn_url_512 IS NOT NULL
                LIMIT 1
            """)
            avatar_r = await db.execute(avatar_q, {'profile_id': profile_id})
            avatar_row = avatar_r.fetchone()
            cdn_avatar_url = avatar_row[0] if avatar_row else profile.cdn_avatar_url

            response_data = build_new_profile_response(
                profile, posts, posts_cdn_urls, cdn_avatar_url,
                pipeline_results=pipeline_results
            )

            # STEP 5: Auto-unlock profile for the user
            from app.database.unified_models import User, UserProfileAccess
            user_q = select(User).where(User.supabase_user_id == user_id)
            user_r = await db.execute(user_q)
            app_user = user_r.scalar_one_or_none()

            if app_user:
                existing_access_q = select(UserProfileAccess).where(
                    UserProfileAccess.user_id == app_user.id,
                    UserProfileAccess.profile_id == profile.id,
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )
                existing_access_r = await db.execute(existing_access_q)
                if not existing_access_r.scalar_one_or_none():
                    from datetime import timedelta
                    new_access = UserProfileAccess(
                        user_id=app_user.id,
                        profile_id=profile.id,
                        granted_at=datetime.now(timezone.utc),
                        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
                    )
                    db.add(new_access)
                    await db.commit()
                    logger.info(f"[CREATOR-SEARCH] Auto-unlocked {username} for user {user_id}")

        # STEP 6: Store response in job result
        from app.utils.json_serializer import safe_json_response
        sanitized = safe_json_response(response_data)

        await job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message=f"Analysis complete for @{username}",
            result=sanitized
        )

        # Notify user of completion
        await job_processor.create_completion_notification(
            job_id, 'creator_search', user_id, {'username': username, **sanitized}
        )

        logger.info(f"[CREATOR-SEARCH] Job {job_id} completed for {username}")
        return sanitized

    except Exception as e:
        logger.error(f"[CREATOR-SEARCH] Failed for {username}: {e}")

        await job_processor.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_details={
                'error': str(e),
                'username': username,
            }
        )
        raise


# ============================================================================
# CELERY TASKS - POST ANALYSIS
# ============================================================================

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_post_analysis(self, job_id: str):
    """Process post analysis job"""

    try:
        logger.info(f"Starting post analysis job {job_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_post_analysis_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Post analysis job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e)}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (2 ** self.request.retries))

        raise

async def _process_post_analysis_async(job_id: str) -> Dict[str, Any]:
    """
    Async implementation of single post analysis.
    Handles two param shapes:
      - post_url based (from post_analytics_routes /analyze endpoint)
      - username based (from fast_handoff_api /analytics/posts/{username})
    """

    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    post_url = params.get('post_url')
    username = params.get('username')
    credit_cost = params.get('credit_cost', 5)
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    label = post_url or username or 'unknown'

    # Update status
    await job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting post analysis for {label}"
    )

    try:
        # Deduct credits
        if credit_cost > 0:
            credit_deducted = await job_processor.deduct_credits(
                user_id,
                credit_cost,
                f"Post analysis for {label}"
            )
            if not credit_deducted:
                raise Exception("Failed to deduct credits - insufficient balance")

        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=20,
            progress_message=f"Fetching post data for {label}"
        )

        # Run actual post analysis via standalone service
        if post_url:
            from app.services.standalone_post_analytics_service import standalone_post_analytics_service

            async with optimized_pools.get_background_session() as db:
                analysis_result = await standalone_post_analytics_service.analyze_post_by_url(
                    post_url=post_url,
                    db=db,
                    user_id=user_id
                )

            await job_processor.update_job_status(
                job_id, JobStatus.PROCESSING,
                progress_percent=90,
                progress_message="Finalizing post analysis"
            )

            # Build result in the same shape the sync endpoint used to return
            from app.utils.json_serializer import safe_json_response
            result = safe_json_response({
                'success': True,
                'data': analysis_result,
                'message': 'Post analysis completed successfully'
            })
        else:
            # Legacy username-based path (from fast_handoff_api)
            await job_processor.update_job_status(
                job_id, JobStatus.PROCESSING,
                progress_percent=50,
                progress_message=f"Analyzing posts for {username}"
            )

            result = {
                'success': True,
                'data': {
                    'username': username,
                    'posts_analyzed': 0,
                },
                'message': 'Post analysis completed',
                'completion_time': datetime.now(timezone.utc).isoformat()
            }

        await job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Post analysis completed",
            result=result
        )

        # Notify user of completion
        await job_processor.create_completion_notification(
            job_id, 'post_analysis', user_id, {**(result or {}), 'username': username}
        )

        return result

    except Exception as e:
        logger.error(f"Post analysis failed for {label} (job {job_id}): {e}")

        # Refund credits on failure
        if credit_cost > 0:
            try:
                await job_processor.credit_service.add_credits(
                    user_id,
                    credit_cost,
                    f"Refund for failed post analysis of {label}"
                )
            except Exception as refund_err:
                logger.error(f"Failed to refund credits for job {job_id}: {refund_err}")

        await job_processor.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_details={
                'error': str(e),
                'post_url': post_url,
                'username': username,
                'credits_refunded': credit_cost > 0
            }
        )

        raise

# ============================================================================
# CELERY TASKS - BATCH POST ANALYSIS
# ============================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def process_batch_post_analysis(self, job_id: str):
    """
    Process batch post analysis job.
    Iterates over multiple post URLs sequentially with progress updates.
    """
    try:
        logger.info(f"Starting batch post analysis job {job_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_batch_post_analysis_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Batch post analysis job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'task_retry': self.request.retries}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            retry_delay = min(300, 60 * (2 ** self.request.retries))
            logger.info(f"Retrying batch post analysis job {job_id} in {retry_delay}s (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay)

        raise


async def _process_batch_post_analysis_async(job_id: str) -> Dict[str, Any]:
    """
    Async implementation of batch post analysis.
    Processes each post URL sequentially via standalone_post_analytics_service,
    updating progress after each post completes.
    """
    from app.services.standalone_post_analytics_service import standalone_post_analytics_service

    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    post_urls = params.get('post_urls', [])
    total_posts = params.get('total_posts', len(post_urls))
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    logger.info(f"[BATCH-POST] Processing {total_posts} posts (job: {job_id})")

    await job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting batch analysis for {total_posts} posts"
    )

    results = []
    successful = 0
    failed = 0

    for i, post_url in enumerate(post_urls):
        # Update progress before each post
        progress_pct = int(((i) / total_posts) * 95)  # Reserve 5% for finalization
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=progress_pct,
            progress_message=f"Analyzing post {i + 1}/{total_posts}: {post_url[:60]}..."
        )

        try:
            async with optimized_pools.get_background_session() as db:
                analysis_result = await standalone_post_analytics_service.analyze_post_by_url(
                    post_url=post_url,
                    db=db,
                    user_id=user_id
                )

            results.append({
                "success": True,
                "post_url": post_url,
                "data": analysis_result
            })
            successful += 1
            logger.info(f"[BATCH-POST] Post {i + 1}/{total_posts} succeeded: {post_url}")

        except Exception as post_err:
            logger.warning(f"[BATCH-POST] Post {i + 1}/{total_posts} failed ({post_url}): {post_err}")
            results.append({
                "success": False,
                "post_url": post_url,
                "error": str(post_err)
            })
            failed += 1

        # Brief pause between posts to avoid rate-limiting external APIs
        if i < total_posts - 1:
            await asyncio.sleep(2)

    # Build final result in the same shape as the old sync batch endpoint
    from app.utils.json_serializer import safe_json_response
    success_rate = round((successful / total_posts) * 100, 1) if total_posts > 0 else 0

    final_result = safe_json_response({
        "success": True,
        "data": {
            "results": results,
            "summary": {
                "total_requested": total_posts,
                "successful": successful,
                "failed": failed,
                "success_rate": success_rate
            }
        },
        "message": f"Batch analysis completed: {successful}/{total_posts} successful"
    })

    await job_processor.update_job_status(
        job_id,
        JobStatus.COMPLETED,
        progress_percent=100,
        progress_message=f"Batch analysis completed: {successful}/{total_posts} successful",
        result=final_result
    )

    # Notify user of completion
    await job_processor.create_completion_notification(
        job_id, 'batch_post_analysis', user_id, final_result
    )

    logger.info(f"[BATCH-POST] Job {job_id} completed: {successful}/{total_posts} successful")
    return final_result

# ============================================================================
# CELERY TASKS - CAMPAIGN POST ANALYTICS
# ============================================================================

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_post_analytics_campaign(self, job_id: str):
    """Process post analytics for campaign with background processing"""

    try:
        logger.info(f"🚀 Starting campaign post analytics job {job_id}")

        # Use async runner for the actual processing
        asyncio.run(_process_post_analytics_campaign_async(job_id))

        logger.info(f"✅ Campaign post analytics job {job_id} completed successfully")
        return {
            'status': 'success',
            'job_id': job_id,
            'message': 'Campaign post analytics completed'
        }

    except Exception as e:
        logger.error(f"❌ Campaign post analytics job {job_id} failed: {e}")

        # Update job status to failed
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    job_processor.update_job_status(
                        job_id,
                        JobStatus.FAILED,
                        error_details={'error': str(e), 'task_retry': self.request.retries}
                    )
                )
            finally:
                loop.close()
        except Exception:
            pass

        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retrying campaign post analytics job {job_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60)

        raise


async def _process_post_analytics_campaign_async(job_id: str):
    """Async implementation of campaign post analytics processing"""

    # Get job parameters from database
    async with optimized_pools.get_user_session() as session:
        result = await session.execute(
            text("SELECT params FROM job_queue WHERE id = :job_id").execution_options(prepare=False),
            {"job_id": job_id}
        )
        job_row = result.fetchone()

        if not job_row:
            raise Exception(f"Job {job_id} not found")

        params = job_row.params if isinstance(job_row.params, dict) else json.loads(job_row.params)

        # Extract job parameters
        campaign_id = params['campaign_id']
        instagram_post_url = params['instagram_post_url']
        user_id = params['user_id']

        logger.info(f"📊 Processing post {instagram_post_url} for campaign {campaign_id}")

        # Update job status to processing
        await job_processor.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress_percent=0,
            progress_message="Processing post analytics"
        )

        # Step 1: Run post analytics
        from app.services.standalone_post_analytics_service import standalone_post_analytics_service

        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=30,
            progress_message="Analyzing Instagram post"
        )

        async with optimized_pools.get_user_session() as db_session:
            post_analysis = await standalone_post_analytics_service.analyze_post_by_url(
                post_url=instagram_post_url,
                db=db_session,
                user_id=user_id
            )

            # Step 2: Add post to campaign
            from app.services.campaign_service import campaign_service

            await job_processor.update_job_status(
                job_id, JobStatus.PROCESSING,
                progress_percent=70,
                progress_message="Adding post to campaign"
            )

            campaign_post = await campaign_service.add_post_to_campaign(
                db=db_session,
                campaign_id=campaign_id,
                post_data=post_analysis,
                user_id=user_id
            )

            # Update job status to completed
            result = {
                "success": True,
                "campaign_post_id": str(campaign_post.id) if campaign_post else None,
                "post_url": instagram_post_url,
                "campaign_id": campaign_id,
                "completion_time": datetime.now(timezone.utc).isoformat()
            }

            await job_processor.update_job_status(
                job_id,
                JobStatus.COMPLETED,
                progress_percent=100,
                progress_message="Post added to campaign successfully",
                result=result
            )

            logger.info(f"✅ Post added to campaign {campaign_id} successfully")


# ============================================================================
# CELERY TASKS - BULK ANALYSIS
# ============================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def process_bulk_analysis(self, job_id: str):
    """Process bulk analysis job with throttling"""

    try:
        logger.info(f"Starting bulk analysis job {job_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_bulk_analysis_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Bulk analysis job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e)}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120 * (2 ** self.request.retries))

        raise

async def _process_bulk_analysis_async(job_id: str) -> Dict[str, Any]:
    """Async implementation of bulk analysis with throttling"""

    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    usernames = params.get('usernames', [])
    credit_cost = params.get('credit_cost', 0)
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    await job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting bulk analysis for {len(usernames)} profiles"
    )

    try:
        # Deduct credits upfront
        credit_deducted = await job_processor.deduct_credits(
            user_id,
            credit_cost,
            f"Bulk analysis for {len(usernames)} profiles"
        )

        if not credit_deducted:
            raise Exception("Failed to deduct credits")

        # Process profiles with throttling
        successful_analyses = []
        failed_analyses = []

        for i, username in enumerate(usernames):
            try:
                await job_processor.update_job_status(
                    job_id, JobStatus.PROCESSING,
                    progress_percent=int((i / len(usernames)) * 90),
                    progress_message=f"Processing {username} ({i+1}/{len(usernames)})"
                )

                # Trigger analysis for individual profile
                analytics_result = await job_processor.analytics_service.trigger_comprehensive_analytics(
                    username=username,
                    priority="low",
                    user_id=user_id
                )

                if analytics_result.get('success'):
                    successful_analyses.append(username)
                else:
                    failed_analyses.append(username)

                # Throttling: wait between profiles
                if i < len(usernames) - 1:  # Don't wait after last profile
                    await asyncio.sleep(2)  # 2 second delay between profiles

            except Exception as e:
                logger.warning(f"Failed to process {username} in bulk job: {e}")
                failed_analyses.append(username)

        result = {
            'total_profiles': len(usernames),
            'successful_analyses': len(successful_analyses),
            'failed_analyses': len(failed_analyses),
            'successful_usernames': successful_analyses,
            'failed_usernames': failed_analyses,
            'completion_time': datetime.now(timezone.utc).isoformat()
        }

        await job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message=f"Bulk analysis completed: {len(successful_analyses)}/{len(usernames)} successful",
            result=result
        )

        # Notify user of completion
        await job_processor.create_completion_notification(
            job_id, 'bulk_analysis', user_id, result
        )

        return result

    except Exception as e:
        # Refund credits on failure
        try:
            await job_processor.credit_service.add_credits(
                user_id,
                credit_cost,
                f"Refund for failed bulk analysis"
            )
        except Exception:
            pass

        raise

# ============================================================================
# BACKGROUND PROFILE ANALYSIS (For Instagram Endpoint)
# ============================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def process_profile_analysis_background(self, job_id: str):
    """Process background profile analysis triggered from Instagram endpoint"""

    try:
        logger.info(f"Starting background profile analysis job {job_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_profile_analysis_background_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Background profile analysis job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'task_retry': self.request.retries}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            retry_delay = 120 * (2 ** self.request.retries)  # 2min, 4min
            logger.info(f"Retrying background job {job_id} in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)

        raise

async def _process_profile_analysis_background_async(job_id: str) -> Dict[str, Any]:
    """Async implementation of background profile analysis"""

    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Background job {job_id} not found")

    params = job_details['params']
    username = params.get('username')
    profile_id = params.get('profile_id')
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    logger.info(f"Processing background analysis for {username} (profile_id: {profile_id})")

    # Update status to processing
    await job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting background analysis for {username}"
    )

    try:
        # Use the existing comprehensive analytics service
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=20,
            progress_message="Triggering comprehensive analytics"
        )

        # No credit deduction for background processing (triggered from existing profiles)
        # CRITICAL: Set is_background_discovery=True to prevent recursive discovery
        async with optimized_pools.get_background_session() as db:
            profile, analytics_result = await job_processor.analytics_service.trigger_full_creator_analytics(
                username=username,
                db=db,
                force_refresh=True,
                is_background_discovery=True  # PREVENT RECURSIVE DISCOVERY
            )

        if not analytics_result.get('is_full_analytics'):
            raise Exception(f"Analytics failed: {analytics_result.get('error', 'Incomplete analytics')}")

        # Wait for completion with progress updates
        profile_id = profile.id if profile else None
        completion_result = await _wait_for_analytics_completion(
            job_id, profile_id, username, progress_start=30
        )

        # Prepare final result
        final_result = {
            'profile_id': profile_id,
            'username': username,
            'analytics_completed': True,
            'background_processing': True,
            'completion_time': datetime.now(timezone.utc).isoformat(),
            **completion_result
        }

        # Update job as completed
        await job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Background analysis completed successfully",
            result=final_result
        )

        logger.info(f"Background analysis completed for {username} (job: {job_id})")
        return final_result

    except Exception as e:
        logger.error(f"Background analysis failed for {username}: {e}")

        # Update job as failed
        await job_processor.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_details={
                'error': str(e),
                'username': username,
                'background_processing': True
            }
        )

        raise

# ============================================================================
# CELERY TASKS - DISCOVERY UNLOCK (single profile, async 202)
# ============================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def process_discovery_unlock(self, job_id: str):
    """
    Process a single discovery profile unlock that needs the full pipeline.
    Triggered when a user unlocks a profile that is incomplete in the DB.
    """
    try:
        logger.info(f"Starting discovery unlock job {job_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_process_discovery_unlock_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Discovery unlock job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'task_retry': self.request.retries}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            retry_delay = min(300, 60 * (2 ** self.request.retries))
            logger.info(f"Retrying discovery unlock job {job_id} in {retry_delay}s (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay)

        raise


async def _process_discovery_unlock_async(job_id: str) -> Dict[str, Any]:
    """
    Async implementation of discovery unlock.
    1. Deduct credits
    2. Run the full Apify + CDN + AI pipeline for the profile
    3. Create the unlock/access record
    4. Store the result in the job for frontend retrieval
    """
    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    profile_id = params.get('profile_id')
    username = params.get('username', 'unknown')
    unlock_reason = params.get('unlock_reason')
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    logger.info(f"[DISCOVERY-UNLOCK] Processing unlock for @{username} (profile_id: {profile_id}, job: {job_id})")

    await job_processor.update_job_status(
        job_id, JobStatus.PROCESSING,
        progress_percent=5,
        progress_message=f"Starting full pipeline for @{username}"
    )

    try:
        # STEP 1: Deduct credits upfront (25 credits for profile_analysis)
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=10,
            progress_message="Validating credits"
        )

        from app.services.credit_wallet_service import credit_wallet_service
        from uuid import UUID as _UUID

        permission = await credit_wallet_service.can_perform_action(
            _UUID(user_id), "profile_analysis", 25
        )

        if not permission.can_perform:
            raise Exception(f"Insufficient credits: {permission.message}")

        transaction = await credit_wallet_service.spend_credits(
            user_id=_UUID(user_id),
            amount=25,
            action_type="profile_analysis",
            reference_id=profile_id,
            reference_type="profile",
            description=f"Discovery unlock: @{username}"
        )

        # STEP 2: Run comprehensive analytics pipeline
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=20,
            progress_message=f"Triggering comprehensive analytics for @{username}"
        )

        async with optimized_pools.get_background_session() as db:
            profile, analytics_result = await job_processor.analytics_service.trigger_full_creator_analytics(
                username=username,
                db=db,
                force_refresh=True,
                is_background_discovery=False
            )

        if not analytics_result.get('is_full_analytics'):
            raise Exception(f"Analytics failed: {analytics_result.get('error', 'Incomplete analytics')}")

        # STEP 3: Wait for pipeline completion with progress updates
        resolved_profile_id = str(profile.id) if profile else profile_id
        completion_result = await _wait_for_analytics_completion(
            job_id, resolved_profile_id, username, progress_start=30
        )

        # STEP 4: Create unlock / access record
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=90,
            progress_message=f"Creating unlock record for @{username}"
        )

        from app.database.unified_models import UserProfileAccess
        from sqlalchemy import select
        from datetime import timedelta

        async with optimized_pools.get_background_session() as db:
            existing_q = select(UserProfileAccess).where(
                UserProfileAccess.user_id == _UUID(user_id),
                UserProfileAccess.profile_id == _UUID(resolved_profile_id),
            )
            existing_r = await db.execute(existing_q)
            if not existing_r.scalar_one_or_none():
                new_access = UserProfileAccess(
                    user_id=_UUID(user_id),
                    profile_id=_UUID(resolved_profile_id),
                    granted_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30)
                )
                db.add(new_access)
                await db.commit()

        # STEP 5: Build final result
        final_result = {
            'success': True,
            'unlocked': True,
            'profile_id': resolved_profile_id,
            'username': username,
            'credits_spent': 25,
            'transaction_id': str(transaction.id) if transaction else None,
            'analytics_completed': True,
            'completion_time': datetime.now(timezone.utc).isoformat(),
            **completion_result
        }

        await job_processor.update_job_status(
            job_id, JobStatus.COMPLETED,
            progress_percent=100,
            progress_message=f"Unlock complete for @{username}",
            result=final_result
        )

        # Notify user of completion
        await job_processor.create_completion_notification(
            job_id, 'discovery_unlock', user_id, final_result
        )

        logger.info(f"[DISCOVERY-UNLOCK] Job {job_id} completed for @{username}")
        return final_result

    except Exception as e:
        logger.error(f"[DISCOVERY-UNLOCK] Failed for @{username}: {e}")

        # Attempt credit refund
        try:
            from app.services.credit_wallet_service import credit_wallet_service
            from uuid import UUID as _UUID
            await credit_wallet_service.add_credits(
                _UUID(user_id), 25,
                f"Refund for failed discovery unlock of @{username}"
            )
            logger.info(f"[DISCOVERY-UNLOCK] Refunded 25 credits for failed job {job_id}")
        except Exception as refund_err:
            logger.error(f"[DISCOVERY-UNLOCK] Credit refund failed for job {job_id}: {refund_err}")

        await job_processor.update_job_status(
            job_id, JobStatus.FAILED,
            error_details={
                'error': str(e),
                'username': username,
                'profile_id': profile_id,
                'credits_refunded': True,
            }
        )
        raise


# ============================================================================
# CELERY TASKS - BULK UNLOCK (multiple profiles, async 202)
# ============================================================================

@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def process_bulk_unlock(self, job_id: str):
    """
    Process bulk profile unlock job.
    Processes profiles 3-at-a-time with concurrency control.
    """
    try:
        logger.info(f"Starting bulk unlock job {job_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_process_bulk_unlock_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Bulk unlock job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'task_retry': self.request.retries}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120 * (2 ** self.request.retries))

        raise


async def _process_bulk_unlock_async(job_id: str) -> Dict[str, Any]:
    """
    Async implementation of bulk unlock.
    - Deducts credits upfront for all profiles that need unlocking
    - Processes profiles 3 at a time with asyncio.Semaphore
    - Updates progress per profile
    - Stores a BulkProfileUnlockResponse-shaped result
    """
    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    profiles_to_unlock = params.get('profiles_to_unlock', [])
    already_unlocked_ids = params.get('already_unlocked_ids', [])
    invalid_ids = params.get('invalid_ids', [])
    unlock_reason = params.get('unlock_reason')
    total_credit_cost = params.get('total_credit_cost', 0)
    total_requested = params.get('total_requested', 0)
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    logger.info(
        f"[BULK-UNLOCK] Processing {len(profiles_to_unlock)} profiles "
        f"(already_unlocked={len(already_unlocked_ids)}, invalid={len(invalid_ids)}, "
        f"job: {job_id})"
    )

    await job_processor.update_job_status(
        job_id, JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting bulk unlock for {len(profiles_to_unlock)} profiles"
    )

    try:
        # STEP 1: Deduct credits upfront
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=5,
            progress_message="Deducting credits"
        )

        from app.services.credit_wallet_service import credit_wallet_service
        from uuid import UUID as _UUID

        if total_credit_cost > 0:
            permission = await credit_wallet_service.can_perform_action(
                _UUID(user_id), "profile_analysis", total_credit_cost
            )
            if not permission.can_perform:
                raise Exception(f"Insufficient credits for bulk unlock: {permission.message}")

            await credit_wallet_service.spend_credits(
                user_id=_UUID(user_id),
                amount=total_credit_cost,
                action_type="profile_analysis",
                reference_id=job_id,
                reference_type="bulk_unlock",
                description=f"Bulk unlock of {len(profiles_to_unlock)} profiles"
            )

        # STEP 2: Process profiles with concurrency control (3 at a time)
        semaphore = asyncio.Semaphore(3)
        results = []
        successful_count = 0
        failed_count = 0

        async def _unlock_single(index: int, profile_info: Dict[str, Any]) -> Dict[str, Any]:
            """Unlock a single profile within the semaphore."""
            nonlocal successful_count, failed_count
            pid = profile_info['profile_id']
            uname = profile_info.get('username', 'unknown')

            async with semaphore:
                try:
                    # Update progress
                    progress = 10 + int((index / max(len(profiles_to_unlock), 1)) * 80)
                    await job_processor.update_job_status(
                        job_id, JobStatus.PROCESSING,
                        progress_percent=progress,
                        progress_message=f"Unlocking @{uname} ({index + 1}/{len(profiles_to_unlock)})"
                    )

                    # Run the discovery service unlock (handles DB record creation)
                    from app.services.discovery_service import discovery_service
                    unlock_data = await discovery_service.unlock_profile(
                        user_id=_UUID(user_id),
                        profile_id=_UUID(pid),
                        unlock_reason=unlock_reason
                    )

                    if "error" in unlock_data:
                        failed_count += 1
                        return {
                            'profile_id': pid,
                            'success': False,
                            'credits_spent': 0,
                            'error_message': unlock_data.get('message', 'Unlock failed'),
                            'already_unlocked': False,
                        }

                    if unlock_data.get('already_unlocked'):
                        return {
                            'profile_id': pid,
                            'success': True,
                            'credits_spent': 0,
                            'already_unlocked': True,
                        }

                    successful_count += 1
                    return {
                        'profile_id': pid,
                        'success': True,
                        'credits_spent': unlock_data.get('credits_spent', 25),
                        'unlock_id': str(unlock_data.get('unlock_id', '')),
                        'already_unlocked': False,
                    }

                except Exception as exc:
                    logger.error(f"[BULK-UNLOCK] Failed to unlock {pid} (@{uname}): {exc}")
                    failed_count += 1
                    return {
                        'profile_id': pid,
                        'success': False,
                        'credits_spent': 0,
                        'error_message': str(exc),
                        'already_unlocked': False,
                    }

        # Launch all tasks (semaphore limits concurrency to 3)
        tasks = [
            _unlock_single(i, p)
            for i, p in enumerate(profiles_to_unlock)
        ]
        unlock_results = await asyncio.gather(*tasks)
        results.extend(unlock_results)

        # Add already-unlocked and invalid entries
        for pid in already_unlocked_ids:
            results.append({
                'profile_id': pid,
                'success': True,
                'credits_spent': 0,
                'already_unlocked': True,
            })

        for pid in invalid_ids:
            results.append({
                'profile_id': pid,
                'success': False,
                'credits_spent': 0,
                'error_message': 'Profile not found or unavailable',
                'already_unlocked': False,
            })

        # Calculate actuals
        actual_credits_spent = sum(r.get('credits_spent', 0) for r in results)

        # Refund excess credits if some profiles failed or were already unlocked
        refund_amount = total_credit_cost - actual_credits_spent
        if refund_amount > 0:
            try:
                await credit_wallet_service.add_credits(
                    _UUID(user_id), refund_amount,
                    f"Partial refund for bulk unlock job {job_id} ({failed_count} failed)"
                )
                logger.info(f"[BULK-UNLOCK] Refunded {refund_amount} credits for job {job_id}")
            except Exception as refund_err:
                logger.error(f"[BULK-UNLOCK] Partial refund failed: {refund_err}")

        # Build final result matching BulkProfileUnlockResponse shape
        final_result = {
            'total_requested': total_requested,
            'successful_unlocks': successful_count,
            'already_unlocked': len(already_unlocked_ids) + sum(
                1 for r in unlock_results if r.get('already_unlocked')
            ),
            'failed_unlocks': failed_count + len(invalid_ids),
            'total_credits_spent': actual_credits_spent,
            'results': results,
            'completion_time': datetime.now(timezone.utc).isoformat(),
        }

        await job_processor.update_job_status(
            job_id, JobStatus.COMPLETED,
            progress_percent=100,
            progress_message=f"Bulk unlock complete: {successful_count} unlocked, {failed_count} failed",
            result=final_result
        )

        # Notify user of completion
        await job_processor.create_completion_notification(
            job_id, 'bulk_unlock', user_id, final_result
        )

        logger.info(f"[BULK-UNLOCK] Job {job_id} completed: {successful_count}/{len(profiles_to_unlock)} successful")
        return final_result

    except Exception as e:
        logger.error(f"[BULK-UNLOCK] Job {job_id} failed: {e}")

        # Refund all credits on total failure
        if total_credit_cost > 0:
            try:
                from app.services.credit_wallet_service import credit_wallet_service
                from uuid import UUID as _UUID
                await credit_wallet_service.add_credits(
                    _UUID(user_id), total_credit_cost,
                    f"Full refund for failed bulk unlock job {job_id}"
                )
                logger.info(f"[BULK-UNLOCK] Full refund of {total_credit_cost} credits for job {job_id}")
            except Exception as refund_err:
                logger.error(f"[BULK-UNLOCK] Full refund failed: {refund_err}")

        await job_processor.update_job_status(
            job_id, JobStatus.FAILED,
            error_details={
                'error': str(e),
                'profiles_requested': len(profiles_to_unlock),
                'credits_refunded': True,
            }
        )
        raise


# ============================================================================
# CELERY TASKS - CAMPAIGN EXPORT (async 202 endpoint)
# ============================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_campaign_export(self, job_id: str):
    """Process campaign export job"""
    try:
        logger.info(f"Starting campaign export job {job_id}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_process_campaign_export_async(job_id))
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Campaign export job {job_id} failed: {e}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                job_processor.update_job_status(
                    job_id, JobStatus.FAILED, error_details={'error': str(e)}
                )
            )
        finally:
            loop.close()
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        raise

async def _process_campaign_export_async(job_id: str) -> Dict[str, Any]:
    """Async implementation of campaign export"""
    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    campaign_id = params.get('campaign_id')
    export_format = params.get('format', 'csv')
    campaign_name = params.get('campaign_name', 'campaign')
    user_id = str(job_details['user_id'])  # Convert UUID to str for supabase_user_id queries

    await job_processor.update_job_status(
        job_id, JobStatus.PROCESSING,
        progress_percent=10,
        progress_message=f"Starting {export_format.upper()} export for '{campaign_name}'"
    )

    try:
        from app.services.campaign_export_service import campaign_export_service
        from uuid import UUID as PyUUID

        async with optimized_pools.get_background_session() as db:
            await job_processor.update_job_status(
                job_id, JobStatus.PROCESSING,
                progress_percent=30,
                progress_message="Generating export data"
            )

            if export_format == 'csv':
                content = await campaign_export_service.export_campaign_to_csv(
                    db=db,
                    campaign_id=PyUUID(campaign_id),
                    user_id=PyUUID(user_id),
                    include_posts=True,
                    include_creators=True,
                    include_audience=True
                )
            else:
                content = await campaign_export_service.export_campaign_to_json(
                    db=db,
                    campaign_id=PyUUID(campaign_id),
                    user_id=PyUUID(user_id),
                    include_posts=True,
                    include_creators=True,
                    include_audience=True
                )

        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=80,
            progress_message="Export generated, preparing result"
        )

        safe_name = campaign_name.replace(' ', '_')
        filename = f"{safe_name}_campaign_export.{export_format}"

        final_result = {
            'filename': filename,
            'format': export_format,
            'content': content,
            'campaign_id': campaign_id,
            'campaign_name': campaign_name,
            'completion_time': datetime.now(timezone.utc).isoformat()
        }

        await job_processor.update_job_status(
            job_id, JobStatus.COMPLETED,
            progress_percent=100,
            progress_message=f"Export completed: {filename}",
            result=final_result
        )
        return final_result

    except Exception as e:
        logger.error(f"Campaign export failed for {campaign_name}: {e}")
        raise


# ============================================================================
# WORKER HEALTH MONITORING
# ============================================================================

@celery_app.task
def health_check():
    """Worker health check task"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'worker_id': os.getpid()
    }

# ============================================================================
# CELERY SIGNALS
# ============================================================================

@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing worker functionality"""
    print(f'Request: {self.request!r}')
    return {'status': 'debug_complete', 'worker_id': os.getpid()}

if __name__ == '__main__':
    # Start worker when run directly
    celery_app.start(['worker', '--loglevel=info', '--concurrency=4'])