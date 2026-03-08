"""
Campaign Proposal Routes - Brand-facing proposal endpoints
Handles proposal viewing, influencer selection, request-more, approval/rejection
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.optimized_pools import get_db_optimized as get_db
from app.services.campaign_proposals_service import campaign_proposals_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Campaign Proposals"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class InfluencerDeliverableSelection(BaseModel):
    """Per-influencer deliverable selection"""
    influencer_id: UUID
    deliverables: List[str] = []  # e.g. ["post", "reel", "story"]

class InfluencerSelectionRequest(BaseModel):
    """Request model for updating influencer selection (uses ProposalInfluencer IDs)"""
    selected_influencer_ids: List[UUID]
    deliverable_selections: Optional[List[InfluencerDeliverableSelection]] = None

class ApproveProposalRequest(BaseModel):
    """Request model for approving proposal"""
    selected_influencer_ids: List[UUID]
    notes: Optional[str] = None

class RejectProposalRequest(BaseModel):
    """Request model for rejecting proposal"""
    reason: Optional[str] = None

class RequestMoreRequest(BaseModel):
    """Request model for requesting more influencers"""
    notes: Optional[str] = None

class AISnapshotRequest(BaseModel):
    """Request model for AI selection snapshot"""
    selected_influencer_ids: List[UUID]

# =============================================================================
# HEALTH CHECK (must be BEFORE parameterized routes to avoid path conflicts)
# =============================================================================

@router.get("/campaigns/proposals/health/check")
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
                "request_more",
                "proposal_approval",
                "proposal_rejection"
            ]
        },
        "message": "Campaign proposals module is operational"
    }

# =============================================================================
# PRICING SYNC (must be BEFORE parameterized routes)
# =============================================================================

@router.post("/campaigns/proposals/pricing/influencers")
async def sync_influencer_pricing(
    pricing_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Sync pricing to influencer_database table. Requires admin."""
    from app.services.influencer_database_service import InfluencerDatabaseService

    influencer_id = pricing_data.pop("influencer_id", None)
    if not influencer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="influencer_id is required")

    try:
        result = await InfluencerDatabaseService.sync_pricing(db, UUID(str(influencer_id)), pricing_data)
        return {"success": True, "data": {"influencer": result}, "message": "Pricing synced"}
    except ValueError as e:
        error_msg = str(e)
        code = status.HTTP_409_CONFLICT if "status" in error_msg.lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error syncing pricing: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to sync pricing")

# =============================================================================
# USER PROPOSAL ENDPOINTS
# =============================================================================

@router.get("/campaigns/proposals")
async def list_proposals(
    status_filter: Optional[str] = Query(None, pattern='^(sent|in_review|approved|rejected|more_requested)$'),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's proposals with enhanced summary data."""
    try:
        proposals, total = await campaign_proposals_service.list_user_proposals(
            db=db,
            user_id=current_user.id,
            status=status_filter,
            limit=limit,
            offset=offset
        )

        pending_count = await campaign_proposals_service.count_pending_proposals(
            db=db,
            user_id=current_user.id
        )

        proposals_data = []
        for p in proposals:
            # Load influencer counts via relationship
            inf_count = 0
            selected_count = 0
            if hasattr(p, 'proposal_influencers') and p.proposal_influencers:
                inf_count = len(p.proposal_influencers)
                selected_count = sum(1 for pi in p.proposal_influencers if pi.selected_by_user)

            proposals_data.append({
                "id": str(p.id),
                "title": p.title,
                "campaign_name": p.campaign_name,
                "description": p.description,
                "proposal_notes": p.proposal_notes,
                "status": p.status,
                "total_budget": float(p.total_budget) if p.total_budget else None,
                "total_sell_amount": float(p.total_sell_amount) if p.total_sell_amount else None,
                "proposal_type": p.proposal_type,
                "deadline_at": p.deadline_at.isoformat() if p.deadline_at else None,
                "cover_image_url": p.cover_image_url,
                "total_influencers": inf_count,
                "selected_count": selected_count,
                "created_at": p.created_at.isoformat(),
                "sent_at": p.sent_at.isoformat() if p.sent_at else None,
                "responded_at": p.responded_at.isoformat() if p.responded_at else None,
                "more_added_at": p.more_added_at.isoformat() if p.more_added_at else None,
            })

        return {
            "success": True,
            "data": {
                "proposals": proposals_data,
                "pending_count": pending_count,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                    "has_more": (offset + len(proposals_data)) < total
                }
            },
            "message": f"Retrieved {len(proposals_data)} proposals"
        }

    except Exception as e:
        logger.error(f"Error listing proposals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list proposals"
        )

