"""
CDN Processing Tasks
Celery tasks for background image processing and CDN management
"""
import asyncio
import logging
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.database.connection import async_engine
from app.infrastructure.r2_storage_client import R2StorageClient
from app.services.cdn_image_service import CDNImageService
from app.services.image_transcoder_service import ImageTranscoderService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery app for CDN processing
app = Celery(
    'cdn_processing',
    broker='redis://localhost:6379/0',  # Direct Redis URL like AI worker
    backend='redis://localhost:6379/0'  # Direct Redis URL like AI worker
)

# Celery configuration optimized for image processing (matching working AI worker config)
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,  # Don't prefetch too many tasks
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_default_retry_delay=60,  # 1 minute retry delay
    task_max_retries=3,
    # Performance tuning
    worker_concurrency=2,  # Limit concurrent tasks to prevent memory issues
    worker_max_tasks_per_child=50  # Restart worker after 50 tasks to prevent memory leaks
)

# Global service instances (initialized in tasks)
r2_client = None
transcoder_service = None

def get_services():
    """Initialize global service instances"""
    global r2_client, transcoder_service
    
    if r2_client is None:
        r2_client = R2StorageClient(
            account_id=settings.CF_ACCOUNT_ID,
            access_key=settings.R2_ACCESS_KEY_ID,
            secret_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME
        )
    
    if transcoder_service is None:
        transcoder_service = ImageTranscoderService(r2_client)
    
    return r2_client, transcoder_service

async def get_db_session() -> AsyncSession:
    """Get database session for async operations"""
    from app.database.connection import init_database, get_session
    
    # Initialize database if not already done
    await init_database()
    
    # Use the existing get_session context manager
    return get_session()

@app.task(bind=True, name="process_cdn_image_job")
def process_cdn_image_job(self, job_id: str):
    """Process a single CDN image job"""
    return asyncio.run(_process_cdn_image_job_async(self, job_id))

async def _process_cdn_image_job_async(task_self, job_id: str):
    """Async implementation of CDN image job processing"""
    try:
        logger.info(f"[TRIGGER] Starting CDN job {job_id}")
        
        # Initialize services
        r2_client, transcoder = get_services()
        
        # Get database session using context manager approach
        from app.database.connection import init_database, get_session
        await init_database()
        
        # Create session directly with async context
        async with get_session() as db_session:
            # Get job from database
            job_sql = """
            SELECT j.*, a.source_id as profile_id, a.media_id, a.source_url
            FROM cdn_image_jobs j
            JOIN cdn_image_assets a ON j.asset_id = a.id
            WHERE j.id = :job_id
            """
            
            result = await db_session.execute(text(job_sql), {'job_id': job_id})
            job = result.fetchone()
            
            if not job:
                logger.error(f"[ERROR] Job {job_id} not found")
                return {'success': False, 'error': 'Job not found'}
            
            # Update job status to processing
            update_job_sql = """
            UPDATE cdn_image_jobs 
            SET status = 'processing', 
                started_at = NOW(),
                worker_id = :worker_id
            WHERE id = :job_id
            """
            await db_session.execute(
                text(update_job_sql), 
                {'job_id': job_id, 'worker_id': task_self.request.id}
            )
            await db_session.commit()
            
            # Prepare job data for transcoder
            job_data = {
                'asset_id': str(job.asset_id),
                'source_url': job.source_url,
                'target_sizes': job.target_sizes or [256, 512],
                'profile_id': str(job.profile_id),
                'media_id': job.media_id
            }
            
            # Process the image
            processing_result = await transcoder.process_job(job_data)
            
            if processing_result.success:
                # Update asset record with results
                await _update_asset_with_results(
                    db_session, job.asset_id, processing_result
                )
                
                # Update job status to completed
                complete_job_sql = """
                        UPDATE cdn_image_jobs 
                    SET status = 'completed', 
                        completed_at = NOW(),
                        processing_duration_ms = :duration
                    WHERE id = :job_id
                """
                await db_session.execute(
                    text(complete_job_sql),
                    {
                        'job_id': job_id,
                        'duration': (processing_result.processing_stats or {}).get('total_time_ms', 0)
                    }
                )
                await db_session.commit()
                
                logger.info(f"[SUCCESS] Job {job_id} completed successfully")
                return {
                    'success': True,
                    'processing_stats': processing_result.processing_stats,
                    'derivatives': list(processing_result.derivatives.keys())
                }
            
            else:
                # Handle failure
                await _handle_job_failure(db_session, job_id, processing_result.error)
                
                logger.error(f"[ERROR] Job {job_id} failed: {processing_result.error}")
                return {'success': False, 'error': processing_result.error}
    
    except Exception as e:
        logger.error(f"[ERROR] CDN job {job_id} processing failed: {e}")
        return {'success': False, 'error': str(e)}

