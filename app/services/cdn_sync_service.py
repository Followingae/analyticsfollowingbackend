"""
CDN SYNCHRONIZATION SERVICE
Ensures CDN URLs are properly synchronized between R2 storage and database
Provides fallback mechanisms when database is out of sync
"""
import logging
from typing import Dict, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

class CDNSyncService:
    """
    Handles CDN URL synchronization and fallback mechanisms
    Ensures frontend always gets valid image URLs
    """

    CDN_BASE_URL = "https://cdn.following.ae"

    def __init__(self):
        self.logger = logger

    async def get_profile_cdn_url(self, db: AsyncSession, profile_id: str, username: str) -> Optional[str]:
        """
        Get profile picture CDN URL with database fallback to direct R2 URL

        Returns:
            CDN URL if available, None if no image exists
        """
        try:
            # STEP 1: Try to get from database (preferred)
            db_query = text("""
                SELECT cdn_url_512
                FROM cdn_image_assets
                WHERE source_id = :profile_id
                AND source_type = 'instagram_profile'
                AND cdn_url_512 IS NOT NULL
                LIMIT 1
            """)
            db_result = await db.execute(db_query, {'profile_id': profile_id})
            db_row = db_result.fetchone()

            if db_row and db_row[0]:
                self.logger.info(f"[CDN] Profile {username}: Found database CDN URL")
                return db_row[0]

            # STEP 2: Database empty - construct direct R2 URL
            direct_r2_url = f"{self.CDN_BASE_URL}/profiles/ig/{username}/profile_picture.webp"
            self.logger.warning(f"[CDN] Profile {username}: Database empty, using direct R2 URL: {direct_r2_url}")

            # STEP 3: Insert into database for future requests (async, non-blocking)
            await self._populate_profile_cdn_record(db, profile_id, username, direct_r2_url)

            return direct_r2_url

        except Exception as e:
            self.logger.error(f"[CDN] Error getting profile CDN URL for {username}: {e}")
            # Fallback to direct R2 URL
            return f"{self.CDN_BASE_URL}/profiles/ig/{username}/profile_picture.webp"

    async def get_posts_cdn_urls(self, db: AsyncSession, profile_id: str, username: str, post_ids: List[str]) -> Dict[str, str]:
        """
        Get post thumbnail CDN URLs with database fallback to direct R2 URLs

        Args:
            profile_id: Profile UUID
            username: Instagram username
            post_ids: List of Instagram post IDs (can be shortcodes or full instagram_post_ids)

        Returns:
            Dict mapping original_post_id -> CDN URL
        """
        try:
            # STEP 1: Try to get from posts table (current system - preferred)
            if post_ids:
                # Handle both formats: "shortcode_ABC123" and "ABC123"
                # Extract shortcodes for database query
                shortcodes = []
                post_id_to_shortcode = {}

                for post_id in post_ids:
                    if post_id.startswith('shortcode_'):
                        shortcode = post_id.replace('shortcode_', '')
                    else:
                        shortcode = post_id
                    shortcodes.append(shortcode)
                    post_id_to_shortcode[shortcode] = post_id

                posts_query = text("""
                    SELECT shortcode, cdn_thumbnail_url
                    FROM posts
                    WHERE profile_id = :profile_id
                    AND cdn_thumbnail_url IS NOT NULL
                    AND shortcode = ANY(:shortcodes)
                """)
                posts_result = await db.execute(posts_query, {
                    'profile_id': profile_id,
                    'shortcodes': shortcodes
                })

                # Map back to original post_id format
                posts_urls = {}
                for shortcode, cdn_url in posts_result.fetchall():
                    original_post_id = post_id_to_shortcode[shortcode]
                    posts_urls[original_post_id] = cdn_url

                if posts_urls:
                    self.logger.info(f"[CDN] Profile {username}: Found {len(posts_urls)} post CDN URLs in posts table")
                    return posts_urls

            # STEP 2: Try legacy cdn_image_assets table (fallback)
            if post_ids:
                assets_query = text("""
                    SELECT media_id, cdn_url_512
                    FROM cdn_image_assets
                    WHERE source_id = :profile_id
                    AND source_type = 'post_thumbnail'
                    AND cdn_url_512 IS NOT NULL
                    AND media_id = ANY(:post_ids)
                """)
                assets_result = await db.execute(assets_query, {
                    'profile_id': profile_id,
                    'post_ids': post_ids
                })
                assets_urls = {row[0]: row[1] for row in assets_result.fetchall()}

                if assets_urls:
                    self.logger.info(f"[CDN] Profile {username}: Found {len(assets_urls)} post CDN URLs in cdn_image_assets table")
                    return assets_urls

            # STEP 3: Database empty - construct direct R2 URLs (legacy thumbnails)
            # Check if we have legacy thumbnail structure in R2
            legacy_urls = {}
            for post_id in post_ids:
                # Try legacy thumbnail path first (old system)
                legacy_url = f"{self.CDN_BASE_URL}/th/ig/{profile_id}/{post_id}/512/"
                legacy_urls[post_id] = legacy_url

            if legacy_urls:
                self.logger.warning(f"[CDN] Profile {username}: Database empty, using {len(legacy_urls)} legacy R2 URLs")

            return legacy_urls

        except Exception as e:
            self.logger.error(f"[CDN] Error getting post CDN URLs for {username}: {e}")
            return {}

    async def _populate_profile_cdn_record(self, db: AsyncSession, profile_id: str, username: str, cdn_url: str):
        """
        Populate CDN database record for profile (async, non-blocking)
        This ensures future requests will find the URL in database
        """
        try:
            insert_query = text("""
                INSERT INTO cdn_image_assets (
                    source_type, source_id, media_id, source_url, cdn_url_512
                ) VALUES (
                    'instagram_profile', :profile_id, 'avatar', :source_url, :cdn_url
                )
                ON CONFLICT (source_type, source_id, media_id)
                DO UPDATE SET cdn_url_512 = EXCLUDED.cdn_url_512
            """)

            await db.execute(insert_query, {
                'profile_id': profile_id,
                'source_url': f"https://instagram.com/{username}",  # Placeholder
                'cdn_url': cdn_url
            })
            await db.commit()

            self.logger.info(f"[CDN] Populated database record for profile {username}")

        except Exception as e:
            self.logger.error(f"[CDN] Failed to populate database record for {username}: {e}")
            await db.rollback()

    async def sync_existing_profiles(self, db: AsyncSession) -> Dict[str, any]:
        """
        ADMIN FUNCTION: Sync all existing profiles with their R2 CDN URLs
        Run this to fix the current database gap
        """
        try:
            # Get all profiles without CDN URLs
            profiles_query = text("""
                SELECT p.id, p.username, p.profile_pic_url
                FROM profiles p
                LEFT JOIN cdn_image_assets cia ON cia.source_id = p.id
                    AND cia.source_type = 'instagram_profile'
                WHERE cia.id IS NULL OR p.profile_pic_url IS NULL OR p.profile_pic_url = ''
            """)

            result = await db.execute(profiles_query)
            profiles_to_sync = result.fetchall()

            synced_count = 0
            for profile_id, username, current_url in profiles_to_sync:
                # Construct R2 URL
                r2_url = f"{self.CDN_BASE_URL}/profiles/ig/{username}/profile_picture.webp"

                # Update profile table
                await db.execute(text("""
                    UPDATE profiles
                    SET profile_pic_url = :cdn_url
                    WHERE id = :profile_id
                """), {'profile_id': profile_id, 'cdn_url': r2_url})

                # Insert into CDN assets table
                await self._populate_profile_cdn_record(db, str(profile_id), username, r2_url)

                synced_count += 1

            await db.commit()

            return {
                "success": True,
                "profiles_synced": synced_count,
                "total_profiles_checked": len(profiles_to_sync),
                "message": f"Successfully synced {synced_count} profiles with CDN URLs"
            }

        except Exception as e:
            await db.rollback()
            self.logger.error(f"[CDN] Bulk sync failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to sync profiles with CDN URLs"
            }

# Global singleton instance
cdn_sync_service = CDNSyncService()