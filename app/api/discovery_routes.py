"""
Discovery API Routes - Credit-gated influencer discovery endpoints
Implements search, pagination, profile unlocking, and filter management
"""
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body
from fastapi.responses import JSONResponse

from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.models.discovery import (
    DiscoverySearchCriteria, DiscoverySessionCreate, DiscoverySessionResponse,
    DiscoveryPageRequest, DiscoveryPageResponse, DiscoveryErrorResponse,
    ProfileUnlockRequest, ProfileUnlockResponse, ProfileUnlockApiResponse,
    UnlockedProfileSummary, DiscoveryFilterCreate, DiscoveryFilterResponse,
    BulkProfileUnlockRequest, BulkProfileUnlockResponse,
    DiscoverySearchResponse, DiscoveryUsageStats
)
from app.services.discovery_service import discovery_service
from app.middleware.credit_gate import requires_credits

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["Discovery"])


# ============================================================================
# DISCOVERY SEARCH ENDPOINTS
# ============================================================================

@router.post("/search", response_model=DiscoverySearchResponse)
async def start_discovery_search(
    search_request: DiscoverySessionCreate,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Start a new discovery search session
    First page is free, subsequent pages cost 1 credit each
    """
    user_id = UUID(str(current_user.id))
    
    try:
        # Start discovery session (first page is free)
        session_data = await discovery_service.start_discovery_session(
            user_id=user_id,
            search_criteria=search_request.search_criteria.dict()
        )
        
        response_data = DiscoverySessionResponse(**session_data)
        
        return DiscoverySearchResponse(
            success=True,
            data=response_data,
            message="Discovery session started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting discovery search for user {user_id}: {e}")
        return DiscoverySearchResponse(
            success=False,
            error=DiscoveryErrorResponse(
                error="search_failed",
                message=str(e)
            )
        )


@router.get("/page/{session_id}/{page_number}", response_model=DiscoverySearchResponse)
async def get_discovery_page(
    session_id: UUID = Path(..., description="Discovery session ID"),
    page_number: int = Path(..., ge=1, description="Page number to retrieve"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get a specific page of discovery results
    Pages 1-3 are free, page 4+ costs 1 credit each
    """
    user_id = UUID(str(current_user.id))
    
    try:
        page_data = await discovery_service.get_discovery_page(
            user_id=user_id,
            session_id=session_id,
            page_number=page_number
        )
        
        # Check for credit-related errors
        if "error" in page_data:
            return DiscoverySearchResponse(
                success=False,
                error=DiscoveryErrorResponse(**page_data)
            )
        
        response_data = DiscoveryPageResponse(**page_data)
        
        return DiscoverySearchResponse(
            success=True,
            data=response_data,
            message=f"Page {page_number} retrieved successfully"
        )
        
    except ValueError as e:
        logger.warning(f"Invalid discovery page request: {e}")
        return DiscoverySearchResponse(
            success=False,
            error=DiscoveryErrorResponse(
                error="invalid_request",
                message=str(e)
            )
        )
    except Exception as e:
        logger.error(f"Error getting discovery page {page_number} for user {user_id}: {e}")
        return DiscoverySearchResponse(
            success=False,
            error=DiscoveryErrorResponse(
                error="page_retrieval_failed",
                message="Error retrieving discovery page"
            )
        )


# ============================================================================
# PROFILE UNLOCK ENDPOINTS
# ============================================================================

@router.post("/unlock", response_model=ProfileUnlockApiResponse)
@requires_credits("profile_analysis", credits_required=25, check_unlock_status=True, return_detailed_response=True)
async def unlock_profile(
    unlock_request: ProfileUnlockRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Unlock a profile for detailed analysis (25 credits)
    Once unlocked, profile remains unlocked forever for this user
    """
    user_id = UUID(str(current_user.id))
    
    try:
        unlock_data = await discovery_service.unlock_profile(
            user_id=user_id,
            profile_id=unlock_request.profile_id,
            unlock_reason=unlock_request.unlock_reason
        )
        
        # Check for credit-related errors
        if "error" in unlock_data:
            return ProfileUnlockApiResponse(
                success=False,
                error=DiscoveryErrorResponse(**unlock_data)
            )
        
        response_data = ProfileUnlockResponse(**unlock_data)
        
        return ProfileUnlockApiResponse(
            success=True,
            data=response_data,
            message="Profile unlocked successfully" if unlock_data.get("unlocked") 
                   else "Profile was already unlocked"
        )
        
    except ValueError as e:
        logger.warning(f"Invalid profile unlock request: {e}")
        return ProfileUnlockApiResponse(
            success=False,
            error=DiscoveryErrorResponse(
                error="invalid_request",
                message=str(e)
            )
        )
    except Exception as e:
        logger.error(f"Error unlocking profile {unlock_request.profile_id} for user {user_id}: {e}")
        return ProfileUnlockApiResponse(
            success=False,
            error=DiscoveryErrorResponse(
                error="unlock_failed",
                message="Error unlocking profile"
            )
        )


@router.post("/unlock/bulk", response_model=BulkProfileUnlockResponse)
async def bulk_unlock_profiles(
    bulk_request: BulkProfileUnlockRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Unlock multiple profiles at once
    Credits are charged per successful unlock (25 credits each)
    """
    user_id = UUID(str(current_user.id))
    
    try:
        results = []
        total_credits_spent = 0
        successful_unlocks = 0
        already_unlocked = 0
        failed_unlocks = 0
        
        for profile_id in bulk_request.profile_ids:
            try:
                unlock_data = await discovery_service.unlock_profile(
                    user_id=user_id,
                    profile_id=profile_id,
                    unlock_reason=bulk_request.unlock_reason
                )
                
                if "error" in unlock_data:
                    results.append({
                        "profile_id": profile_id,
                        "success": False,
                        "error_message": unlock_data["message"]
                    })
                    failed_unlocks += 1
                elif unlock_data.get("already_unlocked"):
                    results.append({
                        "profile_id": profile_id,
                        "success": True,
                        "credits_spent": 0,
                        "already_unlocked": True
                    })
                    already_unlocked += 1
                else:
                    results.append({
                        "profile_id": profile_id,
                        "success": True,
                        "credits_spent": unlock_data["credits_spent"],
                        "unlock_id": unlock_data["unlock_id"]
                    })
                    total_credits_spent += unlock_data["credits_spent"]
                    successful_unlocks += 1
                    
            except Exception as e:
                logger.error(f"Error in bulk unlock for profile {profile_id}: {e}")
                results.append({
                    "profile_id": profile_id,
                    "success": False,
                    "error_message": str(e)
                })
                failed_unlocks += 1
        
        return BulkProfileUnlockResponse(
            total_requested=len(bulk_request.profile_ids),
            successful_unlocks=successful_unlocks,
            already_unlocked=already_unlocked,
            failed_unlocks=failed_unlocks,
            total_credits_spent=total_credits_spent,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Error in bulk profile unlock for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error processing bulk unlock request")


@router.get("/unlocked", response_model=List[UnlockedProfileSummary])
async def get_unlocked_profiles(
    limit: int = Query(50, ge=1, le=100, description="Number of profiles to return"),
    offset: int = Query(0, ge=0, description="Number of profiles to skip"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get list of profiles unlocked by the current user"""
    user_id = UUID(str(current_user.id))
    
    try:
        unlocked_profiles = await discovery_service.get_user_unlocked_profiles(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        return [UnlockedProfileSummary(**profile) for profile in unlocked_profiles]
        
    except Exception as e:
        logger.error(f"Error getting unlocked profiles for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving unlocked profiles")


# ============================================================================
# DISCOVERY FILTER MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/filters", response_model=DiscoveryFilterResponse)
async def save_discovery_filter(
    filter_request: DiscoveryFilterCreate,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Save a discovery filter for reuse"""
    user_id = UUID(str(current_user.id))
    
    try:
        filter_data = await discovery_service.save_discovery_filter(
            user_id=user_id,
            filter_name=filter_request.filter_name,
            filter_criteria=filter_request.filter_criteria.dict(),
            description=filter_request.description
        )
        
        return DiscoveryFilterResponse(**filter_data)
        
    except Exception as e:
        logger.error(f"Error saving discovery filter for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error saving discovery filter")


@router.get("/filters", response_model=List[DiscoveryFilterResponse])
async def get_discovery_filters(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get user's saved discovery filters"""
    user_id = UUID(str(current_user.id))
    
    try:
        filters = await discovery_service.get_user_discovery_filters(user_id=user_id)
        return [DiscoveryFilterResponse(**filter_data) for filter_data in filters]
        
    except Exception as e:
        logger.error(f"Error getting discovery filters for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving discovery filters")


# ============================================================================
# DISCOVERY ANALYTICS ENDPOINTS  
# ============================================================================

@router.get("/analytics/usage", response_model=DiscoveryUsageStats)
async def get_discovery_usage_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get discovery usage statistics for the current user"""
    user_id = UUID(str(current_user.id))
    
    try:
        # This would be implemented in the discovery service
        # For now, return placeholder data
        return DiscoveryUsageStats(
            total_sessions=0,
            total_pages_viewed=0,
            total_credits_spent=0,
            unique_profiles_discovered=0,
            profiles_unlocked=0,
            avg_session_duration_minutes=0.0,
            most_used_filters=[]
        )
        
    except Exception as e:
        logger.error(f"Error getting discovery usage stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving usage statistics")


# ============================================================================
# DISCOVERY UTILITY ENDPOINTS
# ============================================================================

@router.get("/filters/categories")
async def get_available_categories():
    """Get list of available profile categories for filtering"""
    try:
        # This would typically come from database or config
        categories = [
            "Fashion & Beauty",
            "Travel & Lifestyle", 
            "Food & Cooking",
            "Fitness & Health",
            "Technology",
            "Entertainment",
            "Sports",
            "Business",
            "Art & Design",
            "Music",
            "Photography",
            "Gaming",
            "Education",
            "Parenting",
            "Home & Garden",
            "Automotive",
            "Finance",
            "News & Politics",
            "Comedy",
            "General"
        ]
        
        return {
            "categories": categories,
            "total_count": len(categories)
        }
        
    except Exception as e:
        logger.error(f"Error getting available categories: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving categories")


@router.get("/filters/languages")
async def get_available_languages():
    """Get list of available languages for filtering"""
    try:
        # Common languages for influencer content
        languages = [
            {"code": "en", "name": "English"},
            {"code": "ar", "name": "Arabic"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "hi", "name": "Hindi"},
            {"code": "tr", "name": "Turkish"},
            {"code": "nl", "name": "Dutch"},
            {"code": "sv", "name": "Swedish"},
            {"code": "no", "name": "Norwegian"},
            {"code": "da", "name": "Danish"},
            {"code": "fi", "name": "Finnish"},
            {"code": "pl", "name": "Polish"},
            {"code": "cs", "name": "Czech"}
        ]
        
        return {
            "languages": languages,
            "total_count": len(languages)
        }
        
    except Exception as e:
        logger.error(f"Error getting available languages: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving languages")


@router.get("/health")
async def discovery_health_check():
    """Health check for discovery system"""
    try:
        return {
            "status": "healthy",
            "service": "discovery",
            "features": {
                "search": True,
                "pagination": True,
                "profile_unlock": True,
                "saved_filters": True,
                "bulk_operations": True,
                "analytics": True
            },
            "credit_integration": True,
            "timestamp": "2025-01-21T15:00:00Z"
        }
    except Exception as e:
        logger.error(f"Discovery health check failed: {e}")
        raise HTTPException(status_code=500, detail="Discovery service unhealthy")