async def _update_asset_with_results(db_session: AsyncSession, asset_id: UUID, result):
    """Update asset record with processing results"""
    try:
        derivatives = result.derivatives
        stats = result.processing_stats
        
        # Build CDN URLs
        cdn_url_256 = derivatives.get(256, {}).get('cdn_url')
        cdn_url_512 = derivatives.get(512, {}).get('cdn_url')
        cdn_path_256 = derivatives.get(256, {}).get('path')
        cdn_path_512 = derivatives.get(512, {}).get('path')
        
        update_sql = """
            UPDATE cdn_image_assets 
            SET 
                processing_status = 'completed',
                processing_completed_at = NOW(),
                cdn_url_256 = :cdn_url_256,
                cdn_url_512 = :cdn_url_512,
                cdn_path_256 = :cdn_path_256,
                cdn_path_512 = :cdn_path_512,
                content_hash_256 = :hash_256,
                content_hash_512 = :hash_512,
                file_size_256 = :size_256,
                file_size_512 = :size_512,
                download_time_ms = :download_time,
                processing_time_ms = :processing_time,
                upload_time_ms = :upload_time,
                total_processing_time_ms = :total_time,
                original_file_size = :original_size,
                output_format = 'webp',
                updated_at = NOW()
            WHERE id = :asset_id
        """
        
        await db_session.execute(
            text(update_sql),
            {
                'asset_id': asset_id,
                'cdn_url_256': cdn_url_256,
                'cdn_url_512': cdn_url_512,
                'cdn_path_256': cdn_path_256,
                'cdn_path_512': cdn_path_512,
                'hash_256': derivatives.get(256, {}).get('content_hash'),
                'hash_512': derivatives.get(512, {}).get('content_hash'),
                'size_256': derivatives.get(256, {}).get('file_size'),
                'size_512': derivatives.get(512, {}).get('file_size'),
                'download_time': stats.get('download_time_ms'),
                'processing_time': stats.get('processing_time_ms'),
                'upload_time': stats.get('upload_time_ms'),
                'total_time': stats.get('total_time_ms'),
                'original_size': stats.get('original_size_bytes')
            }
        )
        
        await db_session.commit()
        logger.debug(f"[SUCCESS] Asset {asset_id} updated with processing results")
        
    except Exception as e:
        await db_session.rollback()
        logger.error(f"[ERROR] Failed to update asset {asset_id}: {e}")
        raise

async def _handle_job_failure(db_session: AsyncSession, job_id: str, error_message: str):
    """Handle job failure with retry logic"""
    try:
        # Increment retry count and update status
        failure_sql = """
            UPDATE cdn_image_jobs 
            SET 
                status = 'failed',
                retry_count = retry_count + 1,
                error_message = :error_message,
                completed_at = NOW()
            WHERE id = :job_id
        """
        
        await db_session.execute(
            text(failure_sql),
            {'job_id': job_id, 'error_message': error_message}
        )
        
        # Also update the associated asset
        asset_failure_sql = """
            UPDATE cdn_image_assets 
            SET 
                processing_status = 'failed',
                processing_attempts = processing_attempts + 1,
                processing_error = :error_message,
                updated_at = NOW()
            WHERE id = (
                SELECT asset_id FROM cdn_image_jobs WHERE id = :job_id
            )
        """
        
        await db_session.execute(
            text(asset_failure_sql),
            {'job_id': job_id, 'error_message': error_message}
        )
        
        await db_session.commit()
        
    except Exception as e:
        await db_session.rollback()
        logger.error(f"[ERROR] Failed to handle job failure for {job_id}: {e}")
        raise

@app.task(bind=True, name="batch_enqueue_profile_assets")
def batch_enqueue_profile_assets(self, profile_data_list: List[Dict]):
    """Batch enqueue multiple profiles for CDN processing"""
    return asyncio.run(_batch_enqueue_profile_assets_async(profile_data_list))

