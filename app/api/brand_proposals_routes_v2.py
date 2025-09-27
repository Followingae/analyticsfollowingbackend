"""
Brand Proposals API Routes V2 - For brand users to view and respond to proposals
Refined for B2B workflow where superadmin creates proposals for brands
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.refined_proposals_service import refined_proposals_service
from app.services.currency_service import currency_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brand/proposals", tags=["Brand Proposals V2"])

def require_brand_user(current_user: UserInDB):
    """Ensure user has brand access"""
    # Allow brand users and admins to access brand routes
    if current_user.role not in ['brand', 'brand_premium', 'brand_standard', 'premium', 'standard', 'admin', 'superadmin', 'super_admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Brand access required, user has '{current_user.role}' role"
        )

@router.get("/")
async def get_brand_proposals(
    status_filter: Optional[str] = Query(None, description="Filter by proposal status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get proposals assigned to current brand user
    
    Returns proposals where the current user is in the assigned_brand_users array.
    Proposals are created by superadmin and assigned to specific brand users.
    """
    require_brand_user(current_user)
    
    try:
        proposals = await refined_proposals_service.get_brand_user_proposals(
            brand_user_id=current_user.id,
            status_filter=status_filter,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "data": proposals,
            "user_id": str(current_user.id),
            "message": "Proposals retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting brand proposals for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposals"
        )

@router.get("/{proposal_id}")
async def get_proposal_details(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed view of a specific proposal assigned to brand user
    
    Returns complete proposal information including campaign details,
    timeline, requirements, and budget (without sensitive pricing breakdown).
    """
    require_brand_user(current_user)
    
    try:
        # Get basic proposal details
        proposals = await refined_proposals_service.get_brand_user_proposals(
            brand_user_id=current_user.id,
            limit=1000  # Get all to find this specific one
        )
        
        # Find the specific proposal
        target_proposal = None
        for proposal in proposals["data"]["proposals"]:
            if proposal["id"] == str(proposal_id):
                target_proposal = proposal
                break
        
        if not target_proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found or access denied"
            )
        
        # Get influencers for this proposal
        influencers = await refined_proposals_service.get_brand_proposal_influencers(
            brand_user_id=current_user.id,
            proposal_id=proposal_id
        )
        
        # Combine proposal details with influencers
        proposal_details = {
            **target_proposal,
            "influencers": influencers,
            "influencer_count": len(influencers)
        }
        
        return {
            "success": True,
            "data": proposal_details,
            "message": "Proposal details retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proposal details {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposal details"
        )

@router.get("/{proposal_id}/influencers")
async def get_proposal_influencers(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of influencers assigned to this proposal
    
    Returns influencer details including social metrics, deliverables, 
    and expected performance (without detailed pricing breakdown).
    """
    require_brand_user(current_user)
    
    try:
        influencers = await refined_proposals_service.get_brand_proposal_influencers(
            brand_user_id=current_user.id,
            proposal_id=proposal_id
        )
        
        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal_id),
                "influencers": influencers,
                "total_count": len(influencers)
            },
            "message": f"Found {len(influencers)} influencers for this proposal"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting proposal influencers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving influencers"
        )

@router.post("/{proposal_id}/respond")
async def submit_proposal_response(
    proposal_id: UUID,
    response_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit brand response to proposal
    
    Body:
    {
        "response": "approved", // approved, rejected, requested_changes, needs_discussion
        "feedback": "We love the influencer selection and timeline...",
        "requested_changes": [
            {"type": "timeline", "description": "Can we move start date to March 1st?"},
            {"type": "budget", "description": "Budget looks too high, can we negotiate?"}
        ]
    }
    """
    require_brand_user(current_user)
    
    try:
        # Validate required fields
        if "response" not in response_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="response field is required"
            )
        
        valid_responses = ["approved", "rejected", "requested_changes", "needs_discussion"]
        if response_data["response"] not in valid_responses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"response must be one of: {', '.join(valid_responses)}"
            )
        
        result = await refined_proposals_service.submit_brand_response(
            brand_user_id=current_user.id,
            proposal_id=proposal_id,
            response_data=response_data
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Response submitted successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error submitting response"
        )

@router.get("/{proposal_id}/status")
async def get_proposal_status(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current status and response details for proposal
    
    Returns proposal status, any brand feedback, response deadline, etc.
    """
    require_brand_user(current_user)
    
    try:
        # Get proposals and find the specific one
        proposals = await refined_proposals_service.get_brand_user_proposals(
            brand_user_id=current_user.id,
            limit=1000
        )
        
        target_proposal = None
        for proposal in proposals["data"]["proposals"]:
            if proposal["id"] == str(proposal_id):
                target_proposal = proposal
                break
        
        if not target_proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found or access denied"
            )
        
        # Extract status-relevant information
        status_info = {
            "proposal_id": str(proposal_id),
            "current_status": target_proposal["status"],
            "priority_level": target_proposal["priority_level"],
            "sent_to_brands_at": target_proposal["sent_to_brands_at"],
            "brand_response_deadline": target_proposal["brand_response_deadline"],
            "brand_response": target_proposal["brand_response"],
            "brand_feedback": target_proposal["brand_feedback"],
            "brand_responded_at": target_proposal["brand_responded_at"],
            "is_overdue": False,
            "days_remaining": None
        }
        
        # Calculate time remaining if there's a deadline
        if target_proposal["brand_response_deadline"]:
            from datetime import datetime
            deadline = datetime.fromisoformat(target_proposal["brand_response_deadline"].replace("Z", "+00:00"))
            now = datetime.now(deadline.tzinfo)
            time_remaining = deadline - now
            
            status_info["is_overdue"] = time_remaining.total_seconds() < 0
            status_info["days_remaining"] = time_remaining.days if time_remaining.days >= 0 else 0
        
        return {
            "success": True,
            "data": status_info,
            "message": "Status retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proposal status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposal status"
        )

