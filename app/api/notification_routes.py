"""
User Notifications - Routes
List, read, mark-read for the authenticated user's notifications.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.optimized_pools import get_db_optimized as get_db
from app.middleware.auth_middleware import get_current_active_user
from app.services.notification_service import NotificationService

router = APIRouter(tags=["Notifications"])
logger = logging.getLogger(__name__)


@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    notification_type: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List notifications for the authenticated user."""
    try:
        result = await NotificationService.list_notifications(
            db,
            user_id=current_user.id,
            user_email=current_user.email,
            page=page,
            page_size=page_size,
            notification_type=notification_type,
            unread_only=unread_only,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error listing notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get unread notification count by type."""
    try:
        counts = await NotificationService.get_unread_count(
            db,
            user_id=current_user.id,
            user_email=current_user.email,
        )
        return {"success": True, "data": counts}
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mark a single notification as read."""
    try:
        marked = await NotificationService.mark_read(
            db,
            notification_id=notification_id,
            user_id=current_user.id,
            user_email=current_user.email,
        )
        return {"success": True, "data": {"marked": marked}}
    except Exception as e:
        logger.error(f"Error marking notification read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/mark-read-by-reference")
async def mark_read_by_reference(
    reference_type: str = Query(..., description="e.g. 'proposal', 'share', 'profile'"),
    reference_id: Optional[str] = Query(None, description="Specific reference UUID"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mark notifications as read by reference_type and optionally reference_id.
    Used for auto-marking notifications when visiting the relevant page."""
    try:
        ref_uuid = UUID(reference_id) if reference_id else None
        count = await NotificationService.mark_read_by_reference(
            db,
            user_id=current_user.id,
            user_email=current_user.email,
            reference_type=reference_type,
            reference_id=ref_uuid,
        )
        return {"success": True, "data": {"marked_count": count}}
    except Exception as e:
        logger.error(f"Error marking notifications read by reference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/mark-all-read")
async def mark_all_read(
    notification_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mark all notifications as read, optionally filtered by type."""
    try:
        count = await NotificationService.mark_all_read(
            db,
            user_id=current_user.id,
            user_email=current_user.email,
            notification_type=notification_type,
        )
        return {"success": True, "data": {"marked_count": count}}
    except Exception as e:
        logger.error(f"Error marking all read: {e}")
        raise HTTPException(status_code=500, detail=str(e))
