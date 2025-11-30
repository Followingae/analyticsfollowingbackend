"""
Dedicated Post Analytics Worker
Handles all post analytics processing asynchronously to keep the backend responsive
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from uuid import UUID
import uuid as uuid_lib

from app.core.job_queue import JobStatus, JobPriority, QueueType
from app.services.standalone_post_analytics_service import standalone_post_analytics_service
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from app.services.unified_background_processor import UnifiedBackgroundProcessor
from app.services.campaign_service import campaign_service
from app.workers.worker_database import worker_db  # Use raw asyncpg connection
from app.database.connection import get_session  # Still needed for services
from sqlalchemy import text

logger = logging.getLogger(__name__)


class PostAnalyticsWorker:
    """
    Dedicated worker for processing post analytics jobs
    Runs independently from the main API to keep backend responsive
    """

    def __init__(self):
        self.running = False
        self.current_job = None
        logger.info("[INIT] Post Analytics Worker initialized")

    async def start(self):
        """Start the worker to process post analytics jobs"""
        self.running = True

        # CRITICAL: Clean up stuck jobs on startup
        await self._cleanup_stuck_jobs()

        logger.info("[SUCCESS] Post Analytics Worker started")

        while self.running:
            try:
                # Get next job from queue
                job = await self._get_next_job()

                if job:
                    await self._process_job(job)
                else:
                    # No jobs available, wait before checking again
                    await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"[ERROR] Worker error: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def stop(self):
        """Stop the worker gracefully"""
        self.running = False
        logger.info("[STOP] Post Analytics Worker stopping...")

    async def _cleanup_stuck_jobs(self):
        """Clean up any stuck jobs from previous runs"""
        logger.info("[CLEANUP] Checking for stuck jobs...")

        try:
            # Reset any jobs that have been stuck for more than 30 minutes
            result = await worker_db.execute_query("""
                UPDATE job_queue
                SET status = 'queued',
                    started_at = NULL,
                    progress_message = 'Reset after worker restart'
                WHERE status IN ('processing', 'queued')
                AND (
                    created_at < NOW() - INTERVAL '30 minutes'
                    OR started_at < NOW() - INTERVAL '30 minutes'
                )
                RETURNING id, job_type
            """)

            if result:
                logger.info(f"[CLEANUP] Reset {len(result)} stuck jobs to queued status")
                for row in result:
                    logger.info(f"  - Reset job {row['id']} ({row['job_type']})")
            else:
                logger.info("[CLEANUP] No stuck jobs found")

        except Exception as e:
            logger.error(f"[CLEANUP] Failed to clean up stuck jobs: {e}")
            # Don't fail startup if cleanup fails
            pass

    async def _get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next post analytics job from the queue using raw asyncpg"""
        try:
            # First, reset any jobs that have been processing for too long (30 min timeout)
            await worker_db.execute_query("""
                UPDATE job_queue
                SET status = 'queued',
                    started_at = NULL,
                    progress_message = 'Reset due to timeout'
                WHERE status = 'processing'
                AND started_at < NOW() - INTERVAL '30 minutes'
            """)

            # Now get the next available job
            return await worker_db.get_next_job()

        except Exception as e:
            logger.error(f"[ERROR] Failed to get next job: {e}")
            return None

    async def _process_job(self, job: Dict[str, Any]):
        """Process a single post analytics job"""
        job_id = job["id"]
        params = job["params"]

        logger.info(f"[ANALYTICS] Processing post analytics job {job_id}")
        logger.info(f"   Campaign: {params.get('campaign_id')}")
        logger.info(f"   Post URL: {params.get('instagram_post_url')}")

        try:
            # Get isolated database session for this job
            async with get_session() as db:
                # STEP 1: Run Post Analytics
                logger.info(f"[PROCESSING] Starting post analytics for job {job_id}")

                post_analysis = await standalone_post_analytics_service.analyze_post_by_url(
                    post_url=params["instagram_post_url"],
                    db=db,
                    user_id=UUID(params["user_id"])
                )

                # STEP 2: Wait for FULL Creator Analytics if needed (Option A)
                creator_username = post_analysis.get("profile", {}).get("username")
                if creator_username and params.get("wait_for_full_analytics", True):
                    await self._wait_for_creator_analytics_completion(
                        username=creator_username,
                        db=db,
                        job_id=job_id
                    )

                # STEP 3: Add post to campaign
                logger.info(f"➕ Adding post to campaign for job {job_id}")

                campaign_post = await campaign_service.add_post_to_campaign(
                    db=db,
                    campaign_id=UUID(params["campaign_id"]),
                    post_id=UUID(post_analysis["post_id"]),
                    instagram_post_url=params["instagram_post_url"],
                    user_id=UUID(params["user_id"])
                )

                if not campaign_post:
                    raise ValueError("Failed to add post to campaign")

                # Prepare success result
                result_data = {
                    "success": True,
                    "campaign_post_id": str(campaign_post.id),
                    "post_analysis": post_analysis,
                    "added_at": campaign_post.added_at.isoformat(),
                    "message": "Post added to campaign successfully"
                }

                # Mark job as completed
                await self._update_job_status(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    result=result_data
                )

                logger.info(f"[SUCCESS] Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"[ERROR] Job {job_id} failed: {e}")

            # Check retry count
            retry_count = job.get("retry_count", 0)
            max_retries = 3

            if retry_count < max_retries:
                # Retry the job
                logger.info(f"[RETRY] Job {job_id} will be retried (attempt {retry_count + 1}/{max_retries})")

                # Update job to queued for retry
                await worker_db.execute_query("""
                    UPDATE job_queue
                    SET status = 'queued',
                        retry_count = retry_count + 1,
                        started_at = NULL,
                        progress_message = $1
                    WHERE id = $2::uuid
                """, f"Retry {retry_count + 1}/{max_retries} after error: {str(e)[:100]}", job_id)
            else:
                # Mark job as permanently failed after max retries
                logger.error(f"[FAILED] Job {job_id} failed after {max_retries} attempts")
                await self._update_job_status(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    error=f"Failed after {max_retries} attempts. Last error: {str(e)}"
                )

    async def _wait_for_creator_analytics_completion(
        self,
        username: str,
        db,
        job_id: str
    ):
        """
        Wait for full creator analytics completion (Option A)
        This ensures complete data including Audience demographics
        """
        logger.info(f"⏳ Job {job_id}: Starting FULL Creator Analytics for @{username}")

        try:
            # Trigger Creator Analytics
            profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                username=username,
                db=db,
                force_refresh=False
            )

            if not profile or profile.followers_count == 0:
                logger.warning(f"[WARNING] Job {job_id}: Initial analytics failed, retrying with force refresh")

                # Retry with force refresh
                profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                    username=username,
                    db=db,
                    force_refresh=True
                )

            if profile and profile.followers_count > 0:
                profile_id = str(profile.id)
                logger.info(f"[ANALYTICS] Job {job_id}: Creator Analytics triggered - {profile.followers_count:,} followers")

                # Wait for completion
                processor = UnifiedBackgroundProcessor()
                max_wait_time = 300  # 5 minutes
                check_interval = 5
                elapsed_time = 0

                # Check initial status
                initial_status = await processor.get_profile_processing_status(profile_id)
                logger.info(f"[PROCESSING] Job {job_id}: Initial status - Complete: {initial_status.get('overall_complete')}")

                if not initial_status.get('overall_complete'):
                    logger.info(f"[WAITING] Job {job_id}: Waiting for completion...")

                    while elapsed_time < max_wait_time:
                        try:
                            status = await processor.get_profile_processing_status(profile_id)

                            if status['overall_complete']:
                                logger.info(f"[COMPLETE] Job {job_id}: FULL Creator Analytics COMPLETE for @{username}")
                                break

                            # Update job progress
                            progress_percent = min(90, int((elapsed_time / max_wait_time) * 90))
                            await self._update_job_progress(job_id, progress_percent, status['current_stage'])

                            await asyncio.sleep(check_interval)
                            elapsed_time += check_interval

                        except Exception as status_error:
                            logger.warning(f"[WARNING] Job {job_id}: Status check error: {status_error}")
                            await asyncio.sleep(check_interval)
                            elapsed_time += check_interval

                if elapsed_time >= max_wait_time:
                    logger.warning(f"[TIMEOUT] Job {job_id}: Timeout after {max_wait_time}s")
                else:
                    logger.info(f"[SUCCESS] Job {job_id}: Creator fully processed in {elapsed_time}s")

        except Exception as e:
            logger.error(f"[ERROR] Job {job_id}: Creator analytics failed: {e}")
            # Continue anyway - don't fail the whole job

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        """Update job status in the database using raw asyncpg"""
        try:
            # Use raw asyncpg connection to avoid prepared statement issues
            await worker_db.update_job_status(
                job_id=job_id,
                status=status.value,
                result=result,
                error=error
            )
        except Exception as e:
            logger.error(f"[ERROR] Failed to update job {job_id} status: {e}")

    async def _update_job_progress(self, job_id: str, progress_percent: int, current_stage: str):
        """Update job progress for status polling using raw asyncpg"""
        try:
            # Use raw asyncpg connection to avoid prepared statement issues
            await worker_db.update_job_progress(
                job_id=job_id,
                progress_percent=progress_percent,
                current_stage=current_stage
            )
        except Exception as e:
            logger.warning(f"[WARNING] Failed to update job {job_id} progress: {e}")


# Global worker instance
post_analytics_worker = PostAnalyticsWorker()


async def start_post_analytics_worker():
    """Start the post analytics worker as a background task"""
    logger.info("[INIT] Starting Post Analytics Worker...")
    asyncio.create_task(post_analytics_worker.start())