"""
Campaign Workflow API Routes - Dual Flow System
=================================================
USER Flow: Simple campaign creation → Add post links → Get reports
SUPERADMIN Flow: Full workflow → Select influencers → Lock → Content approval → Reports

Author: Analytics Following Backend
Date: January 2025
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, text
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.optimized_pools import get_db_optimized as get_db
from app.database.unified_models import (
    Campaign, CampaignInfluencerSelection, CampaignContentApproval,
    CampaignWorkflowNotification, CampaignWorkflowState, Profile, Post
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns/workflow", tags=["Campaign Workflow"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateUserCampaignRequest(BaseModel):
    """USER campaign creation - simple flow"""
    name: str
    brand_name: str
    brand_logo_url: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    campaign_type: Optional[str] = 'influencer'  # influencer | ugc

class CreateSuperadminCampaignRequest(BaseModel):
    """SUPERADMIN campaign creation - full workflow"""
    user_id: UUID  # Campaign is FOR this user
    name: str
    brand_name: str
    brand_logo_url: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    campaign_type: Optional[str] = 'influencer'  # influencer | ugc

class SelectInfluencerRequest(BaseModel):
    """Select influencer for campaign"""
    profile_id: UUID
    selection_notes: Optional[str] = None
    estimated_cost: Optional[float] = None

class LockInfluencersRequest(BaseModel):
    """Lock selected influencers (superadmin action)"""
    selection_ids: List[UUID]
    lock_duration_hours: int = 48  # Default 48 hour lock

class SubmitContentRequest(BaseModel):
    """Submit content for approval"""
    profile_id: UUID
    content_type: str  # 'draft', 'final', 'published'
    content_url: Optional[str] = None
    content_caption: Optional[str] = None
    content_media_urls: Optional[List[str]] = None

class ReviewContentRequest(BaseModel):
    """Review submitted content (superadmin action)"""
    approval_status: str  # 'approved', 'rejected', 'revision_requested'
    reviewer_notes: Optional[str] = None
    revision_notes: Optional[str] = None

# =============================================================================
# USER CAMPAIGN FLOW - Simple Creation
# =============================================================================

@router.post("/user/create")
async def create_user_campaign(
    request: CreateUserCampaignRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    USER FLOW: Create a simple campaign

    Flow:
    1. User creates campaign with basic details
    2. User adds post links directly (no influencer selection)
    3. System generates reports automatically

    No workflow state needed - goes straight to 'active'
    """
    try:
        # Validate campaign_type
        campaign_type = request.campaign_type or 'influencer'
        if campaign_type not in ('influencer', 'ugc'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="campaign_type must be 'influencer' or 'ugc'"
            )

        import uuid as uuid_lib
        campaign_id = str(uuid_lib.uuid4())

        # Raw SQL INSERT (PGBouncer AUTOCOMMIT - ORM db.add() silently fails)
        result = await db.execute(
            text("""
                INSERT INTO campaigns (id, user_id, name, brand_name, brand_logo_url, description,
                    budget, start_date, end_date, status, created_by, campaign_type)
                VALUES (:id, :user_id, :name, :brand_name, :brand_logo_url, :description,
                    :budget, :start_date, :end_date, 'active', 'user', :campaign_type)
                RETURNING id, name, brand_name, brand_logo_url, status, created_by, campaign_type, created_at
            """).execution_options(prepare=False),
            {
                "id": campaign_id,
                "user_id": str(current_user.id),
                "name": request.name,
                "brand_name": request.brand_name,
                "brand_logo_url": request.brand_logo_url,
                "description": request.description,
                "budget": request.budget,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "campaign_type": campaign_type
            }
        )
        row = result.fetchone()

        logger.info(f"User {current_user.email} created campaign: {row.name}")

        return {
            "success": True,
            "data": {
                "id": str(row.id),
                "name": row.name,
                "brand_name": row.brand_name,
                "brand_logo_url": row.brand_logo_url,
                "status": row.status,
                "created_by": row.created_by,
                "campaign_type": row.campaign_type,
                "created_at": row.created_at.isoformat(),
                "message": "Campaign created! You can now add Instagram post links to track performance."
            },
            "message": "User campaign created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user campaign: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}"
        )

# =============================================================================
# SUPERADMIN CAMPAIGN FLOW - Full Workflow
# =============================================================================

@router.post("/superadmin/create")
async def create_superadmin_campaign(
    request: CreateSuperadminCampaignRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    SUPERADMIN FLOW: Create campaign with full workflow

    Flow:
    1. Superadmin creates campaign FOR a user
    2. Moves to 'influencer_selection' stage
    3. User selects influencers
    4. Superadmin reviews and locks selections
    5. Content submission and approval workflow
    6. Campaign goes live

    Creates workflow state to track progress
    """
    try:
        # Verify superadmin
        if current_user.role != 'superadmin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can create workflow campaigns"
            )

        # Validate campaign_type
        campaign_type = request.campaign_type or 'influencer'
        if campaign_type not in ('influencer', 'ugc'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="campaign_type must be 'influencer' or 'ugc'"
            )

        import uuid as uuid_lib

        # Raw SQL INSERT for campaign (PGBouncer AUTOCOMMIT)
        campaign_id = str(uuid_lib.uuid4())
        campaign_result = await db.execute(
            text("""
                INSERT INTO campaigns (id, user_id, name, brand_name, brand_logo_url, description,
                    budget, start_date, end_date, status, created_by, campaign_type)
                VALUES (:id, :user_id, :name, :brand_name, :brand_logo_url, :description,
                    :budget, :start_date, :end_date, 'draft', 'superadmin', :campaign_type)
                RETURNING id, name, brand_name, status, created_by, campaign_type, created_at
            """).execution_options(prepare=False),
            {
                "id": campaign_id,
                "user_id": str(request.user_id),
                "name": request.name,
                "brand_name": request.brand_name,
                "brand_logo_url": request.brand_logo_url,
                "description": request.description,
                "budget": request.budget,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "campaign_type": campaign_type
            }
        )
        campaign_row = campaign_result.fetchone()

        # Raw SQL INSERT for workflow state
        workflow_id = str(uuid_lib.uuid4())
        now_utc = datetime.now(timezone.utc)
        await db.execute(
            text("""
                INSERT INTO campaign_workflow_state (id, campaign_id, current_stage, draft_started_at, selection_started_at)
                VALUES (:id, :campaign_id, 'influencer_selection', :draft_started_at, :selection_started_at)
            """).execution_options(prepare=False),
            {
                "id": workflow_id,
                "campaign_id": campaign_id,
                "draft_started_at": now_utc,
                "selection_started_at": now_utc
            }
        )

        # Raw SQL INSERT for notification
        import json
        notification_id = str(uuid_lib.uuid4())
        admin_name = current_user.full_name or current_user.email
        await db.execute(
            text("""
                INSERT INTO campaign_workflow_notifications (id, campaign_id, notification_type, recipient_id,
                    title, message, action_url, metadata)
                VALUES (:id, :campaign_id, 'influencer_selected', :recipient_id,
                    :title, :message, :action_url, :metadata::jsonb)
            """).execution_options(prepare=False),
            {
                "id": notification_id,
                "campaign_id": campaign_id,
                "recipient_id": str(request.user_id),
                "title": f"New Campaign: {request.name}",
                "message": f"A new campaign has been created for you by {admin_name}. Please select influencers to proceed.",
                "action_url": f"/campaigns/{campaign_id}/select-influencers",
                "metadata": json.dumps({"campaign_id": campaign_id, "created_by_admin": current_user.email})
            }
        )

        logger.info(f"Superadmin {current_user.email} created workflow campaign: {campaign_row.name} for user {request.user_id}")

        return {
            "success": True,
            "data": {
                "id": str(campaign_row.id),
                "name": campaign_row.name,
                "brand_name": campaign_row.brand_name,
                "status": campaign_row.status,
                "created_by": campaign_row.created_by,
                "campaign_type": campaign_row.campaign_type,
                "workflow_stage": "influencer_selection",
                "created_at": campaign_row.created_at.isoformat(),
                "message": "Campaign created! Awaiting influencer selection from user."
            },
            "message": "Superadmin campaign created with workflow"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating superadmin campaign: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}"
        )

# =============================================================================
# INFLUENCER SELECTION (USER ACTION IN SUPERADMIN FLOW)
# =============================================================================

@router.post("/{campaign_id}/select-influencer")
async def select_influencer(
    campaign_id: UUID,
    request: SelectInfluencerRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    USER ACTION: Select an influencer for the campaign

    Only available for superadmin-created campaigns
    User can select multiple influencers
    """
    try:
        # Verify campaign ownership
        result = await db.execute(
            select(Campaign).where(
                and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
            )
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        if campaign.created_by != 'superadmin':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This campaign does not use the workflow system"
            )

        # Check if already selected
        result = await db.execute(
            select(CampaignInfluencerSelection).where(
                and_(
                    CampaignInfluencerSelection.campaign_id == campaign_id,
                    CampaignInfluencerSelection.profile_id == request.profile_id
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Influencer already selected for this campaign"
            )

        import uuid as uuid_lib

        # Raw SQL INSERT for selection (PGBouncer AUTOCOMMIT)
        selection_id = str(uuid_lib.uuid4())
        await db.execute(
            text("""
                INSERT INTO campaign_influencer_selections (id, campaign_id, profile_id, selected_by,
                    selection_status, selection_notes, estimated_cost)
                VALUES (:id, :campaign_id, :profile_id, :selected_by,
                    'pending', :selection_notes, :estimated_cost)
            """).execution_options(prepare=False),
            {
                "id": selection_id,
                "campaign_id": str(campaign_id),
                "profile_id": str(request.profile_id),
                "selected_by": str(current_user.id),
                "selection_notes": request.selection_notes,
                "estimated_cost": request.estimated_cost
            }
        )

        # Update workflow state counter
        await db.execute(
            text("""
                UPDATE campaign_workflow_state
                SET influencers_selected = influencers_selected + 1,
                    updated_at = NOW()
                WHERE campaign_id = :campaign_id
            """).execution_options(prepare=False),
            {"campaign_id": str(campaign_id)}
        )

        # Raw SQL INSERT for notification
        notification_id = str(uuid_lib.uuid4())
        user_name = current_user.full_name or current_user.email
        await db.execute(
            text("""
                INSERT INTO campaign_workflow_notifications (id, campaign_id, notification_type, recipient_id,
                    title, message, action_url)
                VALUES (:id, :campaign_id, 'influencer_selected', :recipient_id,
                    :title, :message, :action_url)
            """).execution_options(prepare=False),
            {
                "id": notification_id,
                "campaign_id": str(campaign_id),
                "recipient_id": str(current_user.id),
                "title": f"Influencer Selected: {campaign.name}",
                "message": f"{user_name} selected an influencer. Please review and lock selections.",
                "action_url": f"/admin/campaigns/{campaign_id}/review-selections"
            }
        )

        logger.info(f"User {current_user.email} selected influencer for campaign {campaign_id}")

        return {
            "success": True,
            "data": {
                "selection_id": selection_id,
                "profile_id": str(request.profile_id),
                "status": "pending",
                "message": "Influencer selected! Awaiting superadmin review."
            },
            "message": "Influencer selected successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error selecting influencer: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select influencer: {str(e)}"
        )

# Continue in next section...
