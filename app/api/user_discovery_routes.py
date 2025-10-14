"""
User Discovery API Routes - Frontend Profile Discovery

User-facing discovery endpoints for browsing, searching, and unlocking profiles.
These endpoints provide the main discovery functionality for the frontend.

Key Features:
- Browse ALL profiles in database with pagination
- Advanced search and filtering
- Credit-based profile unlocking for 30-day access
- User dashboard with discovery statistics
- Unlocked profiles management
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database.connection import get_session
from app.services.user_discovery_service import user_discovery_service
from app.middleware.auth_middleware import get_current_active_user
from app.database.unified_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/discovery", tags=["Discovery"])


# Pydantic Models
class ProfileUnlockRequest(BaseModel):
    """Request to unlock a profile"""
    profile_id: UUID = Field(..., description="Profile ID to unlock")
    credits_to_spend: int = Field(25, description="Credits to spend for unlock")


class AdvancedSearchRequest(BaseModel):
    """Advanced search request"""
    query: Optional[str] = Field(None, description="Search query for username, name, bio")
    categories: List[str] = Field(default_factory=list, description="Content categories to filter by")
    follower_range: Dict[str, Optional[int]] = Field(default_factory=dict, description="Min/max followers")
    sentiment_filter: Optional[str] = Field(None, description="Sentiment filter (positive, neutral, negative)")
    verified_only: bool = Field(False, description="Show only verified profiles")
    private_filter: str = Field("all", description="Privacy filter (all, public, private)")
    sort_by: str = Field("followers_desc", description="Sort order")
    page: int = Field(1, description="Page number")
    page_size: int = Field(20, description="Results per page")


# Discovery Browse Endpoints

@router.get("/browse")
async def browse_all_profiles(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    search: Optional[str] = Query(None, description="Search in username, name, biography"),
    category: Optional[str] = Query(None, description="Filter by AI content category"),
    min_followers: Optional[int] = Query(None, ge=0, description="Minimum followers count"),
    max_followers: Optional[int] = Query(None, ge=0, description="Maximum followers count"),
    sort_by: str = Query("followers_desc", description="Sort order (followers_desc, followers_asc, recent, alphabetical)"),
    include_unlocked_status: bool = Query(True, description="Include user's unlock status"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Browse all profiles in the database with filtering and search

    This is the main discovery endpoint that allows users to browse through
    all complete profiles in the database. Each profile shows:
    - Basic profile information (username, followers, etc.)
    - AI analysis results (content category, sentiment)
    - User's unlock status (unlocked/locked, expiry)
    - Preview data without requiring unlock

    Users can filter by:
    - Search query (username, name, bio)
    - Content category (from AI analysis)
    - Follower count range
    - Sort order

    **Note**: This shows ALL profiles - not just unlocked ones.
    Users can see preview data and decide which profiles to unlock.
    """
    try:
        logger.info(f"🔍 Discovery Browse: user={current_user.email}, search='{search}'")

        result = await user_discovery_service.browse_all_profiles(
            db=db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            search_query=search,
            category_filter=category,
            min_followers=min_followers,
            max_followers=max_followers,
            sort_by=sort_by,
            include_unlocked_status=include_unlocked_status
        )

        logger.info(f"✅ Discovery Browse: {len(result['profiles'])} profiles returned")
        return result

    except Exception as e:
        logger.error(f"Discovery browse failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery browse failed: {str(e)}")


