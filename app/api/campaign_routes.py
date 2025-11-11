"""
Campaign API Routes - Brand Campaign Management
Complete CRUD operations for campaigns, posts, and creators
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.campaign_service import campaign_service
from app.services.standalone_post_analytics_service import standalone_post_analytics_service
from app.services.brand_logo_service import brand_logo_service
from app.services.campaign_export_service import campaign_export_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateCampaignRequest(BaseModel):
    """Request model for creating a campaign"""
    name: str
    brand_name: str
    brand_logo_url: Optional[str] = None

class UpdateCampaignRequest(BaseModel):
    """Request model for updating a campaign"""
    name: Optional[str] = None
    brand_name: Optional[str] = None
    brand_logo_url: Optional[str] = None
    status: Optional[str] = None

class AddPostRequest(BaseModel):
    """Request model for adding a post to campaign"""
    instagram_post_url: str

# =============================================================================
# CAMPAIGN CRUD ENDPOINTS
# =============================================================================

@router.post("/")
async def create_campaign(
    request: CreateCampaignRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new campaign

    Creates a new brand campaign for managing Instagram posts and creators.

    Request Body:
    - name: Campaign name
    - brand_name: Brand name
    - brand_logo_url: Optional CDN URL for brand logo
    """
    try:
        campaign = await campaign_service.create_campaign(
            db=db,
            user_id=current_user.id,
            name=request.name,
            brand_name=request.brand_name,
            brand_logo_url=request.brand_logo_url
        )

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "name": campaign.name,
                "brand_name": campaign.brand_name,
                "brand_logo_url": campaign.brand_logo_url,
                "status": campaign.status,
                "created_at": campaign.created_at.isoformat(),
                "updated_at": campaign.updated_at.isoformat()
            },
            "message": "Campaign created successfully"
        }

    except Exception as e:
        logger.error(f"❌ Error creating campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create campaign"
        )

@router.get("/overview")
async def get_campaigns_overview(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get campaigns dashboard overview

    Returns comprehensive dashboard with:
    - Total campaigns, active campaigns counts
    - 30-day trend analysis vs previous period
    - Engagement rate trends
    - Spend tracking with trends
    - Recent campaigns (last 5)
    - Top creators leaderboard
    """
    try:
        logger.info(f"📊 Getting campaigns overview for user {current_user.email}")
        overview = await campaign_service.get_campaigns_overview(db, current_user.id)

        return {
            "success": True,
            "data": overview,
            "message": "Campaigns overview retrieved successfully"
        }

    except Exception as e:
        logger.error(f"❌ Error retrieving campaigns overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve campaigns overview: {str(e)}"
        )

@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get campaign details

    Returns complete campaign information including posts and creators.
    """
    try:
        campaign = await campaign_service.get_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        # Get campaign stats
        stats = await campaign_service.get_campaign_stats(db, campaign_id, current_user.id)

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "name": campaign.name,
                "brand_name": campaign.brand_name,
                "brand_logo_url": campaign.brand_logo_url,
                "status": campaign.status,
                "created_at": campaign.created_at.isoformat(),
                "updated_at": campaign.updated_at.isoformat(),
                "posts_count": stats.get('posts_count', 0),
                "creators_count": stats.get('creators_count', 0),
                "total_reach": stats.get('total_reach', 0),
                "engagement_rate": stats.get('engagement_rate', 0.0)
            },
            "message": "Campaign retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign"
        )

