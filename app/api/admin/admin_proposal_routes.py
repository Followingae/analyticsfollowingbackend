"""
Admin Proposal Management Routes
Superadmin endpoints for creating, managing, and sending proposals to brands.
"""
import logging
import os
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.optimized_pools import get_db_optimized as get_db
from app.middleware.auth_middleware import require_admin
from app.services.campaign_proposals_service import campaign_proposals_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin Proposals"])

MAX_COVER_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# =============================================================================
# REQUEST MODELS
# =============================================================================

class CreateProposalRequest(BaseModel):
    user_id: UUID
    title: str = Field(..., max_length=255)
    campaign_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    proposal_notes: Optional[str] = None
    total_budget: Optional[float] = None
    proposal_type: str = "influencer_list"
    visible_fields: Optional[dict] = None
    deadline_at: Optional[str] = None
    cover_image_url: Optional[str] = None


class UpdateProposalRequest(BaseModel):
    title: Optional[str] = None
    campaign_name: Optional[str] = None
    description: Optional[str] = None
    proposal_notes: Optional[str] = None
    visible_fields: Optional[dict] = None
    deadline_at: Optional[str] = None
    cover_image_url: Optional[str] = None
    total_budget: Optional[float] = None


class DeliverableAssignment(BaseModel):
    type: str  # post, story, reel, carousel, video, bundle, monthly
    quantity: int = 1

class InfluencerDeliverableAssignment(BaseModel):
    influencer_db_id: UUID
    deliverables: List[DeliverableAssignment]

class AddInfluencersRequest(BaseModel):
    influencer_ids: List[UUID]
    custom_pricing: Optional[dict] = None
    deliverable_assignments: Optional[List[InfluencerDeliverableAssignment]] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/proposals")
