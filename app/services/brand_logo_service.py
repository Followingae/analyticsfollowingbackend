"""
Brand Logo Upload Service
Handles uploading brand logos to Cloudflare R2 for campaigns
"""

import logging
import hashlib
import io
from typing import Optional, Tuple
from PIL import Image
from uuid import UUID
import os

from app.infrastructure.r2_storage_client import R2StorageClient

logger = logging.getLogger(__name__)


class BrandLogoService:
    """Service for uploading and managing brand logos in R2"""

    def __init__(self):
        # Initialize R2 client
        account_id = os.getenv("CF_ACCOUNT_ID")
        access_key = os.getenv("CF_R2_ACCESS_KEY_ID")
        secret_key = os.getenv("CF_R2_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("CF_R2_BUCKET_NAME", "thumbnails-prod")

        if not all([account_id, access_key, secret_key]):
            logger.error("❌ Missing R2 credentials in environment")
            self.r2_client = None
        else:
            self.r2_client = R2StorageClient(
                account_id=account_id,
                access_key=access_key,
                secret_key=secret_key,
                bucket_name=bucket_name
            )
            logger.info("✅ Brand logo service initialized with R2 client")

        self.cdn_base_url = os.getenv("CDN_BASE_URL", "https://cdn.following.ae")
        self.max_logo_size_mb = 5  # 5MB max
        self.allowed_formats = ['PNG', 'JPEG', 'JPG', 'WEBP']
        self.target_size = (512, 512)  # Standard logo size

    async def upload_brand_logo(
        self,
        image_content: bytes,
        campaign_id: UUID,
        user_id: UUID
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload brand logo to R2 storage

        Args:
            image_content: Raw image bytes
            campaign_id: Campaign ID (for organizing logos)
            user_id: User ID (for organizing logos)

        Returns:
            Tuple of (success: bool, cdn_url: str, error_message: str)
        """
        try:
            if not self.r2_client:
                return False, None, "R2 storage not configured"

            # Validate file size
            size_mb = len(image_content) / (1024 * 1024)
            if size_mb > self.max_logo_size_mb:
                return False, None, f"Logo size ({size_mb:.2f}MB) exceeds maximum ({self.max_logo_size_mb}MB)"

            # Validate and process image
            try:
                image = Image.open(io.BytesIO(image_content))

                # Validate format
                if image.format not in self.allowed_formats:
                    return False, None, f"Invalid image format. Allowed: {', '.join(self.allowed_formats)}"

                # Convert to RGB if needed (for WEBP/PNG with transparency)
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGB')

                # Resize to standard size while maintaining aspect ratio
                image.thumbnail(self.target_size, Image.Resampling.LANCZOS)

                # Create new image with white background for transparency
                if image.mode == 'RGBA':
                    background = Image.new('RGB', self.target_size, (255, 255, 255))
                    # Center the image
                    offset = ((self.target_size[0] - image.size[0]) // 2,
                             (self.target_size[1] - image.size[1]) // 2)
                    background.paste(image, offset, mask=image.split()[3] if len(image.split()) > 3 else None)
                    image = background

                # Convert to WEBP for optimal CDN delivery
                output = io.BytesIO()
                image.save(output, format='WEBP', quality=90, method=6)
                processed_content = output.getvalue()

                logger.info(f"✅ Processed logo: {len(image_content)} bytes → {len(processed_content)} bytes")

            except Exception as e:
                logger.error(f"❌ Image processing failed: {e}")
                return False, None, f"Invalid image file: {str(e)}"

            # Generate unique key with hash for deduplication
            content_hash = hashlib.sha256(processed_content).hexdigest()[:16]

            # Key structure: brand-logos/{user_id}/{campaign_id}_{hash}.webp
            key = f"brand-logos/{user_id}/{campaign_id}_{content_hash}.webp"

            # Check if already exists (deduplication)
            exists = await self.r2_client.object_exists(key)
            if exists:
                logger.info(f"✅ Logo already exists (deduplicated): {key}")
                cdn_url = f"{self.cdn_base_url}/{key}"
                return True, cdn_url, None

            # Upload to R2
            success = await self.r2_client.upload_object(
                key=key,
                content=processed_content,
                content_type='image/webp',
                cache_control='public, max-age=31536000, immutable',  # Cache for 1 year
                metadata={
                    'campaign_id': str(campaign_id),
                    'user_id': str(user_id),
                    'original_size': str(len(image_content)),
                    'processed_size': str(len(processed_content))
                }
            )

            if not success:
                return False, None, "Failed to upload to R2 storage"

            # Generate CDN URL
            cdn_url = f"{self.cdn_base_url}/{key}"

            logger.info(f"✅ Brand logo uploaded successfully: {cdn_url}")
            return True, cdn_url, None

        except Exception as e:
            logger.error(f"❌ Brand logo upload failed: {e}")
            return False, None, f"Upload failed: {str(e)}"

    async def delete_brand_logo(self, cdn_url: str) -> bool:
        """
        Delete brand logo from R2 storage

        Args:
            cdn_url: Full CDN URL of the logo

        Returns:
            True if deleted successfully
        """
        try:
            if not self.r2_client:
                logger.error("❌ R2 storage not configured")
                return False

            # Extract key from CDN URL
            key = cdn_url.replace(f"{self.cdn_base_url}/", "")

            if not key.startswith("brand-logos/"):
                logger.error(f"❌ Invalid brand logo URL: {cdn_url}")
                return False

            # Delete from R2
            success = await self.r2_client.delete_object(key)

            if success:
                logger.info(f"✅ Brand logo deleted: {key}")
            else:
                logger.warning(f"⚠️ Failed to delete brand logo: {key}")

            return success

        except Exception as e:
            logger.error(f"❌ Brand logo deletion failed: {e}")
            return False


# Global service instance
brand_logo_service = BrandLogoService()