@router.get("/campaigns/proposals/{proposal_id}")
async def get_proposal_details(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full proposal detail with influencers, pricing, and summary.
    Returns data filtered by visible_fields. NEVER returns cost pricing.
    """
    try:
        result = await campaign_proposals_service.get_brand_visible_proposal(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )

        return {
            "success": True,
            "data": result,
            "message": "Proposal details retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving proposal details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve proposal details"
        )

@router.put("/campaigns/proposals/{proposal_id}/influencers")
async def update_influencer_selection(
    proposal_id: UUID,
    request: InfluencerSelectionRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update influencer selection in proposal (uses ProposalInfluencer IDs)."""
    try:
        deliverable_map = {}
        if request.deliverable_selections:
            for ds in request.deliverable_selections:
                deliverable_map[ds.influencer_id] = ds.deliverables

        proposal = await campaign_proposals_service.update_influencer_selection(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            selected_influencer_ids=request.selected_influencer_ids,
            deliverable_selections=deliverable_map if deliverable_map else None,
        )

        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal.id),
                "status": proposal.status,
                "selected_count": len(request.selected_influencer_ids),
                "updated_at": proposal.updated_at.isoformat()
            },
            "message": "Influencer selection updated successfully"
        }

    except ValueError as e:
        error_msg = str(e)
        code = status.HTTP_409_CONFLICT if "status" in error_msg.lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error updating influencer selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update influencer selection"
        )

@router.post("/campaigns/proposals/{proposal_id}/request-more")
async def request_more_influencers(
    proposal_id: UUID,
    request: RequestMoreRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Brand requests more influencer suggestions (status → more_requested)."""
    try:
        proposal = await campaign_proposals_service.handle_request_more(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            notes=request.notes,
        )

        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal.id),
                "status": proposal.status,
                "request_more_at": proposal.request_more_at.isoformat() if proposal.request_more_at else None,
            },
            "message": "Request for more influencers submitted"
        }

    except ValueError as e:
        error_msg = str(e)
        code = status.HTTP_409_CONFLICT if "status" in error_msg.lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error requesting more influencers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request more influencers"
        )

@router.post("/campaigns/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: UUID,
    request: ApproveProposalRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve proposal with final influencer selections. Creates campaign."""
    try:
        campaign = await campaign_proposals_service.approve_proposal(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            selected_influencer_ids=request.selected_influencer_ids,
            notes=request.notes
        )

        return {
            "success": True,
            "data": {
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "campaign_status": campaign.status,
                "proposal_id": str(proposal_id),
                "selected_influencers_count": len(request.selected_influencer_ids),
                "created_at": campaign.created_at.isoformat()
            },
            "message": "Proposal approved and campaign created successfully"
        }

    except ValueError as e:
        error_msg = str(e)
        code = status.HTTP_409_CONFLICT if "status" in error_msg.lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error approving proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve proposal"
        )

@router.post("/campaigns/proposals/{proposal_id}/ai-snapshot")
async def get_ai_snapshot(
    proposal_id: UUID,
    request: AISnapshotRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate AI-powered insights about the brand's current creator selection."""
    try:
        snapshot = await campaign_proposals_service.generate_selection_snapshot(
            db=db,
            proposal_id=proposal_id,
            user_id=current_user.id,
            selected_influencer_ids=request.selected_influencer_ids,
        )

        return {
            "success": True,
            "data": snapshot,
            "message": "AI snapshot generated"
        }

    except ValueError as e:
        error_msg = str(e)
        code = status.HTTP_409_CONFLICT if "status" in error_msg.lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error generating AI snapshot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI snapshot"
        )

@router.post("/campaigns/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: UUID,
    request: RejectProposalRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject proposal with optional reason."""
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
        error_msg = str(e)
        code = status.HTTP_409_CONFLICT if "status" in error_msg.lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error rejecting proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject proposal"
        )
