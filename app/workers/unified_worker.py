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
        'unified_worker.process_profile_analysis': {'queue': 'high_priority'},
        'unified_worker.process_profile_analysis_background': {'queue': 'normal_priority'},
        'unified_worker.process_post_analysis': {'queue': 'cdn_processing'},
        'unified_worker.process_bulk_analysis': {'queue': 'bulk_processing'},
        'unified_worker.process_discovery_analysis': {'queue': 'discovery'},
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
                """), update_data)

                await session.commit()
                logger.info(f"Updated job {job_id} status to {status.value}")

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")

    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details from database"""
        try:
            async with optimized_pools.get_background_session() as session:
                result = await session.execute(text("""
                    SELECT id, user_id, job_type, params, status, priority, created_at
                    FROM job_queue WHERE id = :job_id
                """), {'job_id': job_id})

                job_data = result.fetchone()
                if not job_data:
                    return None

                return {
                    'id': job_data.id,
                    'user_id': job_data.user_id,
                    'job_type': job_data.job_type,
                    'params': json.loads(job_data.params) if job_data.params else {},
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
    user_id = job_details['user_id']

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
                """), {'profile_id': profile_id})

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
    """Async implementation of post analysis"""

    job_details = await job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"Job {job_id} not found")

    params = job_details['params']
    username = params.get('username')
    credit_cost = params.get('credit_cost', 5)
    user_id = job_details['user_id']

    # Update status
    await job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message=f"Starting post analysis for {username}"
    )

    try:
        # Deduct credits
        credit_deducted = await job_processor.deduct_credits(
            user_id,
            credit_cost,
            f"Post analysis for {username}"
        )

        if not credit_deducted:
            raise Exception("Failed to deduct credits")

        # Process posts (implementation would call PostAnalyticsService)
        await job_processor.update_job_status(
            job_id, JobStatus.PROCESSING,
            progress_percent=50,
            progress_message="Analyzing posts"
        )

        # TODO: Implement actual post analysis logic
        result = {
            'username': username,
            'posts_analyzed': 0,  # Placeholder
            'completion_time': datetime.now(timezone.utc).isoformat()
        }

        await job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Post analysis completed",
            result=result
        )

        return result

    except Exception as e:
        # Refund credits on failure
        try:
            await job_processor.credit_service.add_credits(
                user_id,
                credit_cost,
                f"Refund for failed post analysis of {username}"
            )
        except Exception:
            pass

        raise

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
    user_id = job_details['user_id']

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
    user_id = job_details['user_id']

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