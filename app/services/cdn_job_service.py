"""
CDN Job Service - Interface for managing CDN image processing jobs
Provides clean interface between main application and CDN background worker
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.cdn_background_worker import celery_app

logger = logging.getLogger(__name__)

class CDNJobService:
    """Service for managing CDN image processing jobs"""
    
    @staticmethod
    async def enqueue_profile_images(db: AsyncSession, profile_id: str, image_urls: List[str]) -> Dict[str, Any]:
        """
        Enqueue multiple image processing jobs for a profile
        
        Args:
            db: Database session
            profile_id: Profile UUID
            image_urls: List of Instagram image URLs to process
            
        Returns:
            Enqueue results with job IDs
        """
        try:
            jobs_created = []
            jobs_skipped = []
            
            for url in image_urls:
                # Check if job already exists
                existing_query = """
                    SELECT id, status FROM cdn_image_jobs 
                    WHERE profile_id = :profile_id AND instagram_url = :url
                """
                existing_result = await db.execute(
                    text(existing_query), 
                    {'profile_id': profile_id, 'url': url}
                )
                existing_job = existing_result.fetchone()
                
                if existing_job and existing_job.status in ['queued', 'processing']:
                    jobs_skipped.append({
                        'url': url,
                        'job_id': str(existing_job.id),
                        'reason': f'Already {existing_job.status}'
                    })
                    continue
                
                # Create new job
                job_query = """
                    INSERT INTO cdn_image_jobs 
                    (profile_id, instagram_url, status, priority_level, target_format, 
                     target_size, max_retries, created_at)
                    VALUES (:profile_id, :url, 'queued', 'normal', 'webp', 
                           :target_size, 3, :now)
                    RETURNING id
                """
                
                job_result = await db.execute(
                    text(job_query),
                    {
                        'profile_id': profile_id,
                        'url': url,
                        'target_size': '400x400',
                        'now': datetime.now(timezone.utc)
                    }
                )
                
                job_id = job_result.scalar()
                
                # Enqueue for background processing
                celery_app.send_task(
                    'cdn_worker.process_image_job',
                    args=[str(job_id)],
                    queue='cdn_processing'
                )
                
                jobs_created.append({
                    'url': url,
                    'job_id': str(job_id)
                })
                
                logger.info(f"Enqueued CDN job {job_id} for profile {profile_id}: {url}")
            
            await db.commit()
            
            return {
                'success': True,
                'profile_id': profile_id,
                'jobs_created': len(jobs_created),
                'jobs_skipped': len(jobs_skipped),
                'created_jobs': jobs_created,
                'skipped_jobs': jobs_skipped,
                'total_urls': len(image_urls)
            }
            
        except Exception as e:
            logger.error(f"Failed to enqueue profile images for {profile_id}: {e}")
            await db.rollback()
            raise e
    
    @staticmethod
    async def get_profile_cdn_status(db: AsyncSession, profile_id: str) -> Dict[str, Any]:
        """
        Get CDN processing status for a profile
        
        Args:
            db: Database session
            profile_id: Profile UUID
            
        Returns:
            CDN status information
        """
        try:
            # Get job counts by status
            status_query = """
                SELECT 
                    status,
                    COUNT(*) as count
                FROM cdn_image_jobs 
                WHERE profile_id = :profile_id
                GROUP BY status
            """
            
            status_result = await db.execute(text(status_query), {'profile_id': profile_id})
            status_counts = {row.status: row.count for row in status_result.fetchall()}
            
            # Get completed CDN URLs
            assets_query = """
                SELECT 
                    original_url,
                    cdn_url,
                    file_size,
                    created_at
                FROM cdn_image_assets 
                WHERE profile_id = :profile_id
                ORDER BY created_at DESC
            """
            
            assets_result = await db.execute(text(assets_query), {'profile_id': profile_id})
            cdn_assets = [
                {
                    'original_url': row.original_url,
                    'cdn_url': row.cdn_url,
                    'file_size': row.file_size,
                    'created_at': row.created_at.isoformat() if row.created_at else None
                }
                for row in assets_result.fetchall()
            ]
            
            # Calculate processing stats
            total_jobs = sum(status_counts.values())
            completed_jobs = status_counts.get('completed', 0)
            processing_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            
            return {
                'profile_id': profile_id,
                'total_jobs': total_jobs,
                'status_breakdown': status_counts,
                'processing_rate': round(processing_rate, 1),
                'cdn_assets_count': len(cdn_assets),
                'cdn_assets': cdn_assets,
                'has_active_jobs': status_counts.get('queued', 0) + status_counts.get('processing', 0) > 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get CDN status for profile {profile_id}: {e}")
            raise e
    
    @staticmethod
    async def retry_failed_jobs(db: AsyncSession, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retry failed CDN processing jobs
        
        Args:
            db: Database session
            profile_id: Optional profile ID to retry (if None, retries all failed jobs)
            
        Returns:
            Retry results
        """
        try:
            # Build retry query
            retry_conditions = ["status = 'failed'", "retry_count < max_retries"]
            params = {}
            
            if profile_id:
                retry_conditions.append("profile_id = :profile_id")
                params['profile_id'] = profile_id
            
            retry_query = f"""
                SELECT id FROM cdn_image_jobs 
                WHERE {' AND '.join(retry_conditions)}
                ORDER BY created_at ASC
                LIMIT 50
            """
            
            retry_result = await db.execute(text(retry_query), params)
            failed_job_ids = [str(row.id) for row in retry_result.fetchall()]
            
            if not failed_job_ids:
                return {
                    'success': True,
                    'retried_jobs': 0,
                    'message': 'No failed jobs to retry'
                }
            
            # Reset job status to queued
            reset_query = """
                UPDATE cdn_image_jobs 
                SET status = 'queued', 
                    started_at = NULL,
                    completed_at = NULL,
                    worker_id = NULL,
                    error_message = NULL
                WHERE id = ANY(:job_ids)
            """
            
            await db.execute(text(reset_query), {'job_ids': failed_job_ids})
            
            # Re-enqueue jobs
            for job_id in failed_job_ids:
                celery_app.send_task(
                    'cdn_worker.process_image_job',
                    args=[job_id],
                    queue='cdn_processing'
                )
            
            await db.commit()
            
            logger.info(f"Retried {len(failed_job_ids)} failed CDN jobs")
            
            return {
                'success': True,
                'retried_jobs': len(failed_job_ids),
                'job_ids': failed_job_ids,
                'profile_id': profile_id
            }
            
        except Exception as e:
            logger.error(f"Failed to retry CDN jobs: {e}")
            await db.rollback()
            raise e

# Global service instance
cdn_job_service = CDNJobService()