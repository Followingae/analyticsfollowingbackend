"""
Simple Campaign Routes - Direct Database Access
Frontend-compatible campaign APIs with exact response structures
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import logging

# Database and auth imports
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user
from app.models.auth import UserInDB

# Pydantic models
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["simple_campaigns"])

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CampaignCreate(BaseModel):
    name: str
    brand_name: str
    brand_logo_url: Optional[str] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    brand_name: Optional[str] = None
    brand_logo_url: Optional[str] = None
    status: Optional[str] = None

# =============================================================================
# SIMPLE CAMPAIGN CRUD - DIRECT DATABASE ACCESS
# =============================================================================

@router.get("/")
async def list_campaigns_simple(
    status: Optional[str] = Query(None, description="Filter by campaign status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List campaigns - Simple direct database access

    Frontend requirement: GET /api/v1/campaigns
    """
    try:
        # Build query with optional status filter
        base_query = """
            SELECT c.id, c.name, c.brand_name, c.brand_logo_url, c.status,
                   c.created_at, c.updated_at,
                   COUNT(DISTINCT cc.profile_id) as creators_count,
                   COUNT(cp.id) as posts_count,
                   COALESCE(SUM(p.followers_count), 0) as total_reach
            FROM campaigns c
            LEFT JOIN campaign_creators cc ON c.id = cc.campaign_id
            LEFT JOIN campaign_posts cp ON c.id = cp.campaign_id
            LEFT JOIN profiles p ON cc.profile_id = p.id
            WHERE c.user_id = :user_id
        """

        params = {"user_id": current_user.id}

        if status:
            base_query += " AND c.status = :status"
            params["status"] = status

        base_query += """
            GROUP BY c.id, c.name, c.brand_name, c.brand_logo_url, c.status,
                     c.created_at, c.updated_at
            ORDER BY c.created_at DESC
            LIMIT :limit OFFSET :offset
        """

        params.update({"limit": limit, "offset": offset})

        result = await db.execute(text(base_query), params)
        campaigns_rows = result.fetchall()

        # Build response
        campaigns = []
        for row in campaigns_rows:
            campaigns.append({
                "id": str(row.id),
                "name": row.name,
                "brand_name": row.brand_name,
                "brand_logo_url": row.brand_logo_url,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "creators_count": row.creators_count or 0,
                "posts_count": row.posts_count or 0,
                "total_reach": int(row.total_reach or 0)
            })

        # Get summary for frontend dashboard
        summary_query = """
            SELECT
                COUNT(*) as total_campaigns,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_campaigns,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_campaigns,
                COUNT(CASE WHEN status = 'draft' THEN 1 END) as pending_proposals
            FROM campaigns
            WHERE user_id = :user_id
        """

        result = await db.execute(text(summary_query), {"user_id": current_user.id})
        summary_row = result.fetchone()

        return {
            "campaigns": campaigns,
            "summary": {
                "totalCampaigns": summary_row.total_campaigns or 0,
                "activeCampaigns": summary_row.active_campaigns or 0,
                "completedCampaigns": summary_row.completed_campaigns or 0,
                "pendingProposals": summary_row.pending_proposals or 0
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(campaigns),
                "has_more": len(campaigns) == limit
            }
        }

    except Exception as e:
        logger.error(f"Failed to list campaigns for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list campaigns: {str(e)}"
        )

