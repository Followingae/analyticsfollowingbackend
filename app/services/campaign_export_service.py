"""
Campaign Export Service
Export campaign data to CSV and JSON formats
"""

import logging
import csv
import json
import io
from typing import Dict, List, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.campaign_service import campaign_service

logger = logging.getLogger(__name__)


class CampaignExportService:
    """Service for exporting campaign data"""

    async def export_campaign_to_csv(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID,
        include_posts: bool = True,
        include_creators: bool = True,
        include_audience: bool = True
    ) -> str:
        """
        Export campaign data to CSV format

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)
            include_posts: Include posts data
            include_creators: Include creators data
            include_audience: Include audience aggregation

        Returns:
            CSV content as string
        """
        try:
            # Get campaign details
            campaign = await campaign_service.get_campaign(db, campaign_id, user_id)
            if not campaign:
                raise ValueError("Campaign not found")

            output = io.StringIO()
            writer = csv.writer(output)

            # Campaign Overview Section
            writer.writerow(["=== CAMPAIGN OVERVIEW ==="])
            writer.writerow(["Campaign Name", campaign.name])
            writer.writerow(["Brand Name", campaign.brand_name])
            writer.writerow(["Status", campaign.status])
            writer.writerow(["Created At", campaign.created_at.isoformat()])
            writer.writerow(["Updated At", campaign.updated_at.isoformat()])
            writer.writerow([])

            # Posts Section
            if include_posts:
                posts = await campaign_service.get_campaign_posts(db, campaign_id, user_id)

                writer.writerow(["=== CAMPAIGN POSTS ==="])
                writer.writerow([
                    "Post URL",
                    "Creator Username",
                    "Creator Full Name",
                    "Likes",
                    "Comments",
                    "Engagement Rate",
                    "Content Category",
                    "Sentiment",
                    "Language",
                    "Added At"
                ])

                for post in posts:
                    writer.writerow([
                        post.get("instagram_post_url"),
                        post.get("creator_username"),
                        post.get("creator_full_name"),
                        post.get("likes_count"),
                        post.get("comments_count"),
                        f"{post.get('engagement_rate', 0):.2f}%",
                        post.get("ai_content_category"),
                        post.get("ai_sentiment"),
                        post.get("ai_language_code"),
                        post.get("added_at")
                    ])

                writer.writerow([])

            # Creators Section
            if include_creators:
                creators = await campaign_service.get_campaign_creators(db, campaign_id, user_id)

                writer.writerow(["=== CAMPAIGN CREATORS ==="])
                writer.writerow([
                    "Username",
                    "Full Name",
                    "Followers",
                    "Following",
                    "Total Posts",
                    "Verified",
                    "Posts in Campaign",
                    "Total Likes",
                    "Total Comments",
                    "Avg Engagement Rate",
                    "Primary Content Type",
                    "Content Quality Score"
                ])

                for creator in creators:
                    writer.writerow([
                        creator.get("username"),
                        creator.get("full_name"),
                        creator.get("followers_count"),
                        creator.get("following_count"),
                        creator.get("posts_count"),
                        "Yes" if creator.get("is_verified") else "No",
                        creator.get("posts_in_campaign"),
                        creator.get("total_likes"),
                        creator.get("total_comments"),
                        f"{creator.get('avg_engagement_rate', 0):.2f}%",
                        creator.get("ai_primary_content_type"),
                        f"{creator.get('ai_content_quality_score', 0):.2f}"
                    ])

                writer.writerow([])

            # Audience Aggregation Section
            if include_audience:
                audience = await campaign_service.get_campaign_audience_aggregation(db, campaign_id, user_id)

                writer.writerow(["=== AGGREGATED AUDIENCE ==="])
                writer.writerow(["Total Reach", audience.get("total_reach", 0)])
                writer.writerow(["Total Creators", audience.get("total_creators", 0)])
                writer.writerow([])

                # Gender Distribution
                writer.writerow(["Gender Distribution"])
                writer.writerow(["Gender", "Percentage"])
                gender_dist = audience.get("gender_distribution", {})
                for gender, percentage in gender_dist.items():
                    writer.writerow([gender, f"{percentage}%"])
                writer.writerow([])

                # Age Distribution
                writer.writerow(["Age Distribution"])
                writer.writerow(["Age Range", "Percentage"])
                age_dist = audience.get("age_distribution", {})
                for age_range, percentage in age_dist.items():
                    writer.writerow([age_range, f"{percentage}%"])
                writer.writerow([])

                # Country Distribution (Top 10)
                writer.writerow(["Top 10 Countries"])
                writer.writerow(["Country", "Percentage"])
                country_dist = audience.get("country_distribution", {})
                sorted_countries = sorted(country_dist.items(), key=lambda x: x[1], reverse=True)[:10]
                for country, percentage in sorted_countries:
                    writer.writerow([country, f"{percentage}%"])

            csv_content = output.getvalue()
            output.close()

            logger.info(f"✅ Exported campaign {campaign_id} to CSV ({len(csv_content)} bytes)")
            return csv_content

        except Exception as e:
            logger.error(f"❌ Failed to export campaign to CSV: {e}")
            raise

    async def export_campaign_to_json(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID,
        include_posts: bool = True,
        include_creators: bool = True,
        include_audience: bool = True
    ) -> str:
        """
        Export campaign data to JSON format

        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)
            include_posts: Include posts data
            include_creators: Include creators data
            include_audience: Include audience aggregation

        Returns:
            JSON content as string
        """
        try:
            # Get campaign details
            campaign = await campaign_service.get_campaign(db, campaign_id, user_id)
            if not campaign:
                raise ValueError("Campaign not found")

            export_data = {
                "campaign": {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "brand_name": campaign.brand_name,
                    "brand_logo_url": campaign.brand_logo_url,
                    "status": campaign.status,
                    "created_at": campaign.created_at.isoformat(),
                    "updated_at": campaign.updated_at.isoformat()
                }
            }

            # Add posts
            if include_posts:
                posts = await campaign_service.get_campaign_posts(db, campaign_id, user_id)
                export_data["posts"] = posts
                export_data["posts_count"] = len(posts)

            # Add creators
            if include_creators:
                creators = await campaign_service.get_campaign_creators(db, campaign_id, user_id)
                export_data["creators"] = creators
                export_data["creators_count"] = len(creators)

            # Add audience aggregation
            if include_audience:
                audience = await campaign_service.get_campaign_audience_aggregation(db, campaign_id, user_id)
                export_data["audience"] = audience

            # Convert to formatted JSON
            json_content = json.dumps(export_data, indent=2, ensure_ascii=False)

            logger.info(f"✅ Exported campaign {campaign_id} to JSON ({len(json_content)} bytes)")
            return json_content

        except Exception as e:
            logger.error(f"❌ Failed to export campaign to JSON: {e}")
            raise

    async def export_all_campaigns_summary(
        self,
        db: AsyncSession,
        user_id: UUID,
        format: str = "csv"
    ) -> str:
        """
        Export summary of all user's campaigns

        Args:
            db: Database session
            user_id: User ID
            format: Export format ('csv' or 'json')

        Returns:
            Export content as string
        """
        try:
            # Get all campaigns
            campaigns = await campaign_service.list_campaigns(
                db=db,
                user_id=user_id,
                limit=1000  # Get all campaigns
            )

            if format == "csv":
                output = io.StringIO()
                writer = csv.writer(output)

                writer.writerow([
                    "Campaign Name",
                    "Brand Name",
                    "Status",
                    "Posts Count",
                    "Creators Count",
                    "Created At",
                    "Updated At"
                ])

                for campaign in campaigns:
                    # Get counts
                    posts = await campaign_service.get_campaign_posts(db, campaign.id, user_id)
                    creators = await campaign_service.get_campaign_creators(db, campaign.id, user_id)

                    writer.writerow([
                        campaign.name,
                        campaign.brand_name,
                        campaign.status,
                        len(posts),
                        len(creators),
                        campaign.created_at.isoformat(),
                        campaign.updated_at.isoformat()
                    ])

                content = output.getvalue()
                output.close()

            else:  # JSON
                campaigns_data = []
                for campaign in campaigns:
                    posts = await campaign_service.get_campaign_posts(db, campaign.id, user_id)
                    creators = await campaign_service.get_campaign_creators(db, campaign.id, user_id)

                    campaigns_data.append({
                        "id": str(campaign.id),
                        "name": campaign.name,
                        "brand_name": campaign.brand_name,
                        "status": campaign.status,
                        "posts_count": len(posts),
                        "creators_count": len(creators),
                        "created_at": campaign.created_at.isoformat(),
                        "updated_at": campaign.updated_at.isoformat()
                    })

                content = json.dumps({
                    "campaigns": campaigns_data,
                    "total_campaigns": len(campaigns_data)
                }, indent=2, ensure_ascii=False)

            logger.info(f"✅ Exported {len(campaigns)} campaigns summary to {format.upper()}")
            return content

        except Exception as e:
            logger.error(f"❌ Failed to export campaigns summary: {e}")
            raise


# Global service instance
campaign_export_service = CampaignExportService()