@router.get("/")
async def list_campaigns(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List user's campaigns

    Query Parameters:
    - status_filter: Optional filter by status (draft, active, completed)
    - limit: Max results (default: 50)
    - offset: Pagination offset (default: 0)
    """
    try:
        campaigns = await campaign_service.list_campaigns(
            db=db,
            user_id=current_user.id,
            status=status_filter,
            limit=limit,
            offset=offset
        )

        # Get summary statistics (Frontend required)
        summary = await campaign_service.get_campaigns_summary(
            db=db,
            user_id=current_user.id
        )

        # Build campaigns data with per-campaign stats
        campaigns_data = []
        for c in campaigns:
            # Get quick stats for this campaign
            stats = await campaign_service.get_campaign_stats(
                db=db,
                campaign_id=c.id,
                user_id=current_user.id
            )

            campaigns_data.append({
                "id": str(c.id),
                "name": c.name,
                "brand_name": c.brand_name,
                "brand_logo_url": c.brand_logo_url,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),

                # Per-campaign statistics
                "creators_count": stats["creators_count"],
                "posts_count": stats["posts_count"],
                "total_reach": stats["total_reach"],
                "engagement_rate": stats["engagement_rate"]
            })

        return {
            "success": True,
            "data": {
                "campaigns": campaigns_data,
                "summary": summary,  # Frontend required: totalCampaigns, totalCreators, totalReach, avgEngagementRate
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(campaigns_data),
                    "has_more": len(campaigns_data) == limit
                }
            },
            "message": f"Retrieved {len(campaigns_data)} campaigns"
        }

    except Exception as e:
        logger.error(f"❌ Error listing campaigns: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list campaigns"
        )

@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    request: UpdateCampaignRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update campaign details

    Partial update - only provided fields will be updated.

    Request Body:
    - name: Optional new campaign name
    - brand_name: Optional new brand name
    - brand_logo_url: Optional new brand logo URL
    - status: Optional new status (draft, active, completed)
    """
    try:
        campaign = await campaign_service.update_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id,
            name=request.name,
            brand_name=request.brand_name,
            brand_logo_url=request.brand_logo_url,
            status=request.status
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "name": campaign.name,
                "brand_name": campaign.brand_name,
                "brand_logo_url": campaign.brand_logo_url,
                "status": campaign.status,
                "updated_at": campaign.updated_at.isoformat()
            },
            "message": "Campaign updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update campaign"
        )

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete campaign

    Cascade deletes all associated posts and creators.
    """
    try:
        success = await campaign_service.delete_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "message": "Campaign deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete campaign"
        )

# =============================================================================
# CAMPAIGN POST ENDPOINTS
# =============================================================================

@router.post("/{campaign_id}/posts")
async def add_post_to_campaign(
    campaign_id: UUID,
    request: AddPostRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add Instagram post to campaign

    This endpoint:
    1. Runs Post Analytics on the URL (Apify + AI analysis)
    2. Auto-triggers Creator Analytics if new username detected
    3. Adds post to campaign
    4. Auto-populates campaign creators (via database trigger)

    Note: This process takes 5-10 minutes for Post Analytics completion.

    Request Body:
    - instagram_post_url: Instagram post URL (e.g., https://instagram.com/p/ABC123/)
    """
    try:
        logger.info(f"🔍 Adding post to campaign {campaign_id}: {request.instagram_post_url}")

        # STEP 1: Run Post Analytics (includes auto-trigger of Creator Analytics)
        post_analysis = await standalone_post_analytics_service.analyze_post_by_url(
            post_url=request.instagram_post_url,
            db=db,
            user_id=current_user.id
        )

        # STEP 2: Add post to campaign
        campaign_post = await campaign_service.add_post_to_campaign(
            db=db,
            campaign_id=campaign_id,
            post_id=UUID(post_analysis["post_id"]),
            instagram_post_url=request.instagram_post_url,
            user_id=current_user.id
        )

        if not campaign_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "data": {
                "campaign_post_id": str(campaign_post.id),
                "post_analysis": post_analysis,
                "added_at": campaign_post.added_at.isoformat()
            },
            "message": "Post added to campaign successfully"
        }

    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding post to campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add post to campaign"
        )

