"""
Influencer Master Database - Admin Routes (Endpoints 1-11)
Superadmin-only CRUD, bulk operations, and export for the influencer CRM.
"""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.middleware.auth_middleware import require_admin
from app.models.influencer_database import (
    AddInfluencerRequest,
    BulkImportRequest,
    BulkPricingRequest,
    BulkTagRequest,
    ExportRequest,
    InfluencerUpdateRequest,
)
from app.services.influencer_database_service import InfluencerDatabaseService

router = APIRouter(tags=["Influencer Database"])
logger = logging.getLogger(__name__)


# =============================================================================
# 1. LIST INFLUENCERS
# =============================================================================

@router.get("/influencers/database")
async def list_influencers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    tier: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    categories: Optional[str] = Query(None, description="Comma-separated categories"),
    min_followers: Optional[int] = Query(None, ge=0),
    max_followers: Optional[int] = Query(None, ge=0),
    engagement_min: Optional[float] = Query(None, ge=0),
    engagement_max: Optional[float] = Query(None, ge=0),
    is_verified: Optional[bool] = Query(None),
    has_pricing: Optional[bool] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """List all influencers with pagination and filters."""
    try:
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        category_list = [c.strip() for c in categories.split(",")] if categories else None
        result = await InfluencerDatabaseService.list_influencers(
            db,
            page=page,
            page_size=page_size,
            search=search,
            status=status_filter,
            tier=tier,
            tags=tag_list,
            categories=category_list,
            min_followers=min_followers,
            max_followers=max_followers,
            engagement_min=engagement_min,
            engagement_max=engagement_max,
            is_verified=is_verified,
            has_pricing=has_pricing,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error listing influencers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 2. GET ALL TAGS
# =============================================================================

@router.get("/influencers/tags")
async def get_all_tags(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Get all unique tags used across influencers."""
    try:
        tags = await InfluencerDatabaseService.get_all_tags(db)
        return {"success": True, "data": {"tags": tags}}
    except Exception as e:
        logger.error(f"Error fetching tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 3. ADD SINGLE INFLUENCER
# =============================================================================

@router.post("/influencers/add")
async def add_influencer(
    request: AddInfluencerRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Add a single influencer by Instagram username."""
    try:
        record = await InfluencerDatabaseService.add_influencer(
            db,
            username=request.username,
            added_by=current_user.id,
            categories=request.categories,
            tags=request.tags,
            notes=request.notes,
            status=request.status.value if request.status else "active",
            tier=request.tier,
            cost_pricing=request.cost_pricing.dict(exclude_none=True) if request.cost_pricing else None,
            sell_pricing=request.sell_pricing.dict(exclude_none=True) if request.sell_pricing else None,
        )
        return {"success": True, "data": {"influencer": record}, "message": f"@{request.username} added"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding influencer @{request.username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 4. BULK IMPORT
# =============================================================================

@router.post("/influencers/bulk-import")
async def bulk_import(
    request: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Bulk import influencers by username list."""
    try:
        result = await InfluencerDatabaseService.bulk_import(
            db, request.usernames, current_user.id
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error bulk importing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 5. BULK TAG
# =============================================================================

@router.post("/influencers/bulk-tag")
async def bulk_tag(
    request: BulkTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Bulk add or remove tags on multiple influencers."""
    try:
        count = await InfluencerDatabaseService.bulk_tag(
            db,
            influencer_ids=request.influencer_ids,
            tags=request.tags,
            action=request.action.value,
        )
        return {"success": True, "data": {"updated_count": count}}
    except Exception as e:
        logger.error(f"Error bulk tagging: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 6. BULK PRICING
# =============================================================================

@router.post("/influencers/bulk-pricing")
async def bulk_pricing(
    request: BulkPricingRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Bulk update pricing for multiple influencers."""
    try:
        updates = [u.dict(exclude_none=True) for u in request.updates]
        result = await InfluencerDatabaseService.bulk_pricing(db, updates)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error bulk pricing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 7. EXPORT
# =============================================================================

@router.post("/influencers/export")
async def export_influencers(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Export influencers to CSV or JSON."""
    try:
        content, media_type, filename = await InfluencerDatabaseService.export_influencers(
            db,
            format=request.format.value,
            fields=request.fields,
            scope=request.scope.value,
            selected_ids=request.selected_ids,
            filters=request.filters,
        )

        def iter_content():
            yield content

        return StreamingResponse(
            iter_content(),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"Error exporting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 8. GET DETAILED (by UUID or username)
# =============================================================================

@router.get("/influencers/{identifier}/detailed")
async def get_influencer_detailed(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Get detailed influencer data by UUID or username. DB-only lookup (influencer_database then profiles table)."""
    try:
        result = await InfluencerDatabaseService.get_detailed(db, identifier)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting influencer {identifier}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 9. UPDATE INFLUENCER
# =============================================================================

@router.put("/influencers/{influencer_id}")
async def update_influencer(
    influencer_id: UUID,
    request: InfluencerUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Update an influencer's CRM data and pricing."""
    try:
        data = request.dict(exclude_none=True)
        # Convert nested pydantic to dict
        if "cost_pricing" in data and data["cost_pricing"]:
            data["cost_pricing"] = (
                request.cost_pricing.dict(exclude_none=True)
                if request.cost_pricing else {}
            )
        if "sell_pricing" in data and data["sell_pricing"]:
            data["sell_pricing"] = (
                request.sell_pricing.dict(exclude_none=True)
                if request.sell_pricing else {}
            )
        result = await InfluencerDatabaseService.update_influencer(db, influencer_id, data)
        return {"success": True, "data": {"influencer": result}}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating influencer {influencer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 10. DELETE INFLUENCER
# =============================================================================

@router.delete("/influencers/{influencer_id}")
async def delete_influencer(
    influencer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Delete an influencer from the database."""
    try:
        deleted = await InfluencerDatabaseService.delete_influencer(db, influencer_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Influencer not found")
        return {"success": True, "message": "Influencer deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting influencer {influencer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 11. REFRESH ANALYTICS
# =============================================================================

@router.post("/influencers/{influencer_id}/refresh")
async def refresh_influencer(
    influencer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """Re-fetch Instagram data for an influencer."""
    try:
        result = await InfluencerDatabaseService.refresh_influencer(db, influencer_id)
        return {"success": True, "data": {"influencer": result}, "message": "Analytics refreshed"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error refreshing influencer {influencer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
