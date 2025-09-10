#!/usr/bin/env python3
"""
Restart CDN Workers and Process Queued Jobs
Ensures CDN processing pipeline is running correctly
"""

import asyncio
import logging
import subprocess
import sys
from typing import Dict, Any
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CDNWorkerManager:
    """Manage CDN worker processes and queue processing"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        
    async def check_redis_connection(self) -> bool:
        """Check if Redis is available"""
        try:
            import redis
            from app.core.config import settings
            
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            logger.info("[SUCCESS] Redis connection successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Redis connection failed: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics"""
        try:
            from app.database.connection import init_database, get_session
            from sqlalchemy import text
            
            await init_database()
            
            async with get_session() as db_session:
                stats_sql = """
                    SELECT 
                        COUNT(CASE WHEN status = 'queued' THEN 1 END) as queued,
                        COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                        COUNT(*) as total
                    FROM cdn_image_jobs
                """
                
                result = await db_session.execute(text(stats_sql))
                stats = result.fetchone()
                
                return {
                    'queued': stats.queued or 0,
                    'processing': stats.processing or 0,
                    'completed': stats.completed or 0,
                    'failed': stats.failed or 0,
                    'total': stats.total or 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {'error': str(e)}
    
    def start_celery_worker(self) -> bool:
        """Start Celery worker for CDN processing"""
        try:
            logger.info("[TRIGGER] Starting Celery worker for CDN processing")
            
            # Command to start Celery worker
            cmd = [
                sys.executable, "-m", "celery",
                "worker",
                "-A", "app.tasks.cdn_processing_tasks",
                "--loglevel=info",
                "--queues=cdn_processing",
                "--concurrency=2",
                "--max-tasks-per-child=50"
            ]
            
            # Start the worker process
            process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info(f"[SUCCESS] Celery worker started with PID: {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to start Celery worker: {e}")
            return False
    
    def start_celery_beat(self) -> bool:
        """Start Celery beat scheduler"""
        try:
            logger.info("[SCHEDULE] Starting Celery beat scheduler")
            
            cmd = [
                sys.executable, "-m", "celery",
                "beat",
                "-A", "app.tasks.cdn_processing_tasks",
                "--loglevel=info"
            ]
            
            process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info(f"[SUCCESS] Celery beat started with PID: {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to start Celery beat: {e}")
            return False
    
    async def process_queued_jobs_manually(self, limit: int = 10) -> Dict[str, Any]:
        """Manually process a few queued jobs to test the pipeline"""
        try:
            from app.database.connection import init_database, get_session
            from sqlalchemy import text
            from app.tasks.cdn_processing_tasks import process_cdn_image_job
            
            await init_database()
            
            results = {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            async with get_session() as db_session:
                # Get some queued jobs
                jobs_sql = """
                    SELECT id FROM cdn_image_jobs
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT :limit
                """
                
                result = await db_session.execute(text(jobs_sql), {'limit': limit})
                job_ids = [row[0] for row in result.fetchall()]
                
                logger.info(f"[REPAIR] Manually processing {len(job_ids)} queued jobs")
                
                for job_id in job_ids:
                    try:
                        # Process job directly (not through Celery)
                        job_result = process_cdn_image_job(str(job_id))
                        
                        if job_result.get('success'):
                            results['successful'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append({
                                'job_id': str(job_id),
                                'error': job_result.get('error', 'Unknown error')
                            })
                        
                        results['processed'] += 1
                        
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'job_id': str(job_id),
                            'error': str(e)
                        })
                        logger.error(f"Error processing job {job_id}: {e}")
            
            logger.info(f"[SUCCESS] Manual processing complete: {results['successful']} successful, {results['failed']} failed")
            return results
            
        except Exception as e:
            logger.error(f"[ERROR] Manual job processing failed: {e}")
            return {'error': str(e)}
    
    async def monitor_queue_processing(self, duration_seconds: int = 300):
        """Monitor queue processing for a specified duration"""
        logger.info(f"[MONITOR] Monitoring queue processing for {duration_seconds} seconds")
        
        import time
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            stats = await self.get_queue_stats()
            
            if 'error' not in stats:
                logger.info(
                    f"[STATS] Queue Stats: {stats['queued']} queued, "
                    f"{stats['processing']} processing, "
                    f"{stats['completed']} completed, "
                    f"{stats['failed']} failed"
                )
            
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
        
        logger.info("[SUCCESS] Monitoring complete")

async def main():
    """Main worker management function"""
    try:
        manager = CDNWorkerManager()
        
        # 1. Check Redis connection
        if not await manager.check_redis_connection():
            print("[ERROR] Redis not available. Please start Redis first.")
            return
        
        # 2. Get initial queue stats
        initial_stats = await manager.get_queue_stats()
        print(f"[STATS] Initial Queue Stats: {initial_stats}")
        
        # 3. Process a few jobs manually to test the pipeline
        if initial_stats.get('queued', 0) > 0:
            print("[TEST] Testing pipeline with manual job processing...")
            manual_results = await manager.process_queued_jobs_manually(limit=5)
            print(f"[TEST] Manual Processing Results: {manual_results}")
        
        # 4. Start Celery worker (optional - user should run this separately)
        print("\n[DOCS] To start the CDN processing workers, run these commands:")
        print("   celery -A app.tasks.cdn_processing_tasks worker --loglevel=info --queues=cdn_processing")
        print("   celery -A app.tasks.cdn_processing_tasks beat --loglevel=info")
        
        # 5. Get final stats
        final_stats = await manager.get_queue_stats()
        print(f"[STATS] Final Queue Stats: {final_stats}")
        
        print("[SUCCESS] CDN worker management completed!")
        
    except Exception as e:
        print(f"[ERROR] Worker management failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())