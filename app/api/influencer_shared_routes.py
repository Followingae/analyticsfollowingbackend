"""
Shared Influencers - User-facing Routes (Endpoints 18-19)
Regular users access influencer lists shared with them via access shares.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.optimized_pools import get_db_optimized as get_db
from app.middleware.auth_middleware import get_current_active_user
from app.services.influencer_database_service import InfluencerDatabaseService

router = APIRouter(tags=["Shared Influencers"])
logger = logging.getLogger(__name__)


# =============================================================================
# 18. GET SHARED INFLUENCERS (flat list — legacy)
# =============================================================================

@router.get("/influencers/shared")
async def get_shared_influencers(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get all influencers shared with the authenticated user (flat list).
    Returns filtered data based on each share's visible_fields configuration.
    Never returns cost pricing or internal notes.
    """
    try:
        influencers = await InfluencerDatabaseService.get_shared_influencers(
            db,
            user_id=current_user.id,
            user_email=current_user.email,
        )
        return {
            "success": True,
            "data": {
                "influencers": influencers,
                "total_count": len(influencers),
            },
        }
    except Exception as e:
        logger.error(f"Error fetching shared influencers for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 19. GET SHARED LISTS (grouped by share — used by Lists module)
# =============================================================================

@router.get("/influencers/shared/lists")
async def get_shared_lists(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get all share lists the user has access to, with metadata.
    Returns share name, description, influencer count, expiry — NOT the influencer data itself.
    """
    try:
        lists = await InfluencerDatabaseService.get_user_shared_lists(
            db,
            user_id=current_user.id,
            user_email=current_user.email,
        )
        return {"success": True, "data": {"lists": lists, "total_count": len(lists)}}
    except Exception as e:
        logger.error(f"Error fetching shared lists for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 20. GET SINGLE SHARED LIST (influencers inside a specific share)
# =============================================================================

@router.get("/influencers/shared/lists/{share_id}")
async def get_shared_list_detail(
    share_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get the influencers inside a specific share, filtered by visible_fields.
    Verifies the user actually has access to this share.
    """
    try:
        result = await InfluencerDatabaseService.get_user_shared_list_detail(
            db,
            share_id=share_id,
            user_id=current_user.id,
            user_email=current_user.email,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching shared list {share_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