@router.post("/search-advanced")
async def advanced_profile_search(
    search_request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Advanced profile search with multiple criteria

    Provides more sophisticated search capabilities than the basic browse endpoint.
    Supports multiple categories, complex filters, and advanced sorting options.

    Use this endpoint for:
    - Complex search queries with multiple filters
    - Category-based discovery (multiple categories)
    - Advanced follower and engagement filtering
    - Sophisticated sorting and ranking
    """
    try:
        logger.info(f"🔍 Advanced Search: user={current_user.email}")

        search_params = search_request.dict()
        result = await user_discovery_service.search_profiles_advanced(
            db=db,
            user_id=current_user.id,
            search_params=search_params
        )

        logger.info(f"✅ Advanced Search: {len(result['profiles'])} profiles found")
        return result

    except Exception as e:
        logger.error(f"Advanced search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Advanced search failed: {str(e)}")


# Profile Unlock Endpoints

@router.post("/unlock-profile")
async def unlock_profile_for_access(
    unlock_request: ProfileUnlockRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Unlock a profile for 30-day access using credits

    **Cost**: 25 credits per profile
    **Access Duration**: 30 days from unlock time
    **Access Includes**:
    - Complete profile analytics
    - Full post history and analytics
    - AI analysis results
    - Engagement metrics
    - Audience demographics (if available)

    **Process**:
    1. Validates user has sufficient credits (25 required)
    2. Checks if profile is already unlocked (returns existing access)
    3. Deducts credits from user's wallet
    4. Creates 30-day access record
    5. Returns complete profile access information

    **Notes**:
    - If profile is already unlocked, no credits are charged
    - Access automatically expires after 30 days
    - Users can re-unlock expired profiles
    - All unlocks are tracked for billing and analytics
    """
    try:
        logger.info(f"🔓 Profile Unlock: user={current_user.email}, profile={unlock_request.profile_id}")

        result = await user_discovery_service.unlock_profile_for_user(
            db=db,
            user_id=current_user.id,
            profile_id=unlock_request.profile_id,
            credits_to_spend=unlock_request.credits_to_spend
        )

        if result["success"]:
            if result.get("already_unlocked"):
                logger.info(f"✅ Profile already unlocked: {result['profile']['username']}")
            else:
                logger.info(f"✅ Profile unlocked successfully: {result['profile']['username']}")
        else:
            logger.warning(f"❌ Profile unlock failed: {result.get('error', 'Unknown error')}")

        return result

    except Exception as e:
        logger.error(f"Profile unlock failed: {e}")
        raise HTTPException(status_code=500, detail=f"Profile unlock failed: {str(e)}")


@router.get("/unlocked-profiles")
async def get_user_unlocked_profiles(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    include_expired: bool = Query(False, description="Include expired access records"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get all profiles the user has unlocked

    Returns paginated list of all profiles the user has paid to unlock,
    including access status, expiry information, and remaining time.

    **Response includes**:
    - Complete profile information
    - Access details (granted time, expiry, remaining days)
    - Active/expired status
    - Profile analytics preview

    **Use cases**:
    - "My Unlocked Creators" page
    - Access management dashboard
    - Renewal notifications
    - Usage tracking and analytics

    **Note**: By default, only active (non-expired) unlocks are shown.
    Set `include_expired=true` to see historical unlocks.
    """
    try:
        logger.info(f"📊 Unlocked Profiles: user={current_user.email}")

        result = await user_discovery_service.get_user_unlocked_profiles(
            db=db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            include_expired=include_expired
        )

        logger.info(f"✅ Unlocked Profiles: {result['summary']['active_unlocks']} active, {result['summary']['expired_unlocks']} expired")
        return result

    except Exception as e:
        logger.error(f"Get unlocked profiles failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get unlocked profiles: {str(e)}")


# Discovery Dashboard and Statistics

@router.get("/dashboard")
async def get_discovery_dashboard(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get discovery dashboard statistics and overview

    Provides comprehensive discovery system overview for the user dashboard:

    **Discovery Overview**:
    - Total profiles available in discovery
    - User's unlocked profiles count
    - Discovery percentage (how much of database explored)
    - Recent discovery activity

    **Content Categories**:
    - Breakdown of available content types
    - Popular categories for discovery
    - User's unlocked categories distribution

    **Credits & Usage**:
    - Current credit balance
    - Total discovery spending
    - Unlock capacity with current credits
    - Spending recommendations

    **Use cases**:
    - Discovery dashboard homepage
    - Usage analytics and insights
    - Credit management and planning
    - Discovery strategy optimization
    """
    try:
        logger.info(f"📊 Discovery Dashboard: user={current_user.email}")

        result = await user_discovery_service.get_discovery_stats(
            db=db,
            user_id=current_user.id
        )

        logger.info(f"✅ Dashboard Stats: {result['discovery_overview']['total_profiles_available']} total profiles")
        return result

    except Exception as e:
        logger.error(f"Discovery dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard failed: {str(e)}")


# Discovery System Information

@router.get("/categories")
async def get_available_categories(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get available content categories for filtering

    Returns list of all AI-detected content categories available in the system.
    Use this for populating filter dropdowns and category-based discovery.

    **Response includes**:
    - Category names from AI analysis
    - Profile counts per category
    - Popular categories ranked by usage
    - Category descriptions and examples

    **Use cases**:
    - Filter dropdown population
    - Category-based discovery navigation
    - Content strategy planning
    - Campaign targeting assistance
    """
    try:
        from sqlalchemy import select, func
        from app.database.unified_models import Profile

        # Get category statistics
        categories_query = select(
            Profile.ai_primary_content_type.label('category'),
            func.count(Profile.id).label('count')
        ).where(
            and_(
                Profile.followers_count > 0,
                Profile.ai_primary_content_type.isnot(None)
            )
        ).group_by(Profile.ai_primary_content_type).order_by(func.count(Profile.id).desc())

        result = await db.execute(categories_query)
        categories = [
            {
                "name": row.category,
                "count": row.count,
                "description": f"Profiles focused on {row.category.lower()} content"
            }
            for row in result.fetchall()
        ]

        return {
            "success": True,
            "categories": categories,
            "total_categories": len(categories),
            "message": f"Found {len(categories)} content categories"
        }

    except Exception as e:
        logger.error(f"Get categories failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/pricing")
async def get_discovery_pricing(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get discovery system pricing information

    Returns current pricing for discovery actions and credit requirements.
    Use this for displaying costs to users before they take actions.

    **Current Pricing**:
    - Profile Unlock: 25 credits (30-day access)
    - Bulk discounts: Available for large unlocks
    - Credit packages: Various denominations available

    **Use cases**:
    - Pricing display in UI
    - Credit calculation for bulk operations
    - User cost planning
    - Purchase recommendations
    """
    try:
        return {
            "success": True,
            "pricing": {
                "profile_unlock": {
                    "cost": 25,
                    "currency": "credits",
                    "duration": "30 days",
                    "description": "Full profile access including analytics, posts, and AI insights"
                },
                "bulk_discounts": {
                    "10_profiles": {"cost_per_profile": 25, "total_cost": 250},
                    "25_profiles": {"cost_per_profile": 23, "total_cost": 575, "savings": "8%"},
                    "50_profiles": {"cost_per_profile": 22, "total_cost": 1100, "savings": "12%"}
                }
            },
            "credit_packages": [
                {"amount": 1000, "price_usd": 50, "bonus": 0},
                {"amount": 2500, "price_usd": 125, "bonus": 100},
                {"amount": 10000, "price_usd": 500, "bonus": 500}
            ],
            "message": "Current discovery system pricing"
        }

    except Exception as e:
        logger.error(f"Get pricing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pricing: {str(e)}")


# Helper function to add dependencies
from sqlalchemy import and_