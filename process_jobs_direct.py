#!/usr/bin/env python3
"""
Process CDN jobs directly without Celery to test the pipeline
"""

import asyncio
import logging
from sqlalchemy import text
from app.database.connection import init_database, get_session
from app.tasks.cdn_processing_tasks import _process_cdn_image_job_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockTask:
    """Mock task object for direct processing"""
    def __init__(self):
        self.request = MockRequest()

class MockRequest:
    """Mock request object"""
    def __init__(self):
        self.id = 'direct-processing'

async def process_jobs_direct():
    """Process a few jobs directly to test the pipeline"""
    try:
        await init_database()
        
        async with get_session() as db:
            # Get some queued jobs
            result = await db.execute(text("SELECT id FROM cdn_image_jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 5"))
            job_ids = [str(row[0]) for row in result.fetchall()]
            
            logger.info(f"Found {len(job_ids)} queued jobs to process")
            
            mock_task = MockTask()
            results = []
            
            for job_id in job_ids:
                try:
                    logger.info(f"Processing job {job_id}")
                    result = await _process_cdn_image_job_async(mock_task, job_id)
                    results.append({
                        'job_id': job_id,
                        'success': result.get('success', False),
                        'error': result.get('error')
                    })
                    logger.info(f"Job {job_id} result: {result}")
                    
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {e}")
                    results.append({
                        'job_id': job_id,
                        'success': False,
                        'error': str(e)
                    })
            
            # Summary
            successful = len([r for r in results if r['success']])
            failed = len(results) - successful
            
            print(f"\n=== Processing Summary ===")
            print(f"Total jobs processed: {len(results)}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            
            if failed > 0:
                print("\nFailed jobs:")
                for result in results:
                    if not result['success']:
                        print(f"  {result['job_id']}: {result['error']}")
            
            return results
            
    except Exception as e:
        logger.error(f"Direct processing failed: {e}")
        return {'error': str(e)}

if __name__ == "__main__":
    asyncio.run(process_jobs_direct())