@router.post("/")
async def create_campaign_simple(
    campaign: CampaignCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create campaign - Simple direct database access

    Frontend requirement: POST /api/v1/campaigns
    """
    try:
        # Insert campaign directly
        insert_query = """
            INSERT INTO campaigns (user_id, name, brand_name, brand_logo_url, status)
            VALUES (:user_id, :name, :brand_name, :brand_logo_url, 'draft')
            RETURNING id, name, brand_name, brand_logo_url, status, created_at, updated_at
        """

        result = await db.execute(text(insert_query), {
            "user_id": current_user.id,
            "name": campaign.name,
            "brand_name": campaign.brand_name,
            "brand_logo_url": campaign.brand_logo_url
        })

        await db.commit()

        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create campaign"
            )

        return {
            "campaign": {
                "id": str(row.id),
                "name": row.name,
                "brand_name": row.brand_name,
                "brand_logo_url": row.brand_logo_url,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "creators_count": 0,
                "posts_count": 0,
                "total_reach": 0
            }
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create campaign for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}"
        )

@router.get("/{campaign_id}")
async def get_campaign_simple(
    campaign_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get campaign details - Simple direct database access

    Frontend requirement: GET /api/v1/campaigns/{id}
    """
    try:
        query = """
            SELECT c.id, c.name, c.brand_name, c.brand_logo_url, c.status,
                   c.created_at, c.updated_at,
                   COUNT(DISTINCT cc.profile_id) as creators_count,
                   COUNT(cp.id) as posts_count,
                   COALESCE(SUM(p.followers_count), 0) as total_reach
            FROM campaigns c
            LEFT JOIN campaign_creators cc ON c.id = cc.campaign_id
            LEFT JOIN campaign_posts cp ON c.id = cp.campaign_id
            LEFT JOIN profiles p ON cc.profile_id = p.id
            WHERE c.id = :campaign_id AND c.user_id = :user_id
            GROUP BY c.id, c.name, c.brand_name, c.brand_logo_url, c.status,
                     c.created_at, c.updated_at
        """

        result = await db.execute(text(query), {
            "campaign_id": campaign_id,
            "user_id": current_user.id
        })

        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "campaign": {
                "id": str(row.id),
                "name": row.name,
                "brand_name": row.brand_name,
                "brand_logo_url": row.brand_logo_url,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "creators_count": row.creators_count or 0,
                "posts_count": row.posts_count or 0,
                "total_reach": int(row.total_reach or 0)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign: {str(e)}"
        )

@router.put("/{campaign_id}")
async def update_campaign_simple(
    campaign_id: str,
    updates: CampaignUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update campaign - Simple direct database access

    Frontend requirement: PUT /api/v1/campaigns/{id}
    """
    try:
        # Build dynamic update query
        update_fields = []
        params = {"campaign_id": campaign_id, "user_id": current_user.id}

        if updates.name is not None:
            update_fields.append("name = :name")
            params["name"] = updates.name

        if updates.brand_name is not None:
            update_fields.append("brand_name = :brand_name")
            params["brand_name"] = updates.brand_name

        if updates.brand_logo_url is not None:
            update_fields.append("brand_logo_url = :brand_logo_url")
            params["brand_logo_url"] = updates.brand_logo_url

        if updates.status is not None:
            update_fields.append("status = :status")
            params["status"] = updates.status

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        update_fields.append("updated_at = NOW()")

        update_query = f"""
            UPDATE campaigns
            SET {', '.join(update_fields)}
            WHERE id = :campaign_id AND user_id = :user_id
            RETURNING id, name, brand_name, brand_logo_url, status, created_at, updated_at
        """

        result = await db.execute(text(update_query), params)
        await db.commit()

        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {
            "campaign": {
                "id": str(row.id),
                "name": row.name,
                "brand_name": row.brand_name,
                "brand_logo_url": row.brand_logo_url,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign: {str(e)}"
        )

@router.delete("/{campaign_id}")
async def delete_campaign_simple(
    campaign_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete campaign - Simple direct database access

    Frontend requirement: DELETE /api/v1/campaigns/{id}
    """
    try:
        delete_query = """
            DELETE FROM campaigns
            WHERE id = :campaign_id AND user_id = :user_id
            RETURNING id
        """

        result = await db.execute(text(delete_query), {
            "campaign_id": campaign_id,
            "user_id": current_user.id
        })

        await db.commit()

        deleted_row = result.fetchone()
        if not deleted_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return {"success": True, "message": "Campaign deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete campaign: {str(e)}"
        )

# =============================================================================
# DEBUG ENDPOINTS
# =============================================================================

@router.get("/debug/check-database")
async def debug_check_database(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Debug: Check database connection and campaign table structure"""
    try:
        # Test basic database connection
        test_query = "SELECT 1 as test"
        result = await db.execute(text(test_query))
        test_row = result.fetchone()

        # Check campaigns table structure
        table_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'campaigns'
            ORDER BY ordinal_position
        """
        result = await db.execute(text(table_query))
        columns = result.fetchall()

        # Check if user has any campaigns
        user_campaigns_query = """
            SELECT COUNT(*) as count,
                   MIN(created_at) as first_campaign,
                   MAX(created_at) as last_campaign
            FROM campaigns
            WHERE user_id = :user_id
        """
        result = await db.execute(text(user_campaigns_query), {"user_id": current_user.id})
        campaigns_info = result.fetchone()

        return {
            "database_connection": "OK" if test_row else "FAILED",
            "campaigns_table_columns": [
                {"name": col.column_name, "type": col.data_type, "nullable": col.is_nullable}
                for col in columns
            ],
            "user_campaigns": {
                "count": campaigns_info.count,
                "first_campaign": campaigns_info.first_campaign.isoformat() if campaigns_info.first_campaign else None,
                "last_campaign": campaigns_info.last_campaign.isoformat() if campaigns_info.last_campaign else None
            },
            "current_user_id": current_user.id
        }

    except Exception as e:
        logger.error(f"Debug check failed: {e}")
        return {
            "error": str(e),
            "database_connection": "FAILED"
        }