@router.get("/")
async def get_proposals_summary(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get summary of all proposals for brand dashboard
    
    Returns counts by status, overdue proposals, recent activity, etc.
    """
    require_brand_user(current_user)
    
    try:
        # Get all proposals for this brand user
        all_proposals = await refined_proposals_service.get_brand_user_proposals(
            brand_user_id=current_user.id,
            limit=1000
        )
        
        proposals = all_proposals["data"]["proposals"]
        
        # Calculate summary statistics
        status_counts = {}
        priority_counts = {}
        overdue_count = 0
        total_budget = 0
        
        from datetime import datetime
        
        for proposal in proposals:
            # Status distribution
            status = proposal["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Priority distribution
            priority = proposal["priority_level"]
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Budget totals
            total_budget += proposal.get("total_campaign_budget_usd_cents", 0)
            
            # Check for overdue responses
            if (proposal["brand_response_deadline"] and 
                proposal["status"] in ["sent", "under_review"] and
                not proposal["brand_response"]):
                deadline = datetime.fromisoformat(proposal["brand_response_deadline"].replace("Z", "+00:00"))
                if datetime.now(deadline.tzinfo) > deadline:
                    overdue_count += 1
        
        # Get user's currency for proper formatting
        user_currency = await currency_service.get_user_currency(str(current_user.id), db)
        formatted_budget = await currency_service.format_amount(
            total_budget,
            currency_info=user_currency
        )

        summary_data = {
            "overview": {
                "total_proposals": len(proposals),
                "pending_response": status_counts.get("sent", 0),
                "approved_proposals": status_counts.get("approved", 0),
                "overdue_responses": overdue_count,
                "total_budget_cents": total_budget,
                "total_budget_formatted": formatted_budget,
                "currency_info": user_currency
            },
            "status_distribution": status_counts,
            "priority_distribution": priority_counts,
            "recent_proposals": proposals[:5]  # 5 most recent
        }
        
        return {
            "success": True,
            "data": summary_data,
            "user_id": str(current_user.id),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting proposals summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposals summary"
        )

# ============================================================================
# BRAND USER FEEDBACK & COMMUNICATION
# ============================================================================

@router.post("/{proposal_id}/feedback")
async def add_proposal_feedback(
    proposal_id: UUID,
    feedback_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add feedback or comment to proposal (for internal brand team discussion)
    
    Body:
    {
        "message": "The influencer selection looks great, but can we adjust the timeline?",
        "is_internal": true, // Internal brand team note or message to admin
        "urgency": "normal" // low, normal, high
    }
    """
    require_brand_user(current_user)
    
    try:
        if not feedback_data.get("message"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="message is required"
            )
        
        # For now, this can be a placeholder for future communication features
        # The actual response submission should use the /respond endpoint
        
        return {
            "success": True,
            "data": {
                "proposal_id": str(proposal_id),
                "feedback_added": True,
                "message": "Feedback functionality coming soon. Use /respond endpoint for official responses."
            },
            "message": "Feedback noted (placeholder response)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error adding feedback"
        )

# ============================================================================
# SYSTEM UTILITIES
# ============================================================================

@router.get("/health")
async def brand_proposals_health(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Health check for brand proposals system"""
    require_brand_user(current_user)
    
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "brand_proposals_v2",
            "user_role": current_user.role,
            "user_id": str(current_user.id),
            "timestamp": f"{datetime.now().isoformat()}Z"
        }
    }