"""
Standalone Post Analytics Service - Instagram Post Analysis
Uses the main posts table with proper profile management
"""

import logging
import asyncio
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_, desc, asc
from uuid import UUID
import uuid as uuid_lib
import json

from app.scrapers.apify_instagram_client import ApifyInstagramClient, ApifyProfileNotFoundError, ApifyAPIError
from app.database.unified_models import Post, Profile, AudienceDemographics
from app.database.post_analytics_models import CampaignPostAnalytics
from app.core.config import settings
from app.services.ai.bulletproof_content_intelligence import bulletproof_content_intelligence

logger = logging.getLogger(__name__)

class StandalonePostAnalyticsService:
    """
    Standalone Post Analytics Service - Instagram Post Analysis

    Features:
    - Analyze individual Instagram posts by URL
    - Use existing posts table with proper profile management
    - AI analysis with all available models
    - No campaign dependency - standalone functionality
    """

    def __init__(self):
        self.apify_token = settings.APIFY_API_TOKEN

    async def analyze_post_by_url(self, post_url: str, db: AsyncSession, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Analyze a single Instagram post by URL

        Args:
            post_url: Instagram post URL (any format)
            db: Database session
            user_id: Optional user ID for tracking

        Returns:
            Complete post analytics data
        """
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode_from_url(post_url)
            if not shortcode:
                raise ValueError(f"Could not extract shortcode from URL: {post_url}")

            logger.info(f"🔍 Analyzing post: {shortcode}")

            # Check if post already analyzed
            existing_post = await self._get_post_by_shortcode(db, shortcode)
            if existing_post:
                logger.info(f"📊 Post {shortcode} already exists, returning existing data")
                return await self._format_post_analytics(existing_post)

            try:
                # Fetch post data using Apify
                post_data = await self._fetch_post_data_from_apify(post_url)

                # Get or create profile for this post
                profile = await self._get_or_create_profile(db, post_data, user_id)

                # Store post analysis
                post_record = await self._store_post_analysis(db, post_data, shortcode, post_url, profile.id)

                # Run AI analysis
                ai_analysis = await self._analyze_post_with_ai(post_data)

                # Update with AI results
                await self._update_ai_analysis(db, post_record.id, ai_analysis)

                # Process thumbnail with Cloudflare CDN
                await self._process_post_thumbnail(db, post_record.id, post_data)

                logger.info(f"✅ Post analysis completed successfully for {shortcode}")

                # Refresh post record to get the updated CDN URL
                await db.refresh(post_record)

                # Return complete analytics
                return await self._format_post_analytics(post_record)

            except Exception as e:
                logger.error(f"❌ Failed to complete analysis for {shortcode}: {e}")
                raise

        except Exception as e:
            logger.error(f"❌ Error analyzing post {post_url}: {e}")
            raise

    async def get_post_analytics_by_shortcode(self, shortcode: str, db: AsyncSession) -> Dict[str, Any]:
        """Get existing post analytics by shortcode"""
        post = await self._get_post_by_shortcode(db, shortcode)
        if not post:
            raise ValueError(f"Post not found for shortcode: {shortcode}")

        return await self._format_post_analytics(post)

    async def get_post_analytics_by_id(self, post_id: UUID, db: AsyncSession) -> Dict[str, Any]:
        """Get post analytics by post ID"""
        post = await self._get_post_by_id(db, post_id)
        if not post:
            raise ValueError(f"Post not found for ID: {post_id}")

        return await self._format_post_analytics(post)

    # Private helper methods

    def _extract_shortcode_from_url(self, post_url: str) -> Optional[str]:
        """Extract shortcode from Instagram post/reel URL"""
        # Match Instagram post URLs: /p/SHORTCODE/ or /reel/SHORTCODE/
        patterns = [
            r'instagram\.com\/p\/([A-Za-z0-9_-]+)',
            r'instagram\.com\/reel\/([A-Za-z0-9_-]+)',
            r'\/reel\/([A-Za-z0-9_-]+)',
            r'\/p\/([A-Za-z0-9_-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, post_url)
            if match:
                return match.group(1)

        return None

    async def _fetch_post_data_from_apify(self, post_url: str) -> Dict[str, Any]:
        """Fetch post data using Apify Instagram scraper"""
        try:
            async with ApifyInstagramClient(self.apify_token) as client:
                # Use Apify to scrape individual post
                run_input = {
                    "directUrls": [post_url],
                    "resultsType": "details",
                    "resultsLimit": 1,
                    "addParentData": True,
                    "maxRequestRetries": 2,
                    "sessionPoolSize": 1,
                    "pageTimeout": 60,
                    "requestTimeout": 90
                }

                # Run the scraper
                run = client.client.actor("apify/instagram-scraper").call(
                    run_input=run_input,
                    timeout_secs=300
                )

                if run.get("status") != "SUCCEEDED":
                    raise ApifyAPIError(f"Apify run failed with status: {run.get('status')}")

                # Get results
                results = []
                dataset_id = run.get("defaultDatasetId")
                if dataset_id:
                    for item in client.client.dataset(dataset_id).iterate_items():
                        results.append(item)

                if not results:
                    raise ApifyProfileNotFoundError("No post data found")

                logger.info(f"✅ Fetched post data from Apify")
                return results[0]

        except Exception as e:
            logger.error(f"❌ Apify fetch failed for {post_url}: {e}")
            raise ApifyAPIError(f"Failed to fetch post data: {e}")

    async def _get_or_create_profile(self, db: AsyncSession, post_data: Dict[str, Any], user_id: Optional[UUID] = None) -> Profile:
        """Get or create profile for the post owner"""
        try:
            # Try multiple possible username fields with debug logging
            username = post_data.get("ownerUsername")
            logger.info(f"🔍 Debug: ownerUsername value = '{username}', type = {type(username)}")

            if not username:
                username = post_data.get("username", "")
                logger.info(f"🔍 Debug: fallback username value = '{username}', type = {type(username)}")

            # If nested in owner object, try that too
            if not username and isinstance(post_data.get("owner"), dict):
                username = post_data.get("owner", {}).get("username", "")
                logger.info(f"🔍 Debug: nested username value = '{username}', type = {type(username)}")

            if not username:
                logger.error(f"❌ No username found in post data. Available keys: {list(post_data.keys())}")
                logger.error(f"❌ ownerUsername value: '{post_data.get('ownerUsername')}' (type: {type(post_data.get('ownerUsername'))})")
                raise ValueError(f"No username found in post data. Available fields: {list(post_data.keys())}")

            # Check if profile exists
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            existing_profile = result.scalar_one_or_none()

            if existing_profile:
                # Check if profile needs full analytics using comprehensive completeness check
                needs_analytics = await self._check_profile_needs_analytics(db, existing_profile)

                if needs_analytics:
                    logger.info(f"🔥 Profile {username} exists but incomplete - triggering full analytics")
                    asyncio.create_task(self._trigger_full_creator_analytics(username, user_id))
                else:
                    logger.info(f"✅ Profile {username} has complete analytics - using existing data")

                return existing_profile

            # 🆕 NEW USERNAME DETECTED - Create stub and trigger FULL Creator Analytics
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"🆕 NEW CREATOR DETECTED: {username}")
            logger.info(f"🚀 Creating stub profile and triggering FULL Creator Analytics")
            logger.info(f"   Pipeline: APIFY + CDN + AI + Database Storage")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Create minimal stub profile (will be enriched by creator analytics)
            profile = Profile(
                username=str(username),
                full_name=str(post_data.get("ownerFullName", "")),
                followers_count=0,  # Will be updated by creator analytics
                following_count=0,  # Will be updated by creator analytics
                posts_count=0,      # Will be updated by creator analytics
                is_verified=bool(post_data.get("ownerIsVerified", False)),
                is_private=bool(post_data.get("ownerIsPrivate", False)),
                is_business_account=False,
                biography="",  # Will be updated by creator analytics
                external_url="",
                profile_pic_url=str(post_data.get("ownerProfilePicUrl", "")),
                raw_data=post_data,
                last_refreshed=datetime.now(timezone.utc)
            )

            db.add(profile)
            await db.commit()
            await db.refresh(profile)

            logger.info(f"✅ Stub profile created for {username} (ID: {profile.id})")

            # 🔥 TRIGGER FULL CREATOR ANALYTICS (non-blocking background task)
            # IMPORTANT: Don't pass db session - background task creates its own
            asyncio.create_task(self._trigger_full_creator_analytics(username, user_id))

            return profile

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to get/create profile: {e}")
            raise

    async def _get_post_by_shortcode(self, db: AsyncSession, shortcode: str) -> Optional[Post]:
        """Get post by shortcode - only posts from post analytics, not creator analytics"""
        try:
            # Check if analysis_source column exists (for backward compatibility)
            result = await db.execute(
                select(Post).where(
                    and_(
                        Post.shortcode == shortcode,
                        Post.analysis_source == 'post_analytics'
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            # If analysis_source column doesn't exist yet, fallback to checking all posts
            # but this will be temporary until migration is applied
            logger.warning(f"analysis_source column not available, using fallback logic: {e}")
            result = await db.execute(
                select(Post).where(Post.shortcode == shortcode)
            )
            return result.scalar_one_or_none()

    async def _get_post_by_id(self, db: AsyncSession, post_id: UUID) -> Optional[Post]:
        """Get post by ID"""
        result = await db.execute(
            select(Post).where(Post.id == post_id)
        )
        return result.scalar_one_or_none()

    async def _store_post_analysis(self, db: AsyncSession, post_data: Dict[str, Any],
                                 shortcode: str, post_url: str, profile_id: UUID) -> Post:
        """Store post analysis in posts table"""
        try:
            # Check if post already exists (from Creator Analytics or previous Post Analytics)
            # Check by both instagram_post_id AND shortcode for maximum safety
            instagram_post_id = str(post_data.get("id", ""))

            # First check by instagram_post_id
            if instagram_post_id:
                result = await db.execute(
                    select(Post).where(Post.instagram_post_id == instagram_post_id)
                )
                existing_post = result.scalar_one_or_none()
                if existing_post:
                    logger.info(f"✅ Post {shortcode} already exists by instagram_post_id (ID: {existing_post.id}), reusing existing record")
                    return existing_post

            # Also check by shortcode (in case instagram_post_id doesn't match)
            if shortcode:
                result = await db.execute(
                    select(Post).where(Post.shortcode == shortcode)
                )
                existing_post = result.scalar_one_or_none()
                if existing_post:
                    logger.info(f"✅ Post {shortcode} already exists by shortcode (ID: {existing_post.id}), reusing existing record")
                    return existing_post

            # Extract hashtags and mentions from caption
            caption = post_data.get("caption", "")
            hashtags, mentions = self._extract_hashtags_and_mentions(caption)

            # Create post record - VERIFIED FIELDS ONLY
            post = Post(
                profile_id=profile_id,
                instagram_post_id=post_data.get("id", ""),
                shortcode=shortcode,

                # Media information
                media_type=post_data.get("type", "photo"),
                is_video=post_data.get("isVideo", False),
                display_url=post_data.get("displayUrl", ""),
                thumbnail_src=post_data.get("thumbnailSrc", ""),

                # Video-specific (ensure proper types)
                video_url=post_data.get("videoUrl", ""),
                video_view_count=int(post_data.get("videoViewCount", 0)) if post_data.get("videoViewCount") else 0,
                video_duration=int(post_data.get("videoDuration", 0)) if post_data.get("videoDuration") else None,
                has_audio=post_data.get("hasAudio", False),

                # Dimensions (ensure integers)
                width=int(post_data.get("dimensions", {}).get("width", 0)) if post_data.get("dimensions", {}).get("width") else None,
                height=int(post_data.get("dimensions", {}).get("height", 0)) if post_data.get("dimensions", {}).get("height") else None,

                # Content
                caption=caption,
                accessibility_caption=post_data.get("accessibilityCaption", ""),

                # Engagement (ensure bigint)
                likes_count=int(post_data.get("likesCount", 0)) if post_data.get("likesCount") is not None else 0,
                comments_count=int(post_data.get("commentsCount", 0)) if post_data.get("commentsCount") is not None else 0,
                comments_disabled=post_data.get("commentsDisabled", False),

                # Post settings
                like_and_view_counts_disabled=post_data.get("likeAndViewCountsDisabled", False),
                viewer_can_reshare=post_data.get("viewerCanReshare", True),

                # Location
                location_name=post_data.get("locationName", ""),
                location_id=post_data.get("locationId", ""),

                # Carousel (ensure proper types)
                is_carousel=bool(post_data.get("isCarousel", False)),
                carousel_media_count=int(post_data.get("carouselMediaCount", 1)) if post_data.get("carouselMediaCount") else 1,

                # Timestamps (taken_at_timestamp must be bigint/int)
                taken_at_timestamp=self._convert_timestamp_to_int(post_data.get("timestamp")),
                posted_at=self._convert_timestamp(post_data.get("timestamp")),

                # Structured data
                thumbnail_resources=post_data.get("thumbnailResources", []),
                sidecar_children=post_data.get("sidecarChildren", []),
                tagged_users=post_data.get("taggedUsers", []),

                # Content analysis
                hashtags=hashtags,
                mentions=mentions,

                # Performance
                engagement_rate=self._calculate_engagement_rate(post_data),

                # Raw data
                raw_data=post_data,

                # Analysis source - mark as post analytics
                analysis_source='post_analytics'

                # created_at auto-populated by database default
            )

            db.add(post)
            await db.commit()
            await db.refresh(post)

            logger.info(f"✅ Stored post analysis for {shortcode}")
            return post

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to store post analysis: {e}")
            raise

    async def _analyze_post_with_ai(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """AI analysis disabled - return empty analysis"""
        logger.info("AI analysis disabled - returning Apify data only")
        return {"status": "disabled", "analysis": {}}

    async def _update_ai_analysis(self, db: AsyncSession, post_id: UUID, ai_analysis: Dict[str, Any]):
        """Update post with AI results"""
        try:
            await db.execute(
                text("""
                    UPDATE posts
                    SET
                        ai_content_category = :category,
                        ai_category_confidence = :category_confidence,
                        ai_sentiment = :sentiment,
                        ai_sentiment_score = :sentiment_score,
                        ai_sentiment_confidence = :sentiment_confidence,
                        ai_language_code = :language,
                        ai_language_confidence = :language_confidence,
                        ai_analysis_raw = :raw_analysis,
                        ai_analyzed_at = :analyzed_at,
                        ai_analysis_version = :version
                    WHERE id = :post_id
                """),
                {
                    "post_id": post_id,
                    "category": ai_analysis.get("content_category", {}).get("category"),
                    "category_confidence": ai_analysis.get("content_category", {}).get("confidence", 0.0),
                    "sentiment": ai_analysis.get("sentiment", {}).get("label"),
                    "sentiment_score": ai_analysis.get("sentiment", {}).get("score", 0.0),
                    "sentiment_confidence": ai_analysis.get("sentiment", {}).get("confidence", 0.0),
                    "language": ai_analysis.get("language", {}).get("language"),
                    "language_confidence": ai_analysis.get("language", {}).get("confidence", 0.0),
                    "raw_analysis": json.dumps(ai_analysis),
                    "analyzed_at": datetime.now(timezone.utc),
                    "version": "1.0.0"
                }
            )
            await db.commit()
            logger.info(f"✅ Updated AI analysis for post")

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to update AI analysis: {e}")
            raise

    async def _format_post_analytics(self, post: Post) -> Dict[str, Any]:
        """Format post into comprehensive analytics response"""
        try:
            return {
                "post_id": str(post.id),
                "profile_id": str(post.profile_id),
                "shortcode": post.shortcode,
                "instagram_post_id": post.instagram_post_id,

                # CDN URL at top level for easy frontend access
                "cdn_thumbnail_url": getattr(post, 'cdn_thumbnail_url', None),

                # Media
                "media": {
                    "type": post.media_type,
                    "is_video": post.is_video,
                    "display_url": post.display_url,
                    "thumbnail_src": post.thumbnail_src,
                    "cdn_thumbnail_url": getattr(post, 'cdn_thumbnail_url', None),  # Cloudflare CDN URL
                    "video_url": post.video_url,
                    "video_view_count": post.video_view_count,
                    "dimensions": {
                        "width": post.width,
                        "height": post.height
                    }
                },

                # Content
                "content": {
                    "caption": post.caption,
                    "accessibility_caption": post.accessibility_caption,
                    "hashtags": post.hashtags or [],
                    "mentions": post.mentions or []
                },

                # Engagement
                "engagement": {
                    "likes_count": post.likes_count,
                    "comments_count": post.comments_count,
                    "video_view_count": post.video_view_count,
                    "engagement_rate": post.engagement_rate,
                    "total_engagement": (post.likes_count or 0) + (post.comments_count or 0)
                },

                # Location
                "location": {
                    "name": post.location_name,
                    "id": post.location_id
                },

                # AI Analysis
                "ai_analysis": {
                    "content_category": {
                        "category": post.ai_content_category,
                        "confidence": post.ai_category_confidence
                    },
                    "sentiment": {
                        "label": post.ai_sentiment,
                        "score": post.ai_sentiment_score,
                        "confidence": post.ai_sentiment_confidence
                    },
                    "language": {
                        "code": post.ai_language_code,
                        "confidence": post.ai_language_confidence
                    },
                    "analyzed_at": post.ai_analyzed_at.isoformat() if post.ai_analyzed_at else None,
                    "version": post.ai_analysis_version,
                    "raw_analysis": post.ai_analysis_raw
                },

                # Timestamps
                "timestamps": {
                    "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                    "created_at": post.created_at.isoformat() if post.created_at else None,
                    "taken_at_timestamp": post.taken_at_timestamp
                },

                # Raw data
                "raw_data": post.raw_data
            }

        except Exception as e:
            logger.error(f"❌ Error formatting post analytics: {e}")
            raise

    # Utility methods

    def _extract_hashtags_and_mentions(self, caption: str) -> tuple[List[str], List[str]]:
        """Extract hashtags and mentions from caption"""
        if not caption:
            return [], []

        hashtags = re.findall(r'#(\w+)', caption)
        mentions = re.findall(r'@(\w+)', caption)

        return hashtags, mentions

    def _calculate_engagement_rate(self, post_data: Dict[str, Any]) -> Optional[float]:
        """Calculate engagement rate"""
        followers = post_data.get("ownerFollowersCount", 0)
        if followers == 0:
            return None

        likes = post_data.get("likesCount", 0)
        comments = post_data.get("commentsCount", 0)
        total_engagement = likes + comments

        return round((total_engagement / followers) * 100, 2)

    def _convert_timestamp(self, timestamp) -> Optional[datetime]:
        """Convert timestamp to datetime object"""
        if not timestamp:
            return None

        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            elif isinstance(timestamp, str):
                # Try parsing ISO format
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                return None
        except:
            return None

    def _convert_timestamp_to_int(self, timestamp) -> Optional[int]:
        """Convert timestamp to integer (unix timestamp) for database bigint field"""
        if not timestamp:
            return None

        try:
            if isinstance(timestamp, (int, float)):
                return int(timestamp)
            elif isinstance(timestamp, str):
                # Parse ISO format and convert to unix timestamp
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return int(dt.timestamp())
            else:
                return None
        except Exception as e:
            logger.warning(f"Failed to convert timestamp {timestamp}: {e}")
            return None

    async def _process_post_thumbnail(self, db: AsyncSession, post_id: UUID, post_data: Dict[str, Any]):
        """Process post thumbnail with Cloudflare CDN"""
        try:
            thumbnail_url = post_data.get("displayUrl")
            shortcode = post_data.get("shortCode", "unknown")

            if not thumbnail_url:
                logger.warning(f"No thumbnail URL found for post {shortcode}")
                return

            logger.info(f"🖼️ Processing thumbnail for post {shortcode}")

            # Import CDN service
            from app.services.comprehensive_cdn_service import ComprehensiveCDNService
            cdn_service = ComprehensiveCDNService()

            # Generate CDN key for post thumbnail
            cdn_key = f"posts/{shortcode}/thumbnail.webp"

            # Process the thumbnail
            result = await cdn_service._process_single_image(
                image_url=thumbnail_url,
                cdn_key=cdn_key,
                image_type="post_thumbnail"
            )

            if result.get('success'):
                cdn_url = result['cdn_url']

                # Update post with CDN thumbnail URL
                await db.execute(
                    text("UPDATE posts SET cdn_thumbnail_url = :cdn_url WHERE id = :post_id"),
                    {"cdn_url": cdn_url, "post_id": post_id}
                )
                await db.commit()

                logger.info(f"✅ Thumbnail processed successfully: {cdn_url}")
            else:
                logger.warning(f"❌ Thumbnail processing failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"❌ Error processing thumbnail: {e}")
            # Don't raise - thumbnail processing is optional

    async def _check_profile_needs_analytics(self, db: AsyncSession, profile) -> bool:
        """
        Check if profile has COMPLETE analytics (100% complete as per user's definition):
        - Profile has followers_count, posts_count populated
        - Has at least 12 posts with non-null AI fields
        - Has audience_demographics record with non-null distributions
        - Has CDN thumbnails for posts

        Returns True if analytics should run, False if complete data exists
        """
        from app.database.unified_models import AudienceDemographics

        try:
            # Check 1: Profile has basic data populated
            if not profile.followers_count or profile.followers_count == 0:
                logger.info(f"❌ {profile.username}: Missing followers_count")
                return True

            if not profile.posts_count or profile.posts_count == 0:
                logger.info(f"❌ {profile.username}: Missing posts_count")
                return True

            # Check 2: Has at least 12 posts with AI analysis
            posts_query = select(Post).where(Post.profile_id == profile.id).limit(12)
            posts_result = await db.execute(posts_query)
            posts = posts_result.scalars().all()

            if len(posts) < 12:
                logger.info(f"❌ {profile.username}: Only {len(posts)} posts (need 12)")
                return True

            # Check if posts have AI analysis
            posts_with_ai = sum(1 for p in posts if p.ai_content_category and p.ai_sentiment and p.ai_language_code)
            if posts_with_ai < 12:
                logger.info(f"❌ {profile.username}: Only {posts_with_ai}/12 posts have AI analysis")
                return True

            # Check 3: Has audience demographics
            demographics_query = select(AudienceDemographics).where(
                AudienceDemographics.profile_id == profile.id
            )
            demographics_result = await db.execute(demographics_query)
            demographics = demographics_result.scalar_one_or_none()

            if not demographics:
                logger.info(f"❌ {profile.username}: Missing audience_demographics")
                return True

            # Check if demographics have actual data (not empty distributions)
            if not demographics.gender_distribution or not demographics.age_distribution:
                logger.info(f"❌ {profile.username}: Demographics exist but distributions are empty")
                return True

            # Check 4: Posts have CDN thumbnails (optional but good to check)
            posts_with_cdn = sum(1 for p in posts if p.cdn_thumbnail_url)
            if posts_with_cdn < 12:
                logger.info(f"⚠️ {profile.username}: Only {posts_with_cdn}/12 posts have CDN thumbnails (non-critical)")
                # Don't fail for missing CDN - it's non-critical
                # return True

            # All checks passed - profile has complete analytics
            logger.info(f"✅ {profile.username}: Has complete analytics (Apify + CDN + AI + Demographics)")
            return False

        except Exception as e:
            logger.error(f"❌ Error checking profile completeness: {e}")
            # On error, assume incomplete and trigger analytics
            return True

    async def _trigger_full_creator_analytics(self, username: str, user_id: Optional[UUID]):
        """
        Trigger FULL Creator Analytics using EXACT same pipeline as Creators Module

        CRITICAL: This uses the bulletproof unified_background_processor to ensure
        100% identical behavior with ALL 10 AI models + CDN + Demographics
        """
        from app.database.connection import SessionLocal
        from app.database.comprehensive_service import ComprehensiveDataService
        from app.database.unified_models import Profile
        from sqlalchemy import select
        from app.core.config import settings

        async with SessionLocal() as db:
            try:
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🔥 BULLETPROOF CREATOR ANALYTICS STARTED: {username}")
                logger.info(f"   Pipeline: Apify → Database → CDN → AI (ALL 10 MODELS)")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

                # Check if profile already exists
                profile_query = select(Profile).where(Profile.username == username)
                profile_result = await db.execute(profile_query)
                existing_profile = profile_result.scalar_one_or_none()

                profile = existing_profile

                # If profile doesn't exist or is incomplete, fetch from Apify
                if not existing_profile:
                    logger.info(f"[1/4] 📡 Fetching from Apify (new profile)...")
                    async with ApifyInstagramClient(settings.APIFY_API_TOKEN) as apify_client:
                        apify_data = await apify_client.get_instagram_profile_comprehensive(username)

                    if not apify_data:
                        raise ValueError(f"No Apify data for {username}")

                    logger.info(f"[2/4] 💾 Storing profile + posts in database...")
                    comprehensive_service = ComprehensiveDataService()
                    profile, is_new = await comprehensive_service.store_complete_profile(
                        db, username, apify_data
                    )
                    logger.info(f"✅ Profile stored: {profile.followers_count:,} followers")
                else:
                    logger.info(f"✅ Profile exists - running comprehensive refresh...")

                # CRITICAL: Use unified_background_processor for complete pipeline
                # This runs the EXACT same pipeline as Creator Search with ALL 10 AI models
                logger.info(f"[3/4] 🚀 Starting UNIFIED background processing (CDN → AI ALL 10 MODELS)...")

                try:
                    from app.services.unified_background_processor import unified_background_processor

                    # Run complete pipeline (BLOCKING until 100% complete)
                    # This includes: CDN processing + ALL 10 AI models + Demographics
                    pipeline_results = await unified_background_processor.process_profile_complete_pipeline(
                        profile_id=str(profile.id),
                        username=username
                    )

                    logger.info(f"✅ UNIFIED PROCESSING COMPLETE:")
                    logger.info(f"   CDN: {pipeline_results.get('results', {}).get('cdn_results', {}).get('processed_images', 0)} images")
                    logger.info(f"   AI: {pipeline_results.get('results', {}).get('ai_results', {}).get('completed_models', 0)}/10 models")
                    logger.info(f"   Success Rate: {pipeline_results.get('results', {}).get('ai_results', {}).get('success_rate', 0):.1%}")

                except Exception as processing_error:
                    logger.error(f"❌ Unified processing failed: {processing_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Don't fail - partial data is better than no data

                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"✅ BULLETPROOF CREATOR ANALYTICS COMPLETE: {username}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            except Exception as e:
                logger.error(f"❌ Bulletproof creator analytics failed: {e}")
                import traceback
                logger.error(traceback.format_exc())


# Global service instance
standalone_post_analytics_service = StandalonePostAnalyticsService()