"""
Standard R2 Upload Service - Industry standard boto3 implementation
Uses S3-compatible API with Cloudflare R2 - the standard industry approach
"""

import logging
import boto3
import asyncio
from concurrent.futures import ThreadPoolExecutor
from botocore.config import Config
from botocore.exceptions import ClientError
import os
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class StandardR2Service:
    """Industry standard R2 upload service using boto3 S3-compatible API"""

    def __init__(self, bucket_name: str = "thumbnails-prod"):
        self.bucket_name = bucket_name
        self.cloudflare_base_url = "https://cdn.following.ae"

        # Get R2 credentials from environment
        self.account_id = os.getenv("CF_ACCOUNT_ID")
        self.access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

        if not all([self.account_id, self.access_key, self.secret_key]):
            logger.warning("[STANDARD-R2] Missing R2 credentials - uploads will fail")
            self.s3_client = None
        else:
            # Configure boto3 client for Cloudflare R2
            self.s3_client = boto3.client(
                's3',
                endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(
                    region_name='auto',
                    retries={'max_attempts': 3},
                    max_pool_connections=10
                )
            )

        # Thread pool for sync operations
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def upload_image(self, image_data: bytes, r2_key: str, content_type: str = "image/webp") -> Dict[str, Any]:
        """
        Upload image to Cloudflare R2 using standard boto3 S3 API

        Args:
            image_data: Raw image bytes
            r2_key: R2 object key/path
            content_type: MIME type

        Returns:
            Dict with success status and CDN URL
        """
        if not self.s3_client:
            logger.error("[STANDARD-R2] No S3 client - missing credentials")
            return {
                'success': False,
                'error': 'Missing R2 credentials',
                'r2_key': r2_key,
                'upload_type': 'standard_failed'
            }

        try:
            logger.info(f"[STANDARD-R2] Uploading {len(image_data)} bytes to {r2_key}")

            # Execute upload in thread pool (boto3 is sync)
            success = await self._upload_to_r2(image_data, r2_key, content_type)

            if success:
                cdn_url = f"{self.cloudflare_base_url}/{r2_key}"
                logger.info(f"[STANDARD-R2] SUCCESS: {cdn_url}")

                return {
                    'success': True,
                    'cdn_url': cdn_url,
                    'r2_key': r2_key,
                    'size': len(image_data),
                    'upload_type': 'standard_boto3',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                raise Exception("boto3 R2 upload failed")

        except Exception as e:
            logger.error(f"[STANDARD-R2] Upload failed for {r2_key}: {e}")
            return {
                'success': False,
                'error': str(e),
                'r2_key': r2_key,
                'upload_type': 'standard_failed'
            }

    async def _upload_to_r2(self, image_data: bytes, r2_key: str, content_type: str) -> bool:
        """Execute the actual upload using boto3 S3 client"""
        try:
            # Run boto3 upload in thread pool
            loop = asyncio.get_event_loop()

            def upload_sync():
                try:
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=r2_key,
                        Body=image_data,
                        ContentType=content_type,
                        ContentLength=len(image_data),
                        # Optional: Add metadata
                        Metadata={
                            'uploaded-by': 'analytics-following',
                            'upload-timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    )
                    return True
                except ClientError as e:
                    logger.error(f"[STANDARD-R2] ClientError: {e}")
                    return False
                except Exception as e:
                    logger.error(f"[STANDARD-R2] Upload error: {e}")
                    return False

            # Execute upload
            result = await loop.run_in_executor(self.executor, upload_sync)

            if result:
                logger.info(f"[STANDARD-R2] boto3 upload successful: {r2_key}")
            else:
                logger.error(f"[STANDARD-R2] boto3 upload failed: {r2_key}")

            return result

        except Exception as e:
            logger.error(f"[STANDARD-R2] Upload execution error: {e}")
            return False

    async def upload_profile_picture(self, image_data: bytes, username: str) -> Dict[str, Any]:
        """Upload profile picture to standardized path"""
        r2_key = f"profiles/ig/{username}/profile_picture.webp"
        return await self.upload_image(image_data, r2_key)

    async def upload_post_thumbnail(self, image_data: bytes, username: str, shortcode: str) -> Dict[str, Any]:
        """Upload post thumbnail to standardized path"""
        r2_key = f"thumbnails/ig/{username}/{shortcode}/512.webp"
        return await self.upload_image(image_data, r2_key)

    def close(self):
        """Clean up thread pool"""
        if self.executor:
            self.executor.shutdown(wait=True)

# Global service instance
standard_r2_service = StandardR2Service()