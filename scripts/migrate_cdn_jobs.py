"""
Migrate existing CDN jobs to new robust worker system
"""
import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_async_session
from app.workers.cdn_background_worker import celery_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_queued_jobs():
    """Migrate existing queued CDN jobs to new worker system"""
    
    async with get_async_session() as db:
        try:
            # Get all queued jobs
            queued_query = """
                SELECT id, profile_id, instagram_url, status
                FROM cdn_image_jobs 
                WHERE status IN ('queued', 'failed')
                ORDER BY created_at ASC
            """
            
            result = await db.execute(text(queued_query))
            jobs = result.fetchall()
            
            if not jobs:
                logger.info("No queued or failed jobs found")
                return
            
            logger.info(f"Found {len(jobs)} jobs to migrate")
            
            # Reset all to queued status
            reset_query = """
                UPDATE cdn_image_jobs 
                SET status = 'queued',
                    started_at = NULL,
                    completed_at = NULL,
                    worker_id = NULL,
                    error_message = NULL
                WHERE id = ANY(:job_ids)
            """
            
            job_ids = [str(job.id) for job in jobs]
            await db.execute(text(reset_query), {'job_ids': job_ids})
            await db.commit()
            
            # Enqueue jobs with new worker
            successful_enqueues = 0
            for job in jobs:
                try:
                    # Send task to new robust worker
                    celery_app.send_task(
                        'cdn_worker.process_image_job',
                        args=[str(job.id)],
                        queue='cdn_processing'
                    )
                    
                    logger.info(f"Enqueued job {job.id} for profile {job.profile_id}")
                    successful_enqueues += 1
                    
                except Exception as e:
                    logger.error(f"Failed to enqueue job {job.id}: {e}")
            
            logger.info(f"Successfully migrated {successful_enqueues}/{len(jobs)} jobs to new worker")
            
            return {
                'total_jobs': len(jobs),
                'migrated_jobs': successful_enqueues,
                'success_rate': (successful_enqueues / len(jobs)) * 100
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise

async def verify_worker_health():
    """Verify new CDN worker is healthy"""
    try:
        # Test health check task
        health_result = celery_app.send_task(
            'cdn_worker.health_check',
            queue='health_checks'
        )
        
        # Wait for result with timeout
        result = health_result.get(timeout=10)
        
        logger.info(f"Worker health check: {result}")
        return result.get('status') == 'healthy'
        
    except Exception as e:
        logger.error(f"Worker health check failed: {e}")
        return False

async def main():
    """Main migration function"""
    logger.info("Starting CDN jobs migration to robust worker...")
    
    # Check worker health first
    logger.info("Verifying new worker health...")
    is_healthy = await verify_worker_health()
    
    if not is_healthy:
        logger.error("Worker health check failed - aborting migration")
        return
    
    logger.info("Worker is healthy - proceeding with migration")
    
    # Migrate jobs
    result = await migrate_queued_jobs()
    
    if result:
        logger.info("="*50)
        logger.info("MIGRATION COMPLETE")
        logger.info(f"Total jobs: {result['total_jobs']}")
        logger.info(f"Migrated: {result['migrated_jobs']}")
        logger.info(f"Success rate: {result['success_rate']:.1f}%")
        logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(main())