async def create_proposal(
    request: CreateProposalRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Create a new proposal for a brand user."""
    try:
        from datetime import datetime
        deadline = None
        if request.deadline_at:
            deadline = datetime.fromisoformat(request.deadline_at.replace("Z", "+00:00"))

        proposal = await campaign_proposals_service.create_proposal(
            db=db,
            user_id=request.user_id,
            created_by_admin_id=current_user.id,
            title=request.title,
            campaign_name=request.campaign_name,
            description=request.description,
            proposal_notes=request.proposal_notes,
            total_budget=request.total_budget,
            proposal_type=request.proposal_type,
            visible_fields=request.visible_fields,
            deadline_at=deadline,
            cover_image_url=request.cover_image_url,
        )
        return {
            "success": True,
            "data": {
                "id": str(proposal.id),
                "status": proposal.status,
                "title": proposal.title,
                "campaign_name": proposal.campaign_name,
                "user_id": str(proposal.user_id),
                "created_at": proposal.created_at.isoformat(),
            },
            "message": "Proposal created successfully",
        }
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create proposal")


@router.get("/proposals")
async def list_proposals(
    status_filter: Optional[str] = Query(None, alias="status"),
    user_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """List all proposals with optional filters."""
    try:
        proposals, total = await campaign_proposals_service.list_all_proposals(
            db=db,
            status=status_filter,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        proposals_data = []
        for p in proposals:
            inf_count = len(p.proposal_influencers) if p.proposal_influencers else 0
            selected_count = sum(1 for pi in (p.proposal_influencers or []) if pi.selected_by_user)
            proposals_data.append({
                "id": str(p.id),
                "title": p.title,
                "campaign_name": p.campaign_name,
                "status": p.status,
                "user_id": str(p.user_id),
                "user_email": p.user.email if p.user else None,
                "total_influencers": inf_count,
                "selected_count": selected_count,
                "total_sell_amount": float(p.total_sell_amount) if p.total_sell_amount else None,
                "total_cost_amount": float(p.total_cost_amount) if p.total_cost_amount else None,
                "margin_percentage": float(p.margin_percentage) if p.margin_percentage else None,
                "deadline_at": p.deadline_at.isoformat() if p.deadline_at else None,
                "created_at": p.created_at.isoformat(),
                "sent_at": p.sent_at.isoformat() if p.sent_at else None,
            })

        return {
            "success": True,
            "data": {
                "proposals": proposals_data,
                "pagination": {"limit": limit, "offset": offset, "total": total},
            },
        }
    except Exception as e:
        logger.error(f"Error listing proposals: {e}")
        raise HTTPException(status_code=500, detail="Failed to list proposals")


@router.get("/proposals/stats")
async def get_proposal_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Get admin proposal dashboard stats."""
    try:
        stats = await campaign_proposals_service.get_admin_stats(db)
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get proposal stats")


@router.post("/proposals/upload-cover")
async def upload_proposal_cover(
    file: UploadFile = File(...),
    current_user=Depends(require_admin()),
):
    """Upload a proposal cover image to R2 CDN. Returns the CDN URL."""
    try:
        contents = await file.read()
        if len(contents) > MAX_COVER_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_COVER_SIZE // (1024*1024)}MB",
            )
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )

        ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "png"
        unique_name = f"cover_{uuid4().hex[:12]}.{ext}"

        from app.infrastructure.r2_storage_client import R2StorageClient

        r2_client = R2StorageClient(
            account_id=os.getenv("CF_ACCOUNT_ID"),
            access_key=os.getenv("R2_ACCESS_KEY_ID"),
            secret_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            bucket_name="thumbnails-prod",
        )

        r2_key = f"proposals/covers/{unique_name}"
        upload_ok = await r2_client.upload_object(
            key=r2_key,
            content=contents,
            content_type=file.content_type,
            metadata={
                "uploaded_by": current_user.email,
                "upload_timestamp": datetime.utcnow().isoformat(),
            },
        )
        if not upload_ok:
            raise HTTPException(status_code=500, detail="Failed to upload to CDN")

        cdn_url = f"https://cdn.following.ae/{r2_key}"
        return {"success": True, "data": {"url": cdn_url}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading proposal cover: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload cover image")


@router.get("/proposals/{proposal_id}")
async def get_proposal_detail(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Get full proposal detail with influencers and financials (admin view)."""
    try:
        proposal = await campaign_proposals_service.get_admin_proposal_detail(db, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        # Build influencer list with full cost + sell data
        influencers = []
        for pi in sorted(proposal.proposal_influencers, key=lambda x: x.priority_order or 0):
            inf_db = pi.influencer_db
            profile = pi.profile

            inf_data = {
                "id": str(pi.id),
                "influencer_db_id": str(pi.influencer_db_id) if pi.influencer_db_id else None,
                "profile_id": str(pi.profile_id) if pi.profile_id else None,
                "priority_order": pi.priority_order,
                "selected_by_user": pi.selected_by_user,
                "selected_at": pi.selected_at.isoformat() if pi.selected_at else None,
                "admin_notes": pi.admin_notes,
                # Profile data
                # H13: Use if-is-not-None to avoid falsy value bugs (e.g. is_verified=False)
                "username": inf_db.username if inf_db and inf_db.username is not None else (profile.username if profile else None),
                "full_name": inf_db.full_name if inf_db and inf_db.full_name is not None else (profile.full_name if profile else None),
                "profile_image_url": inf_db.profile_image_url if inf_db and inf_db.profile_image_url is not None else (profile.profile_pic_url if profile else None),
                "is_verified": inf_db.is_verified if inf_db and inf_db.is_verified is not None else (profile.is_verified if profile else False),
                "followers_count": inf_db.followers_count if inf_db and inf_db.followers_count is not None else (profile.followers_count if profile else None),
                "engagement_rate": float(inf_db.engagement_rate) if inf_db and inf_db.engagement_rate else None,
                "categories": inf_db.categories if inf_db else [],
                "tier": inf_db.tier if inf_db else None,
                # Full pricing (admin sees both)
                "sell_price_snapshot": pi.sell_price_snapshot,
                "cost_price_snapshot": pi.cost_price_snapshot,
                "custom_sell_pricing": pi.custom_sell_pricing,
                "assigned_deliverables": pi.assigned_deliverables or [],
                "selected_deliverables": pi.selected_deliverables or [],
            }
            influencers.append(inf_data)

        financials = await campaign_proposals_service.get_proposal_financials(db, proposal_id)

        # Build timeline events
        timeline = [{"event": "created", "timestamp": proposal.created_at.isoformat()}]
        if proposal.sent_at:
            timeline.append({"event": "sent", "timestamp": proposal.sent_at.isoformat()})
        if proposal.request_more_at:
            timeline.append({"event": "more_requested", "timestamp": proposal.request_more_at.isoformat(), "notes": proposal.request_more_notes})
        if proposal.more_added_at:
            timeline.append({"event": "more_added", "timestamp": proposal.more_added_at.isoformat()})
        if proposal.responded_at:
            event = "approved" if proposal.status == "approved" else "rejected"
            timeline.append({"event": event, "timestamp": proposal.responded_at.isoformat()})

        return {
            "success": True,
            "data": {
                "proposal": {
                    "id": str(proposal.id),
                    "title": proposal.title,
                    "campaign_name": proposal.campaign_name,
                    "description": proposal.description,
                    "proposal_notes": proposal.proposal_notes,
                    "status": proposal.status,
                    "user_id": str(proposal.user_id),
                    "user_email": proposal.user.email if proposal.user else None,
                    "visible_fields": proposal.visible_fields,
                    "brand_notes": proposal.brand_notes,
                    "request_more_notes": proposal.request_more_notes,
                    "deadline_at": proposal.deadline_at.isoformat() if proposal.deadline_at else None,
                    "cover_image_url": proposal.cover_image_url,
                    "created_at": proposal.created_at.isoformat(),
                    "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
                },
                "influencers": influencers,
                "financials": financials,
                "timeline": timeline,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proposal detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to get proposal detail")


@router.put("/proposals/{proposal_id}")
async def update_proposal(
    proposal_id: UUID,
    request: UpdateProposalRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Update proposal metadata."""
    try:
        from datetime import datetime
        # H2: Use exclude_unset to allow clearing nullable fields with explicit None
        kwargs = request.model_dump(exclude_unset=True)
        if "deadline_at" in kwargs and kwargs["deadline_at"]:
            kwargs["deadline_at"] = datetime.fromisoformat(kwargs["deadline_at"].replace("Z", "+00:00"))

        proposal = await campaign_proposals_service.update_proposal(db, proposal_id, **kwargs)
        return {
            "success": True,
            "data": {
                "id": str(proposal.id),
                "title": proposal.title,
                "campaign_name": proposal.campaign_name,
                "status": proposal.status,
                "updated_at": proposal.updated_at.isoformat() if proposal.updated_at else None,
            },
            "message": "Proposal updated",
        }
    except ValueError as e:
        # L1: Status guard errors are 409 Conflict, not-found is 404
        error_msg = str(e)
        status_code = 409 if "status" in error_msg.lower() else 404
        raise HTTPException(status_code=status_code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error updating proposal: {e}")
        raise HTTPException(status_code=500, detail="Failed to update proposal")


@router.post("/proposals/{proposal_id}/influencers")
async def add_influencers(
    proposal_id: UUID,
    request: AddInfluencersRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Add influencers from master DB with price snapshots."""
    try:
        # Build deliverable assignment map: {influencer_db_id: [{"type": "reel", "quantity": 2}]}
        deliverable_map = None
        if request.deliverable_assignments:
            deliverable_map = {}
            for da in request.deliverable_assignments:
                deliverable_map[da.influencer_db_id] = [
                    {"type": d.type, "quantity": d.quantity} for d in da.deliverables
                ]

        created = await campaign_proposals_service.add_influencers_from_db(
            db=db,
            proposal_id=proposal_id,
            influencer_db_ids=request.influencer_ids,
            custom_pricing=request.custom_pricing,
            deliverable_assignments=deliverable_map,
        )
        return {
            "success": True,
            "data": {
                "added_count": len(created),
                "influencer_ids": [str(pi.id) for pi in created],
            },
            "message": f"Added {len(created)} influencers to proposal",
        }
    except ValueError as e:
        error_msg = str(e)
        status_code = 409 if "status" in error_msg.lower() else 404
        raise HTTPException(status_code=status_code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error adding influencers: {e}")
        raise HTTPException(status_code=500, detail="Failed to add influencers")


@router.delete("/proposals/{proposal_id}/influencers/{influencer_id}")
async def remove_influencer(
    proposal_id: UUID,
    influencer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Remove an influencer from a proposal."""
    try:
        await campaign_proposals_service.remove_influencer_from_proposal(
            db, proposal_id, influencer_id
        )
        return {
            "success": True,
            "data": {"removed": True},
            "message": "Influencer removed from proposal",
        }
    except ValueError as e:
        error_msg = str(e)
        status_code = 409 if "status" in error_msg.lower() else 404
        raise HTTPException(status_code=status_code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error removing influencer: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove influencer")


@router.post("/proposals/{proposal_id}/send")
async def send_proposal(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Send proposal to brand user (status → sent, triggers notification)."""
    try:
        proposal = await campaign_proposals_service.send_proposal(db, proposal_id)
        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal.id),
                "status": proposal.status,
                "sent_at": proposal.sent_at.isoformat(),
            },
            "message": "Proposal sent to brand",
        }
    except ValueError as e:
        error_msg = str(e)
        status_code = 409 if "status" in error_msg.lower() else 404
        raise HTTPException(status_code=status_code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error sending proposal: {e}")
        raise HTTPException(status_code=500, detail="Failed to send proposal")


@router.post("/proposals/{proposal_id}/add-more")
async def add_more_influencers(
    proposal_id: UUID,
    request: AddInfluencersRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Add more influencers after brand requested (status → sent, notifies brand)."""
    try:
        deliverable_map = None
        if request.deliverable_assignments:
            deliverable_map = {}
            for da in request.deliverable_assignments:
                deliverable_map[da.influencer_db_id] = [
                    {"type": d.type, "quantity": d.quantity} for d in da.deliverables
                ]

        created = await campaign_proposals_service.add_more_influencers(
            db=db,
            proposal_id=proposal_id,
            influencer_db_ids=request.influencer_ids,
            custom_pricing=request.custom_pricing,
            deliverable_assignments=deliverable_map,
        )
        return {
            "success": True,
            "data": {
                "added_count": len(created),
                "influencer_ids": [str(pi.id) for pi in created],
            },
            "message": f"Added {len(created)} more influencers and notified brand",
        }
    except ValueError as e:
        error_msg = str(e)
        status_code = 409 if "status" in error_msg.lower() else 404
        raise HTTPException(status_code=status_code, detail=error_msg)
    except Exception as e:
        logger.error(f"Error adding more influencers: {e}")
        raise HTTPException(status_code=500, detail="Failed to add more influencers")
