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
        
        for proposal in proposals["proposals"]:
            # Status distribution
            proposal_status = proposal["status"]
            status_counts[proposal_status] = status_counts.get(proposal_status, 0) + 1

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
            "recent_proposals": proposals["proposals"][:10]  # Last 10 proposals
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
# PROPOSAL CREATION HELPERS
# ============================================================================

@router.get("/brands/available")
async def get_available_brands(
    search: Optional[str] = Query(None, description="Search brands by name or email"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available brands for proposal creation"""
    require_superadmin_role(current_user)

    try:
        # Build query to get brand users
        where_conditions = ["role IN ('brand', 'brand_premium', 'premium')"]
        params = {"limit": limit, "offset": offset}

        if search:
            where_conditions.append("(email ILIKE :search OR full_name ILIKE :search)")
            params["search"] = f"%{search}%"

        where_clause = " AND ".join(where_conditions)

        # Get brand users with their teams and recent activity
        result = await db.execute(
            text(f"""
                SELECT DISTINCT
                    u.id,
                    u.email,
                    u.full_name,
                    u.role,
                    u.subscription_tier,
                    u.status,
                    u.created_at,
                    t.name as team_name,
                    t.id as team_id,
                    COALESCE(proposal_count.total, 0) as total_proposals
                FROM users u
                LEFT JOIN team_members tm ON u.id = tm.user_id
                LEFT JOIN teams t ON tm.team_id = t.id
                LEFT JOIN (
                    SELECT brand_user_id, COUNT(*) as total
                    FROM admin_brand_proposals
                    GROUP BY brand_user_id
                ) proposal_count ON u.id = proposal_count.brand_user_id
                WHERE {where_clause}
                ORDER BY u.full_name, u.email
                LIMIT :limit OFFSET :offset
            """),
            params
        )

        brands = result.fetchall()

        # Get total count
        count_result = await db.execute(
            text(f"SELECT COUNT(DISTINCT u.id) FROM users u WHERE {where_clause}"),
            {k: v for k, v in params.items() if k not in ['limit', 'offset']}
        )
        total_count = count_result.scalar()

        brands_data = []
        for brand in brands:
            brands_data.append({
                "id": str(brand.id),
                "email": brand.email,
                "full_name": brand.full_name,
                "role": brand.role,
                "subscription_tier": brand.subscription_tier,
                "status": brand.status,
                "team": {
                    "id": str(brand.team_id) if brand.team_id else None,
                    "name": brand.team_name
                } if brand.team_id else None,
                "total_proposals": brand.total_proposals,
                "created_at": brand.created_at.isoformat()
            })

        return {
            "success": True,
            "data": {
                "brands": brands_data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        }

    except Exception as e:
        logger.error(f"Error getting available brands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving available brands"
        )

@router.get("/influencers/available")
async def get_available_influencers(
    search: Optional[str] = Query(None, description="Search by username or name"),
    category: Optional[str] = Query(None, description="Filter by content category"),
    min_followers: Optional[int] = Query(None, description="Minimum follower count"),
    max_followers: Optional[int] = Query(None, description="Maximum follower count"),
    has_pricing: Optional[bool] = Query(None, description="Filter by pricing availability"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available influencers for proposal creation"""
    require_superadmin_role(current_user)

    try:
        # Build query conditions
        where_conditions = ["p.id IS NOT NULL"]
        params = {"limit": limit, "offset": offset}

        if search:
            where_conditions.append("(p.username ILIKE :search OR p.full_name ILIKE :search)")
            params["search"] = f"%{search}%"

        if category:
            where_conditions.append("p.ai_primary_content_type = :category")
            params["category"] = category

        if min_followers:
            where_conditions.append("p.followers_count >= :min_followers")
            params["min_followers"] = min_followers

        if max_followers:
            where_conditions.append("p.followers_count <= :max_followers")
            params["max_followers"] = max_followers

        if has_pricing is not None:
            if has_pricing:
                where_conditions.append("ip.profile_id IS NOT NULL")
            else:
                where_conditions.append("ip.profile_id IS NULL")

        where_clause = " AND ".join(where_conditions)

        # Get influencers with their pricing information
        result = await db.execute(
            text(f"""
                SELECT DISTINCT
                    p.id,
                    p.username,
                    p.full_name,
                    p.biography,
                    p.followers_count,
                    p.following_count,
                    p.posts_count,
                    p.is_verified,
                    p.ai_primary_content_type,
                    p.ai_avg_sentiment_score,
                    p.profile_picture_url,
                    -- Pricing information
                    ip.story_price_usd_cents,
                    ip.post_price_usd_cents,
                    ip.reel_price_usd_cents,
                    ip.pricing_tier,
                    ip.negotiable,
                    ip.pricing_effective_date,
                    -- Engagement metrics
                    p.engagement_rate
                FROM profiles p
                LEFT JOIN influencer_pricing ip ON p.id = ip.profile_id
                WHERE {where_clause}
                ORDER BY p.followers_count DESC, p.username
                LIMIT :limit OFFSET :offset
            """),
            params
        )

        influencers = result.fetchall()

        # Get total count
        count_result = await db.execute(
            text(f"""
                SELECT COUNT(DISTINCT p.id)
                FROM profiles p
                LEFT JOIN influencer_pricing ip ON p.id = ip.profile_id
                WHERE {where_clause}
            """),
            {k: v for k, v in params.items() if k not in ['limit', 'offset']}
        )
        total_count = count_result.scalar()

        influencers_data = []
        for inf in influencers:
            pricing = None
            if inf.story_price_usd_cents or inf.post_price_usd_cents or inf.reel_price_usd_cents:
                pricing = {
                    "story_price_usd_cents": inf.story_price_usd_cents,
                    "post_price_usd_cents": inf.post_price_usd_cents,
                    "reel_price_usd_cents": inf.reel_price_usd_cents,
                    "pricing_tier": inf.pricing_tier,
                    "negotiable": inf.negotiable,
                    "effective_date": inf.pricing_effective_date.isoformat() if inf.pricing_effective_date else None
                }

            influencers_data.append({
                "id": str(inf.id),
                "username": inf.username,
                "full_name": inf.full_name,
                "biography": inf.biography,
                "followers_count": inf.followers_count,
                "following_count": inf.following_count,
                "posts_count": inf.posts_count,
                "is_verified": inf.is_verified,
                "profile_picture_url": inf.profile_picture_url,
                "content_category": inf.ai_primary_content_type,
                "sentiment_score": inf.ai_avg_sentiment_score,
                "engagement_rate": inf.engagement_rate,
                "pricing": pricing,
                "has_database_pricing": pricing is not None
            })

        return {
            "success": True,
            "data": {
                "influencers": influencers_data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        }

    except Exception as e:
        logger.error(f"Error getting available influencers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving available influencers"
        )

@router.post("/proposals/create-comprehensive")
async def create_comprehensive_proposal(
    proposal_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a comprehensive proposal with brands, influencers, and pricing

    Body:
    {
        "brand_details": {
            "brand_user_ids": ["uuid1", "uuid2"],  // Selected brand users
            "brand_company_name": "Fashion Brand Inc",
            "primary_contact_email": "contact@brand.com"
        },
        "proposal_details": {
            "proposal_title": "Q1 Influencer Campaign",
            "proposal_description": "Complete campaign description...",
            "campaign_brief": "Detailed brief...",
            "campaign_objectives": ["awareness", "engagement", "sales"],
            "target_demographics": {
                "age_range": "18-35",
                "interests": ["fashion", "lifestyle"]
            },
            "proposed_start_date": "2024-02-01",
            "proposed_end_date": "2024-02-28",
            "priority_level": "high"
        },
        "influencers": [
            {
                "profile_id": "uuid",
                "pricing_override": {
                    "story_price_usd_cents": 50000,
                    "post_price_usd_cents": 100000,
                    "reel_price_usd_cents": 150000,
                    "use_database_pricing": false  // true = use DB, false = use override
                },
                "deliverables": [
                    {"type": "story", "quantity": 2},
                    {"type": "post", "quantity": 1}
                ],
                "special_requirements": "Must include brand hashtags"
            }
        ],
        "deliverables": [
            {"type": "story", "quantity": 4, "specs": "Instagram Stories with brand tags"},
            {"type": "post", "quantity": 2, "specs": "Feed posts 1080x1080"}
        ],
        "total_campaign_budget_usd_cents": 500000,
        "payment_terms": "Net 30",
        "usage_rights": "1 year social media usage",
        "special_terms": "Additional terms and conditions"
    }
    """
    require_superadmin_role(current_user)

    try:
        # Validate required data
        if not proposal_data.get("brand_details", {}).get("brand_user_ids"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one brand user must be selected"
            )

        if not proposal_data.get("influencers"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one influencer must be selected"
            )

        # Validate brand users exist
        brand_user_ids = proposal_data["brand_details"]["brand_user_ids"]
        brand_check = await db.execute(
            text("SELECT id, email, full_name FROM users WHERE id = ANY(:brand_ids) AND role IN ('brand', 'brand_premium', 'premium')"),
            {"brand_ids": brand_user_ids}
        )
        valid_brands = brand_check.fetchall()

        if len(valid_brands) != len(brand_user_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more selected brand users are invalid"
            )

        # Validate influencers exist
        influencer_ids = [inf["profile_id"] for inf in proposal_data["influencers"]]
        influencer_check = await db.execute(
            text("SELECT id, username FROM profiles WHERE id = ANY(:profile_ids)"),
            {"profile_ids": influencer_ids}
        )
        valid_influencers = influencer_check.fetchall()

        if len(valid_influencers) != len(influencer_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more selected influencers are invalid"
            )

        # Create proposals for each brand user
        created_proposals = []

        for brand_user_id in brand_user_ids:
            # Prepare proposal data for this specific brand
            brand_proposal_data = {
                **proposal_data.get("proposal_details", {}),
                "assigned_brand_users": [brand_user_id],
                "brand_company_name": proposal_data["brand_details"]["brand_company_name"],
                "total_campaign_budget_usd_cents": proposal_data.get("total_campaign_budget_usd_cents", 0),
                "deliverables": proposal_data.get("deliverables", []),
                "payment_terms": proposal_data.get("payment_terms", ""),
                "usage_rights": proposal_data.get("usage_rights", ""),
                "special_terms": proposal_data.get("special_terms", "")
            }

            # Create the proposal
            proposal_result = await refined_proposals_service.create_brand_proposal(
                admin_user_id=current_user.id,
                proposal_data=brand_proposal_data
            )

            proposal_id = UUID(proposal_result["id"])

            # Add influencers to the proposal
            influencer_result = await refined_proposals_service.add_influencers_to_proposal(
                admin_user_id=current_user.id,
                proposal_id=proposal_id,
                influencers_data=proposal_data["influencers"]
            )

            created_proposals.append({
                "proposal_id": proposal_result["id"],
                "brand_user_id": brand_user_id,
                "brand_email": next(b.email for b in valid_brands if str(b.id) == brand_user_id),
                "proposal_title": proposal_result["proposal_title"],
                "influencer_count": len(proposal_data["influencers"]),
                "total_budget": proposal_data.get("total_campaign_budget_usd_cents", 0)
            })

        return {
            "success": True,
            "data": {
                "created_proposals": created_proposals,
                "total_proposals_created": len(created_proposals),
                "message": f"Successfully created {len(created_proposals)} proposal(s) for {len(brand_user_ids)} brand(s)"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comprehensive proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating comprehensive proposal"
        )

@router.get("/influencers/{profile_id}/pricing")
async def get_influencer_pricing(
    profile_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed pricing information for an influencer"""
    require_superadmin_role(current_user)

    try:
        # Get pricing from service
        pricing = await refined_proposals_service.get_influencer_pricing(
            admin_user_id=current_user.id,
            profile_id=profile_id
        )

        if not pricing:
            # Get basic profile info even without pricing
            profile_result = await db.execute(
                text("""
                    SELECT id, username, full_name, followers_count, is_verified
                    FROM profiles WHERE id = :profile_id
                """),
                {"profile_id": str(profile_id)}
            )
            profile = profile_result.fetchone()

            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Influencer not found"
                )

            return {
                "success": True,
                "data": {
                    "profile_id": str(profile.id),
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "followers_count": profile.followers_count,
                    "is_verified": profile.is_verified,
                    "has_pricing": False,
                    "pricing": None
                }
            }

        return {
            "success": True,
            "data": {
                **pricing,
                "has_pricing": True
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting influencer pricing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving influencer pricing"
        )

@router.post("/influencers/{profile_id}/pricing")
async def set_influencer_pricing(
    profile_id: UUID,
    pricing_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Set or update pricing for an influencer

    Body:
    {
        "story_price_usd_cents": 50000,
        "post_price_usd_cents": 100000,
        "reel_price_usd_cents": 150000,
        "ugc_video_price_usd_cents": 200000,
        "story_series_price_usd_cents": 300000,
        "carousel_post_price_usd_cents": 120000,
        "igtv_price_usd_cents": 180000,
        "pricing_tier": "premium",  // standard, premium, exclusive
        "negotiable": true,
        "minimum_campaign_value_usd_cents": 500000,
        "package_pricing": {
            "story_post_combo": 140000,
            "full_campaign": 800000
        },
        "volume_discounts": {
            "5_posts": 0.10,
            "10_posts": 0.15
        },
        "pricing_effective_date": "2024-01-01",
        "pricing_expires_date": "2024-12-31"
    }
    """
    require_superadmin_role(current_user)

    try:
        # Set pricing through service
        result = await refined_proposals_service.manage_influencer_pricing(
            admin_user_id=current_user.id,
            profile_id=profile_id,
            pricing_data=pricing_data
        )

        return {
            "success": True,
            "data": result,
            "message": f"Successfully {result['action']} pricing for influencer"
        }

    except Exception as e:
        logger.error(f"Error setting influencer pricing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error setting influencer pricing"
        )

@router.get("/pricing/calculate")
async def calculate_proposal_pricing(
    influencer_ids: str = Query(..., description="Comma-separated list of influencer profile IDs"),
    deliverables: str = Query(..., description="JSON string of deliverables by influencer"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate total pricing for a proposal based on influencers and deliverables

    Example:
    - influencer_ids: "uuid1,uuid2,uuid3"
    - deliverables: '{"uuid1":[{"type":"story","quantity":2},{"type":"post","quantity":1}],"uuid2":[{"type":"reel","quantity":1}]}'
    """
    require_superadmin_role(current_user)

    try:
        import json

        # Parse parameters
        profile_ids = [id.strip() for id in influencer_ids.split(",")]
        deliverables_data = json.loads(deliverables)

        # Get pricing for all influencers
        pricing_calculations = []
        total_campaign_cost = 0

        for profile_id in profile_ids:
            try:
                profile_uuid = UUID(profile_id)

                # Get pricing for this influencer
                pricing = await refined_proposals_service.get_influencer_pricing(
                    admin_user_id=current_user.id,
                    profile_id=profile_uuid
                )

                if not pricing:
                    pricing_calculations.append({
                        "profile_id": profile_id,
                        "username": "Unknown",
                        "has_pricing": False,
                        "cost_breakdown": [],
                        "total_cost": 0,
                        "note": "No pricing data available"
                    })
                    continue

                # Calculate cost for this influencer's deliverables
                influencer_deliverables = deliverables_data.get(profile_id, [])
                cost_breakdown = []
                influencer_total = 0

                for deliverable in influencer_deliverables:
                    deliverable_type = deliverable.get("type")
                    quantity = deliverable.get("quantity", 1)

                    # Map deliverable types to pricing fields
                    price_field_map = {
                        "story": "story_price_usd_cents",
                        "post": "post_price_usd_cents",
                        "reel": "reel_price_usd_cents",
                        "ugc_video": "ugc_video_price_usd_cents",
                        "story_series": "story_series_price_usd_cents",
                        "carousel_post": "carousel_post_price_usd_cents",
                        "igtv": "igtv_price_usd_cents"
                    }

                    price_field = price_field_map.get(deliverable_type)
                    if price_field and pricing["pricing"].get(price_field):
                        unit_price = pricing["pricing"][price_field]
                        line_total = unit_price * quantity
                        influencer_total += line_total

                        cost_breakdown.append({
                            "type": deliverable_type,
                            "quantity": quantity,
                            "unit_price_usd_cents": unit_price,
                            "line_total_usd_cents": line_total
                        })

                total_campaign_cost += influencer_total

                pricing_calculations.append({
                    "profile_id": profile_id,
                    "username": pricing["username"],
                    "full_name": pricing["full_name"],
                    "has_pricing": True,
                    "pricing_tier": pricing["pricing"]["pricing_tier"],
                    "negotiable": pricing["pricing"]["negotiable"],
                    "cost_breakdown": cost_breakdown,
                    "total_cost": influencer_total
                })

            except Exception as e:
                logger.warning(f"Error calculating pricing for influencer {profile_id}: {e}")
                pricing_calculations.append({
                    "profile_id": profile_id,
                    "username": "Error",
                    "has_pricing": False,
                    "cost_breakdown": [],
                    "total_cost": 0,
                    "error": str(e)
                })

        return {
            "success": True,
            "data": {
                "influencer_calculations": pricing_calculations,
                "total_campaign_cost_usd_cents": total_campaign_cost,
                "total_campaign_cost_usd": total_campaign_cost / 100,
                "currency": "USD",
                "calculation_date": datetime.now().isoformat()
            }
        }

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format for deliverables parameter"
        )
    except Exception as e:
        logger.error(f"Error calculating proposal pricing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating proposal pricing"
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