"""
Brand Proposals API Routes - For brand users to view available proposals
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional, List
from uuid import UUID
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brand", tags=["Brand Proposals"])

@router.get("/proposals")
async def get_brand_proposals(
    status_filter: Optional[str] = Query(None, description="Filter by proposal status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available proposals for brands - OPEN ACCESS

    Proposals are now available to all authenticated users.
    No team membership or superadmin approval required.
    """
    try:
        # REMOVED: Access control restrictions - now available to all users
        # Previous restrictions: team membership and superadmin approval
        
        # Query the admin_brand_proposals table for proposals sent to this brand user
        query = """
        SELECT 
            id, proposal_title, proposal_description, service_type, 
            proposed_budget_usd, status, priority_level, created_at,
            proposed_start_date, proposed_end_date, brand_response_due_date
        FROM admin_brand_proposals 
        WHERE brand_user_id = :user_id
        """
        
        if status_filter:
            query += " AND status = :status"
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        
        params = {
            "user_id": str(current_user.id),
            "limit": limit,
            "offset": offset
        }
        
        if status_filter:
            params["status"] = status_filter
        
        result = await db.execute(text(query), params)
        proposals = result.fetchall()
        
        # Convert to list of dictionaries
        proposals_list = []
        for proposal in proposals:
            proposals_list.append({
                "id": str(proposal.id),
                "proposal_title": proposal.proposal_title,
                "proposal_description": proposal.proposal_description,
                "service_type": proposal.service_type,
                "proposed_budget_usd": proposal.proposed_budget_usd,
                "status": proposal.status,
                "priority_level": proposal.priority_level,
                "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
                "proposed_start_date": proposal.proposed_start_date.isoformat() if proposal.proposed_start_date else None,
                "proposed_end_date": proposal.proposed_end_date.isoformat() if proposal.proposed_end_date else None,
                "brand_response_due_date": proposal.brand_response_due_date.isoformat() if proposal.brand_response_due_date else None
            })
        
        # Get total count
        count_query = """
        SELECT COUNT(*) FROM admin_brand_proposals 
        WHERE brand_user_id = :user_id
        """
        if status_filter:
            count_query += " AND status = :status"
            
        count_result = await db.execute(text(count_query), params)
        total = count_result.scalar()
        
        return {
            "proposals": proposals_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise  # Let access control errors (402/403) pass through to frontend
    except Exception as e:
        logger.error(f"Error getting brand proposals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposals"
        )


# REMOVED: Access control functions - no longer needed with open access
# async def _get_user_team_id(user_id: UUID, db: AsyncSession) -> Optional[UUID]:
# async def _check_proposal_access(team_id: UUID, db: AsyncSession) -> bool:

@router.get("/proposals/{proposal_id}")
async def get_brand_proposal(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific proposal details"""
    try:
        # Return 404 for now since this feature is not implemented
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found or feature not available"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proposal {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposal"
        )