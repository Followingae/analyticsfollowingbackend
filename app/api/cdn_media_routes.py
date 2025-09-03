"""
CDN Media Routes
API endpoints for CDN image system
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional, List
from uuid import UUID
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.infrastructure.r2_storage_client import R2StorageClient
from app.services.cdn_image_service import cdn_image_service, CDNImageService, CDNServiceError
from app.services.image_transcoder_service import ImageTranscoderService
from app.middleware.auth_middleware import get_current_active_user
from app.scrapers.enhanced_decodo_client import EnhancedDecodoClient
from app.core.config import settings
from app.tasks.cdn_processing_tasks import (
    process_cdn_image_job, 
    batch_enqueue_profile_assets,
    cleanup_failed_jobs
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["CDN Media"])

# Initialize global services
_r2_client = None
_transcoder_service = None

def get_r2_client() -> R2StorageClient:
    """Get R2 storage client singleton"""
    global _r2_client
    if _r2_client is None:
        _r2_client = R2StorageClient(
            account_id=settings.CF_ACCOUNT_ID,
            access_key=settings.R2_ACCESS_KEY_ID,
            secret_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME
        )
    return _r2_client

def get_transcoder_service() -> ImageTranscoderService:
    """Get image transcoder service singleton"""
    global _transcoder_service
    if _transcoder_service is None:
        _transcoder_service = ImageTranscoderService(get_r2_client())
    return _transcoder_service

async def get_cdn_service(db: AsyncSession = Depends(get_db)):
    """Get CDN image service with database dependency"""
    cdn_image_service.set_db_session(db)
    return cdn_image_service

@router.get("/creators/ig/{profile_identifier}/media")
async def get_profile_media_urls(
    profile_identifier: str,
    current_user=Depends(get_current_active_user),
    cdn_service: CDNImageService = Depends(get_cdn_service),
    db: AsyncSession = Depends(get_db)
):
    """Get CDN URLs for profile images (avatar + recent posts)"""
    try:
        logger.info(f"🔍 Getting media URLs for profile: {profile_identifier}")
        
        # Check if it's a UUID or username
        profile_uuid = None
        try:
            profile_uuid = UUID(profile_identifier)
            logger.info(f"📱 Using provided UUID: {profile_uuid}")
        except ValueError:
            # It's a username, look up the UUID
            logger.info(f"📱 Looking up UUID for username: {profile_identifier}")
            from sqlalchemy import select
            from app.database.unified_models import Profile
            
            query = select(Profile.id).where(Profile.username == profile_identifier)
            result = await db.execute(query)
            profile_uuid = result.scalar_one_or_none()
            
            if not profile_uuid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Profile not found: {profile_identifier}"
                )
            
            logger.info(f"📱 Found UUID for {profile_identifier}: {profile_uuid}")
        
        # Get media URLs from CDN service
        media_response = await cdn_service.get_profile_media_urls(profile_uuid)
        
        # Build response with placeholders for missing assets
        cdn_base_url = settings.CDN_BASE_URL
        
        response = {
            "profile_id": str(profile_uuid),
            "profile_identifier": profile_identifier,
            "avatar": {
                "256": media_response.avatar_256 or f"{cdn_base_url}/placeholders/avatar-256.webp",
                "512": media_response.avatar_512 or f"{cdn_base_url}/placeholders/avatar-512.webp",
                "available": bool(media_response.avatar_256),
                "placeholder": not bool(media_response.avatar_256)
            },
            "posts": [
                {
                    "mediaId": post['media_id'],
                    "thumb": {
                        "256": post['cdn_url_256'] or f"{cdn_base_url}/placeholders/post-256.webp",
                        "512": post['cdn_url_512'] or f"{cdn_base_url}/placeholders/post-512.webp"
                    },
                    "available": post['available'],
                    "placeholder": not post['available'],
                    "processing_status": post.get('processing_status', 'unknown')
                }
                for post in media_response.posts
            ],
            "processing_status": {
                "queued": media_response.has_pending_jobs,
                "total_assets": media_response.total_assets,
                "completed_assets": media_response.completed_assets,
                "completion_percentage": round(
                    (media_response.completed_assets / media_response.total_assets * 100) 
                    if media_response.total_assets > 0 else 0, 1
                )
            },
            "cdn_info": {
                "base_url": cdn_base_url,
                "cache_ttl": "31536000",  # 1 year
                "formats_available": ["webp"],
                "sizes_available": [256, 512],
                "immutable_urls": True
            },
            "meta": {
                "requested_at": datetime.utcnow().isoformat(),
                "user_id": current_user.id if hasattr(current_user, 'id') else None
            }
        }
        
        logger.info(f"✅ Retrieved media for profile {profile_uuid}: {len(response['posts'])} posts")
        return response
        
    except CDNServiceError as e:
        logger.error(f"❌ CDN service error for profile {profile_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CDN service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error getting media for profile {profile_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve media URLs"
        )

@router.post("/creators/ig/{profile_id}/media/refresh")
async def refresh_profile_media(
    profile_id: str,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_active_user),
    cdn_service: CDNImageService = Depends(get_cdn_service)
):
    """Refresh profile media by re-fetching from Decodo and updating CDN"""
    try:
        logger.info(f"🔄 Refreshing media for profile: {profile_id}")
        
        # Validate profile ID format
        try:
            profile_uuid = UUID(profile_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid profile ID format"
            )
        
        # Get latest data from Decodo
        decodo_client = EnhancedDecodoClient(
            username=settings.SMARTPROXY_USERNAME,
            password=settings.SMARTPROXY_PASSWORD
        )
        
        async with decodo_client:
            try:
                # Fetch comprehensive profile data
                profile_data = await decodo_client.get_instagram_profile_comprehensive(profile_id)
                
                # Parse the profile data structure
                if not profile_data or 'results' not in profile_data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Profile not found or inaccessible"
                    )
                
                # Extract relevant data for CDN processing
                results = profile_data.get('results', [])
                if not results:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No profile data available"
                    )
                
                content = results[0].get('content', {})
                data = content.get('data', {})
                user_data = data.get('user', {})
                
                # Build decodo_data format for CDN service
                decodo_data = {
                    'profile_pic_url': user_data.get('profile_pic_url'),
                    'profile_pic_url_hd': user_data.get('profile_pic_url_hd'),
                    'recent_posts': []
                }
                
                # Extract recent posts
                edge_media = user_data.get('edge_owner_to_timeline_media', {})
                posts_edges = edge_media.get('edges', [])[:settings.IMG_MAX_POSTS_PER_PROFILE]
                
                for post_edge in posts_edges:
                    post_node = post_edge.get('node', {})
                    decodo_data['recent_posts'].append({
                        'shortcode': post_node.get('shortcode'),
                        'display_url': post_node.get('display_url'),
                        'thumbnail_src': post_node.get('thumbnail_src')
                    })
                
            except Exception as e:
                logger.error(f"❌ Decodo fetch failed for {profile_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch profile data: {str(e)}"
                )
        
        # Enqueue for CDN processing
        result = await cdn_service.enqueue_profile_assets(profile_uuid, decodo_data)
        
        if result.success:
            # Add background task to monitor processing
            background_tasks.add_task(
                _monitor_processing_completion, 
                profile_uuid, 
                result.jobs_created
            )
            
            response = {
                "success": True,
                "message": f"Enqueued {result.jobs_created} assets for processing",
                "jobs_created": result.jobs_created,
                "estimated_processing_time": f"{result.jobs_created * 3}-{result.jobs_created * 8} seconds",
                "profile_id": profile_id,
                "refresh_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"✅ Refresh initiated for {profile_id}: {result.jobs_created} jobs")
            return response
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enqueue assets: {result.error}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error refreshing profile media: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh media"
        )

async def _monitor_processing_completion(profile_id: UUID, jobs_count: int):
    """Background task to monitor processing completion"""
    try:
        # This could send notifications, update caches, etc.
        logger.info(f"🔍 Monitoring {jobs_count} jobs for profile {profile_id}")
        # Implementation could include WebSocket notifications to frontend
    except Exception as e:
        logger.error(f"❌ Monitoring task failed: {e}")

@router.get("/cdn/processing-status")
async def get_processing_status(
    current_user=Depends(get_current_active_user),
    cdn_service: CDNImageService = Depends(get_cdn_service)
):
    """Get overall CDN processing system status"""
    try:
        logger.debug("📊 Getting CDN processing status")
        
        # Get processing statistics
        stats = await cdn_service.get_processing_stats()
        
        # Get R2 storage statistics
        r2_client = get_r2_client()
        storage_stats = r2_client.get_storage_stats()
        
        # Get transcoder statistics
        transcoder = get_transcoder_service()
        transcoder_stats = transcoder.get_processing_stats()
        
        # Determine system status
        queue_depth = stats.get('queue_depth', 0)
        completion_rate = stats.get('completion_rate', 0)
        
        if queue_depth > 2000:
            system_status = "overloaded"
        elif queue_depth > 1000:
            system_status = "busy"
        elif completion_rate < 95:
            system_status = "degraded"
        else:
            system_status = "healthy"
        
        response = {
            "system_status": system_status,
            "queue_depth": queue_depth,
            "processing_rate": f"{stats.get('jobs_completed_24h', 0)}/24h",
            "success_rate": f"{completion_rate}%",
            "average_processing_time": f"{stats.get('avg_processing_time_ms', 0)}ms",
            "workers_active": "8",  # From configuration
            "storage_stats": {
                "total_assets": stats.get('total_assets', 0),
                "completed_assets": stats.get('completed_assets', 0),
                "storage_used_mb": storage_stats.get('total_size_mb', 0),
                "storage_used_gb": storage_stats.get('total_size_gb', 0),
                "bucket_object_count": storage_stats.get('object_count', 0)
            },
            "performance_metrics": {
                "avg_processing_time_ms": stats.get('avg_processing_time_ms', 0),
                "transcoder_success_rate": transcoder_stats.get('success_rate', 0),
                "transcoder_avg_download_ms": transcoder_stats.get('avg_download_time_ms', 0),
                "transcoder_avg_processing_ms": transcoder_stats.get('avg_processing_time_ms', 0),
                "transcoder_avg_upload_ms": transcoder_stats.get('avg_upload_time_ms', 0)
            },
            "last_updated": stats.get('last_updated', datetime.utcnow().isoformat())
        }
        
        logger.debug(f"✅ System status: {system_status}, Queue: {queue_depth}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error getting processing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get processing status"
        )

@router.post("/cdn/sync-existing-profiles")
async def sync_existing_profiles(
    batch_size: int = 100,
    current_user=Depends(get_current_active_user),
    cdn_service: CDNImageService = Depends(get_cdn_service)
):
    """Sync existing profiles with CDN system (admin operation)"""
    try:
        # Check if user has admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.info(f"🔄 Starting sync of existing profiles (batch size: {batch_size})")
        
        # Validate batch size
        if not 1 <= batch_size <= 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size must be between 1 and 1000"
            )
        
        # Perform sync
        sync_result = await cdn_service.sync_with_existing_profiles(batch_size)
        
        if 'error' in sync_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sync failed: {sync_result['error']}"
            )
        
        response = {
            "success": True,
            "profiles_processed": sync_result.get('profiles_processed', 0),
            "jobs_created": sync_result.get('jobs_created', 0),
            "errors": sync_result.get('errors', []),
            "sync_timestamp": datetime.utcnow().isoformat(),
            "batch_size": batch_size
        }
        
        logger.info(f"✅ Sync completed: {response['profiles_processed']} profiles, {response['jobs_created']} jobs")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Profile sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile sync failed"
        )

@router.get("/admin/cdn/metrics")
async def get_cdn_metrics(
    hours: int = 24,
    current_user=Depends(get_current_active_user),
    cdn_service: CDNImageService = Depends(get_cdn_service)
):
    """Comprehensive CDN metrics for monitoring (admin endpoint)"""
    try:
        # Check admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.debug(f"📊 Getting CDN metrics for last {hours} hours")
        
        # Get comprehensive statistics
        processing_stats = await cdn_service.get_processing_stats()
        r2_client = get_r2_client()
        storage_stats = r2_client.get_storage_stats()
        transcoder_stats = get_transcoder_service().get_processing_stats()
        
        # Get historical data from database
        db = cdn_service.db
        historical_sql = f"""
            SELECT 
                date, hour,
                SUM(jobs_processed) as total_processed,
                SUM(jobs_failed) as total_failed,
                AVG(avg_processing_time_ms) as avg_time
            FROM cdn_processing_stats 
            WHERE date >= CURRENT_DATE - INTERVAL '{hours} hours'
            GROUP BY date, hour
            ORDER BY date DESC, hour DESC
        """
        
        from sqlalchemy import text
        result = await db.execute(text(historical_sql))
        historical_data = [dict(row) for row in result.fetchall()]
        
        response = {
            "processing_metrics": {
                "queue_depth": processing_stats.get('queue_depth', 0),
                "processing_rate_per_hour": processing_stats.get('jobs_completed_24h', 0) // 24,
                "success_rate_24h": processing_stats.get('completion_rate', 0),
                "average_processing_time_ms": processing_stats.get('avg_processing_time_ms', 0),
                "failed_jobs_24h": processing_stats.get('jobs_failed_24h', 0),
                "total_jobs_processed": transcoder_stats.get('jobs_processed', 0)
            },
            "storage_metrics": {
                "total_assets": processing_stats.get('total_assets', 0),
                "completed_assets": processing_stats.get('completed_assets', 0),
                "storage_used_gb": storage_stats.get('total_size_gb', 0),
                "storage_used_mb": storage_stats.get('total_size_mb', 0),
                "object_count": storage_stats.get('object_count', 0),
                "bucket_name": storage_stats.get('bucket_name')
            },
            "performance_metrics": {
                "avg_download_time_ms": transcoder_stats.get('avg_download_time_ms', 0),
                "avg_processing_time_ms": transcoder_stats.get('avg_processing_time_ms', 0),
                "avg_upload_time_ms": transcoder_stats.get('avg_upload_time_ms', 0),
                "success_rate": transcoder_stats.get('success_rate', 0),
                "bytes_processed": transcoder_stats.get('bytes_processed', 0)
            },
            "historical_data": historical_data,
            "system_health": {
                "status": "healthy",  # Could be determined by rules
                "uptime_hours": hours,
                "last_updated": datetime.utcnow().isoformat()
            }
        }
        
        logger.debug(f"✅ Retrieved CDN metrics: {len(historical_data)} historical points")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting CDN metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve CDN metrics"
        )

@router.get("/admin/cdn/failed-jobs")
async def get_failed_jobs(
    limit: int = 100,
    current_user=Depends(get_current_active_user)
):
    """Get recent failed processing jobs for debugging (admin endpoint)"""
    try:
        # Check admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.debug(f"🔍 Getting {limit} failed jobs")
        
        # Get failed jobs from database
        from app.database import get_db
        db = await get_db()
        
        try:
            failed_jobs_sql = """
                SELECT 
                    j.id, j.asset_id, j.source_url, j.error_message,
                    j.retry_count, j.created_at, j.completed_at,
                    a.source_type, a.source_id, a.media_id
                FROM cdn_image_jobs j
                JOIN cdn_image_assets a ON j.asset_id = a.id
                WHERE j.status = 'failed'
                ORDER BY j.completed_at DESC
                LIMIT :limit
            """
            
            from sqlalchemy import text
            result = await db.execute(text(failed_jobs_sql), {'limit': limit})
            failed_jobs = [
                {
                    'job_id': str(row.id),
                    'asset_id': str(row.asset_id),
                    'source_url': row.source_url,
                    'error_message': row.error_message,
                    'retry_count': row.retry_count,
                    'source_type': row.source_type,
                    'source_id': str(row.source_id),
                    'media_id': row.media_id,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'failed_at': row.completed_at.isoformat() if row.completed_at else None
                }
                for row in result.fetchall()
            ]
            
            response = {
                "failed_jobs": failed_jobs,
                "total_count": len(failed_jobs),
                "retrieved_at": datetime.utcnow().isoformat()
            }
            
            logger.debug(f"✅ Retrieved {len(failed_jobs)} failed jobs")
            return response
            
        finally:
            await db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting failed jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve failed jobs"
        )

@router.post("/admin/cdn/retry-failed")
async def retry_failed_jobs(
    job_ids: List[str],
    current_user=Depends(get_current_active_user)
):
    """Manually retry specific failed jobs (admin endpoint)"""
    try:
        # Check admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        if not job_ids or len(job_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide 1-100 job IDs to retry"
            )
        
        logger.info(f"🔄 Manually retrying {len(job_ids)} failed jobs")
        
        # Reset job status and enqueue for processing
        from app.database import get_db
        db = await get_db()
        
        try:
            retry_results = []
            
            for job_id in job_ids:
                try:
                    # Reset job status
                    reset_sql = """
                        UPDATE cdn_image_jobs 
                        SET status = 'queued',
                            started_at = NULL,
                            completed_at = NULL,
                            worker_id = NULL,
                            error_message = NULL
                        WHERE id = :job_id AND status = 'failed'
                    """
                    
                    from sqlalchemy import text
                    result = await db.execute(text(reset_sql), {'job_id': job_id})
                    
                    if result.rowcount > 0:
                        # Enqueue for processing
                        process_cdn_image_job.delay(job_id)
                        retry_results.append({
                            'job_id': job_id,
                            'success': True,
                            'message': 'Job reset and queued for processing'
                        })
                    else:
                        retry_results.append({
                            'job_id': job_id,
                            'success': False,
                            'message': 'Job not found or not in failed status'
                        })
                        
                except Exception as e:
                    retry_results.append({
                        'job_id': job_id,
                        'success': False,
                        'message': str(e)
                    })
            
            await db.commit()
            
            successful_retries = len([r for r in retry_results if r['success']])
            
            response = {
                "success": True,
                "total_jobs": len(job_ids),
                "successful_retries": successful_retries,
                "failed_retries": len(job_ids) - successful_retries,
                "results": retry_results,
                "retry_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"✅ Retry completed: {successful_retries}/{len(job_ids)} successful")
            return response
            
        finally:
            await db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrying failed jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry jobs"
        )

@router.post("/admin/cdn/cleanup-jobs")
async def trigger_cleanup_jobs(
    current_user=Depends(get_current_active_user)
):
    """Manually trigger job cleanup (admin endpoint)"""
    try:
        # Check admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.info("🧹 Manually triggering job cleanup")
        
        # Trigger cleanup task
        cleanup_task = cleanup_failed_jobs.delay()
        
        response = {
            "success": True,
            "task_id": cleanup_task.id,
            "message": "Job cleanup task initiated",
            "triggered_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Cleanup task initiated: {cleanup_task.id}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error triggering cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger cleanup"
        )