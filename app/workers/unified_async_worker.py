"""
Unified Async Worker - In-Process Background Job Processor

Runs on a DEDICATED THREAD with its own asyncio event loop and its own
asyncpg database pool, so heavy job processing never blocks FastAPI's
main event loop. This is the same isolation model that Celery provides
(each task gets its own loop), without the subprocess overhead.

Polls the job_queue table directly via raw asyncpg and dispatches to the
existing _process_*_async(job_id) functions from unified_worker.py.
"""

import asyncio
import logging
import threading
from typing import Dict, Any, Optional

from app.workers.worker_database import WorkerDatabase

logger = logging.getLogger(__name__)

# Maximum number of jobs processed concurrently
MAX_CONCURRENT_JOBS = 3

# Seconds between polls when the queue is empty
POLL_INTERVAL = 2

# Job types handled by PostAnalyticsWorker - we must NOT claim these
POST_ANALYTICS_WORKER_TYPES = {'post_analytics_campaign'}


class UnifiedAsyncWorker:
    """
    In-process async worker for ALL job types except post_analytics_campaign.
    Runs on a dedicated background thread with its own event loop and DB pool.
    """

    JOB_TYPE_HANDLERS = {
        'profile_analysis': '_process_profile_analysis_async',
        'profile_analysis_background': '_process_profile_analysis_background_async',
        'creator_search': '_process_creator_search_async',
        'post_analysis': '_process_post_analysis_async',
        'batch_post_analysis': '_process_batch_post_analysis_async',
        'post_analytics_campaign': '_process_post_analytics_campaign_async',
        'bulk_analysis': '_process_bulk_analysis_async',
        'discovery_unlock': '_process_discovery_unlock_async',
        'bulk_unlock': '_process_bulk_unlock_async',
        'campaign_export': '_process_campaign_export_async',
        'imd_creator_analytics': '_process_imd_analytics_async',
    }

    def __init__(self):
        self.running = False
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_tasks: set = set()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Own DB pool - NOT shared with PostAnalyticsWorker on the main loop
        self._db: Optional[WorkerDatabase] = None
        logger.info("[INIT] Unified Async Worker initialized")

    async def start(self):
        """
        Launch the worker on a SEPARATE THREAD with its own event loop.
        Called from FastAPI's lifespan, but all heavy work happens on the
        dedicated thread so HTTP requests are never blocked.
        """
        self.running = True
        self._thread = threading.Thread(
            target=self._run_in_thread,
            name="unified-async-worker",
            daemon=True,
        )
        self._thread.start()

    def _run_in_thread(self):
        """Entry point for the worker thread - creates its own event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            logger.error(f"[UNIFIED-WORKER] Thread crashed: {e}")
        finally:
            # Clean up our own DB pool
            if self._db and self._db.pool:
                self._loop.run_until_complete(self._db.close())
            self._loop.close()

    async def _main_loop(self):
        """Actual async main loop running on the worker thread's own event loop."""
        # Initialize our own asyncpg pool on THIS thread's event loop
        self._db = WorkerDatabase()
        await self._db.initialize()
        logger.info("[UNIFIED-WORKER] Dedicated DB pool initialized on worker thread")

        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

        await self._cleanup_stuck_jobs()

        logger.info(
            f"[SUCCESS] Unified Async Worker started on dedicated thread "
            f"(concurrency={MAX_CONCURRENT_JOBS}, poll={POLL_INTERVAL}s)"
        )

        polls_since_cleanup = 0
        # Run periodic cleanup every ~5 minutes (150 polls * 2s)
        CLEANUP_INTERVAL_POLLS = 150

        while self.running:
            try:
                # Only poll if we have capacity
                if self._semaphore._value > 0:  # noqa: SLF001
                    job = await self._get_next_job()
                    if job:
                        task = asyncio.create_task(self._run_with_semaphore(job))
                        self._active_tasks.add(task)
                        task.add_done_callback(self._active_tasks.discard)
                        continue  # immediately try to grab another job

                # Periodic stuck-job cleanup (catches jobs orphaned by server kills)
                polls_since_cleanup += 1
                if polls_since_cleanup >= CLEANUP_INTERVAL_POLLS:
                    polls_since_cleanup = 0
                    await self._cleanup_stuck_jobs()
                    # Also clean up stale IMD analytics jobs
                    try:
                        import app.workers.unified_worker as uw
                        await uw.cleanup_stale_imd_analytics()
                    except Exception as e:
                        logger.warning(f"[UNIFIED-WORKER] IMD stale cleanup failed: {e}")

                # Nothing to do or at capacity - sleep briefly
                await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                logger.error(f"[UNIFIED-WORKER] Loop error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Graceful shutdown - let in-flight jobs finish."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=30)
        logger.info("[UNIFIED-WORKER] Stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _cleanup_stuck_jobs(self):
        """Reset jobs stuck in 'processing' for over 5 minutes back to 'queued'.

        When the server is killed, no worker can be processing these jobs anymore.
        5 minutes is safe — real jobs typically finish or fail well within that window,
        and a killed server means zero live workers.
        """
        try:
            result = await self._db.execute_query("""
                UPDATE job_queue
                SET status = 'queued',
                    started_at = NULL,
                    progress_message = 'Reset after unified worker restart'
                WHERE status = 'processing'
                AND started_at < NOW() - INTERVAL '5 minutes'
                AND job_type != 'post_analytics_campaign'
                RETURNING id, job_type
            """)
            if result:
                logger.info(f"[CLEANUP] Reset {len(result)} stuck jobs")
                for row in result:
                    logger.info(f"  - Reset job {row['id']} ({row['job_type']})")
            else:
                logger.info("[CLEANUP] No stuck jobs found")
        except Exception as e:
            logger.error(f"[CLEANUP] Failed: {e}")

    async def _get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Poll job_queue for the next queued job (excluding post_analytics_campaign).
        Atomically claims it by setting status='processing'.
        Uses FOR UPDATE SKIP LOCKED for safe concurrent access.
        """
        return await self._db.get_next_unified_job(
            exclude_types=list(POST_ANALYTICS_WORKER_TYPES)
        )

    async def _run_with_semaphore(self, job: Dict[str, Any]):
        """Acquire a concurrency slot, process the job, release."""
        async with self._semaphore:
            await self._process_job(job)

    async def _process_job(self, job: Dict[str, Any]):
        """
        Dispatch to the correct _process_*_async(job_id) function.
        Handles retries (up to 3) on failure.
        """
        job_id = job['id']
        job_type = job['job_type']
        retry_count = job.get('retry_count', 0)
        max_retries = 3

        handler_name = self.JOB_TYPE_HANDLERS.get(job_type)
        if not handler_name:
            logger.error(f"[UNIFIED-WORKER] Unknown job type: {job_type} (job {job_id})")
            await self._db.update_job_status(
                job_id, 'failed', error=f"Unknown job type: {job_type}"
            )
            return

        logger.info(f"[UNIFIED-WORKER] Processing {job_type} job {job_id} (retry={retry_count})")

        try:
            # Import the handler function from unified_worker module
            import app.workers.unified_worker as uw_module
            handler_fn = getattr(uw_module, handler_name)

            # Call the async handler - it manages its own DB sessions via
            # optimized_pools, which creates new connections on the current
            # event loop (this thread's loop, not the main FastAPI loop)
            await handler_fn(job_id)

            logger.info(f"[UNIFIED-WORKER] Completed {job_type} job {job_id}")

        except Exception as e:
            logger.error(f"[UNIFIED-WORKER] Job {job_id} ({job_type}) failed: {e}")

            if retry_count < max_retries:
                logger.info(
                    f"[UNIFIED-WORKER] Re-queuing job {job_id} for retry "
                    f"({retry_count + 1}/{max_retries})"
                )
                try:
                    await self._db.execute_query("""
                        UPDATE job_queue
                        SET status = 'queued',
                            retry_count = retry_count + 1,
                            started_at = NULL,
                            progress_message = $1
                        WHERE id = $2::uuid
                    """, f"Retry {retry_count + 1}/{max_retries}: {str(e)[:200]}", job_id)
                except Exception as retry_err:
                    logger.error(f"[UNIFIED-WORKER] Failed to re-queue job {job_id}: {retry_err}")
            else:
                try:
                    await self._db.update_job_status(
                        job_id, 'failed',
                        error=f"Failed after {max_retries} retries: {str(e)[:500]}"
                    )
                except Exception:
                    pass

    def is_running(self) -> bool:
        return self.running

    def get_status(self) -> Dict[str, Any]:
        return {
            'running': self.running,
            'active_jobs': len(self._active_tasks),
            'max_concurrent': MAX_CONCURRENT_JOBS,
        }


# Global singleton
unified_async_worker = UnifiedAsyncWorker()
