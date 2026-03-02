"""
Influencer Access Shares - Admin Routes (Endpoints 12-16)
Superadmin share management: create, update, revoke, extend shares.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.middleware.auth_middleware import require_admin
from app.models.influencer_database import (
    ShareCreateRequest,
    ShareExtendRequest,
    ShareUpdateRequest,
)
from app.services.influencer_database_service import InfluencerDatabaseService
from app.services.notification_service import NotificationService

router = APIRouter(tags=["Influencer Shares"])
logger = logging.getLogger(__name__)


# =============================================================================
# 12. LIST ALL SHARES
# =============================================================================

@router.get("/influencers/shares")
async def list_shares(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """List all influencer access shares with associated users."""
    try:
        shares = await InfluencerDatabaseService.list_shares(db)
        return {"success": True, "data": {"shares": shares}}
    except Exception as e:
        logger.error(f"Error listing shares: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 13. CREATE SHARE
# =============================================================================

@router.post("/influencers/shares")
async def create_share(
    request: ShareCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Create a new influencer access share."""
    try:
        vf = request.visible_fields.dict() if request.visible_fields else None
        share = await InfluencerDatabaseService.create_share(
            db,
            name=request.name,
            created_by=current_user.id,
            influencer_ids=request.influencer_ids,
            user_emails=request.user_emails,
            description=request.description,
            visible_fields=vf,
            duration=request.duration or "30d",
        )

        # Notify shared users
        try:
            await NotificationService.notify_share_created(
                db,
                share_name=request.name,
                share_id=share["id"],
                user_emails=request.user_emails,
                influencer_count=len(request.influencer_ids),
            )
        except Exception as notify_err:
            logger.warning(f"Failed to send share notifications: {notify_err}")

        return {"success": True, "data": {"share": share}, "message": "Share created"}
    except Exception as e:
        logger.error(f"Error creating share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 14. UPDATE SHARE
# =============================================================================

@router.put("/influencers/shares/{share_id}")
async def update_share(
    share_id: UUID,
    request: ShareUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Update an existing share configuration."""
    try:
        data = request.dict(exclude_none=True)
        if "visible_fields" in data and data["visible_fields"]:
            data["visible_fields"] = request.visible_fields.dict() if request.visible_fields else None
        share = await InfluencerDatabaseService.update_share(db, share_id, data)
        return {"success": True, "data": {"share": share}}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating share {share_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 15. REVOKE SHARE
# =============================================================================

@router.post("/influencers/shares/{share_id}/revoke")
async def revoke_share(
    share_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Revoke (deactivate) an access share."""
    try:
        # Get share name before revoking (for notification)
        from sqlalchemy import text as sa_text
        name_result = await db.execute(
            sa_text("SELECT name FROM influencer_access_shares WHERE id = CAST(:id AS uuid)"),
            {"id": str(share_id)},
        )
        name_row = name_result.fetchone()
        share_name = name_row[0] if name_row else "Unknown"

        revoked = await InfluencerDatabaseService.revoke_share(db, share_id)
        if not revoked:
            raise HTTPException(status_code=404, detail="Share not found")

        # Notify affected users
        try:
            await NotificationService.notify_share_revoked(db, share_id, share_name)
        except Exception as notify_err:
            logger.warning(f"Failed to send revoke notifications: {notify_err}")

        return {"success": True, "message": "Share revoked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking share {share_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 16. EXTEND SHARE
# =============================================================================

@router.post("/influencers/shares/{share_id}/extend")
async def extend_share(
    share_id: UUID,
    request: ShareExtendRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Extend a share's expiration date."""
    try:
        share = await InfluencerDatabaseService.extend_share(db, share_id, request.expires_at)

        # Notify affected users
        try:
            share_name = share.get("name", "Unknown")
            expires_str = request.expires_at.strftime("%b %d, %Y")
            await NotificationService.notify_share_extended(db, share_id, share_name, expires_str)
        except Exception as notify_err:
            logger.warning(f"Failed to send extend notifications: {notify_err}")

        return {"success": True, "data": {"share": share}, "message": "Share extended"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error extending share {share_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
