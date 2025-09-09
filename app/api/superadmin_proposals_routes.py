"""
Superadmin Proposals API Routes - Complete B2B proposal management
Handles proposal creation, influencer management, and invite campaigns
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.refined_proposals_service import refined_proposals_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/superadmin/proposals", tags=["Superadmin Proposals"])

def require_superadmin_role(current_user: UserInDB):
    """Enforce superadmin role requirement"""
    if current_user.role not in ['admin', 'superadmin', 'super_admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Requires superadmin role, user has '{current_user.role}' role"
        )

# ============================================================================
# INFLUENCER PRICING MANAGEMENT
# ============================================================================

@router.post("/pricing/influencers")
async def create_influencer_pricing(
    pricing_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update pricing for an influencer (SUPERADMIN ONLY)
    
    Body:
    {
        "profile_id": "uuid",
        "story_price_usd_cents": 50000,  // $500 in cents
        "post_price_usd_cents": 100000,  // $1000 in cents  
        "reel_price_usd_cents": 150000,  // $1500 in cents
        "pricing_tier": "premium",
        "negotiable": true,
        "minimum_campaign_value_usd_cents": 200000
    }
    """
    require_superadmin_role(current_user)
    
    try:
        if "profile_id" not in pricing_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="profile_id is required"
            )
        
        result = await refined_proposals_service.create_influencer_pricing(
            admin_user_id=current_user.id,
            profile_id=UUID(pricing_data["profile_id"]),
            pricing_data=pricing_data
        )
        
        return {
            "success": True,
            "data": result,
            "message": f"Influencer pricing {result['action']} successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error managing influencer pricing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error managing influencer pricing"
        )

