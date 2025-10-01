"""
Campaign Service - Brand Campaign Management System
Handles CRUD operations for campaigns, posts, and creators
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database.unified_models import Campaign, CampaignPost, CampaignCreator, Post, Profile, AudienceDemographics

logger = logging.getLogger(__name__)


class CampaignService:
    """Service for managing brand campaigns"""

    # =============================================================================
    # CAMPAIGN CRUD OPERATIONS
    # =============================================================================

    async def create_campaign(
        self,
        db: AsyncSession,
        user_id: UUID,
        name: str,
        brand_name: str,
        brand_logo_url: Optional[str] = None
    ) -> Campaign:
        """
        Create a new campaign

        Args:
            db: Database session
            user_id: User creating the campaign
            name: Campaign name
            brand_name: Brand name for the campaign
            brand_logo_url: Optional CDN URL for brand logo

        Returns:
            Created Campaign object
        """
        try:
            campaign = Campaign(
                user_id=user_id,
                name=name,
                brand_name=brand_name,
                brand_logo_url=brand_logo_url,
                status='draft'
            )

            db.add(campaign)
            await db.commit()
            await db.refresh(campaign)

            logger.info(f"✅ Created campaign '{name}' for user {user_id}")
            return campaign

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to create campaign: {e}")
            raise

    async def get_campaign(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> Optional[Campaign]:
        """
        Get campaign by ID (with ownership check)

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User requesting the campaign

        Returns:
            Campaign object or None if not found/not authorized
        """
        try:
            result = await db.execute(
                select(Campaign)
                .where(and_(
                    Campaign.id == campaign_id,
                    Campaign.user_id == user_id
                ))
                .options(
                    selectinload(Campaign.campaign_posts).selectinload(CampaignPost.post),
                    selectinload(Campaign.campaign_creators).selectinload(CampaignCreator.profile)
                )
            )
            campaign = result.scalar_one_or_none()

            if campaign:
                logger.info(f"✅ Retrieved campaign {campaign_id}")
            else:
                logger.warning(f"⚠️ Campaign {campaign_id} not found for user {user_id}")

            return campaign

        except Exception as e:
            logger.error(f"❌ Failed to get campaign: {e}")
            raise

    async def list_campaigns(
        self,
        db: AsyncSession,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Campaign]:
        """
        List user's campaigns with optional status filter

        Args:
            db: Database session
            user_id: User ID
            status: Optional status filter (draft, active, completed)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Campaign objects
        """
        try:
            query = select(Campaign).where(Campaign.user_id == user_id)

            if status:
                query = query.where(Campaign.status == status)

            query = query.order_by(desc(Campaign.created_at)).limit(limit).offset(offset)

            result = await db.execute(query)
            campaigns = result.scalars().all()

            logger.info(f"✅ Retrieved {len(campaigns)} campaigns for user {user_id}")
            return campaigns

        except Exception as e:
            logger.error(f"❌ Failed to list campaigns: {e}")
            raise

    async def get_campaigns_summary(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get summary statistics across all user's campaigns

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Summary statistics (totalCampaigns, totalCreators, totalReach, avgEngagementRate)
        """
        try:
            # Get all campaigns
            all_campaigns = await self.list_campaigns(db, user_id, limit=1000)

            total_campaigns = len(all_campaigns)
            total_creators = 0
            total_reach = 0
            total_engagement = 0.0
            engagement_count = 0

            # Aggregate across all campaigns
            for campaign in all_campaigns:
                # Get creators for this campaign
                creators = await self.get_campaign_creators(db, campaign.id, user_id)

                # Count unique creators and accumulate reach
                for creator in creators:
                    total_creators += 1
                    total_reach += creator.get("followers_count", 0)

                    # Accumulate engagement rate
                    avg_engagement = creator.get("avg_engagement_rate", 0)
                    if avg_engagement > 0:
                        total_engagement += avg_engagement
                        engagement_count += 1

            # Calculate average engagement rate
            avg_engagement_rate = (total_engagement / engagement_count) if engagement_count > 0 else 0.0

            summary = {
                "totalCampaigns": total_campaigns,
                "totalCreators": total_creators,
                "totalReach": total_reach,
                "avgEngagementRate": round(avg_engagement_rate, 2)
            }

            logger.info(f"✅ Campaign summary: {summary}")
            return summary

        except Exception as e:
            logger.error(f"❌ Failed to get campaigns summary: {e}")
            raise

    async def update_campaign(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        brand_name: Optional[str] = None,
        brand_logo_url: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[Campaign]:
        """
        Update campaign details

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)
            name: Optional new name
            brand_name: Optional new brand name
            brand_logo_url: Optional new brand logo URL
            status: Optional new status

        Returns:
            Updated Campaign object or None if not found
        """
        try:
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return None

            # Update fields if provided
            if name is not None:
                campaign.name = name
            if brand_name is not None:
                campaign.brand_name = brand_name
            if brand_logo_url is not None:
                campaign.brand_logo_url = brand_logo_url
            if status is not None:
                campaign.status = status

            await db.commit()
            await db.refresh(campaign)

            logger.info(f"✅ Updated campaign {campaign_id}")
            return campaign

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to update campaign: {e}")
            raise

    async def delete_campaign(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Delete campaign (cascade deletes posts and creators)

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)

        Returns:
            True if deleted, False if not found
        """
        try:
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return False

            await db.delete(campaign)
            await db.commit()

            logger.info(f"✅ Deleted campaign {campaign_id}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to delete campaign: {e}")
            raise

    # =============================================================================
    # CAMPAIGN POST OPERATIONS
    # =============================================================================

    async def add_post_to_campaign(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        post_id: UUID,
        instagram_post_url: str,
        user_id: UUID
    ) -> Optional[CampaignPost]:
        """
        Add Instagram post to campaign

        Campaign creator will be auto-populated by database trigger

        Args:
            db: Database session
            campaign_id: Campaign ID
            post_id: Post ID (from posts table)
            instagram_post_url: Original Instagram URL
            user_id: User ID (for ownership check)

        Returns:
            Created CampaignPost object or None if campaign not found
        """
        try:
            # Verify campaign ownership
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                logger.warning(f"⚠️ Campaign {campaign_id} not found for user {user_id}")
                return None

            # Create campaign post
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                post_id=post_id,
                instagram_post_url=instagram_post_url
            )

            db.add(campaign_post)
            await db.commit()
            await db.refresh(campaign_post)

            logger.info(f"✅ Added post {post_id} to campaign {campaign_id}")
            return campaign_post

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to add post to campaign: {e}")
            raise

    async def remove_post_from_campaign(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        post_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Remove post from campaign

        Args:
            db: Database session
            campaign_id: Campaign ID
            post_id: Post ID
            user_id: User ID (for ownership check)

        Returns:
            True if removed, False if not found
        """
        try:
            # Verify campaign ownership
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return False

            # Find and delete campaign post
            result = await db.execute(
                select(CampaignPost).where(and_(
                    CampaignPost.campaign_id == campaign_id,
                    CampaignPost.post_id == post_id
                ))
            )
            campaign_post = result.scalar_one_or_none()

            if not campaign_post:
                return False

            await db.delete(campaign_post)
            await db.commit()

            logger.info(f"✅ Removed post {post_id} from campaign {campaign_id}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to remove post from campaign: {e}")
            raise

    async def get_campaign_posts(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all posts in campaign with complete analytics

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)

        Returns:
            List of post data with analytics
        """
        try:
            # Verify campaign ownership
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return []

            # Get posts with relationships
            result = await db.execute(
                select(CampaignPost)
                .where(CampaignPost.campaign_id == campaign_id)
                .options(selectinload(CampaignPost.post).selectinload(Post.profile))
                .order_by(desc(CampaignPost.added_at))
            )
            campaign_posts = result.scalars().all()

            # Format response
            posts_data = []
            for cp in campaign_posts:
                post = cp.post
                profile = post.profile

                # Determine post type from media_type
                post_type = "static"  # Default
                if post.media_type:
                    media_type_lower = post.media_type.lower()
                    if "video" in media_type_lower or post.is_video:
                        post_type = "reel"
                    elif "sidecar" in media_type_lower or "carousel" in media_type_lower:
                        post_type = "static"  # Carousel is considered static
                    else:
                        post_type = "static"

                # Get CDN thumbnail URL (512px version)
                thumbnail_url = None
                cdn_base = "https://cdn.following.ae"
                if post.shortcode:
                    # CDN path: thumbnails/{profile_username}/posts/{shortcode}/512.webp
                    thumbnail_url = f"{cdn_base}/thumbnails/{profile.username}/posts/{post.shortcode}/512.webp"

                posts_data.append({
                    # Frontend required fields
                    "id": str(post.id),
                    "thumbnail": thumbnail_url,  # CDN URL
                    "url": cp.instagram_post_url,
                    "type": post_type,  # "static" | "reel" | "story"
                    "views": post.video_view_count if post.is_video else 0,
                    "likes": post.likes_count or 0,
                    "comments": post.comments_count or 0,
                    "engagementRate": float(post.engagement_rate) if post.engagement_rate else 0.0,

                    # Additional fields
                    "campaign_post_id": str(cp.id),
                    "post_id": str(post.id),
                    "instagram_post_url": cp.instagram_post_url,
                    "added_at": cp.added_at.isoformat(),
                    "shortcode": post.shortcode,
                    "caption": post.caption,
                    "media_type": post.media_type,
                    "display_url": post.display_url,

                    # AI Analysis
                    "ai_content_category": post.ai_content_category,
                    "ai_sentiment": post.ai_sentiment,
                    "ai_language_code": post.ai_language_code,

                    # Creator
                    "creator_username": profile.username,
                    "creator_full_name": profile.full_name,
                    "creator_followers_count": profile.followers_count
                })

            logger.info(f"✅ Retrieved {len(posts_data)} posts for campaign {campaign_id}")
            return posts_data

        except Exception as e:
            logger.error(f"❌ Failed to get campaign posts: {e}")
            raise

    # =============================================================================
    # CAMPAIGN CREATOR OPERATIONS
    # =============================================================================

    async def get_campaign_creators(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all creators in campaign with aggregated analytics

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)

        Returns:
            List of creator data with aggregated analytics
        """
        try:
            # Verify campaign ownership
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return []

            # Get creators with relationships
            result = await db.execute(
                select(CampaignCreator)
                .where(CampaignCreator.campaign_id == campaign_id)
                .options(
                    selectinload(CampaignCreator.profile).selectinload(Profile.audience_demographics)
                )
                .order_by(desc(CampaignCreator.added_at))
            )
            campaign_creators = result.scalars().all()

            # Format response with aggregated analytics
            creators_data = []
            for cc in campaign_creators:
                profile = cc.profile
                demographics = profile.audience_demographics

                # Get post count for this creator in campaign
                post_count_result = await db.execute(
                    select(func.count(CampaignPost.id))
                    .join(Post, CampaignPost.post_id == Post.id)
                    .where(and_(
                        CampaignPost.campaign_id == campaign_id,
                        Post.profile_id == profile.id
                    ))
                )
                post_count = post_count_result.scalar()

                # Get aggregated engagement for this creator's posts in campaign
                engagement_result = await db.execute(
                    select(
                        func.sum(Post.likes_count).label('total_likes'),
                        func.sum(Post.comments_count).label('total_comments'),
                        func.avg(Post.engagement_rate).label('avg_engagement_rate')
                    )
                    .join(CampaignPost, CampaignPost.post_id == Post.id)
                    .where(and_(
                        CampaignPost.campaign_id == campaign_id,
                        Post.profile_id == profile.id
                    ))
                )
                engagement = engagement_result.one()

                creator_data = {
                    "campaign_creator_id": str(cc.id),
                    "profile_id": str(profile.id),
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "profile_pic_url": profile.profile_pic_url,
                    "added_at": cc.added_at.isoformat(),

                    # Profile metrics
                    "followers_count": profile.followers_count,
                    "following_count": profile.following_count,
                    "posts_count": profile.posts_count,
                    "is_verified": profile.is_verified,

                    # Campaign-specific metrics
                    "posts_in_campaign": post_count,
                    "total_likes": engagement.total_likes or 0,
                    "total_comments": engagement.total_comments or 0,
                    "avg_engagement_rate": float(engagement.avg_engagement_rate) if engagement.avg_engagement_rate else 0.0,

                    # AI Analysis
                    "ai_primary_content_type": profile.ai_primary_content_type,
                    "ai_top_3_categories": profile.ai_top_3_categories,
                    "ai_content_quality_score": float(profile.ai_content_quality_score) if profile.ai_content_quality_score else 0.0,

                    # Audience Demographics (if available)
                    "audience_demographics": None
                }

                if demographics:
                    creator_data["audience_demographics"] = {
                        "gender_distribution": demographics.gender_distribution,
                        "age_distribution": demographics.age_distribution,
                        "country_distribution": demographics.country_distribution,
                        "city_distribution": demographics.city_distribution
                    }

                creators_data.append(creator_data)

            logger.info(f"✅ Retrieved {len(creators_data)} creators for campaign {campaign_id}")
            return creators_data

        except Exception as e:
            logger.error(f"❌ Failed to get campaign creators: {e}")
            raise

    async def get_campaign_audience_aggregation(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Aggregate audience demographics across all creators in campaign

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)

        Returns:
            Aggregated audience demographics
        """
        try:
            # Verify campaign ownership
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return {}

            # Get all creators with demographics
            creators = await self.get_campaign_creators(db, campaign_id, user_id)

            # Aggregate demographics
            total_reach = 0
            aggregated_gender = {}
            aggregated_age = {}
            aggregated_country = {}
            aggregated_city = {}

            for creator in creators:
                followers = creator.get("followers_count", 0)
                total_reach += followers

                demographics = creator.get("audience_demographics")
                if not demographics:
                    continue

                # Weighted aggregation based on follower count
                weight = followers / max(total_reach, 1)  # Avoid division by zero

                # Aggregate gender
                gender_dist = demographics.get("gender_distribution", {})
                for gender, percentage in gender_dist.items():
                    if gender not in aggregated_gender:
                        aggregated_gender[gender] = 0
                    aggregated_gender[gender] += percentage * weight

                # Aggregate age
                age_dist = demographics.get("age_distribution", {})
                for age_range, percentage in age_dist.items():
                    if age_range not in aggregated_age:
                        aggregated_age[age_range] = 0
                    aggregated_age[age_range] += percentage * weight

                # Aggregate country
                country_dist = demographics.get("country_distribution", {})
                for country, percentage in country_dist.items():
                    if country not in aggregated_country:
                        aggregated_country[country] = 0
                    aggregated_country[country] += percentage * weight

                # Aggregate city
                city_dist = demographics.get("city_distribution", {})
                for city, percentage in city_dist.items():
                    if city not in aggregated_city:
                        aggregated_city[city] = 0
                    aggregated_city[city] += percentage * weight

            # Normalize percentages (should sum to ~100)
            def normalize_dict(d: dict) -> dict:
                total = sum(d.values())
                if total > 0:
                    return {k: round((v / total) * 100, 2) for k, v in d.items()}
                return d

            # Find top city
            top_city = None
            if aggregated_city:
                normalized_cities = normalize_dict(aggregated_city)
                top_city_name = max(normalized_cities, key=normalized_cities.get)
                top_city = {
                    "name": top_city_name,
                    "percentage": normalized_cities[top_city_name]
                }

            result = {
                "total_reach": total_reach,
                "total_creators": len(creators),
                "gender_distribution": normalize_dict(aggregated_gender),
                "age_distribution": normalize_dict(aggregated_age),
                "country_distribution": normalize_dict(aggregated_country),
                "city_distribution": normalize_dict(aggregated_city),
                "topCity": top_city  # Frontend required field
            }

            logger.info(f"✅ Aggregated audience for campaign {campaign_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to aggregate campaign audience: {e}")
            raise


# Global service instance
campaign_service = CampaignService()
