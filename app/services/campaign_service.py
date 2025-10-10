"""
Campaign Service - Brand Campaign Management System
Handles CRUD operations for campaigns, posts, and creators
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database.unified_models import Campaign, CampaignPost, CampaignCreator, Post, Profile, AudienceDemographics
from app.services.cdn_sync_service import CDNSyncService

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

            # Get the post to extract correct shortcode for URL generation
            post = await db.get(Post, post_id)
            if not post:
                logger.warning(f"⚠️ Post {post_id} not found")
                return None

            # Generate correct Instagram URL using shortcode (not Instagram post ID)
            correct_instagram_url = f"https://www.instagram.com/p/{post.shortcode}/" if post.shortcode else instagram_post_url
            logger.info(f"🔗 Storing correct Instagram URL: {correct_instagram_url}")

            # Create campaign post
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                post_id=post_id,
                instagram_post_url=correct_instagram_url  # Fixed: Use shortcode-based URL
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

            # Get the post's profile_id before deleting
            post_query = select(Post).where(Post.id == post_id)
            post_result = await db.execute(post_query)
            post = post_result.scalar_one_or_none()

            await db.delete(campaign_post)

            # Check if this was the last post from this creator
            # If yes, remove the creator from campaign_creators
            if post:
                # Count remaining posts from this creator in this campaign
                remaining_posts_query = select(func.count(CampaignPost.id)).select_from(
                    CampaignPost
                ).join(
                    Post, CampaignPost.post_id == Post.id
                ).where(
                    and_(
                        CampaignPost.campaign_id == campaign_id,
                        Post.profile_id == post.profile_id
                    )
                )
                remaining_count_result = await db.execute(remaining_posts_query)
                remaining_count = remaining_count_result.scalar() or 0

                # If no more posts from this creator, remove from campaign_creators
                if remaining_count == 0:
                    creator_query = select(CampaignCreator).where(
                        and_(
                            CampaignCreator.campaign_id == campaign_id,
                            CampaignCreator.profile_id == post.profile_id
                        )
                    )
                    creator_result = await db.execute(creator_query)
                    campaign_creator = creator_result.scalar_one_or_none()

                    if campaign_creator:
                        await db.delete(campaign_creator)
                        logger.info(f"✅ Removed creator {post.profile_id} from campaign {campaign_id} (no more posts)")

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

            # Initialize CDN sync service
            cdn_sync = CDNSyncService()

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

                # Get CDN thumbnail URL - use stored cdn_thumbnail_url or fallback to display_url
                thumbnail_url = post.cdn_thumbnail_url or post.display_url

                # Calculate engagement rate if missing
                if post.engagement_rate is None and profile.followers_count and profile.followers_count > 0:
                    # Calculate on-the-fly: (likes + comments) / followers * 100
                    calculated_engagement = round(
                        ((post.likes_count or 0) + (post.comments_count or 0)) / profile.followers_count * 100,
                        4
                    )
                else:
                    calculated_engagement = float(post.engagement_rate) if post.engagement_rate else 0.0

                # Get CDN URL for profile picture (never use Instagram URLs due to CORS)
                creator_cdn_profile_url = await cdn_sync.get_profile_cdn_url(
                    db=db,
                    profile_id=str(profile.id),
                    username=profile.username
                )


                # Extract collaboration data from raw_data (tagged users, mentions, coauthor_producers)
                collaborators = []

                # Check tagged users (most reliable for collaborations)
                if post.raw_data and post.raw_data.get('tagged_users'):
                    for tagged_user in post.raw_data.get('tagged_users', []):
                        if tagged_user.get('username'):
                            collaborators.append({
                                'username': tagged_user.get('username'),
                                'full_name': tagged_user.get('full_name', ''),
                                'is_verified': tagged_user.get('is_verified', False),
                                'collaboration_type': 'tagged_user'
                            })

                # Also check coauthor_producers for formal Instagram collaborations
                if post.coauthor_producers and len(post.coauthor_producers) > 0:
                    for coauthor in post.coauthor_producers:
                        if isinstance(coauthor, dict) and coauthor.get('username'):
                            collaborators.append({
                                'username': coauthor.get('username'),
                                'full_name': coauthor.get('full_name', ''),
                                'is_verified': coauthor.get('is_verified', False),
                                'collaboration_type': 'coauthor_producer'
                            })

                # Check mentions for brand partnerships  
                if post.mentions and len(post.mentions) > 0:
                    for mention in post.mentions:
                        # Clean mention (@barakatme -> barakatme)
                        clean_mention = mention.replace('@', '').strip()
                        if clean_mention and clean_mention not in [c['username'] for c in collaborators]:
                            collaborators.append({
                                'username': clean_mention,
                                'full_name': '',
                                'is_verified': False,
                                'collaboration_type': 'mention'
                            })

                # Generate correct Instagram URL from shortcode
                correct_instagram_url = f"https://www.instagram.com/p/{post.shortcode}/" if post.shortcode else cp.instagram_post_url

                posts_data.append({
                    # Frontend required fields
                    "id": str(post.id),
                    "thumbnail": thumbnail_url,  # CDN URL from cdn_thumbnail_url column
                    "url": correct_instagram_url,  # Fixed: Use shortcode-based URL instead of stored URL
                    "type": post_type,  # "static" | "reel" | "story"
                    "views": post.video_view_count if post.is_video else 0,
                    "likes": post.likes_count or 0,
                    "comments": post.comments_count or 0,
                    "engagementRate": calculated_engagement,

                    # Additional fields
                    "campaign_post_id": str(cp.id),
                    "post_id": str(post.id),
                    "instagram_post_url": correct_instagram_url,  # Fixed: Use shortcode-based URL
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
                    "creator_followers_count": profile.followers_count,
                    "creator_profile_pic_url": creator_cdn_profile_url,  # Always use CDN URL to avoid CORS
                    "creator_profile_pic_url_hd": None,  # Don't send Instagram URLs, they cause CORS errors

                    # Collaboration Data - BOTH creators for collaboration posts
                    "collaborators": collaborators,
                    "is_collaboration": len(collaborators) > 0,
                    "total_creators": 1 + len([c for c in collaborators if c['collaboration_type'] == 'coauthor_producer'])
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
        NOW INCLUDES: Manual creators + Post collaborators

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)

        Returns:
            List of creator data with aggregated analytics (manual + collaborators)
        """
        try:
            # Verify campaign ownership
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return []

            # Get manually added creators
            result = await db.execute(
                select(CampaignCreator)
                .where(CampaignCreator.campaign_id == campaign_id)
                .order_by(desc(CampaignCreator.added_at))
            )
            campaign_creators = result.scalars().all()

            # Get unique collaborators from posts (coauthor_producers) - Fixed SQL query
            collaborator_query = text("""
                SELECT DISTINCT p.id, p.username, p.full_name, p.followers_count, p.profile_pic_url
                FROM campaign_posts cp
                JOIN posts post ON cp.post_id = post.id
                CROSS JOIN jsonb_array_elements(post.coauthor_producers) AS collaborator
                JOIN profiles p ON p.username = collaborator->>'username'
                WHERE cp.campaign_id = :campaign_id
                  AND post.coauthor_producers IS NOT NULL
                  AND jsonb_array_length(post.coauthor_producers) > 0
            """)

            collaborator_result = await db.execute(collaborator_query, {"campaign_id": campaign_id})
            collaborator_profiles = collaborator_result.all()

            # Initialize CDN sync service
            cdn_sync = CDNSyncService()

            # Format response with aggregated analytics
            creators_data = []
            for cc in campaign_creators:
                profile = cc.profile

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

                # CRITICAL: Skip creators with 0 posts (orphaned entries)
                if post_count == 0:
                    continue

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

                # Get CDN URL for profile picture (never use Instagram URLs due to CORS)
                creator_cdn_profile_url = await cdn_sync.get_profile_cdn_url(
                    db=db,
                    profile_id=str(profile.id),
                    username=profile.username
                )

                creator_data = {
                    "campaign_creator_id": str(cc.id),
                    "profile_id": str(profile.id),
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "profile_pic_url": creator_cdn_profile_url,  # Always use CDN URL to avoid CORS
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

                    # Audience Demographics (extracted from ai_audience_insights)
                    "audience_demographics": None
                }

                # Extract demographics from AI insights (stored in profile.ai_audience_insights JSONB)
                if profile.ai_audience_insights:
                    ai_insights = profile.ai_audience_insights
                    demographic_insights = ai_insights.get('demographic_insights', {})
                    geographic_analysis = ai_insights.get('geographic_analysis', {})

                    # Extract demographics from AI insights
                    gender_split = demographic_insights.get('estimated_gender_split', {})
                    age_groups = demographic_insights.get('estimated_age_groups', {})
                    country_dist = geographic_analysis.get('country_distribution', {})
                    location_dist = geographic_analysis.get('location_distribution', {})

                    # Keep in 0-1 format for aggregation (aggregation function will convert to 0-100)
                    creator_data["audience_demographics"] = {
                        "gender_distribution": {k.upper(): v for k, v in gender_split.items()},
                        "age_distribution": {k: v for k, v in age_groups.items()},
                        "country_distribution": {k: v for k, v in country_dist.items()},
                        "city_distribution": {k: v for k, v in location_dist.items()}
                    }

                creators_data.append(creator_data)

            # Process collaborators (coauthor_producers from posts)
            processed_usernames = {creator["username"] for creator in creators_data}

            for collaborator in collaborator_profiles:
                # Skip if already processed as manual creator
                if collaborator.username in processed_usernames:
                    continue

                # Count posts where this collaborator appears - Fixed SQL query
                collab_count_query = text("""
                    SELECT COUNT(cp.id)
                    FROM campaign_posts cp
                    JOIN posts p ON cp.post_id = p.id
                    CROSS JOIN jsonb_array_elements(p.coauthor_producers) AS collaborator
                    WHERE cp.campaign_id = :campaign_id
                      AND collaborator->>'username' = :username
                      AND p.coauthor_producers IS NOT NULL
                      AND jsonb_array_length(p.coauthor_producers) > 0
                """)

                collab_post_count_result = await db.execute(
                    collab_count_query,
                    {"campaign_id": campaign_id, "username": collaborator.username}
                )
                collab_post_count = collab_post_count_result.scalar() or 0

                if collab_post_count == 0:
                    continue

                # Get CDN URL for collaborator profile picture
                collab_cdn_profile_url = await cdn_sync.get_profile_cdn_url(
                    db=db,
                    profile_id=str(collaborator.id),
                    username=collaborator.username
                )

                # Add collaborator to creators list
                collaborator_data = {
                    "campaign_creator_id": None,  # Collaborators don't have campaign_creator_id
                    "profile_id": str(collaborator.id),
                    "username": collaborator.username,
                    "full_name": collaborator.full_name,
                    "profile_pic_url": collab_cdn_profile_url,
                    "added_at": None,  # Collaborators aren't manually added
                    "creator_type": "collaborator",  # Mark as collaborator

                    # Profile metrics
                    "followers_count": collaborator.followers_count or 0,
                    "following_count": 0,  # Not available for collaborators
                    "posts_count": 0,  # Not available for collaborators
                    "is_verified": False,  # Not available for collaborators

                    # Campaign-specific metrics
                    "posts_in_campaign": collab_post_count,
                    "total_likes": 0,  # Collaborators don't have direct engagement metrics
                    "total_comments": 0,
                    "avg_engagement_rate": 0.0,

                    # AI Analysis (not available for collaborators)
                    "ai_primary_content_type": None,
                    "ai_top_3_categories": None,
                    "ai_content_quality_score": 0.0,
                    "audience_demographics": None
                }

                creators_data.append(collaborator_data)
                processed_usernames.add(collaborator.username)

            logger.info(f"✅ Retrieved {len(creators_data)} creators for campaign {campaign_id} (including collaborators)")
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

            # Count creators with demographics
            creators_with_demographics = [c for c in creators if c.get("audience_demographics")]

            # Calculate total reach (only from creators with demographics)
            for creator in creators_with_demographics:
                total_reach += creator.get("followers_count", 0)

            # If total reach is 0 (all creators have 0 followers), use equal weighting
            use_equal_weight = (total_reach == 0)

            for creator in creators_with_demographics:
                demographics = creator.get("audience_demographics")
                if not demographics:
                    continue

                # Weighted aggregation based on follower count
                # Fallback to equal weight if all creators have 0 followers
                if use_equal_weight:
                    weight = 1.0 / len(creators_with_demographics)
                else:
                    followers = creator.get("followers_count", 0)
                    weight = followers / total_reach

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

            # Helper to find top item from distribution
            def find_top(distribution: dict):
                if not distribution:
                    return None
                normalized = normalize_dict(distribution)
                top_key = max(normalized, key=normalized.get)
                return {
                    "name": top_key,
                    "percentage": normalized[top_key]
                }

            # Find top items for frontend
            top_gender = find_top(aggregated_gender)
            top_age_group = find_top(aggregated_age)
            top_country = find_top(aggregated_country)
            top_city = find_top(aggregated_city)

            result = {
                "total_reach": total_reach,
                "total_creators": len(creators),
                "gender_distribution": normalize_dict(aggregated_gender),
                "age_distribution": normalize_dict(aggregated_age),
                "country_distribution": normalize_dict(aggregated_country),
                "city_distribution": normalize_dict(aggregated_city),

                # Top items for frontend display
                "topGender": top_gender,
                "topAgeGroup": top_age_group,
                "topCountry": top_country,
                "topCity": top_city
            }

            logger.info(f"✅ Aggregated audience for campaign {campaign_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to aggregate campaign audience: {e}")
            raise

    async def get_campaign_stats(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get quick statistics for a single campaign (for campaigns list page)

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)

        Returns:
            Quick stats including creators_count, posts_count, total_reach, engagement_rate
        """
        try:
            # Get campaign
            campaign = await self.get_campaign(db, campaign_id, user_id)
            if not campaign:
                return {
                    "creators_count": 0,
                    "posts_count": 0,
                    "total_reach": 0,
                    "engagement_rate": 0.0
                }

            # Get counts using efficient queries
            from app.database.unified_models import CampaignPost, CampaignCreator

            # Count posts
            posts_result = await db.execute(
                select(func.count(CampaignPost.id))
                .where(CampaignPost.campaign_id == campaign_id)
            )
            posts_count = posts_result.scalar() or 0

            # Count creators and calculate total reach
            # ONLY include creators that have posts in this campaign (exclude orphaned entries)
            creators_with_posts_query = select(CampaignCreator).select_from(
                CampaignCreator
            ).join(
                Post, CampaignCreator.profile_id == Post.profile_id
            ).join(
                CampaignPost, and_(
                    CampaignPost.post_id == Post.id,
                    CampaignPost.campaign_id == campaign_id
                )
            ).where(
                CampaignCreator.campaign_id == campaign_id
            ).distinct().options(selectinload(CampaignCreator.profile))

            creators_result = await db.execute(creators_with_posts_query)
            campaign_profiles = creators_result.scalars().all()

            creators_count = len(campaign_profiles)
            total_reach = sum(cp.profile.followers_count or 0 for cp in campaign_profiles)

            # Calculate average engagement rate from campaign posts
            # Get all posts with their engagement data
            posts_query = await db.execute(
                select(Post, Profile.followers_count)
                .join(CampaignPost, CampaignPost.post_id == Post.id)
                .join(Profile, Profile.id == Post.profile_id)
                .where(CampaignPost.campaign_id == campaign_id)
            )
            posts_data = posts_query.all()

            engagement_rates = []
            for post, followers_count in posts_data:
                if post.engagement_rate is not None:
                    engagement_rates.append(float(post.engagement_rate))
                elif followers_count and followers_count > 0:
                    # Calculate on-the-fly if missing
                    calculated_rate = ((post.likes_count or 0) + (post.comments_count or 0)) / followers_count * 100
                    engagement_rates.append(calculated_rate)

            avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0

            return {
                "creators_count": creators_count,
                "posts_count": posts_count,
                "total_reach": total_reach,
                "engagement_rate": round(avg_engagement, 4)
            }

        except Exception as e:
            logger.error(f"❌ Failed to get campaign stats: {e}")
            return {
                "creators_count": 0,
                "posts_count": 0,
                "total_reach": 0,
                "engagement_rate": 0.0
            }

    async def cleanup_orphaned_creators(
        self,
        db: AsyncSession,
        campaign_id: UUID
    ) -> int:
        """
        Remove creators from campaign_creators that have 0 posts in the campaign

        Args:
            db: Database session
            campaign_id: Campaign ID

        Returns:
            Number of orphaned creators removed
        """
        try:
            # Find all creators in this campaign
            all_creators_query = select(CampaignCreator).where(
                CampaignCreator.campaign_id == campaign_id
            )
            all_creators_result = await db.execute(all_creators_query)
            all_creators = all_creators_result.scalars().all()

            removed_count = 0

            for creator in all_creators:
                # Count posts from this creator in this campaign
                posts_count_query = select(func.count(CampaignPost.id)).select_from(
                    CampaignPost
                ).join(
                    Post, CampaignPost.post_id == Post.id
                ).where(
                    and_(
                        CampaignPost.campaign_id == campaign_id,
                        Post.profile_id == creator.profile_id
                    )
                )
                posts_count_result = await db.execute(posts_count_query)
                posts_count = posts_count_result.scalar() or 0

                # If no posts, remove the creator entry
                if posts_count == 0:
                    await db.delete(creator)
                    removed_count += 1
                    logger.info(f"✅ Removed orphaned creator {creator.profile_id} from campaign {campaign_id}")

            await db.commit()
            logger.info(f"✅ Cleaned up {removed_count} orphaned creators from campaign {campaign_id}")
            return removed_count

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to cleanup orphaned creators: {e}")
            raise


# Global service instance
campaign_service = CampaignService()