@router.delete("/{campaign_id}/posts/{post_id}")
async def remove_post_from_campaign(
    campaign_id: UUID,
    post_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove post from campaign

    Note: This does NOT delete the post from the database,
    only removes it from this campaign.
    """
    try:
        success = await campaign_service.remove_post_from_campaign(
            db=db,
            campaign_id=campaign_id,
            post_id=post_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found in campaign"
            )

        return {
            "success": True,
            "message": "Post removed from campaign successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing post from campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove post from campaign"
        )

@router.get("/{campaign_id}/posts")
async def get_campaign_posts(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all posts in campaign

    Returns complete post analytics for each post in the campaign.
    """
    try:
        posts = await campaign_service.get_campaign_posts(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        # Calculate total views across all posts
        total_views = sum(post.get("views", 0) for post in posts)
        total_likes = sum(post.get("likes", 0) for post in posts)
        total_comments = sum(post.get("comments", 0) for post in posts)

        return {
            "success": True,
            "data": {
                "posts": posts,
                "total_posts": len(posts),
                "total_views": total_views,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_engagement": total_likes + total_comments
            },
            "message": f"Retrieved {len(posts)} posts"
        }

    except Exception as e:
        logger.error(f"❌ Error retrieving campaign posts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign posts"
        )

# =============================================================================
# CAMPAIGN CREATOR ENDPOINTS
# =============================================================================

@router.get("/{campaign_id}/creators")
async def get_campaign_creators(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all creators in campaign

    Returns complete creator analytics including:
    - Profile information
    - Campaign-specific metrics (posts count, total engagement)
    - AI content analysis
    - Audience demographics
    """
    try:
        creators = await campaign_service.get_campaign_creators(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        return {
            "success": True,
            "data": {
                "creators": creators,
                "total_creators": len(creators)
            },
            "message": f"Retrieved {len(creators)} creators"
        }

    except Exception as e:
        logger.error(f"❌ Error retrieving campaign creators: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign creators"
        )

@router.get("/{campaign_id}/audience")
async def get_campaign_audience(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated campaign audience

    Aggregates audience demographics across all creators in the campaign,
    weighted by follower count.

    Returns:
    - Total reach (sum of all creator followers)
    - Total creators count
    - Aggregated gender distribution
    - Aggregated age distribution
    - Aggregated country distribution
    """
    try:
        audience = await campaign_service.get_campaign_audience_aggregation(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not audience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "data": audience,
            "message": "Aggregated campaign audience retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving campaign audience: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign audience"
        )

# =============================================================================
# CAMPAIGN OVERVIEW & ANALYTICS
# =============================================================================
# Note: /overview endpoint moved above /{campaign_id} to avoid route conflicts

@router.get("/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: UUID,
    period: str = Query('all', regex='^(7d|30d|90d|all)$'),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed campaign analytics

    Query Parameters:
    - period: Time period ('7d', '30d', '90d', 'all', default: 'all')

    Returns:
    - daily_stats: Array of daily metrics for charting
    - totals: Total reach, views, impressions, engagement
    - performance_insights: Best day, peak day, trend, growth_rate
    """
    try:
        analytics = await campaign_service.get_campaign_analytics(
            db, campaign_id, current_user.id, period
        )

        if not analytics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "data": analytics,
            "message": "Campaign analytics retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving campaign analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign analytics"
        )

# =============================================================================
# CAMPAIGN STATUS MANAGEMENT
# =============================================================================

@router.patch("/{campaign_id}/status")
async def update_campaign_status(
    campaign_id: UUID,
    status: str = Query(..., regex='^(draft|active|paused|completed|in_review|archived)$'),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update campaign status

    Query Parameters:
    - status: New status (draft, active, paused, completed, in_review, archived)

    Valid status transitions:
    - draft → active, in_review
    - active → paused, completed, archived
    - paused → active, archived
    - in_review → active, draft
    """
    try:
        campaign = await campaign_service.update_campaign_status(
            db, campaign_id, current_user.id, status
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "status": campaign.status,
                "updated_at": campaign.updated_at.isoformat()
            },
            "message": f"Campaign status updated to {status}"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating campaign status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update campaign status"
        )

@router.post("/{campaign_id}/restore")
async def restore_campaign(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Restore archived campaign

    Changes status from 'archived' to 'active' and clears archived_at timestamp.
    """
    try:
        campaign = await campaign_service.restore_campaign(db, campaign_id, current_user.id)

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "status": campaign.status,
                "restored_at": campaign.updated_at.isoformat()
            },
            "message": "Campaign restored successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore campaign"
        )

# =============================================================================
# CAMPAIGN CLEANUP & MAINTENANCE
# =============================================================================

@router.post("/{campaign_id}/cleanup")
async def cleanup_campaign_orphaned_creators(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clean up orphaned creators from campaign

    Removes creators from campaign_creators table that have 0 posts in the campaign.
    This can happen when all posts from a creator are removed.
    """
    try:
        removed_count = await campaign_service.cleanup_orphaned_creators(
            db=db,
            campaign_id=campaign_id
        )

        return {
            "success": True,
            "removed_count": removed_count,
            "message": f"Removed {removed_count} orphaned creator(s) from campaign"
        }

    except Exception as e:
        logger.error(f"❌ Error cleaning up campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup campaign"
        )

# =============================================================================
# BRAND LOGO UPLOAD
# =============================================================================

@router.post("/{campaign_id}/logo")
async def upload_brand_logo(
    campaign_id: UUID,
    logo: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload brand logo for campaign

    Accepts image file (PNG, JPEG, WEBP) up to 5MB.
    Logo will be resized to 512x512 and converted to WEBP for optimal CDN delivery.

    Request:
    - Multipart form data with 'logo' field containing the image file

    Returns:
    - CDN URL of the uploaded logo
    """
    try:
        # Verify campaign ownership
        campaign = await campaign_service.get_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        # Read file content
        content = await logo.read()

        # Upload to R2
        success, cdn_url, error_message = await brand_logo_service.upload_brand_logo(
            image_content=content,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message or "Failed to upload logo"
            )

        # Update campaign with new logo URL
        await campaign_service.update_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id,
            brand_logo_url=cdn_url
        )

        return {
            "success": True,
            "data": {
                "cdn_url": cdn_url,
                "campaign_id": str(campaign_id)
            },
            "message": "Brand logo uploaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading brand logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload brand logo"
        )

@router.delete("/{campaign_id}/logo")
async def delete_brand_logo(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete brand logo from campaign

    Removes the logo from R2 storage and updates campaign.
    """
    try:
        # Verify campaign ownership
        campaign = await campaign_service.get_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        if not campaign.brand_logo_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign has no logo"
            )

        # Delete from R2
        await brand_logo_service.delete_brand_logo(campaign.brand_logo_url)

        # Update campaign
        await campaign_service.update_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id,
            brand_logo_url=None
        )

        return {
            "success": True,
            "message": "Brand logo deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting brand logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete brand logo"
        )

# =============================================================================
# CAMPAIGN EXPORT
# =============================================================================

@router.get("/{campaign_id}/export")
async def export_campaign(
    campaign_id: UUID,
    format: str = Query("csv", regex="^(csv|json)$"),
    include_posts: bool = Query(True),
    include_creators: bool = Query(True),
    include_audience: bool = Query(True),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export campaign data to CSV or JSON

    Query Parameters:
    - format: Export format ('csv' or 'json', default: 'csv')
    - include_posts: Include posts data (default: true)
    - include_creators: Include creators data (default: true)
    - include_audience: Include audience aggregation (default: true)

    Returns:
    - File download with campaign data
    """
    try:
        # Get campaign to verify ownership and get name
        campaign = await campaign_service.get_campaign(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        # Export based on format
        if format == "csv":
            content = await campaign_export_service.export_campaign_to_csv(
                db=db,
                campaign_id=campaign_id,
                user_id=current_user.id,
                include_posts=include_posts,
                include_creators=include_creators,
                include_audience=include_audience
            )
            media_type = "text/csv"
            filename = f"{campaign.name.replace(' ', '_')}_campaign_export.csv"

        else:  # json
            content = await campaign_export_service.export_campaign_to_json(
                db=db,
                campaign_id=campaign_id,
                user_id=current_user.id,
                include_posts=include_posts,
                include_creators=include_creators,
                include_audience=include_audience
            )
            media_type = "application/json"
            filename = f"{campaign.name.replace(' ', '_')}_campaign_export.json"

        # Return as downloadable file
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error exporting campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export campaign"
        )

@router.get("/export/all")
async def export_all_campaigns(
    format: str = Query("csv", regex="^(csv|json)$"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export summary of all user's campaigns

    Query Parameters:
    - format: Export format ('csv' or 'json', default: 'csv')

    Returns:
    - File download with campaigns summary
    """
    try:
        content = await campaign_export_service.export_all_campaigns_summary(
            db=db,
            user_id=current_user.id,
            format=format
        )

        if format == "csv":
            media_type = "text/csv"
            filename = "all_campaigns_summary.csv"
        else:
            media_type = "application/json"
            filename = "all_campaigns_summary.json"

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        logger.error(f"❌ Error exporting campaigns summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export campaigns summary"
        )

# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/health/check")
async def campaign_health():
    """Campaign module health check"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "campaigns",
            "features": [
                "campaign_crud",
                "post_management",
                "creator_tracking",
                "audience_aggregation",
                "auto_creator_analytics"
            ]
        },
        "message": "Campaign module is operational"
    }
