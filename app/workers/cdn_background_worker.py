"""
CDN Background Worker - Celery-based background processing for image thumbnails
Handles CDN image processing tasks asynchronously to prevent blocking main API
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, text

from app.database.connection import get_database_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app (matching AI worker pattern exactly)
celery_app = Celery(
    'cdn_background_worker',
    broker='redis://localhost:6379/0',  # Redis as message broker
    backend='redis://localhost:6379/0'  # Redis as result backend
)

# Celery configuration for production (matching AI worker exactly)
celery_app.conf.update(
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
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
)

# Database setup for background tasks (matching AI worker pattern)
engine = None
async_session_factory = None

def get_async_engine():
    """Get or create async database engine"""
    global engine
    if engine is None:
        database_url = get_database_url()
        # Convert to async URL if needed
        if not database_url.startswith('postgresql+asyncpg'):
            database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return engine

def get_async_session_factory():
    """Get or create async session factory"""
    global async_session_factory
    if async_session_factory is None:
        engine = get_async_engine()
        async_session_factory = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return async_session_factory

@celery_app.task(bind=True, name='cdn_worker.process_image_job')
def process_cdn_image_job(self, job_id: str) -> Dict[str, Any]:
    """
    Background task to process CDN image thumbnail generation
    
    Args:
        job_id: UUID of the CDN image job
        
    Returns:
        Processing results
    """
    task_id = self.request.id
    logger.info(f"🎬 Starting CDN image processing task {task_id} for job {job_id}")
    
    try:
        # Run the async processing in the background thread
        result = asyncio.run(_async_process_cdn_image_job(job_id, task_id))
        
        logger.info(f"[SUCCESS] CDN processing task {task_id} completed for job {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] CDN processing task {task_id} failed for job {job_id}: {e}")
        
        # Retry on failure (Celery will handle this based on configuration)
        raise self.retry(exc=e, countdown=60, max_retries=3)

async def _async_process_cdn_image_job(job_id: str, task_id: str) -> Dict[str, Any]:
    """Async implementation of CDN image processing"""
    session_factory = get_async_session_factory()
    
    async with session_factory() as db:
        try:
            # Get job details
            job_query = """
                SELECT id, profile_id, instagram_url, original_filename, 
                       target_format, target_size, priority_level, max_retries
                FROM cdn_image_jobs 
                WHERE id = :job_id AND status = 'queued'
            """
            
            job_result = await db.execute(text(job_query), {'job_id': job_id})
            job = job_result.fetchone()
            
            if not job:
                return {
                    "success": False,
                    "error": "Job not found or not in queued status",
                    "job_id": job_id
                }
            
            logger.info(f"Task {task_id}: Processing job {job_id} for profile {job.profile_id}")
            
            # Update job status to processing
            await db.execute(
                text("""
                    UPDATE cdn_image_jobs 
                    SET status = 'processing', started_at = :now, worker_id = :worker_id
                    WHERE id = :job_id
                """),
                {
                    'job_id': job_id,
                    'now': datetime.now(timezone.utc),
                    'worker_id': task_id
                }
            )
            
            # Import services here to avoid circular imports
            from app.infrastructure.r2_storage_client import R2StorageClient
            from app.services.image_transcoder_service import ImageTranscoderService
            
            # Initialize services
            r2_client = R2StorageClient()
            transcoder = ImageTranscoderService()
            
            # Download and process image
            logger.info(f"Task {task_id}: Downloading image from {job.instagram_url}")
            
            # Process the image (download, resize, upload to R2)
            processed_result = await transcoder.process_instagram_image(
                instagram_url=job.instagram_url,
                target_format=job.target_format or 'webp',
                target_size=job.target_size or (400, 400),
                original_filename=job.original_filename
            )
            
            if processed_result.get("success"):
                # Upload to R2 storage
                r2_key = f"thumbnails/{job.profile_id}/{processed_result['filename']}"
                
                upload_result = await r2_client.upload_image(
                    key=r2_key,
                    image_data=processed_result["image_data"],
                    content_type=processed_result["content_type"]
                )
                
                if upload_result.get("success"):
                    # Generate CDN URL
                    cdn_url = f"https://cdn.following.ae/{r2_key}"
                    
                    # Update job as completed with CDN URL
                    await db.execute(
                        text("""
                            UPDATE cdn_image_jobs 
                            SET status = 'completed', 
                                completed_at = :now,
                                cdn_url = :cdn_url,
                                file_size = :file_size,
                                r2_key = :r2_key
                            WHERE id = :job_id
                        """),
                        {
                            'job_id': job_id,
                            'now': datetime.now(timezone.utc),
                            'cdn_url': cdn_url,
                            'file_size': processed_result.get("file_size", 0),
                            'r2_key': r2_key
                        }
                    )
                    
                    # Create asset record
                    await db.execute(
                        text("""
                            INSERT INTO cdn_image_assets 
                            (profile_id, original_url, cdn_url, r2_key, file_format, 
                             file_size, image_width, image_height, created_at)
                            VALUES (:profile_id, :original_url, :cdn_url, :r2_key, 
                                   :file_format, :file_size, :width, :height, :now)
                            ON CONFLICT (profile_id, original_url) DO UPDATE SET
                                cdn_url = EXCLUDED.cdn_url,
                                r2_key = EXCLUDED.r2_key,
                                updated_at = :now
                        """),
                        {
                            'profile_id': job.profile_id,
                            'original_url': job.instagram_url,
                            'cdn_url': cdn_url,
                            'r2_key': r2_key,
                            'file_format': job.target_format or 'webp',
                            'file_size': processed_result.get("file_size", 0),
                            'width': processed_result.get("width", 400),
                            'height': processed_result.get("height", 400),
                            'now': datetime.now(timezone.utc)
                        }
                    )
                    
                    await db.commit()
                    
                    logger.info(f"Task {task_id}: Successfully processed job {job_id} -> {cdn_url}")
                    
                    return {
                        "success": True,
                        "job_id": job_id,
                        "cdn_url": cdn_url,
                        "file_size": processed_result.get("file_size", 0),
                        "processing_time": (datetime.now(timezone.utc) - datetime.fromisoformat(task_id.split('-')[0] if '-' in task_id else '2025-01-01')).total_seconds()
                    }
                else:
                    raise Exception(f"R2 upload failed: {upload_result.get('error', 'Unknown error')}")
            else:
                raise Exception(f"Image processing failed: {processed_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Task {task_id}: Processing error for job {job_id}: {e}")
            
            # Update job as failed
            await db.execute(
                text("""
                    UPDATE cdn_image_jobs 
                    SET status = 'failed', 
                        completed_at = :now,
                        error_message = :error,
                        retry_count = retry_count + 1
                    WHERE id = :job_id
                """),
                {
                    'job_id': job_id,
                    'now': datetime.now(timezone.utc),
                    'error': str(e)[:500]  # Truncate long errors
                }
            )
            
            await db.commit()
            raise e

@celery_app.task(bind=True, name='cdn_worker.health_check')
def health_check(self):
    """Health check task for monitoring"""
    try:
        # Test database connection
        health_status = asyncio.run(_async_health_check())
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": health_status,
            "worker_id": self.request.hostname
        }
    except Exception as e:
        logger.error(f"CDN worker health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

async def _async_health_check() -> Dict[str, Any]:
    """Async health check implementation"""
    session_factory = get_async_session_factory()
    
    async with session_factory() as db:
        # Simple database connectivity test
        result = await db.execute(text("SELECT 1"))
        test_value = result.scalar()
        
        return {
            "database_connected": test_value == 1,
            "engine_pool_size": engine.pool.size() if engine else 0
        }

# Task routing configuration (matching AI worker pattern)
celery_app.conf.task_routes = {
    'cdn_worker.process_image_job': {'queue': 'cdn_processing'},
    'cdn_worker.health_check': {'queue': 'health_checks'}
}

if __name__ == '__main__':
    # Start worker for testing: celery -A cdn_background_worker worker --loglevel=info
    celery_app.start()