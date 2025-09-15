"""
CDN Image Service
Core orchestration service for CDN image management
"""
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from dataclasses import dataclass

from app.database.unified_models import Profile, Post
from app.infrastructure.r2_storage_client import R2StorageClient

logger = logging.getLogger(__name__)

@dataclass 
class ProfileMediaResponse:
    """Response model for profile media URLs (OPTIMIZED: Single 512px size for quality and efficiency)"""
    avatar_url: Optional[str] = None  # OPTIMIZED: Single 512px size instead of dual sizes
    posts: List[Dict[str, Any]] = None
    has_pending_jobs: bool = False
    total_assets: int = 0
    completed_assets: int = 0
    
    def __post_init__(self):
        if self.posts is None:
            self.posts = []

@dataclass
class EnqueueResult:
    """Result of asset enqueue operation"""
    success: bool
    jobs_created: int = 0
    message: str = ""
    error: str = ""

class CDNImageService:
    """Core CDN image management service with database dependency injection"""
    
    def __init__(self):
        # Configuration from environment
        self.cdn_base_url = "https://cdn.following.ae"
        self.max_posts_per_profile = 12
        
        # Placeholder URLs for missing assets (OPTIMIZED: Single 512px size)
        self.placeholder_avatar = f"{self.cdn_base_url}/placeholders/avatar-512.webp"
        self.placeholder_post = f"{self.cdn_base_url}/placeholders/post-512.webp"
        
        # Database session will be injected
        self.db = None
        
        logger.info("[TARGET] CDN Image Service initialized")
    
    def set_db_session(self, db: AsyncSession):
        """Set database session for this request"""
        self.db = db
    
    async def get_profile_media_urls_with_session(self, profile_id: UUID, db_session) -> ProfileMediaResponse:
        """Get CDN URLs for profile avatar and recent posts (with explicit session)"""
        try:
            logger.debug(f"[SEARCH] Getting media URLs for profile: {profile_id}")
            
            # Temporarily set session for this request only
            old_db = self.db
            self.db = db_session
            
            try:
                # Get avatar URL
                avatar_asset = await self._get_asset('profile_avatar', profile_id, 'avatar')
                avatar_urls = self._build_cdn_urls(avatar_asset) if avatar_asset else None
                
                # Get recent post thumbnails (limit based on config)
                post_assets = await self._get_recent_post_assets(profile_id, limit=self.max_posts_per_profile)
                post_urls = []
                
                for asset in post_assets:
                    post_data = {
                        'media_id': asset['media_id'],
                        'cdn_url': asset.get('cdn_url_512'),  # FIXED: Use 512px only
                        'available': asset.get('processing_status') == 'completed',
                        'processing_status': asset.get('processing_status', 'unknown')
                    }
                    post_urls.append(post_data)
                
                # Check for pending jobs
                pending_jobs = await self._count_pending_jobs(profile_id)
                
                # Calculate completion stats
                total_assets = len(post_urls) + (1 if avatar_urls else 0)
                completed_assets = len([p for p in post_urls if p['available']]) + (1 if avatar_urls else 0)
                
                response = ProfileMediaResponse(
                    avatar_url=avatar_urls['512'] if avatar_urls else None,  # FIXED: Single URL
                    posts=post_urls,
                    has_pending_jobs=pending_jobs > 0,
                    total_assets=total_assets,
                    completed_assets=completed_assets
                )
                
                logger.debug(f"[SUCCESS] Retrieved {len(post_urls)} post assets, {pending_jobs} pending jobs")
                return response
                
            finally:
                # Restore original session
                self.db = old_db
                
        except Exception as e:
            logger.error(f"[ERROR] Error getting profile media URLs: {e}")
            raise CDNServiceError(f"Failed to get media URLs: {e}")
    
    async def enqueue_profile_assets(self, profile_id: UUID, apify_data: Dict, db: AsyncSession = None) -> EnqueueResult:
        """Enqueue profile assets for CDN processing"""
        try:
            logger.info(f"📥 Enqueuing assets for profile: {profile_id}")
            print(f"[CDN] CDN: Starting CDN asset enqueue for profile {profile_id}")
            
            # Set database session if provided
            if db:
                self.db = db
            
            jobs_created = 0
            
            # Enqueue avatar from Apify data
            print(f"[CDN] CDN: Looking for profile avatar URL in Apify data...")
            avatar_url = None
            if 'profile_pic_url_hd' in apify_data and apify_data['profile_pic_url_hd']:
                avatar_url = apify_data['profile_pic_url_hd']
                print(f"[CDN] CDN: Found HD avatar URL: {avatar_url[:80]}...")
            elif 'profile_pic_url' in apify_data and apify_data['profile_pic_url']:
                avatar_url = apify_data['profile_pic_url']
                print(f"[CDN] CDN: Found standard avatar URL: {avatar_url[:80]}...")
            
            if avatar_url:
                print(f"[CDN] CDN: Enqueuing profile avatar for processing (HIGH priority)...")
                await self._enqueue_asset(
                    source_type='profile_avatar',
                    source_id=profile_id,
                    media_id='avatar',
                    source_url=avatar_url,
                    priority=3  # Higher priority for avatars
                )
                jobs_created += 1
                logger.info(f"Enqueued avatar from Apify: {avatar_url[:80]}...")
                print(f"[SUCCESS] CDN: Profile avatar enqueued successfully")
            else:
                logger.warning(f"No avatar URL found in Apify data for profile {profile_id}")
                print(f"[WARNING]  CDN: No profile avatar URL found in Apify data")

            # Enqueue recent posts from DATABASE (more reliable than Apify structure parsing)
            print(f"[CDN] CDN: Getting recent posts from database for profile {profile_id}...")
            
            if self.db:
                from sqlalchemy import select, desc
                from app.database.unified_models import Post
                
                # Get recent posts with display URLs from database
                posts_query = select(Post.instagram_post_id, Post.display_url).where(
                    Post.profile_id == profile_id
                ).where(
                    Post.display_url.is_not(None)
                ).where(
                    Post.display_url != ''
                ).order_by(desc(Post.created_at)).limit(self.max_posts_per_profile)
                
                posts_result = await self.db.execute(posts_query)
                db_posts = posts_result.fetchall()
                
                print(f"[CDN] CDN: Found {len(db_posts)} posts with display URLs in database")
                logger.info(f"Found {len(db_posts)} recent posts with display URLs from database")
                
                # Process posts from database
                for i, post_row in enumerate(db_posts, 1):
                    media_id = post_row[0] or f'post_{i}'  # instagram_post_id
                    display_url = post_row[1]  # display_url
                    
                    print(f"[CDN] CDN: Processing post {i}/{len(db_posts)} (media_id: {media_id})")
                    
                    if display_url:
                        print(f"[CDN] CDN: Enqueuing post thumbnail: {display_url[:80]}...")
                        await self._enqueue_asset(
                            source_type='post_thumbnail',
                            source_id=profile_id,
                            media_id=media_id,
                            source_url=display_url,
                            priority=5  # Normal priority for posts
                        )
                        jobs_created += 1
                        print(f"[SUCCESS] CDN: Post {i} thumbnail enqueued successfully")
                    else:
                        print(f"[WARNING]  CDN: Post {i} has no display_url, skipping")
            else:
                print(f"[WARNING]  CDN: No database session available, cannot get posts")
                logger.warning(f"No database session available for CDN post processing")
            
            logger.info(f"[SUCCESS] Enqueued {jobs_created} assets for processing")
            print(f"[SUCCESS] CDN: Successfully enqueued {jobs_created} assets for CDN processing")
            print(f"[CDN] CDN: CDN jobs will be processed in background by workers")
            
            return EnqueueResult(
                success=True,
                jobs_created=jobs_created,
                message=f"Enqueued {jobs_created} assets for processing"
            )
            
        except Exception as e:
            logger.error(f"[ERROR] Error enqueuing profile assets: {e}")
            print(f"[ERROR] CDN: Error enqueuing profile assets - {str(e)}")
            # Add more detailed error info for debugging
            print(f"[ERROR] CDN: Error details - profile_id: {profile_id}, db session: {self.db is not None}")
            return EnqueueResult(
                success=False,
                jobs_created=0,
                error=str(e)
            )
    
    async def _enqueue_asset(self, source_type: str, source_id: UUID, 
                           media_id: str, source_url: str, priority: int = 5) -> Optional[UUID]:
        """Create or update asset record and enqueue processing job using raw SQL"""
        try:
            from sqlalchemy import text
            
            # Create or get asset record
            asset = await self._get_or_create_asset(source_type, source_id, media_id, source_url)
            
            # Check if asset needs processing
            if not self._needs_processing(asset, source_url):
                logger.debug(f"Asset {asset['id']} is up to date, skipping")
                return asset['id']
            
            # Create processing job using raw SQL
            job_sql = """
                INSERT INTO cdn_image_jobs (
                    asset_id, job_type, source_url, priority, 
                    target_sizes, output_format, status
                ) VALUES (
                    :asset_id, :job_type, :source_url, :priority,
                    :target_sizes, :output_format, 'queued'
                ) RETURNING id
            """
            
            result = await self.db.execute(
                text(job_sql),
                {
                    'asset_id': asset['id'],
                    'job_type': 'ingest' if asset['processing_status'] == 'pending' else 'update',
                    'source_url': source_url,
                    'priority': priority,
                    'target_sizes': [512],  # FIXED: Only generate 512px to save 50% storage costs
                    'output_format': 'webp'
                }
            )
            
            await self.db.commit()
            job_id = result.scalar()
            
            logger.debug(f"[TARGET] Created job {job_id} for asset {asset['id']}")
            
            # CRITICAL FIX: Process CDN job IMMEDIATELY instead of background Celery
            logger.info(f"[IMMEDIATE] Processing CDN job {job_id} immediately for fast results")
            try:
                immediate_result = await self._process_cdn_job_immediately(job_id, source_url)
                if immediate_result.get("success"):
                    logger.info(f"[SUCCESS] Immediate CDN processing completed for job {job_id}")
                else:
                    logger.warning(f"[WARNING] Immediate CDN processing failed for job {job_id}: {immediate_result.get('error')}")
            except Exception as immediate_error:
                logger.warning(f"[WARNING] Immediate CDN processing failed for job {job_id}: {immediate_error}")
                
            # Fallback: Still trigger Celery task for retry if immediate processing failed
            try:
                from app.workers.simple_cdn_worker import app as celery_app
                celery_app.send_task(
                    'simple_cdn_worker.process_image_job',
                    args=[str(job_id)]
                )
                logger.info(f"[TRIGGER] Triggered fallback CDN processing for job {job_id}")
            except Exception as celery_error:
                logger.warning(f"[WARNING] Failed to trigger fallback CDN processing for job {job_id}: {celery_error}")
            
            return asset['id']
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[ERROR] Failed to enqueue asset: {e}")
            raise
    
    async def _get_or_create_asset(self, source_type: str, source_id: UUID, 
                                 media_id: str, source_url: str) -> Dict[str, Any]:
        """Get existing asset or create new one"""
        try:
            from sqlalchemy import text
            
            # Try to get existing asset
            asset_sql = """
                SELECT * FROM cdn_image_assets 
                WHERE source_type = :source_type 
                AND source_id = :source_id 
                AND media_id = :media_id
            """
            
            result = await self.db.execute(
                text(asset_sql),
                {
                    'source_type': source_type,
                    'source_id': source_id,
                    'media_id': media_id
                }
            )
            
            asset = result.fetchone()
            
            if asset:
                # Convert to dict for consistent access
                asset_dict = dict(asset._mapping)
                
                # Update source URL if it changed
                if asset_dict['source_url'] != source_url:
                    update_sql = """
                        UPDATE cdn_image_assets 
                        SET source_url = :source_url, 
                            needs_update = true,
                            updated_at = NOW()
                        WHERE id = :asset_id
                    """
                    await self.db.execute(
                        text(update_sql),
                        {'source_url': source_url, 'asset_id': asset_dict['id']}
                    )
                    asset_dict['source_url'] = source_url
                    asset_dict['needs_update'] = True
                
                return asset_dict
            else:
                # Create new asset
                create_sql = """
                    INSERT INTO cdn_image_assets (
                        source_type, source_id, media_id, source_url, processing_status
                    ) VALUES (
                        :source_type, :source_id, :media_id, :source_url, 'pending'
                    ) RETURNING *
                """
                
                result = await self.db.execute(
                    text(create_sql),
                    {
                        'source_type': source_type,
                        'source_id': source_id,
                        'media_id': media_id,
                        'source_url': source_url
                    }
                )
                
                new_asset = result.fetchone()
                await self.db.commit()
                
                return dict(new_asset._mapping)
                
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[ERROR] Failed to get/create asset: {e}")
            raise
    
    async def _get_asset(self, source_type: str, source_id: UUID, media_id: str) -> Optional[Dict[str, Any]]:
        """Get asset by source identifiers"""
        try:
            from sqlalchemy import text
            
            asset_sql = text("""
                SELECT * FROM cdn_image_assets 
                WHERE source_type = :source_type 
                AND source_id = :source_id 
                AND media_id = :media_id
                AND processing_status = 'completed'
            """)
            
            result = await self.db.execute(
                asset_sql,
                {
                    'source_type': source_type,
                    'source_id': source_id,
                    'media_id': media_id
                }
            )
            
            row = result.fetchone()
            return dict(row._mapping) if row else None
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to get asset: {e}")
            return None
    
    async def _get_recent_post_assets(self, profile_id: UUID, limit: int = 12) -> List[Dict[str, Any]]:
        """Get recent post assets for a profile"""
        try:
            from sqlalchemy import text
            
            assets_sql = text("""
                SELECT * FROM cdn_image_assets 
                WHERE source_type = 'post_thumbnail' 
                AND source_id = :profile_id 
                ORDER BY created_at DESC 
                LIMIT :limit
            """)
            
            result = await self.db.execute(
                assets_sql,
                {'profile_id': profile_id, 'limit': limit}
            )
            
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to get recent post assets: {e}")
            return []
    
    async def _count_pending_jobs(self, profile_id: UUID) -> int:
        """Count pending processing jobs for a profile"""
        try:
            from sqlalchemy import text
            
            count_sql = text("""
                SELECT COUNT(*) FROM cdn_image_jobs j
                JOIN cdn_image_assets a ON j.asset_id = a.id
                WHERE a.source_id = :profile_id
                AND j.status IN ('queued', 'processing')
            """)
            
            result = await self.db.execute(count_sql, {'profile_id': profile_id})
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to count pending jobs: {e}")
            return 0
    
    def _build_cdn_urls(self, asset: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Build CDN URLs from asset data"""
        if not asset:
            return None
            
        # Use direct CDN URLs from database (FIXED: 512px only)
        cdn_512 = asset.get('cdn_url_512')
        
        if not cdn_512:
            return None
        
        return {
            '512': cdn_512
        }
    
    def _build_cdn_url(self, cdn_path: str) -> Optional[str]:
        """Build full CDN URL from path"""
        if not cdn_path:
            return None
        
        # Ensure path starts with /
        if not cdn_path.startswith('/'):
            cdn_path = '/' + cdn_path
        
        return f"{self.cdn_base_url}{cdn_path}"
    
    def _needs_processing(self, asset: Dict[str, Any], source_url: str) -> bool:
        """Check if asset needs (re)processing"""
        if not asset:
            return True
        
        # New asset
        if asset.get('processing_status') == 'pending':
            return True
        
        # Failed asset that hasn't exceeded retry limits
        if (asset.get('processing_status') == 'failed' and 
            asset.get('processing_attempts', 0) < 3):
            return True
            
        # Source URL changed
        if asset.get('source_url') != source_url:
            return True
            
        # Asset marked for update
        if asset.get('needs_update'):
            return True
        
        return False
    
    async def sync_with_existing_profiles(self, batch_size: int = 100) -> Dict[str, Any]:
        """Sync existing profiles with CDN system"""
        try:
            logger.info(f"[SYNC] Syncing existing profiles with CDN system (batch size: {batch_size})")
            
            # Get profiles that need CDN processing
            profiles_sql = """
                SELECT p.id, p.profile_pic_url, p.profile_pic_url_hd 
                FROM profiles p
                LEFT JOIN cdn_image_assets a ON (
                    a.source_type = 'profile_avatar' 
                    AND a.source_id = p.id 
                    AND a.media_id = 'avatar'
                )
                WHERE a.id IS NULL  -- No CDN asset exists
                AND (p.profile_pic_url IS NOT NULL OR p.profile_pic_url_hd IS NOT NULL)
                LIMIT :batch_size
            """
            
            result = await self.db.execute(profiles_sql, {'batch_size': batch_size})
            profiles = result.fetchall()
            
            sync_stats = {
                'profiles_processed': 0,
                'jobs_created': 0,
                'errors': []
            }
            
            for profile in profiles:
                try:
                    # Create mock apify_data for enqueue function
                    apify_data = {
                        'profile_pic_url': profile.profile_pic_url,
                        'profile_pic_url_hd': profile.profile_pic_url_hd,
                        'recent_posts': []  # Posts will be synced separately
                    }
                    
                    result = await self.enqueue_profile_assets(profile.id, apify_data)
                    
                    if result.success:
                        sync_stats['jobs_created'] += result.jobs_created
                    else:
                        sync_stats['errors'].append({
                            'profile_id': str(profile.id),
                            'error': result.error
                        })
                    
                    sync_stats['profiles_processed'] += 1
                    
                except Exception as e:
                    sync_stats['errors'].append({
                        'profile_id': str(profile.id),
                        'error': str(e)
                    })
            
            logger.info(f"[SUCCESS] Sync completed: {sync_stats['profiles_processed']} profiles, {sync_stats['jobs_created']} jobs created")
            return sync_stats
            
        except Exception as e:
            logger.error(f"[ERROR] Profile sync failed: {e}")
            return {'error': str(e)}
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        try:
            stats_sql = """
                SELECT 
                    COUNT(CASE WHEN j.status = 'queued' THEN 1 END) as queued_jobs,
                    COUNT(CASE WHEN j.status = 'processing' THEN 1 END) as processing_jobs,
                    COUNT(CASE WHEN j.status = 'completed' THEN 1 END) as completed_jobs,
                    COUNT(CASE WHEN j.status = 'failed' THEN 1 END) as failed_jobs,
                    COUNT(CASE WHEN a.processing_status = 'completed' THEN 1 END) as completed_assets,
                    COUNT(*) as total_assets,
                    AVG(a.total_processing_time_ms) as avg_processing_time_ms
                FROM cdn_image_assets a
                LEFT JOIN cdn_image_jobs j ON j.asset_id = a.id
            """
            
            result = await self.db.execute(stats_sql)
            stats = result.fetchone()
            
            return {
                'queue_depth': stats.queued_jobs or 0,
                'jobs_processing': stats.processing_jobs or 0,
                'jobs_completed_24h': stats.completed_jobs or 0,
                'jobs_failed_24h': stats.failed_jobs or 0,
                'total_assets': stats.total_assets or 0,
                'completed_assets': stats.completed_assets or 0,
                'completion_rate': round((stats.completed_assets / stats.total_assets * 100) if stats.total_assets > 0 else 0, 1),
                'avg_processing_time_ms': round(stats.avg_processing_time_ms or 0, 2),
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to get processing stats: {e}")
            return {'error': str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """CDN service health check"""
        health_status = {
            'status': 'healthy',
            'database_connection': False,
            'r2_storage': False,
            'processing_queue_depth': None,
            'error': None
        }
        
        try:
            # Test database connection
            test_sql = "SELECT 1"
            await self.db.execute(test_sql)
            health_status['database_connection'] = True
            
            # Test R2 storage
            r2_health = await self.r2_client.health_check()
            health_status['r2_storage'] = r2_health['status'] == 'healthy'
            
            # Check processing queue depth
            queue_depth = await self._get_total_queue_depth()
            health_status['processing_queue_depth'] = queue_depth
            
            # Determine overall status
            if not health_status['database_connection'] or not health_status['r2_storage']:
                health_status['status'] = 'degraded'
            
            if queue_depth > 2000:
                health_status['status'] = 'overloaded'
                
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return health_status
    
    async def _get_total_queue_depth(self) -> int:
        """Get total processing queue depth"""
        try:
            queue_sql = "SELECT COUNT(*) FROM cdn_image_jobs WHERE status IN ('queued', 'processing')"
            result = await self.db.execute(queue_sql)
            return result.scalar() or 0
        except Exception:
            return -1
    
    async def _process_cdn_job_immediately(self, job_id: str, source_url: str) -> Dict[str, Any]:
        """Process CDN job immediately for fast results"""
        try:
            from sqlalchemy import text
            import httpx
            import io
            from app.core.config import settings
            from app.infrastructure.r2_storage_client import R2StorageClient
            from app.services.image_transcoder_service import ImageTranscoderService
            
            logger.info(f"[IMMEDIATE] Starting immediate CDN processing for job {job_id}")
            
            # Get job details from database
            job_sql = text("""
                SELECT j.*, a.source_id, a.media_id, a.source_type, a.source_url
                FROM cdn_image_jobs j
                JOIN cdn_image_assets a ON j.asset_id = a.id
                WHERE j.id = :job_id
            """)
            
            result = await self.db.execute(job_sql, {'job_id': job_id})
            job = result.fetchone()
            
            if not job:
                return {"success": False, "error": "Job not found"}
            
            # Update job status to processing
            update_sql = text("""
                UPDATE cdn_image_jobs 
                SET status = 'processing', started_at = NOW()
                WHERE id = :job_id
            """)
            await self.db.execute(update_sql, {'job_id': job_id})
            await self.db.commit()
            
            # Download image from source URL
            logger.info(f"[IMMEDIATE] Downloading image from: {source_url[:80]}...")
            
            timeout = httpx.Timeout(30.0, connect=10.0)  # 30s total, 10s connect
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(source_url)
                if response.status_code != 200:
                    raise Exception(f"Failed to download image: HTTP {response.status_code}")
                
                image_data = response.content
                if len(image_data) == 0:
                    raise Exception("Downloaded image is empty")
                
                logger.info(f"[IMMEDIATE] Downloaded {len(image_data)} bytes")
            
            # Initialize R2 and transcoder services
            r2_client = R2StorageClient(
                account_id=settings.CF_ACCOUNT_ID,
                access_key=settings.R2_ACCESS_KEY_ID,
                secret_key=settings.R2_SECRET_ACCESS_KEY,
                bucket_name=settings.R2_BUCKET_NAME
            )
            transcoder = ImageTranscoderService(r2_client)
            
            # Process image to 512px WebP
            logger.info(f"[IMMEDIATE] Processing image to 512px WebP...")
            processed_images = await transcoder.process_image(
                image_data, 
                target_sizes=[512],
                output_format='webp'
            )
            
            if not processed_images or 512 not in processed_images:
                raise Exception("Failed to process image to 512px")
            
            # Generate unique filename
            from uuid import uuid4
            unique_id = str(uuid4())[:8]
            filename = f"{job.source_type}_{job.source_id}_{job.media_id}_{unique_id}.webp"
            
            # Upload to R2
            logger.info(f"[IMMEDIATE] Uploading to R2: {filename}")
            upload_result = await r2_client.upload_object(
                filename,
                processed_images[512],
                content_type='image/webp'
            )
            
            if not upload_result.get('success'):
                raise Exception(f"Failed to upload to R2: {upload_result.get('error')}")
            
            cdn_url = f"https://cdn.following.ae/{filename}"
            
            # Update asset with CDN URL
            asset_update_sql = text("""
                UPDATE cdn_image_assets 
                SET cdn_url_512 = :cdn_url,
                    processing_status = 'completed',
                    processed_at = NOW()
                WHERE id = :asset_id
            """)
            await self.db.execute(asset_update_sql, {
                'cdn_url': cdn_url,
                'asset_id': job.asset_id
            })
            
            # Update job status to completed
            job_complete_sql = text("""
                UPDATE cdn_image_jobs 
                SET status = 'completed',
                    completed_at = NOW(),
                    result = :result
                WHERE id = :job_id
            """)
            await self.db.execute(job_complete_sql, {
                'job_id': job_id,
                'result': {'cdn_url_512': cdn_url, 'processed_immediately': True}
            })
            
            await self.db.commit()
            
            logger.info(f"[SUCCESS] Immediate CDN processing completed: {cdn_url}")
            return {
                "success": True,
                "cdn_url_512": cdn_url,
                "message": "Image processed immediately"
            }
            
        except Exception as e:
            # Mark job as failed
            try:
                fail_sql = text("""
                    UPDATE cdn_image_jobs 
                    SET status = 'failed',
                        completed_at = NOW(),
                        error = :error
                    WHERE id = :job_id
                """)
                await self.db.execute(fail_sql, {
                    'job_id': job_id,
                    'error': str(e)
                })
                await self.db.commit()
            except Exception:
                pass
            
            logger.error(f"[ERROR] Immediate CDN processing failed for job {job_id}: {e}")
            return {"success": False, "error": str(e)}


class CDNServiceError(Exception):
    """Custom exception for CDN service operations"""
    pass


# Global service instance
cdn_image_service = CDNImageService()