@router.get("/pricing/influencers/{profile_id}")
async def get_influencer_pricing(
    profile_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get pricing details for specific influencer (SUPERADMIN ONLY)"""
    require_superadmin_role(current_user)
    
    try:
        pricing = await refined_proposals_service.get_influencer_pricing(
            admin_user_id=current_user.id,
            profile_id=profile_id
        )
        
        if not pricing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pricing not found for this influencer"
            )
        
        return {
            "success": True,
            "data": pricing
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting influencer pricing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving influencer pricing"
        )

@router.post("/pricing/calculate/{profile_id}")
async def calculate_influencer_cost(
    profile_id: UUID,
    deliverables: List[Dict[str, Any]],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate cost for influencer based on deliverables
    
    Body:
    [
        {"type": "story", "quantity": 3},
        {"type": "post", "quantity": 1},
        {"type": "reel", "quantity": 2}
    ]
    """
    require_superadmin_role(current_user)
    
    try:
        calculation = await refined_proposals_service.calculate_influencer_cost(
            admin_user_id=current_user.id,
            profile_id=profile_id,
            deliverables=deliverables
        )
        
        return {
            "success": True,
            "data": calculation,
            "profile_id": str(profile_id)
        }
        
    except Exception as e:
        logger.error(f"Error calculating influencer cost: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating cost"
        )

# ============================================================================
# DYNAMIC INVITE CAMPAIGNS
# ============================================================================

@router.post("/invite-campaigns")
async def create_invite_campaign(
    campaign_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create dynamic invite campaign for influencer applications
    
    Body:
    {
        "campaign_name": "Summer Fashion Campaign",
        "campaign_description": "Looking for fashion influencers...",
        "deliverables": [
            {"type": "post", "quantity": 2, "description": "Feed posts showcasing products"}
        ],
        "campaign_type": "paid", // or "barter"
        "barter_offering": "Free products worth $200", // if barter campaign
        "eligible_follower_range": {"min": 10000, "max": 100000},
        "eligible_categories": ["fashion", "lifestyle"],
        "max_applications": 500,
        "application_deadline": "2024-02-01T00:00:00Z"
    }
    """
    require_superadmin_role(current_user)
    
    try:
        if not campaign_data.get("campaign_name") or not campaign_data.get("deliverables"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="campaign_name and deliverables are required"
            )
        
        result = await refined_proposals_service.create_invite_campaign(
            admin_user_id=current_user.id,
            campaign_data=campaign_data
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Invite campaign created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating invite campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating invite campaign"
        )

@router.post("/invite-campaigns/{campaign_id}/publish")
async def publish_invite_campaign(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Publish invite campaign to make it live for applications"""
    require_superadmin_role(current_user)
    
    try:
        result = await refined_proposals_service.publish_invite_campaign(
            admin_user_id=current_user.id,
            campaign_id=campaign_id
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Campaign published successfully"
        }
        
    except Exception as e:
        logger.error(f"Error publishing campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error publishing campaign"
        )

@router.get("/invite-campaigns/{campaign_id}/applications")
async def get_campaign_applications(
    campaign_id: UUID,
    status_filter: Optional[str] = Query(None, description="Filter by application status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get applications for invite campaign"""
    require_superadmin_role(current_user)
    
    try:
        applications = await refined_proposals_service.get_invite_campaign_applications(
            admin_user_id=current_user.id,
            campaign_id=campaign_id,
            status_filter=status_filter,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "data": applications,
            "campaign_id": str(campaign_id)
        }
        
    except Exception as e:
        logger.error(f"Error getting applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving applications"
        )

@router.post("/applications/{application_id}/approve")
async def approve_campaign_application(
    application_id: UUID,
    approval_data: Dict[str, Any] = {},
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve influencer application"""
    require_superadmin_role(current_user)
    
    try:
        result = await refined_proposals_service.approve_campaign_application(
            admin_user_id=current_user.id,
            application_id=application_id,
            admin_notes=approval_data.get("admin_notes")
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Application approved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error approving application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error approving application"
        )

# ============================================================================
# BRAND PROPOSAL CREATION & MANAGEMENT
# ============================================================================

@router.post("/brand-proposals")
async def create_brand_proposal(
    proposal_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create proposal for brand users
    
    Body:
    {
        "assigned_brand_users": ["brand_user_id_1", "brand_user_id_2"],
        "brand_company_name": "Fashion Brand Inc",
        "proposal_title": "Q1 Influencer Campaign",
        "proposal_description": "Complete campaign description...",
        "campaign_brief": "Detailed brief...",
        "deliverables": [
            {"type": "post", "quantity": 2, "specs": "1080x1080 posts"}
        ],
        "total_campaign_budget_usd_cents": 500000, // $5000 in cents
        "proposed_start_date": "2024-02-01",
        "proposed_end_date": "2024-02-28",
        "brand_response_deadline": "2024-01-25T17:00:00Z"
    }
    """
    require_superadmin_role(current_user)
    
    try:
        required_fields = ["assigned_brand_users", "brand_company_name", "proposal_title", "deliverables", "total_campaign_budget_usd_cents"]
        for field in required_fields:
            if not proposal_data.get(field):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} is required"
                )
        
        result = await refined_proposals_service.create_brand_proposal(
            admin_user_id=current_user.id,
            proposal_data=proposal_data
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Brand proposal created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating brand proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating proposal"
        )

@router.post("/brand-proposals/{proposal_id}/influencers")
async def add_influencers_to_proposal(
    proposal_id: UUID,
    influencers_data: List[Dict[str, Any]],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add influencers to proposal with pricing
    
    Body:
    [
        {
            "profile_id": "existing_profile_uuid", // OR
            "application_id": "application_uuid", // for invite campaign applicants
            "instagram_username": "@influencer1",
            "full_name": "Influencer Name",
            "followers_count": 50000,
            "total_influencer_budget_usd_cents": 150000, // $1500
            "assigned_deliverables": [
                {"type": "post", "quantity": 1},
                {"type": "story", "quantity": 3}
            ],
            "admin_price_adjustments": {"post_price_usd_cents": 80000}, // Custom pricing override
            "price_adjustment_reason": "Negotiated rate for bulk campaign"
        }
    ]
    """
    require_superadmin_role(current_user)
    
    try:
        if not influencers_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one influencer is required"
            )
        
        result = await refined_proposals_service.add_influencers_to_proposal(
            admin_user_id=current_user.id,
            proposal_id=proposal_id,
            influencers_data=influencers_data
        )
        
        return {
            "success": True,
            "data": result,
            "message": f"Added {result['total_added']} influencers to proposal"
        }
        
    except Exception as e:
        logger.error(f"Error adding influencers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error adding influencers to proposal"
        )

@router.post("/brand-proposals/{proposal_id}/send")
async def send_proposal_to_brands(
    proposal_id: UUID,
    send_options: Dict[str, Any] = {},
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send proposal to assigned brand users"""
    require_superadmin_role(current_user)
    
    try:
        result = await refined_proposals_service.send_proposal_to_brands(
            admin_user_id=current_user.id,
            proposal_id=proposal_id,
            send_options=send_options
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Proposal sent to brands successfully"
        }
        
    except Exception as e:
        logger.error(f"Error sending proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sending proposal"
        )

# ============================================================================
# PROPOSAL MANAGEMENT & RETRIEVAL
# ============================================================================

@router.get("/brand-proposals")
async def get_admin_proposals(
    status: Optional[str] = Query(None, description="Filter by proposal status"),
    priority_level: Optional[str] = Query(None, description="Filter by priority"),
    campaign_type: Optional[str] = Query(None, description="Filter by campaign type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all proposals created by admin with filtering"""
    require_superadmin_role(current_user)
    
    try:
        filters = {}
        if status:
            filters["status"] = status
        if priority_level:
            filters["priority_level"] = priority_level
        if campaign_type:
            filters["campaign_type"] = campaign_type
        
        proposals = await refined_proposals_service.get_admin_proposals(
            admin_user_id=current_user.id,
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "data": proposals
        }
        
    except Exception as e:
        logger.error(f"Error getting admin proposals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposals"
        )

@router.get("/brand-proposals/{proposal_id}")
async def get_proposal_details(
    proposal_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete proposal details with influencers"""
    require_superadmin_role(current_user)
    
    try:
        details = await refined_proposals_service.get_proposal_details_with_influencers(
            admin_user_id=current_user.id,
            proposal_id=proposal_id
        )
        
        return {
            "success": True,
            "data": details
        }
        
    except Exception as e:
        logger.error(f"Error getting proposal details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving proposal details"
        )

# ============================================================================
# DASHBOARD & ANALYTICS
# ============================================================================

@router.get("/dashboard")
async def get_proposals_dashboard(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get proposals dashboard with key metrics"""
    require_superadmin_role(current_user)
    
    try:
        # Get summary statistics for dashboard
        proposals = await refined_proposals_service.get_admin_proposals(
            admin_user_id=current_user.id,
            limit=1000  # Get all for stats
        )
        
        # Calculate dashboard metrics
        total_proposals = proposals["total_count"]
        status_counts = {}
        priority_counts = {}
        total_budget = 0
        
        for proposal in proposals["data"]["proposals"]:
            # Status distribution
            status = proposal["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Priority distribution
            priority = proposal["priority_level"]
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Budget totals
            total_budget += proposal.get("total_campaign_budget_usd_cents", 0)
        
        dashboard_data = {
            "overview": {
                "total_proposals": total_proposals,
                "total_budget_usd_cents": total_budget,
                "active_proposals": status_counts.get("sent", 0) + status_counts.get("under_review", 0),
                "approved_proposals": status_counts.get("approved", 0)
            },
            "status_distribution": status_counts,
            "priority_distribution": priority_counts,
            "recent_proposals": proposals["data"]["proposals"][:10]  # Last 10 proposals
        }
        
        return {
            "success": True,
            "data": dashboard_data,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving dashboard data"
        )

# ============================================================================
# SYSTEM HEALTH & UTILITIES
# ============================================================================

@router.get("/health")
async def proposals_health_check(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Health check for proposals system"""
    require_superadmin_role(current_user)
    
    try:
        # Simple health check - verify database connectivity
        health_data = {
            "status": "healthy",
            "service": "proposals",
            "timestamp": datetime.now().isoformat(),
            "user_role": current_user.role,
            "user_email": current_user.email,
            "database": "connected"
        }
        
        return {
            "success": True,
            "data": health_data
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }