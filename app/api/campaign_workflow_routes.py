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
from sqlalchemy import select, and_, func, desc
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
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
        # Create campaign
        campaign = Campaign(
            user_id=current_user.id,
            name=request.name,
            brand_name=request.brand_name,
            brand_logo_url=request.brand_logo_url,
            description=request.description,
            budget=request.budget,
            start_date=request.start_date,
            end_date=request.end_date,
            status='active',  # User campaigns start active
            created_by='user'  # Mark as user-created
        )

        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)

        logger.info(f"✅ User {current_user.email} created campaign: {campaign.name}")

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "name": campaign.name,
                "brand_name": campaign.brand_name,
                "brand_logo_url": campaign.brand_logo_url,
                "status": campaign.status,
                "created_by": campaign.created_by,
                "created_at": campaign.created_at.isoformat(),
                "message": "Campaign created! You can now add Instagram post links to track performance."
            },
            "message": "User campaign created successfully"
        }

    except Exception as e:
        logger.error(f"❌ Error creating user campaign: {e}", exc_info=True)
        await db.rollback()
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

        # Create campaign
        campaign = Campaign(
            user_id=request.user_id,  # FOR this user
            name=request.name,
            brand_name=request.brand_name,
            brand_logo_url=request.brand_logo_url,
            description=request.description,
            budget=request.budget,
            start_date=request.start_date,
            end_date=request.end_date,
            status='draft',  # Workflow campaigns start in draft
            created_by='superadmin'  # Mark as superadmin-created
        )

        db.add(campaign)
        await db.flush()

        # Create workflow state
        workflow_state = CampaignWorkflowState(
            campaign_id=campaign.id,
            current_stage='influencer_selection',
            draft_started_at=datetime.now(timezone.utc),
            selection_started_at=datetime.now(timezone.utc)
        )

        db.add(workflow_state)

        # Create notification for user
        notification = CampaignWorkflowNotification(
            campaign_id=campaign.id,
            notification_type='influencer_selected',
            recipient_id=request.user_id,
            title=f"New Campaign: {campaign.name}",
            message=f"A new campaign has been created for you by {current_user.full_name or current_user.email}. Please select influencers to proceed.",
            action_url=f"/campaigns/{campaign.id}/select-influencers",
            metadata={
                "campaign_id": str(campaign.id),
                "created_by_admin": current_user.email
            }
        )

        db.add(notification)
        await db.commit()
        await db.refresh(campaign)

        logger.info(f"✅ Superadmin {current_user.email} created workflow campaign: {campaign.name} for user {request.user_id}")

        return {
            "success": True,
            "data": {
                "id": str(campaign.id),
                "name": campaign.name,
                "brand_name": campaign.brand_name,
                "status": campaign.status,
                "created_by": campaign.created_by,
                "workflow_stage": workflow_state.current_stage,
                "created_at": campaign.created_at.isoformat(),
                "message": "Campaign created! Awaiting influencer selection from user."
            },
            "message": "Superadmin campaign created with workflow"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating superadmin campaign: {e}", exc_info=True)
        await db.rollback()
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

        # Create selection
        selection = CampaignInfluencerSelection(
            campaign_id=campaign_id,
            profile_id=request.profile_id,
            selected_by=current_user.id,
            selection_status='pending',
            selection_notes=request.selection_notes,
            estimated_cost=request.estimated_cost
        )

        db.add(selection)

        # Update workflow state
        result = await db.execute(
            select(CampaignWorkflowState).where(
                CampaignWorkflowState.campaign_id == campaign_id
            )
        )
        workflow_state = result.scalar_one_or_none()

        if workflow_state:
            workflow_state.influencers_selected += 1
            workflow_state.updated_at = datetime.now(timezone.utc)

        # Notify superadmin
        # Get superadmins (you might want to query from users table)
        notification = CampaignWorkflowNotification(
            campaign_id=campaign_id,
            notification_type='influencer_selected',
            recipient_id=current_user.id,  # For now, notify the user (update with superadmin IDs)
            title=f"Influencer Selected: {campaign.name}",
            message=f"{current_user.full_name or current_user.email} selected an influencer. Please review and lock selections.",
            action_url=f"/admin/campaigns/{campaign_id}/review-selections"
        )

        db.add(notification)
        await db.commit()

        logger.info(f"✅ User {current_user.email} selected influencer for campaign {campaign_id}")

        return {
            "success": True,
            "data": {
                "selection_id": str(selection.id),
                "profile_id": str(selection.profile_id),
                "status": selection.selection_status,
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
