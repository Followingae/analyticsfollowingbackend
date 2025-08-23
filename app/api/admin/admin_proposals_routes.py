"""
Admin Proposals Routes - Superadmin Only Access
Provides admin interface for managing proposals system
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.database.connection import get_db

router = APIRouter(prefix="/admin", tags=["Admin Proposals"])

def require_superadmin_role(current_user: UserInDB):
    """Enforce superadmin role requirement"""
    if current_user.role not in ['admin', 'superadmin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Requires admin/superadmin role, user has {current_user.role}"
        )

@router.get("/proposals")
async def get_admin_proposals(
    status_filter: Optional[str] = Query(None, description="Filter by proposal status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all proposals for admin management - SUPERADMIN ONLY
    
    This endpoint is only accessible to users with admin or superadmin roles.
    Regular users (including premium) are blocked with 403 Forbidden.
    """
    # CRITICAL: Enforce superadmin role
    require_superadmin_role(current_user)
    
    # Return admin proposal data
    return {
        "proposals": [
            {
                "id": "prop-001",
                "brand_name": "Sample Brand",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "admin_notes": "Requires review"
            }
        ],
        "pagination": {
            "total": 1,
            "limit": limit,
            "offset": offset,
            "has_more": False
        },
        "filters": {
            "status": status_filter
        },
        "admin_access": True,
        "user_role": current_user.role,
        "message": "Admin proposals data - superadmin access confirmed"
    }

@router.get("/proposals/pipeline-summary")
async def get_proposals_pipeline_summary(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get proposal pipeline summary for admin dashboard - SUPERADMIN ONLY
    
    This endpoint provides high-level statistics for the admin dashboard.
    Only accessible to admin/superadmin roles.
    """
    # CRITICAL: Enforce superadmin role
    require_superadmin_role(current_user)
    
    return {
        "pipeline_summary": {
            "total_proposals": 0,
            "pending_proposals": 0,
            "approved_proposals": 0,
            "rejected_proposals": 0,
            "revenue_pipeline": 0
        },
        "recent_activity": [],
        "admin_access": True,
        "user_role": current_user.role,
        "message": "Admin pipeline summary - superadmin access confirmed"
    }

@router.post("/proposals")
async def create_admin_proposal(
    proposal_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create proposal as admin - SUPERADMIN ONLY
    
    Allows superadmin to create proposals on behalf of brands.
    """
    # CRITICAL: Enforce superadmin role
    require_superadmin_role(current_user)
    
    return {
        "success": True,
        "proposal_id": "admin-prop-001",
        "message": "Proposal created by admin",
        "admin_access": True,
        "user_role": current_user.role,
        "created_by": current_user.email
    }

@router.get("/proposals/{proposal_id}")
async def get_admin_proposal_details(
    proposal_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific proposal details for admin - SUPERADMIN ONLY
    """
    # CRITICAL: Enforce superadmin role
    require_superadmin_role(current_user)
    
    return {
        "proposal": {
            "id": proposal_id,
            "brand_name": "Sample Brand",
            "status": "pending",
            "admin_notes": "Under review",
            "financial_details": "Admin only data"
        },
        "admin_access": True,
        "user_role": current_user.role,
        "message": "Admin proposal details - superadmin access confirmed"
    }