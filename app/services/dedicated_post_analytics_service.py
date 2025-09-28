"""
Campaign Post Analytics Service - Instagram Post Analysis for Campaigns
Analyzes individual posts by URL using Apify for campaign tracking
Uses campaign_post_analytics table
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

class DedicatedPostAnalyticsService:
    """
    Campaign Post Analytics Service - Instagram Post Analysis for Campaigns

    Features:
    - Analyze individual Instagram posts by URL for campaigns
    - Use 100% of Apify data for comprehensive analysis
    - AI analysis with all available models
    - Storage in campaign_post_analytics table
    - Performance metrics and engagement analysis
    """

    def __init__(self):
        self.apify_token = settings.APIFY_API_TOKEN

    async def analyze_post_by_url(self, post_url: str, db: AsyncSession, campaign_id: UUID, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Analyze a single Instagram post by URL

        Args:
            post_url: Instagram post URL (e.g., https://www.instagram.com/p/ABC123/)
            db: Database session
            user_id: Optional user ID for tracking

        Returns:
            Complete post analytics data
        """
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode_from_url(post_url)
            if not shortcode:
                raise ValueError(f"Invalid Instagram post URL: {post_url}")

            logger.info(f"🔍 Analyzing post: {shortcode}")

            # Check if post already analyzed
            existing_analysis = await self._get_analysis_by_shortcode(db, shortcode)
            if existing_analysis:
                logger.info(f"📊 Post {shortcode} already analyzed, returning existing data")
                return await self._format_post_analytics(existing_analysis)

            # Analysis request logged via main analysis record

            try:
                # Fetch post data using Apify
                post_data = await self._fetch_post_data_from_apify(post_url)

                # Store post analysis in dedicated table
                post_analysis = await self._store_post_analysis(db, post_data, shortcode, post_url, campaign_id, user_id)

                # Run AI analysis
                ai_analysis = await self._analyze_post_with_ai(post_data)

                # Update with AI results
                await self._update_ai_analysis(db, post_analysis.id, ai_analysis)

                # Update history as successful
                await self._complete_analysis_history(db, history_record.id, True)

                # Return complete analytics
                final_analysis = await self._get_analysis_by_id(db, post_analysis.id)
                return await self._format_post_analytics(final_analysis)

            except Exception as e:
                # Update history as failed
                await self._complete_analysis_history(db, history_record.id, False, str(e))
                raise

        except Exception as e:
            logger.error(f"❌ Error analyzing post {post_url}: {e}")
            raise

    async def get_post_analytics_by_shortcode(self, shortcode: str, db: AsyncSession) -> Dict[str, Any]:
        """Get existing post analytics by shortcode"""
        analysis = await self._get_analysis_by_shortcode(db, shortcode)
        if not analysis:
            raise ValueError(f"Post analysis not found for shortcode: {shortcode}")

        return await self._format_post_analytics(analysis)

    async def get_post_analytics_by_id(self, analysis_id: UUID, db: AsyncSession) -> Dict[str, Any]:
        """Get post analytics by analysis ID"""
        analysis = await self._get_analysis_by_id(db, analysis_id)
        if not analysis:
            raise ValueError(f"Post analysis not found for ID: {analysis_id}")

        return await self._format_post_analytics(analysis)

    async def search_post_analyses(self, db: AsyncSession,
                                 user_id: Optional[UUID] = None,
                                 username_filter: Optional[str] = None,
                                 content_category: Optional[str] = None,
                                 sentiment: Optional[str] = None,
                                 media_type: Optional[str] = None,
                                 min_likes: Optional[int] = None,
                                 min_engagement_rate: Optional[float] = None,
                                 limit: int = 50,
                                 offset: int = 0) -> Dict[str, Any]:
        """
        Search and filter post analyses

        Args:
            db: Database session
            user_id: Filter by user who requested analysis
            username_filter: Filter by owner username
            content_category: Filter by AI content category
            sentiment: Filter by AI sentiment
            media_type: Filter by media type
            min_likes: Minimum likes count
            min_engagement_rate: Minimum engagement rate
            limit: Number of results to return
            offset: Pagination offset

        Returns:
            Filtered post analyses with pagination
        """
        try:
            # Build query
            query = select(CampaignPostAnalytics)

            # Apply filters
            conditions = []

            if user_id:
                conditions.append(CampaignPostAnalytics.added_by_user_id == user_id)

            if username_filter:
                conditions.append(CampaignPostAnalytics.creator_username.ilike(f"%{username_filter}%"))

            if content_category:
                conditions.append(CampaignPostAnalytics.apify_raw_data == content_category)

            if sentiment:
                conditions.append(CampaignPostAnalytics.apify_raw_data == sentiment)

            if media_type:
                conditions.append(CampaignPostAnalytics.post_type == media_type)

            if min_likes:
                conditions.append(CampaignPostAnalytics.likes_count >= min_likes)

            if min_engagement_rate:
                conditions.append(CampaignPostAnalytics.engagement_rate >= min_engagement_rate)

            if conditions:
                query = query.where(and_(*conditions))

            # Add ordering and pagination
            query = query.order_by(desc(CampaignPostAnalytics.scraped_at)).limit(limit).offset(offset)

            # Execute query
            result = await db.execute(query)
            analyses = result.scalars().all()

            # Format results
            formatted_analyses = []
            for analysis in analyses:
                formatted_data = await self._format_post_analytics(analysis)
                formatted_analyses.append(formatted_data)

            # Get total count for pagination
            count_query = select(text("COUNT(*)")).select_from(CampaignPostAnalytics.__table__)
            if conditions:
                count_query = count_query.where(and_(*conditions))

            count_result = await db.execute(count_query)
            total_count = count_result.scalar()

            return {
                "analyses": formatted_analyses,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                },
                "filters_applied": {
                    "user_id": str(user_id) if user_id else None,
                    "username_filter": username_filter,
                    "content_category": content_category,
                    "sentiment": sentiment,
                    "media_type": media_type,
                    "min_likes": min_likes,
                    "min_engagement_rate": min_engagement_rate
                }
            }

        except Exception as e:
            logger.error(f"❌ Error searching post analyses: {e}")
            raise

    async def delete_post_analysis(self, analysis_id: UUID, db: AsyncSession, user_id: Optional[UUID] = None) -> bool:
        """Delete a post analysis (only by the user who requested it or admin)"""
        try:
            analysis = await self._get_analysis_by_id(db, analysis_id)
            if not analysis:
                return False

            # Check permissions (only creator or admin can delete)
            if user_id and analysis.requested_by_user_id != user_id:
                raise ValueError("Not authorized to delete this analysis")

            await db.delete(analysis)
            await db.commit()

            logger.info(f"✅ Deleted post analysis {analysis_id}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Error deleting post analysis: {e}")
            raise

    # Private helper methods

    def _extract_shortcode_from_url(self, post_url: str) -> Optional[str]:
        """Extract shortcode from Instagram post URL"""
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

                logger.info(f"✅ Fetched post data from Apify")
                return results[0]  # Return the first (and should be only) result

        except Exception as e:
            logger.error(f"❌ Apify fetch failed for {post_url}: {e}")
            raise ApifyAPIError(f"Failed to fetch post data: {e}")

    async def _get_analysis_by_shortcode(self, db: AsyncSession, shortcode: str) -> Optional[CampaignPostAnalytics]:
        """Get post analysis by shortcode"""
        result = await db.execute(
            select(CampaignPostAnalytics).where(CampaignPostAnalytics.instagram_shortcode == shortcode)
        )
        return result.scalar_one_or_none()

    async def _get_analysis_by_id(self, db: AsyncSession, analysis_id: UUID) -> Optional[CampaignPostAnalytics]:
        """Get post analysis by ID"""
        result = await db.execute(
            select(CampaignPostAnalytics).where(CampaignPostAnalytics.id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def _store_post_analysis(self, db: AsyncSession, post_data: Dict[str, Any],
                                 shortcode: str, post_url: str, campaign_id: UUID, user_id: Optional[UUID] = None) -> CampaignPostAnalytics:
        """Store comprehensive post analysis in dedicated table"""
        try:
            # Extract hashtags and mentions from caption
            caption = post_data.get("caption", "")
            hashtags, mentions = self._extract_hashtags_and_mentions(caption)

            # Create comprehensive post analysis record
            post_analysis = CampaignPostAnalytics(
                campaign_id=campaign_id,
                instagram_post_url=post_url,
                instagram_shortcode=shortcode,
                post_type=self._determine_media_type(post_data),

                # Apify raw data (complete response)
                apify_raw_data=post_data,

                # Key metrics (extracted for easy querying)
                likes_count=post_data.get("likesCount", 0),
                comments_count=post_data.get("commentsCount", 0),
                views_count=post_data.get("videoViewCount", 0) if post_data.get("isVideo") else 0,

                # Post content
                caption=caption,
                hashtags=hashtags,
                mentions=mentions,

                # Media information
                media_urls=[post_data.get("displayUrl", "")] if post_data.get("displayUrl") else [],
                media_count=post_data.get("carouselMediaCount", 1),

                # User/creator info
                creator_username=post_data.get("ownerUsername", ""),
                creator_full_name=post_data.get("ownerFullName", ""),
                creator_followers_count=post_data.get("ownerFollowersCount", 0),

                # Engagement metrics
                engagement_rate=self._calculate_engagement_rate(post_data),

                # Post metadata
                posted_at=self._convert_timestamp(post_data.get("timestamp")),
                scraped_at=datetime.now(timezone.utc),

                # Analysis metadata
                added_by_user_id=user_id,
                is_analysis_complete=True,
                analysis_error=None,
                notes=None
            )

            db.add(post_analysis)
            await db.commit()
            await db.refresh(post_analysis)

            logger.info(f"✅ Stored post analysis for {shortcode}")
            return post_analysis

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to store post analysis: {e}")
            raise

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
                hashtags=self._extract_hashtags_and_mentions(caption)[0],
                mentions=self._extract_hashtags_and_mentions(caption)[1],
                location=post_data.get("locationName", ""),
                engagement={
                    "likes": post_data.get("likesCount", 0),
                    "comments": post_data.get("commentsCount", 0)
                }
            )

            logger.info(f"✅ AI analysis completed")
            return ai_analysis

        except Exception as e:
            logger.error(f"❌ AI analysis failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _update_ai_analysis(self, db: AsyncSession, analysis_id: UUID, ai_analysis: Dict[str, Any]):
        """Update post analysis with AI results"""
        try:
            await db.execute(
                text("""
                    UPDATE post_analyses
                    SET
                        ai_content_category = :category,
                        ai_category_confidence = :category_confidence,
                        ai_sentiment = :sentiment,
                        ai_sentiment_score = :sentiment_score,
                        ai_sentiment_confidence = :sentiment_confidence,
                        ai_language_code = :language,
                        ai_language_confidence = :language_confidence,
                        raw_ai_analysis = :raw_analysis,
                        ai_analyzed_at = :analyzed_at,
                        ai_success = :ai_success,
                        last_updated = :updated_at
                    WHERE id = :analysis_id
                """),
                {
                    "analysis_id": analysis_id,
                    "category": ai_analysis.get("content_category", {}).get("category"),
                    "category_confidence": ai_analysis.get("content_category", {}).get("confidence", 0.0),
                    "sentiment": ai_analysis.get("sentiment", {}).get("label"),
                    "sentiment_score": ai_analysis.get("sentiment", {}).get("score", 0.0),
                    "sentiment_confidence": ai_analysis.get("sentiment", {}).get("confidence", 0.0),
                    "language": ai_analysis.get("language", {}).get("language"),
                    "language_confidence": ai_analysis.get("language", {}).get("confidence", 0.0),
                    "raw_analysis": json.dumps(ai_analysis),
                    "analyzed_at": datetime.now(timezone.utc),
                    "ai_success": ai_analysis.get("status") != "error",
                    "updated_at": datetime.now(timezone.utc)
                }
            )
            await db.commit()
            logger.info(f"✅ Updated AI analysis for post")

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to update AI analysis: {e}")
            raise

    # History tracking is simplified in campaign_post_analytics structure
    # No separate history table needed - status tracked in main table

    async def _format_post_analytics(self, analysis: CampaignPostAnalytics) -> Dict[str, Any]:
        """Format post analysis into comprehensive analytics response"""
        try:
            # Extract data from raw Apify data for compatibility
            raw_data = analysis.apify_raw_data or {}

            return {
                "analysis_id": str(analysis.id),
                "campaign_id": str(analysis.campaign_id),
                "post_url": analysis.instagram_post_url,
                "shortcode": analysis.instagram_shortcode,
                "post_type": analysis.post_type,

                # Post owner/creator
                "owner": {
                    "username": analysis.creator_username,
                    "full_name": analysis.creator_full_name,
                    "followers_count": analysis.creator_followers_count
                },

                # Content
                "content": {
                    "caption": analysis.caption,
                    "hashtags": analysis.hashtags or [],
                    "mentions": analysis.mentions or []
                },

                # Media
                "media": {
                    "type": analysis.post_type,
                    "urls": analysis.media_urls or [],
                    "media_count": analysis.media_count
                },

                # Engagement
                "engagement": {
                    "likes_count": analysis.likes_count,
                    "comments_count": analysis.comments_count,
                    "views_count": analysis.views_count,
                    "engagement_rate": float(analysis.engagement_rate) if analysis.engagement_rate else 0.0,
                    "total_engagement": (analysis.likes_count or 0) + (analysis.comments_count or 0)
                },

                # Timestamps
                "timestamps": {
                    "posted_at": analysis.posted_at.isoformat() if analysis.posted_at else None,
                    "scraped_at": analysis.scraped_at.isoformat() if analysis.scraped_at else None,
                    "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                    "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None
                },

                # Meta
                "meta": {
                    "is_analysis_complete": analysis.is_analysis_complete,
                    "analysis_error": analysis.analysis_error,
                    "notes": analysis.notes,
                    "added_by_user_id": str(analysis.added_by_user_id) if analysis.added_by_user_id else None
                },

                # Raw data (for debugging/full analysis)
                "raw_apify_data": raw_data
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

    def _determine_media_type(self, post_data: Dict[str, Any]) -> str:
        """Determine media type from post data"""
        if post_data.get("isVideo"):
            return "video"
        elif post_data.get("isCarousel"):
            return "carousel"
        else:
            return "photo"

    def _calculate_engagement_rate(self, post_data: Dict[str, Any]) -> Optional[float]:
        """Calculate engagement rate"""
        followers = post_data.get("ownerFollowersCount", 0)
        if followers == 0:
            return None

        likes = post_data.get("likesCount", 0)
        comments = post_data.get("commentsCount", 0)
        total_engagement = likes + comments

        return round((total_engagement / followers) * 100, 2)

    def _calculate_quality_score(self, post_data: Dict[str, Any]) -> float:
        """Calculate overall post quality score (0-100)"""
        score = 0.0
        max_score = 100.0

        # Content quality (40 points)
        caption = post_data.get("caption", "")
        if caption:
            score += 20.0
            if len(caption) > 50:  # Substantial caption
                score += 10.0
            if len(caption) > 200:  # Detailed caption
                score += 10.0

        # Engagement quality (30 points)
        likes = post_data.get("likesCount", 0)
        comments = post_data.get("commentsCount", 0)

        if likes > 0:
            score += 15.0
        if comments > 0:
            score += 15.0

        # Media quality (20 points)
        if post_data.get("displayUrl"):
            score += 10.0

        dimensions = post_data.get("dimensions", {})
        if dimensions.get("width", 0) >= 1080:  # High resolution
            score += 10.0

        # Location data (10 points)
        if post_data.get("locationName"):
            score += 10.0

        return min(score, max_score)

    def _calculate_data_completeness(self, analysis: CampaignPostAnalytics) -> int:
        """Calculate data completeness percentage"""
        fields_to_check = [
            analysis.caption,
            analysis.media_urls,
            analysis.post_type,
            analysis.likes_count is not None,
            analysis.comments_count is not None,
            analysis.posted_at,
            analysis.creator_username,
            analysis.creator_followers_count is not None,
            analysis.apify_raw_data,
            analysis.is_analysis_complete
        ]

        completed_fields = sum(1 for field in fields_to_check if field)
        return int((completed_fields / len(fields_to_check)) * 100)

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
dedicated_post_analytics_service = DedicatedPostAnalyticsService()