"""
Comprehensive CDN Processing Service - Industry Standard Implementation
Handles image processing and Cloudflare R2 uploads with bulletproof reliability
"""
import asyncio
import logging
import aiohttp
import io
import base64
import uuid
import socket
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from PIL import Image
import subprocess
import tempfile
import os
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update
from sqlalchemy.orm import selectinload

from app.database.connection import get_session
from app.services.redis_cache_service import redis_cache

logger = logging.getLogger(__name__)

class ComprehensiveCDNService:
    """
    Enterprise-grade CDN processing service with Cloudflare R2 integration
    CRITICAL: Processes AFTER Apify data is 100% stored in database
    """

    def __init__(self):
        self.cloudflare_base_url = "https://cdn.following.ae"
        self.max_retries = 3
        self.timeout = 30

    async def process_profile_images_comprehensive(self, profile_id: str, username: str) -> Dict[str, Any]:
        """
        COMPREHENSIVE image processing for a profile after Apify data is stored

        Args:
            profile_id: Profile UUID in database
            username: Instagram username

        Returns:
            Processing results with CDN URLs and status
        """
        processing_id = str(uuid.uuid4())
        logger.info(f"[CDN-COMPREHENSIVE] Starting image processing for profile {username} (ID: {profile_id})")

        results = {
            'processing_id': processing_id,
            'profile_id': profile_id,
            'username': username,
            'total_images': 0,
            'processed_images': 0,
            'failed_images': 0,
            'cdn_urls_created': [],
            'processing_errors': [],
            'started_at': datetime.now(timezone.utc),
            'completed_at': None,
            'success': False
        }

        try:
            async with get_session() as db:
                # 1. Get profile and posts data (AFTER Apify storage is complete)
                logger.info(f"[CDN-COMPREHENSIVE] Fetching stored profile and posts data for {username}")

                # Get profile with posts
                profile_query = text("""
                    SELECT p.id, p.username, p.profile_pic_url_hd,
                           COUNT(posts.id) as posts_count
                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    WHERE p.id = :profile_id
                    GROUP BY p.id, p.username, p.profile_pic_url_hd
                """)

                profile_result = await db.execute(profile_query, {'profile_id': profile_id})
                profile_data = profile_result.fetchone()

                if not profile_data:
                    raise Exception(f"Profile {profile_id} not found in database")

                logger.info(f"[CDN-COMPREHENSIVE] Found profile {username} with {profile_data.posts_count} posts")

                # Get posts with image URLs
                posts_query = text("""
                    SELECT id, instagram_post_id, display_url, thumbnail_src as thumbnail_url
                    FROM posts
                    WHERE profile_id = :profile_id
                    AND (display_url IS NOT NULL OR thumbnail_src IS NOT NULL)
                    ORDER BY created_at DESC
                    LIMIT 50
                """)

                posts_result = await db.execute(posts_query, {'profile_id': profile_id})
                posts_data = posts_result.fetchall()

                logger.info(f"[CDN-COMPREHENSIVE] Found {len(posts_data)} posts with image URLs")

                # 2. Process profile picture first
                if profile_data.profile_pic_url_hd:
                    logger.info(f"[CDN-COMPREHENSIVE] Processing profile picture for {username}")

                    profile_pic_result = await self._process_single_image(
                        image_url=profile_data.profile_pic_url_hd,
                        cdn_key=f"profiles/ig/{username}/profile_picture.webp",
                        image_type="profile_picture"
                    )

                    if profile_pic_result['success']:
                        # Update profile with CDN URL (using correct column name)
                        await db.execute(
                            text("UPDATE profiles SET cdn_avatar_url = :cdn_url WHERE id = :profile_id"),
                            {'cdn_url': profile_pic_result['cdn_url'], 'profile_id': profile_id}
                        )
                        results['cdn_urls_created'].append(profile_pic_result['cdn_url'])
                        results['processed_images'] += 1
                        logger.info(f"[CDN-SUCCESS] Profile picture processed: {profile_pic_result['cdn_url']}")
                    else:
                        results['processing_errors'].append(f"Profile picture failed: {profile_pic_result.get('error')}")
                        results['failed_images'] += 1

                # 3. Process post thumbnails
                for post in posts_data:
                    results['total_images'] += 1

                    # Determine best image URL to use
                    image_url = post.display_url or post.thumbnail_url
                    if not image_url:
                        continue

                    logger.info(f"[CDN-COMPREHENSIVE] Processing post {post.instagram_post_id}")

                    # Create CDN key for post thumbnail
                    cdn_key = f"thumbnails/ig/{username}/{post.instagram_post_id}/512.webp"

                    # Process the image
                    post_result = await self._process_single_image(
                        image_url=image_url,
                        cdn_key=cdn_key,
                        image_type="post_thumbnail"
                    )

                    if post_result['success']:
                        # Update post with CDN URL
                        await db.execute(
                            text("UPDATE posts SET cdn_thumbnail_url = :cdn_url WHERE id = :post_id"),
                            {'cdn_url': post_result['cdn_url'], 'post_id': post.id}
                        )
                        results['cdn_urls_created'].append(post_result['cdn_url'])
                        results['processed_images'] += 1
                        logger.info(f"[CDN-SUCCESS] Post thumbnail processed: {post_result['cdn_url']}")
                    else:
                        results['processing_errors'].append(f"Post {post.instagram_post_id} failed: {post_result.get('error')}")
                        results['failed_images'] += 1

                # 4. Commit all database changes
                await db.commit()

                # 5. Update processing stats
                results['completed_at'] = datetime.now(timezone.utc)
                results['success'] = results['processed_images'] > 0

                processing_duration = (results['completed_at'] - results['started_at']).total_seconds()

                logger.info(f"[CDN-COMPREHENSIVE] Processing complete for {username}")
                logger.info(f"[CDN-ANALYTICS] Processed {results['processed_images']}/{results['total_images']} images in {processing_duration:.1f}s")
                logger.info(f"[CDN-ANALYTICS] Success rate: {(results['processed_images']/max(results['total_images'],1))*100:.1f}%")

                # 6. Store processing statistics
                await self._store_processing_stats(db, results)

                return results

        except Exception as e:
            logger.error(f"[CDN-ERROR] Comprehensive processing failed for {username}: {e}")
            results['processing_errors'].append(str(e))
            results['success'] = False
            results['completed_at'] = datetime.now(timezone.utc)
            return results

    async def _process_single_image(self, image_url: str, cdn_key: str, image_type: str) -> Dict[str, Any]:
        """
        Process a single image: Download → Optimize → Upload to R2

        Args:
            image_url: Source Instagram image URL
            cdn_key: Target key in R2 (e.g., "thumbnails/ig/username/post_id/512.webp")
            image_type: Type for logging ("profile_picture" or "post_thumbnail")

        Returns:
            Processing result with CDN URL or error
        """
        processing_start = datetime.now(timezone.utc)

        try:
            # 1. Download image from Instagram
            logger.debug(f"[CDN-PROCESS] Downloading {image_type}: {image_url[:100]}...")

            # Force IPv4 to avoid IPv6 connectivity issues with Instagram CDN
            connector = aiohttp.TCPConnector(family=socket.AF_INET)  # IPv4 only
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector
            ) as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed: HTTP {response.status}")

                    raw_image_data = await response.read()
                    logger.debug(f"[CDN-PROCESS] Downloaded {len(raw_image_data)} bytes")

            # 2. Process and optimize image
            processed_image_data = await self._optimize_image(raw_image_data)
            logger.debug(f"[CDN-PROCESS] Optimized to {len(processed_image_data)} bytes WebP")

            # 3. Upload to Cloudflare R2
            upload_success = await self._upload_to_cloudflare_r2(processed_image_data, cdn_key)

            if upload_success:
                cdn_url = f"{self.cloudflare_base_url}/{cdn_key}"
                processing_duration = (datetime.now(timezone.utc) - processing_start).total_seconds()

                logger.debug(f"[CDN-SUCCESS] {image_type} processed in {processing_duration:.1f}s: {cdn_url}")

                return {
                    'success': True,
                    'cdn_url': cdn_url,
                    'cdn_key': cdn_key,
                    'original_size': len(raw_image_data),
                    'optimized_size': len(processed_image_data),
                    'processing_time': processing_duration,
                    'compression_ratio': (1 - len(processed_image_data) / len(raw_image_data)) * 100
                }
            else:
                raise Exception("R2 upload failed")

        except Exception as e:
            processing_duration = (datetime.now(timezone.utc) - processing_start).total_seconds()
            logger.error(f"[CDN-ERROR] {image_type} processing failed in {processing_duration:.1f}s: {e}")

            return {
                'success': False,
                'error': str(e),
                'processing_time': processing_duration,
                'image_url': image_url[:100] + "..." if len(image_url) > 100 else image_url
            }

    async def _optimize_image(self, image_data: bytes) -> bytes:
        """
        Optimize image: Resize to 512px max, convert to WebP, optimize quality

        Args:
            image_data: Raw image bytes

        Returns:
            Optimized WebP image bytes
        """
        try:
            # Open image with PIL
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary (removes alpha channel)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Resize maintaining aspect ratio (max 512px on longest side)
                img.thumbnail((512, 512), Image.Resampling.LANCZOS)

                # Save as optimized WebP
                output_buffer = io.BytesIO()
                img.save(
                    output_buffer,
                    format='WEBP',
                    quality=85,  # High quality for good visual result
                    optimize=True,  # Enable optimization
                    method=6  # Best compression method
                )

                return output_buffer.getvalue()

        except Exception as e:
            logger.error(f"[CDN-ERROR] Image optimization failed: {e}")
            raise Exception(f"Image optimization failed: {e}")

    async def _upload_to_cloudflare_r2(self, image_data: bytes, r2_key: str) -> bool:
        """
        Upload optimized image to Cloudflare R2 using dedicated R2 upload service

        Args:
            image_data: Optimized image bytes
            r2_key: R2 object key (path)

        Returns:
            Success status
        """
        try:
            logger.debug(f"[R2-UPLOAD] Uploading {len(image_data)} bytes to {r2_key}")

            # Use industry standard boto3 R2 upload service
            from app.services.standard_r2_service import standard_r2_service

            upload_result = await standard_r2_service.upload_image(
                image_data=image_data,
                r2_key=r2_key,
                content_type="image/webp"
            )

            if upload_result['success']:
                logger.debug(f"[R2-SUCCESS] Uploaded {r2_key} to Cloudflare R2")
                return True
            else:
                logger.error(f"[R2-ERROR] Upload failed: {upload_result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"[R2-ERROR] Upload service failed: {e}")
            return False

    async def _store_processing_stats(self, db: AsyncSession, results: Dict[str, Any]) -> None:
        """Store processing statistics in database"""
        try:
            # Convert timezone-aware datetime to naive UTC for database
            completed_at_utc = results['completed_at'].replace(tzinfo=None) if results['completed_at'].tzinfo else results['completed_at']

            stats_data = {
                'processed_images': results['processed_images'],
                'failed_images': results['failed_images'],
                'processing_duration_ms': (results['completed_at'] - results['started_at']).total_seconds() * 1000,
                'created_at': completed_at_utc
            }

            # Use INSERT ... ON CONFLICT to handle duplicate keys
            await db.execute(
                text("""
                    INSERT INTO cdn_processing_stats
                    (date, hour, jobs_processed, jobs_failed, total_bytes_processed,
                     avg_processing_time_ms, worker_utilization_percent, created_at)
                    VALUES
                    (CURRENT_DATE, EXTRACT(HOUR FROM NOW()), :processed_images, :failed_images,
                     0, :processing_duration_ms, 100, :created_at)
                    ON CONFLICT (date, hour)
                    DO UPDATE SET
                        jobs_processed = cdn_processing_stats.jobs_processed + EXCLUDED.jobs_processed,
                        jobs_failed = cdn_processing_stats.jobs_failed + EXCLUDED.jobs_failed,
                        avg_processing_time_ms = (cdn_processing_stats.avg_processing_time_ms + EXCLUDED.avg_processing_time_ms) / 2,
                        created_at = EXCLUDED.created_at
                """),
                stats_data
            )

            logger.debug(f"[CDN-STATS] Stored processing statistics for {results['username']}")

        except Exception as e:
            logger.warning(f"[CDN-WARNING] Failed to store processing stats: {e}")

    async def get_profile_cdn_status(self, profile_id: str) -> Dict[str, Any]:
        """
        Get CDN processing status for a profile

        Args:
            profile_id: Profile UUID

        Returns:
            CDN status information
        """
        try:
            async with get_session() as db:
                # Check profile CDN status (using correct column name)
                profile_query = text("""
                    SELECT
                        p.username,
                        p.cdn_avatar_url,
                        COUNT(posts.id) as total_posts,
                        COUNT(posts.cdn_thumbnail_url) as posts_with_cdn
                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    WHERE p.id = :profile_id
                    GROUP BY p.id, p.username, p.cdn_avatar_url
                """)

                result = await db.execute(profile_query, {'profile_id': profile_id})
                data = result.fetchone()

                if not data:
                    return {'status': 'profile_not_found'}

                cdn_completion = data.posts_with_cdn / max(data.total_posts, 1) * 100

                return {
                    'status': 'found',
                    'username': data.username,
                    'profile_pic_cdn_available': data.cdn_avatar_url is not None,
                    'profile_pic_cdn_url': data.cdn_avatar_url,
                    'total_posts': data.total_posts,
                    'posts_with_cdn': data.posts_with_cdn,
                    'cdn_completion_percentage': round(cdn_completion, 1),
                    'cdn_processing_complete': cdn_completion >= 90  # 90% threshold
                }

        except Exception as e:
            logger.error(f"[CDN-ERROR] Failed to get CDN status: {e}")
            return {'status': 'error', 'error': str(e)}

# Global instance
comprehensive_cdn_service = ComprehensiveCDNService()