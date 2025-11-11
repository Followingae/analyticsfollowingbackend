"""
Campaign Proposal Routes - Superadmin → User Proposal Workflow
Handles proposal creation, influencer selection, and approval/rejection
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.campaign_proposals_service import campaign_proposals_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns/proposals", tags=["Campaign Proposals"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class InfluencerSelectionRequest(BaseModel):
    """Request model for updating influencer selection"""
    selected_profile_ids: List[UUID]

class ApproveProposalRequest(BaseModel):
    """Request model for approving proposal"""
    selected_profile_ids: List[UUID]
    notes: Optional[str] = None

class RejectProposalRequest(BaseModel):
    """Request model for rejecting proposal"""
    reason: Optional[str] = None

# =============================================================================
# USER PROPOSAL ENDPOINTS
# =============================================================================

@router.get("/")
async def list_proposals(
    status_filter: Optional[str] = Query(None, regex='^(draft|sent|in_review|approved|rejected)$'),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List user's proposals

    Query Parameters:
    - status_filter: Optional filter by status (draft, sent, in_review, approved, rejected)
    - limit: Max results (1-100, default: 50)
    - offset: Pagination offset (default: 0)

    Returns:
    - List of proposals with basic info
    - Pending proposals count
    """
    try:
        proposals = await campaign_proposals_service.list_user_proposals(
            db=db,
            user_id=current_user.id,
            status=status_filter,
            limit=limit,
            offset=offset
        )

        # Get pending count
        pending_count = await campaign_proposals_service.count_pending_proposals(
            db=db,
            user_id=current_user.id
        )

        # Format response
        proposals_data = [
            {
                "id": str(p.id),
                "title": p.title,
                "campaign_name": p.campaign_name,
                "description": p.description,
                "proposal_notes": p.proposal_notes,
                "status": p.status,
                "total_budget": float(p.total_budget) if p.total_budget else None,
                "proposal_type": p.proposal_type,
                "created_at": p.created_at.isoformat(),
                "sent_at": p.sent_at.isoformat() if p.sent_at else None,
                "responded_at": p.responded_at.isoformat() if p.responded_at else None
            }
            for p in proposals
        ]

        return {
            "success": True,
            "data": {
                "proposals": proposals_data,
                "pending_count": pending_count,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(proposals_data),
                    "has_more": len(proposals_data) == limit
                }
            },
            "message": f"Retrieved {len(proposals_data)} proposals"
        }

    except Exception as e:
        logger.error(f"❌ Error listing proposals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list proposals"
        )

@router.get("/{proposal_id}")
async def get_proposal_details(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get proposal details with suggested influencers

    Returns:
    - Complete proposal information
    - Suggested influencers with selection status
    - Profile data for each influencer
    """
    try:
        proposal = await campaign_proposals_service.get_proposal_details(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id
        )

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )

        # Format influencers data
        influencers_data = []
        for pi in proposal.proposal_influencers:
            influencers_data.append({
                "profile_id": str(pi.profile_id),
                "username": pi.profile.username if pi.profile else None,
                "full_name": pi.profile.full_name if pi.profile else None,
                "followers_count": pi.profile.followers_count if pi.profile else None,
                "profile_pic_url": pi.profile.profile_pic_url if pi.profile else None,
                "estimated_cost": float(pi.estimated_cost) if pi.estimated_cost else None,
                "suggested_by_admin": pi.suggested_by_admin,
                "selected_by_user": pi.selected_by_user,
                "selected_at": pi.selected_at.isoformat() if pi.selected_at else None
            })

        return {
            "success": True,
            "data": {
                "id": str(proposal.id),
                "title": proposal.title,
                "campaign_name": proposal.campaign_name,
                "description": proposal.description,
                "proposal_notes": proposal.proposal_notes,
                "status": proposal.status,
                "total_budget": float(proposal.total_budget) if proposal.total_budget else None,
                "expected_reach": proposal.expected_reach,
                "avg_engagement_rate": float(proposal.avg_engagement_rate) if proposal.avg_engagement_rate else None,
                "estimated_impressions": proposal.estimated_impressions,
                "proposal_type": proposal.proposal_type,
                "created_at": proposal.created_at.isoformat(),
                "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
                "responded_at": proposal.responded_at.isoformat() if proposal.responded_at else None,
                "influencers": influencers_data,
                "selected_influencers_count": sum(1 for i in influencers_data if i["selected_by_user"]),
                "total_influencers_count": len(influencers_data)
            },
            "message": "Proposal details retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving proposal details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve proposal details"
        )

@router.put("/{proposal_id}/influencers")
async def update_influencer_selection(
    proposal_id: UUID,
    request: InfluencerSelectionRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update influencer selection in proposal

    User selects/deselects influencers from the proposal.
    Updates proposal status to 'in_review' if currently 'sent'.

    Request Body:
    - selected_profile_ids: List of profile IDs user selected
    """
    try:
        proposal = await campaign_proposals_service.update_influencer_selection(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            selected_profile_ids=request.selected_profile_ids
        )

        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal.id),
                "status": proposal.status,
                "selected_count": len(request.selected_profile_ids),
                "updated_at": proposal.updated_at.isoformat()
            },
            "message": "Influencer selection updated successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error updating influencer selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update influencer selection"
        )

@router.post("/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: UUID,
    request: ApproveProposalRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve proposal and create campaign

    User approves the proposal with final influencer selections.
    Creates a new campaign automatically from the proposal.

    Request Body:
    - selected_profile_ids: Final selected profile IDs
    - notes: Optional notes from user

    Returns:
    - Created campaign details
    """
    try:
        campaign = await campaign_proposals_service.approve_proposal(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            selected_profile_ids=request.selected_profile_ids,
            notes=request.notes
        )

        return {
            "success": True,
            "data": {
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "campaign_status": campaign.status,
                "proposal_id": str(proposal_id),
                "selected_influencers_count": len(request.selected_profile_ids),
                "created_at": campaign.created_at.isoformat()
            },
            "message": "Proposal approved and campaign created successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error approving proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve proposal"
        )

@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: UUID,
    request: RejectProposalRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reject proposal

    User rejects the proposal with optional reason.
    Proposal status will be set to 'rejected'.

    Request Body:
    - reason: Optional rejection reason
    """
    try:
        proposal = await campaign_proposals_service.reject_proposal(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            reason=request.reason
        )

        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal.id),
                "status": proposal.status,
                "rejection_reason": proposal.rejection_reason,
                "rejected_at": proposal.responded_at.isoformat() if proposal.responded_at else None
            },
            "message": "Proposal rejected successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error rejecting proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject proposal"
        )

# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/health/check")
async def proposal_health():
    """Campaign proposals module health check"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "campaign_proposals",
            "features": [
                "proposal_listing",
                "proposal_details",
                "influencer_selection",
                "proposal_approval",
                "proposal_rejection"
            ]
        },
        "message": "Campaign proposals module is operational"
    }