async def _batch_enqueue_profile_assets_async(profile_data_list: List[Dict]):
    """Async implementation of batch profile asset enqueueing"""
    db_session = None
    results = []
    
    try:
        # Initialize services
        r2_client, _ = get_services()
        db_session = await get_db_session()
        cdn_service = CDNImageService()
        cdn_service.set_db_session(db_session)
        
        logger.info(f"📦 Batch processing {len(profile_data_list)} profiles")
        
        for profile_data in profile_data_list:
            try:
                profile_id = UUID(profile_data['profile_id'])
                apify_data = profile_data['apify_data']
                
                result = await cdn_service.enqueue_profile_assets(profile_id, apify_data)
                
                results.append({
                    'profile_id': profile_data['profile_id'],
                    'success': result.success,
                    'jobs_created': result.jobs_created,
                    'message': result.message if result.success else result.error
                })
                
            except Exception as e:
                results.append({
                    'profile_id': profile_data.get('profile_id', 'unknown'),
                    'success': False,
                    'jobs_created': 0,
                    'error': str(e)
                })
        
        successful = len([r for r in results if r['success']])
        failed = len(results) - successful
        total_jobs = sum(r['jobs_created'] for r in results)
        
        logger.info(f"[SUCCESS] Batch completed: {successful}/{len(results)} profiles, {total_jobs} jobs created")
        
        return {
            'total_profiles': len(profile_data_list),
            'successful': successful,
            'failed': failed,
            'total_jobs_created': total_jobs,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Batch enqueue failed: {e}")
        return {'error': str(e)}
    
    finally:
        if db_session:
            await db_session.close()

@app.task(bind=True, name="cleanup_failed_jobs")
def cleanup_failed_jobs(self):
    """Clean up old failed jobs and retry eligible ones"""
    return asyncio.run(_cleanup_failed_jobs_async())

async def _cleanup_failed_jobs_async():
    """Async implementation of failed job cleanup"""
    db_session = None
    
    try:
        db_session = await get_db_session()
        
        # Find jobs eligible for retry (failed < 24 hours ago, retry_count < max_retries)
        retry_eligible_sql = """
            SELECT id FROM cdn_image_jobs
            WHERE status = 'failed'
            AND retry_count < max_retries
            AND created_at > NOW() - INTERVAL '24 hours'
        """
        
        result = await db_session.execute(text(retry_eligible_sql))
        eligible_jobs = [row[0] for row in result.fetchall()]
        
        retry_count = 0
        for job_id in eligible_jobs:
            # Reset job status for retry
            retry_sql = """
                UPDATE cdn_image_jobs 
                SET status = 'queued', 
                    started_at = NULL,
                    completed_at = NULL,
                    worker_id = NULL,
                    error_message = NULL
                WHERE id = :job_id
            """
            await db_session.execute(text(retry_sql), {'job_id': job_id})
            
            # Enqueue for processing
            process_cdn_image_job.delay(str(job_id))
            retry_count += 1
        
        # Clean up old failed jobs (> 7 days old, max retries exceeded)
        cleanup_sql = """
            DELETE FROM cdn_image_jobs
            WHERE status = 'failed'
            AND (
                retry_count >= max_retries 
                OR created_at < NOW() - INTERVAL '7 days'
            )
        """
        
        cleanup_result = await db_session.execute(text(cleanup_sql))
        cleanup_count = cleanup_result.rowcount
        
        await db_session.commit()
        
        logger.info(f"🧹 Cleanup completed: {retry_count} jobs retried, {cleanup_count} jobs removed")
        
        return {
            'retried_jobs': retry_count,
            'cleaned_up_jobs': cleanup_count,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Job cleanup failed: {e}")
        if db_session:
            await db_session.rollback()
        return {'error': str(e)}
    
    finally:
        if db_session:
            await db_session.close()

@app.task(bind=True, name="generate_processing_stats")
def generate_processing_stats(self):
    """Generate hourly processing statistics"""
    return asyncio.run(_generate_processing_stats_async())

async def _generate_processing_stats_async():
    """Async implementation of processing stats generation"""
    db_session = None
    
    try:
        db_session = await get_db_session()
        
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # Calculate stats for the current hour
        stats_sql = """
            SELECT 
                COUNT(CASE WHEN j.status = 'completed' AND j.completed_at >= :hour_start THEN 1 END) as jobs_processed,
                COUNT(CASE WHEN j.status = 'failed' AND j.completed_at >= :hour_start THEN 1 END) as jobs_failed,
                AVG(CASE WHEN j.processing_duration_ms IS NOT NULL THEN j.processing_duration_ms END) as avg_processing_time,
                MAX(
                    SELECT COUNT(*) FROM cdn_image_jobs 
                    WHERE status IN ('queued', 'processing')
                ) as peak_queue_depth
            FROM cdn_image_jobs j
            WHERE j.completed_at >= :hour_start
        """
        
        result = await db_session.execute(
            text(stats_sql), 
            {'hour_start': current_hour}
        )
        stats = result.fetchone()
        
        # Insert or update hourly stats
        upsert_stats_sql = """
            INSERT INTO cdn_processing_stats (
                date, hour, jobs_processed, jobs_failed, 
                avg_processing_time_ms, peak_queue_depth
            ) VALUES (
                :date, :hour, :jobs_processed, :jobs_failed,
                :avg_processing_time, :peak_queue_depth
            )
            ON CONFLICT (date, hour) 
            DO UPDATE SET 
                jobs_processed = EXCLUDED.jobs_processed,
                jobs_failed = EXCLUDED.jobs_failed,
                avg_processing_time_ms = EXCLUDED.avg_processing_time_ms,
                peak_queue_depth = EXCLUDED.peak_queue_depth,
                updated_at = NOW()
        """
        
        await db_session.execute(
            text(upsert_stats_sql),
            {
                'date': current_hour.date(),
                'hour': current_hour.hour,
                'jobs_processed': stats.jobs_processed or 0,
                'jobs_failed': stats.jobs_failed or 0,
                'avg_processing_time': int(stats.avg_processing_time or 0),
                'peak_queue_depth': stats.peak_queue_depth or 0
            }
        )
        
        await db_session.commit()
        
        logger.info(f"[STATS] Generated stats for {current_hour}: {stats.jobs_processed} processed")
        
        return {
            'hour': current_hour.isoformat(),
            'jobs_processed': stats.jobs_processed or 0,
            'jobs_failed': stats.jobs_failed or 0,
            'success_rate': round(
                (stats.jobs_processed / (stats.jobs_processed + stats.jobs_failed) * 100) 
                if (stats.jobs_processed + stats.jobs_failed) > 0 else 0, 1
            ),
            'avg_processing_time_ms': int(stats.avg_processing_time or 0)
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Stats generation failed: {e}")
        if db_session:
            await db_session.rollback()
        return {'error': str(e)}
    
    finally:
        if db_session:
            await db_session.close()

@app.task(bind=True, name="nightly_freshness_check")
def nightly_freshness_check(self):
    """Check for updated Apify URLs and mark for refresh"""
    return asyncio.run(_nightly_freshness_check_async())

async def _nightly_freshness_check_async():
    """Async implementation of nightly freshness check"""
    db_session = None
    
    try:
        logger.info("🌙 Starting nightly freshness check")
        
        db_session = await get_db_session()
        
        # Mark assets older than 24 hours for freshness check
        mark_stale_sql = """
            UPDATE cdn_image_assets 
            SET needs_update = true, last_checked = NOW()
            WHERE last_checked < NOW() - INTERVAL '24 hours'
            AND processing_status = 'completed'
        """
        
        result = await db_session.execute(text(mark_stale_sql))
        marked_count = result.rowcount
        
        await db_session.commit()
        
        logger.info(f"[SUCCESS] Marked {marked_count} assets for freshness check")
        
        return {
            'marked_for_refresh': marked_count,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Nightly freshness check failed: {e}")
        if db_session:
            await db_session.rollback()
        return {'error': str(e)}
    
    finally:
        if db_session:
            await db_session.close()

# Periodic task scheduling
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Generate stats every hour at minute 5
    'generate-hourly-stats': {
        'task': 'generate_processing_stats',
        'schedule': crontab(minute=5),
    },
    
    # Clean up failed jobs every 6 hours
    'cleanup-failed-jobs': {
        'task': 'cleanup_failed_jobs',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    
    # Nightly freshness check at 2 AM
    'nightly-freshness-check': {
        'task': 'nightly_freshness_check',
        'schedule': crontab(minute=0, hour=2),
    },
}

# Task routing configuration
app.conf.task_routes = {
    'process_cdn_image_job': {'queue': 'cdn_processing'},
    'batch_enqueue_profile_assets': {'queue': 'cdn_processing'},
    'generate_processing_stats': {'queue': 'cdn_maintenance'},
    'cleanup_failed_jobs': {'queue': 'cdn_maintenance'},
    'nightly_freshness_check': {'queue': 'cdn_maintenance'}
}

if __name__ == '__main__':
    app.start()