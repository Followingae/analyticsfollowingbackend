"""
Post Analytics Service - Comprehensive Instagram Post Analysis
Uses 100% of Apify data to provide detailed post-level analytics
Dedicated service for individual post URL analysis (separate from creator profile posts)
"""

import logging
import asyncio
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_, desc, asc
from uuid import UUID
import json

from app.scrapers.apify_instagram_client import ApifyInstagramClient, ApifyProfileNotFoundError, ApifyAPIError
from app.database.post_analytics_models import CampaignPostAnalytics
from app.core.config import settings
from app.services.ai.bulletproof_content_intelligence import bulletproof_content_intelligence

logger = logging.getLogger(__name__)

class PostAnalyticsService:
    """
    Post Analytics Service - Extract and analyze individual Instagram posts

    Features:
    - Individual post URL analysis
    - Comprehensive post data extraction using Apify
    - AI analysis of post content, sentiment, and performance
    - Post performance metrics and engagement analysis
    - Hashtag and mention analysis
    - Media type analysis (image, video, carousel)
    """

    def __init__(self):
        self.apify_token = settings.APIFY_API_TOKEN

    async def analyze_post_by_url(self, post_url: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Analyze a single Instagram post by URL using Apify

        Args:
            post_url: Instagram post URL (e.g., https://www.instagram.com/p/ABC123/)
            db: Database session

        Returns:
            Complete post analytics data
        """
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode_from_url(post_url)
            if not shortcode:
                raise ValueError(f"Invalid Instagram post URL: {post_url}")

            logger.info(f"🔍 Analyzing post: {shortcode}")

            # Check if post already exists in database
            existing_post = await self._get_post_by_shortcode(db, shortcode)
            if existing_post:
                logger.info(f"📊 Post {shortcode} found in database, returning existing data")
                return await self._format_post_analytics(existing_post, db)

            # Fetch post data using Apify
            post_data = await self._fetch_post_data_from_apify(post_url)

            # Store post data in database
            stored_post = await self._store_post_data(db, post_data, shortcode)

            # Run AI analysis on the post
            ai_analysis = await self._analyze_post_with_ai(post_data)

            # Update post with AI analysis
            await self._update_post_ai_analysis(db, stored_post.id, ai_analysis)


            # Return complete analytics
            final_post = await self._get_post_by_id(db, stored_post.id)
            return await self._format_post_analytics(final_post, db)

        except Exception as e:
            logger.error(f"❌ Error analyzing post {post_url}: {e}")
            raise

    async def analyze_post_by_shortcode(self, shortcode: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Analyze a post by its Instagram shortcode

        Args:
            shortcode: Instagram post shortcode (e.g., ABC123)
            db: Database session

        Returns:
            Complete post analytics data
        """
        post_url = f"https://www.instagram.com/p/{shortcode}/"
        return await self.analyze_post_by_url(post_url, db)

    async def get_post_analytics_by_id(self, post_id: UUID, db: AsyncSession) -> Dict[str, Any]:
        """
        Get analytics for a post by database ID

        Args:
            post_id: Post database ID
            db: Database session

        Returns:
            Complete post analytics data
        """
        post = await self._get_post_by_id(db, post_id)
        if not post:
            raise ValueError(f"Post with ID {post_id} not found")

        return await self._format_post_analytics(post, db)

    async def batch_analyze_posts(self, post_urls: List[str], db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Analyze multiple posts in batch

        Args:
            post_urls: List of Instagram post URLs
            db: Database session

        Returns:
            List of post analytics data
        """
        results = []

        for post_url in post_urls:
            try:
                result = await self.analyze_post_by_url(post_url, db)
                results.append({
                    "success": True,
                    "url": post_url,
                    "data": result
                })
            except Exception as e:
                logger.error(f"❌ Failed to analyze {post_url}: {e}")
                results.append({
                    "success": False,
                    "url": post_url,
                    "error": str(e)
                })

        return results

    async def get_posts_by_profile(self, profile_id: UUID, db: AsyncSession,
                                 limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get all posts for a specific profile with analytics

        Args:
            profile_id: Profile database ID
            db: Database session
            limit: Number of posts to return
            offset: Pagination offset

        Returns:
            Posts with analytics data
        """
        try:
            # Get posts from database
            result = await db.execute(
                select(Post)
                .where(Post.profile_id == profile_id)
                .order_by(desc(Post.taken_at_timestamp))
                .limit(limit)
                .offset(offset)
            )
            posts = result.scalars().all()

            # Format each post with analytics
            formatted_posts = []
            for post in posts:
                post_analytics = await self._format_post_analytics(post, db)
                formatted_posts.append(post_analytics)

            # Get total count
            count_result = await db.execute(
                select(text("COUNT(*)")).select_from(Post.__table__)
                .where(Post.profile_id == profile_id)
            )
            total_count = count_result.scalar()

            return {
                "posts": formatted_posts,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                },
                "profile_id": str(profile_id)
            }

        except Exception as e:
            logger.error(f"❌ Error getting posts for profile {profile_id}: {e}")
            raise

    # Private methods

    def _extract_shortcode_from_url(self, post_url: str) -> Optional[str]:
        """Extract shortcode from Instagram post URL"""
        import re
        # Match Instagram post URLs: https://www.instagram.com/p/SHORTCODE/
        pattern = r'instagram\.com\/p\/([A-Za-z0-9_-]+)'
        match = re.search(pattern, post_url)
        return match.group(1) if match else None

    async def _fetch_post_data_from_apify(self, post_url: str) -> Dict[str, Any]:
        """Fetch post data using Apify Instagram scraper"""
        try:
            async with ApifyInstagramClient(self.apify_token) as client:
                # Use Apify to scrape individual post
                run_input = {
                    "directUrls": [post_url],
                    "resultsType": "details",  # Get detailed post information
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

                return results[0]  # Return the first (and should be only) result

        except Exception as e:
            logger.error(f"❌ Apify fetch failed for {post_url}: {e}")
            raise ApifyAPIError(f"Failed to fetch post data: {e}")

    async def _get_post_by_shortcode(self, db: AsyncSession, shortcode: str) -> Optional[Post]:
        """Get post from database by shortcode"""
        result = await db.execute(
            select(Post).where(Post.shortcode == shortcode)
        )
        return result.scalar_one_or_none()

    async def _get_post_by_id(self, db: AsyncSession, post_id: UUID) -> Optional[Post]:
        """Get post from database by ID"""
        result = await db.execute(
            select(Post).where(Post.id == post_id)
        )
        return result.scalar_one_or_none()

    async def _store_post_data(self, db: AsyncSession, post_data: Dict[str, Any], shortcode: str, post_url: str, user_id: Optional[UUID] = None) -> PostAnalysis:
        """Store comprehensive post data in dedicated post analysis table"""
        try:
            # Extract hashtags and mentions from caption
            caption = post_data.get("caption", "")
            hashtags, mentions = self._extract_hashtags_and_mentions(caption)

            # Create comprehensive post analysis record
            post_analysis = PostAnalysis(
                post_url=post_url,
                shortcode=shortcode,
                instagram_post_id=post_data.get("id", ""),

                # Owner information
                owner_username=post_data.get("ownerUsername", ""),
                owner_full_name=post_data.get("ownerFullName", ""),
                owner_profile_pic_url=post_data.get("ownerProfilePicUrl", ""),
                owner_is_verified=post_data.get("ownerIsVerified", False),
                owner_followers_count=post_data.get("ownerFollowersCount", 0),

                # Content
                caption=caption,
                accessibility_caption=post_data.get("accessibilityCaption", ""),

                # Media information
                media_type=self._determine_media_type(post_data),
                is_video=post_data.get("isVideo", False),
                is_carousel=post_data.get("isCarousel", False),
                carousel_media_count=post_data.get("carouselMediaCount", 1),

                # Media URLs
                display_url=post_data.get("displayUrl", ""),
                thumbnail_url=post_data.get("thumbnailSrc", ""),
                video_url=post_data.get("videoUrl", ""),

                # Media properties
                width=post_data.get("dimensions", {}).get("width"),
                height=post_data.get("dimensions", {}).get("height"),
                video_duration=post_data.get("videoDuration"),
                has_audio=post_data.get("hasAudio"),

                # Engagement metrics
                likes_count=post_data.get("likesCount", 0),
                comments_count=post_data.get("commentsCount", 0),
                video_view_count=post_data.get("videoViewCount", 0),
                plays_count=post_data.get("playsCount", 0),

                # Post settings
                comments_disabled=post_data.get("commentsDisabled", False),
                like_and_view_counts_disabled=post_data.get("likeAndViewCountsDisabled", False),
                viewer_can_reshare=post_data.get("viewerCanReshare", True),

                # Location
                location_name=post_data.get("locationName", ""),
                location_id=post_data.get("locationId", ""),
                location_slug=post_data.get("locationSlug", ""),

                # Content analysis
                hashtags=hashtags,
                mentions=mentions,
                hashtag_count=len(hashtags),
                mention_count=len(mentions),

                # Performance metrics (calculated)
                engagement_rate=self._calculate_engagement_rate(post_data),

                # Timestamps
                post_created_at=self._convert_timestamp(post_data.get("timestamp")),
                analyzed_at=datetime.now(timezone.utc),

                # Raw data storage
                raw_apify_data=post_data,
                apify_success=True,

                # User tracking
                requested_by_user_id=user_id,
                analysis_version="1.0"
            )

            db.add(post_analysis)
            await db.commit()
            await db.refresh(post_analysis)

            logger.info(f"✅ Stored post analysis {shortcode} in database")
            return post_analysis

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to store post analysis {shortcode}: {e}")
            raise

    async def _find_or_create_profile(self, db: AsyncSession, username: str, post_data: Dict[str, Any]) -> Profile:
        """Find existing profile or create a basic one from post data"""
        if not username:
            # Create a placeholder username if none provided
            username = f"user_{post_data.get('id', 'unknown')}"

        # Try to find existing profile
        result = await db.execute(
            select(Profile).where(Profile.username == username)
        )
        profile = result.scalar_one_or_none()

        if profile:
            return profile

        # Create basic profile from post owner data
        profile = Profile(
            username=username,
            full_name=post_data.get("ownerFullName", ""),
            profile_pic_url=post_data.get("ownerProfilePicUrl", ""),
            is_verified=post_data.get("ownerIsVerified", False),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        logger.info(f"✅ Created basic profile for {username}")
        return profile

    async def _analyze_post_with_ai(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive AI analysis on post data"""
        try:
            caption = post_data.get("caption", "")

            if not caption:
                logger.warning("No caption found for AI analysis")
                return {"status": "no_caption", "analysis": {}}

            # Use bulletproof content intelligence for analysis
            ai_analysis = await bulletproof_content_intelligence.analyze_single_post_comprehensive(
                caption=caption,
                hashtags=post_data.get("hashtags", []),
                mentions=post_data.get("mentions", []),
                location=post_data.get("locationName", ""),
                engagement={
                    "likes": post_data.get("likesCount", 0),
                    "comments": post_data.get("commentsCount", 0)
                }
            )

            logger.info(f"✅ AI analysis completed for post")
            return ai_analysis

        except Exception as e:
            logger.error(f"❌ AI analysis failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _update_post_ai_analysis(self, db: AsyncSession, post_id: UUID, ai_analysis: Dict[str, Any]):
        """Update post with AI analysis results"""
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
                        updated_at = :updated_at
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
                    "updated_at": datetime.now(timezone.utc)
                }
            )
            await db.commit()
            logger.info(f"✅ Updated post {post_id} with AI analysis")

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to update post AI analysis: {e}")
            raise

    async def _format_post_analytics(self, post: Post, db: AsyncSession) -> Dict[str, Any]:
        """Format post data into comprehensive analytics response"""
        try:
            # Get profile information
            profile_result = await db.execute(
                select(Profile).where(Profile.id == post.profile_id)
            )
            profile = profile_result.scalar_one_or_none()

            # Calculate engagement rate
            total_engagement = (post.likes_count or 0) + (post.comments_count or 0)
            follower_count = profile.followers_count if profile and profile.followers_count else 1
            engagement_rate = (total_engagement / follower_count * 100) if follower_count > 0 else 0

            # Extract hashtags and mentions from caption
            hashtags, mentions = self._extract_hashtags_and_mentions(post.caption or "")

            return {
                "post_id": str(post.id),
                "shortcode": post.shortcode,
                "instagram_post_id": post.instagram_post_id,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",

                # Profile information
                "profile": {
                    "id": str(profile.id) if profile else None,
                    "username": profile.username if profile else "unknown",
                    "full_name": profile.full_name if profile else "",
                    "profile_pic_url": profile.profile_pic_url if profile else "",
                    "is_verified": profile.is_verified if profile else False,
                    "followers_count": profile.followers_count if profile else 0
                },

                # Media information
                "media": {
                    "type": post.media_type,
                    "is_video": post.is_video,
                    "is_carousel": post.is_carousel,
                    "carousel_media_count": post.carousel_media_count,
                    "display_url": post.display_url,
                    "thumbnail_src": post.thumbnail_src,
                    "video_url": post.video_url if post.is_video else None,
                    "video_duration": post.video_duration if post.is_video else None,
                    "video_view_count": post.video_view_count if post.is_video else None,
                    "dimensions": {
                        "width": post.width,
                        "height": post.height
                    }
                },

                # Content
                "content": {
                    "caption": post.caption,
                    "accessibility_caption": post.accessibility_caption,
                    "hashtags": hashtags,
                    "mentions": mentions,
                    "hashtag_count": len(hashtags),
                    "mention_count": len(mentions)
                },

                # Engagement metrics
                "engagement": {
                    "likes_count": post.likes_count,
                    "comments_count": post.comments_count,
                    "total_engagement": total_engagement,
                    "engagement_rate": round(engagement_rate, 2),
                    "comments_disabled": post.comments_disabled,
                    "like_and_view_counts_disabled": post.like_and_view_counts_disabled
                },

                # Location
                "location": {
                    "name": post.location_name,
                    "id": post.location_id
                } if post.location_name else None,

                # AI Analysis
                "ai_analysis": {
                    "content_category": {
                        "category": post.ai_content_category,
                        "confidence": post.ai_category_confidence
                    } if post.ai_content_category else None,
                    "sentiment": {
                        "label": post.ai_sentiment,
                        "score": post.ai_sentiment_score,
                        "confidence": post.ai_sentiment_confidence
                    } if post.ai_sentiment else None,
                    "language": {
                        "code": post.ai_language_code,
                        "confidence": post.ai_language_confidence
                    } if post.ai_language_code else None,
                    "analyzed_at": post.ai_analyzed_at.isoformat() if post.ai_analyzed_at else None,
                    "raw_analysis": json.loads(post.ai_analysis_raw) if post.ai_analysis_raw else None
                },

                # Timestamps
                "timestamps": {
                    "taken_at": post.taken_at_timestamp.isoformat() if post.taken_at_timestamp else None,
                    "created_at": post.created_at.isoformat() if post.created_at else None,
                    "updated_at": post.updated_at.isoformat() if post.updated_at else None
                },

                # Meta information
                "meta": {
                    "has_ai_analysis": bool(post.ai_analyzed_at),
                    "data_quality_score": self._calculate_data_quality_score(post),
                    "completeness_percentage": self._calculate_completeness_percentage(post)
                }
            }

        except Exception as e:
            logger.error(f"❌ Error formatting post analytics: {e}")
            raise

    def _extract_hashtags_and_mentions(self, caption: str) -> tuple[List[str], List[str]]:
        """Extract hashtags and mentions from caption"""
        import re

        hashtags = re.findall(r'#(\w+)', caption) if caption else []
        mentions = re.findall(r'@(\w+)', caption) if caption else []

        return hashtags, mentions

    def _calculate_data_quality_score(self, post: Post) -> float:
        """Calculate data quality score (0.0 to 1.0)"""
        score = 0.0
        max_score = 10.0

        # Basic data completeness
        if post.caption: score += 2.0
        if post.display_url: score += 1.0
        if post.likes_count > 0: score += 1.0
        if post.taken_at_timestamp: score += 1.0

        # Media information
        if post.media_type: score += 1.0
        if post.width and post.height: score += 1.0

        # AI analysis
        if post.ai_analyzed_at: score += 2.0

        # Location data
        if post.location_name: score += 1.0

        return min(score / max_score, 1.0)

    def _calculate_completeness_percentage(self, post: Post) -> int:
        """Calculate data completeness percentage"""
        fields_checked = [
            post.caption,
            post.display_url,
            post.media_type,
            post.likes_count is not None,
            post.comments_count is not None,
            post.taken_at_timestamp,
            post.width,
            post.height,
            post.ai_analyzed_at,
            bool(post.raw_data)  # Has raw Apify data
        ]

        completed_fields = sum(1 for field in fields_checked if field)
        return int((completed_fields / len(fields_checked)) * 100)

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


# Global service instance
post_analytics_service = PostAnalyticsService()