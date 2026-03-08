"""
Discovery API Routes - Credit-gated influencer discovery endpoints
Implements search, pagination, profile unlocking, and filter management
"""
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body
from fastapi.responses import JSONResponse
from sqlalchemy import text

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
from app.middleware.atomic_credit_gate import atomic_requires_credits
from app.core.job_queue import job_queue, JobPriority, QueueType
from app.api.fast_handoff_api import FastHandoffResponse
from app.database.optimized_pools import optimized_pools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discovery", tags=["Discovery"])


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
@atomic_requires_credits(
    action_type="discovery", 
    return_detailed_response=True
)
async def get_discovery_page(
    session_id: UUID = Path(..., description="Discovery session ID"),
    page_number: int = Path(..., ge=1, description="Page number to retrieve"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get a specific page of discovery results - Credit-gated pagination
    
    Credits: 1 credit per page (50 free pages per month)
    - Automatic free allowance handling by credit system
    - After 50 pages per month, charged 1 credit per page
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

@router.post("/unlock")
@atomic_requires_credits("profile_analysis", credits_required=25, check_unlock_status=True, return_detailed_response=True)
async def unlock_profile(
    unlock_request: ProfileUnlockRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Unlock a profile for detailed analysis (25 credits).

    Fast path (200): Profile already unlocked or profile is complete in DB.
    Async path (202): Profile needs full pipeline (Apify + CDN + AI) -- returns job_id.
    """
    user_id = UUID(str(current_user.id))
    profile_id = unlock_request.profile_id

    try:
        # ------------------------------------------------------------------
        # FAST PATH 1: Already unlocked -- no credits charged, instant return
        # ------------------------------------------------------------------
        async with optimized_pools.get_user_session() as session:
            completeness = await session.execute(text("""
                SELECT
                    p.id,
                    p.username,
                    p.followers_count,
                    p.posts_count,
                    p.ai_profile_analyzed_at,
                    p.blacklisted,
                    p.inactive,
                    (SELECT COUNT(*) FROM posts
                        WHERE profile_id = p.id
                        AND ai_content_category IS NOT NULL
                        AND ai_sentiment IS NOT NULL
                        AND ai_language_code IS NOT NULL) AS ai_posts_count,
                    (SELECT COUNT(*) FROM posts
                        WHERE profile_id = p.id
                        AND cdn_thumbnail_url IS NOT NULL) AS cdn_posts_count,
                    -- Check if already unlocked by this user
                    EXISTS(
                        SELECT 1 FROM user_profile_access upa
                        WHERE upa.user_id = :user_id AND upa.profile_id = p.id
                    ) AS already_unlocked,
                    -- Get user subscription tier
                    (SELECT subscription_tier FROM users WHERE id = :user_id) AS user_tier
                FROM profiles p
                WHERE p.id = :profile_id
            """).execution_options(prepare=False), {
                'profile_id': str(profile_id),
                'user_id': str(user_id)
            })
            profile_row = completeness.fetchone()

        if not profile_row:
            return ProfileUnlockApiResponse(
                success=False,
                error=DiscoveryErrorResponse(
                    error="profile_not_found",
                    message="Profile not found"
                )
            )

        if profile_row.blacklisted or profile_row.inactive:
            return ProfileUnlockApiResponse(
                success=False,
                error=DiscoveryErrorResponse(
                    error="profile_unavailable",
                    message="Profile is not available for unlock"
                )
            )

        username = profile_row.username or "unknown"
        user_tier = profile_row.user_tier or 'free'

        # If already unlocked, return immediately (no credits charged by decorator)
        if profile_row.already_unlocked:
            unlock_data = await discovery_service.unlock_profile(
                user_id=user_id,
                profile_id=profile_id,
                unlock_reason=unlock_request.unlock_reason
            )
            response_data = ProfileUnlockResponse(**unlock_data)
            return ProfileUnlockApiResponse(
                success=True,
                data=response_data,
                message="Profile was already unlocked"
            )

        # ------------------------------------------------------------------
        # FAST PATH 2: Profile is complete in DB -- unlock synchronously
        # Complete = followers > 0, posts > 0, 12+ AI-analyzed posts,
        #            ai_profile_analyzed_at set, 12+ CDN posts
        # ------------------------------------------------------------------
        is_complete = (
            profile_row.followers_count
            and profile_row.followers_count > 0
            and profile_row.posts_count
            and profile_row.posts_count > 0
            and profile_row.ai_posts_count >= 12
            and profile_row.cdn_posts_count >= 12
            and profile_row.ai_profile_analyzed_at is not None
        )

        if is_complete:
            # Profile is fully analyzed -- do synchronous unlock
            unlock_data = await discovery_service.unlock_profile(
                user_id=user_id,
                profile_id=profile_id,
                unlock_reason=unlock_request.unlock_reason
            )

            if "error" in unlock_data:
                return ProfileUnlockApiResponse(
                    success=False,
                    error=DiscoveryErrorResponse(**unlock_data)
                )

            response_data = ProfileUnlockResponse(**unlock_data)
            return ProfileUnlockApiResponse(
                success=True,
                data=response_data,
                message="Profile unlocked successfully"
            )

        # ------------------------------------------------------------------
        # ASYNC PATH: Profile is incomplete -- enqueue background job
        # ------------------------------------------------------------------
        logger.info(
            f"[DISCOVERY-UNLOCK] Profile @{username} incomplete "
            f"(ai_posts={profile_row.ai_posts_count}, cdn_posts={profile_row.cdn_posts_count}, "
            f"ai_analyzed={profile_row.ai_profile_analyzed_at is not None}). "
            f"Enqueueing async job for user {user_id}"
        )

        enqueue_result = await job_queue.enqueue_job(
            user_id=str(user_id),
            job_type='discovery_unlock',
            params={
                'profile_id': str(profile_id),
                'username': username,
                'unlock_reason': unlock_request.unlock_reason,
            },
            priority=JobPriority.HIGH,
            queue_type=QueueType.API_QUEUE,
            estimated_duration=30,
            user_tier=user_tier
        )

        if not enqueue_result.get('success'):
            error_type = enqueue_result.get('error', 'enqueue_failed')
            status_code = 429 if error_type == 'quota_exceeded' else 503
            return JSONResponse(
                status_code=status_code,
                content=FastHandoffResponse.error(
                    error_type,
                    enqueue_result.get('message', 'Failed to enqueue unlock job')
                )
            )

        return JSONResponse(
            status_code=202,
            content=FastHandoffResponse.success(
                job_id=enqueue_result['job_id'],
                estimated_completion_seconds=enqueue_result.get('estimated_completion_seconds', 30),
                queue_position=enqueue_result.get('queue_position', 0),
                message=f"Unlock started for @{username} -- profile requires full analysis"
            )
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
        logger.error(f"Error unlocking profile {profile_id} for user {user_id}: {e}")
        return ProfileUnlockApiResponse(
            success=False,
            error=DiscoveryErrorResponse(
                error="unlock_failed",
                message="Error unlocking profile"
            )
        )


@router.post("/unlock/bulk")
async def bulk_unlock_profiles(
    bulk_request: BulkProfileUnlockRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Unlock multiple profiles at once (async 202 pattern).

    Credits are validated upfront (25 per profile that isn't already unlocked).
    Processing happens in a background worker with concurrency control (3 at a time).
    Poll /api/v1/jobs/{job_id}/status for progress and /api/v1/jobs/{job_id}/result
    for the final BulkProfileUnlockResponse.
    """
    user_id = UUID(str(current_user.id))
    profile_ids = bulk_request.profile_ids

    try:
        # ------------------------------------------------------------------
        # Upfront validation: check which profiles exist, are available,
        # and which are already unlocked.  Calculate actual credit cost.
        # ------------------------------------------------------------------
        id_list = [str(pid) for pid in profile_ids]
        placeholders = ', '.join([f"'{pid}'" for pid in id_list])

        async with optimized_pools.get_user_session() as session:
            rows = await session.execute(text(f"""
                SELECT
                    p.id AS profile_id,
                    p.username,
                    p.blacklisted,
                    p.inactive,
                    EXISTS(
                        SELECT 1 FROM user_profile_access upa
                        WHERE upa.user_id = :user_id AND upa.profile_id = p.id
                    ) AS already_unlocked
                FROM profiles p
                WHERE p.id IN ({placeholders})
            """).execution_options(prepare=False), {'user_id': str(user_id)})
            profile_rows = rows.fetchall()

            # Get user credits and tier
            user_row = await session.execute(text("""
                SELECT credits, subscription_tier FROM users WHERE id = :user_id
            """).execution_options(prepare=False), {'user_id': str(user_id)})
            user_data = user_row.fetchone()

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        user_tier = user_data.subscription_tier or 'free'

        # Build lookup for quick access
        profile_lookup = {str(r.profile_id): r for r in profile_rows}

        # Determine which profiles actually need unlocking (not already unlocked,
        # not blacklisted/inactive, and actually exist)
        profiles_to_unlock = []
        already_unlocked_ids = []
        invalid_ids = []

        for pid in profile_ids:
            pid_str = str(pid)
            row = profile_lookup.get(pid_str)
            if not row:
                invalid_ids.append(pid_str)
            elif row.blacklisted or row.inactive:
                invalid_ids.append(pid_str)
            elif row.already_unlocked:
                already_unlocked_ids.append(pid_str)
            else:
                profiles_to_unlock.append({
                    'profile_id': pid_str,
                    'username': row.username or 'unknown'
                })

        # If nothing to unlock, return synchronously
        if not profiles_to_unlock:
            return BulkProfileUnlockResponse(
                total_requested=len(profile_ids),
                successful_unlocks=0,
                already_unlocked=len(already_unlocked_ids),
                failed_unlocks=len(invalid_ids),
                total_credits_spent=0,
                results=[
                    *[{"profile_id": UUID(pid), "success": True, "credits_spent": 0, "already_unlocked": True}
                      for pid in already_unlocked_ids],
                    *[{"profile_id": UUID(pid), "success": False, "credits_spent": 0,
                       "error_message": "Profile not found or unavailable"}
                      for pid in invalid_ids],
                ]
            )

        # Validate credits upfront: 25 per profile that needs unlocking
        total_credit_cost = len(profiles_to_unlock) * 25
        if user_data.credits < total_credit_cost:
            return JSONResponse(
                status_code=402,
                content=FastHandoffResponse.error(
                    "insufficient_credits",
                    f"Bulk unlock requires {total_credit_cost} credits "
                    f"({len(profiles_to_unlock)} profiles x 25), "
                    f"you have {user_data.credits}",
                    details={
                        "required": total_credit_cost,
                        "available": user_data.credits,
                        "profiles_to_unlock": len(profiles_to_unlock),
                        "already_unlocked": len(already_unlocked_ids),
                        "invalid": len(invalid_ids),
                    }
                )
            )

        # ------------------------------------------------------------------
        # Enqueue single bulk job
        # ------------------------------------------------------------------
        enqueue_result = await job_queue.enqueue_job(
            user_id=str(user_id),
            job_type='bulk_unlock',
            params={
                'profiles_to_unlock': profiles_to_unlock,
                'already_unlocked_ids': already_unlocked_ids,
                'invalid_ids': invalid_ids,
                'unlock_reason': bulk_request.unlock_reason,
                'total_credit_cost': total_credit_cost,
                'total_requested': len(profile_ids),
            },
            priority=JobPriority.BULK,
            queue_type=QueueType.BULK_QUEUE,
            estimated_duration=len(profiles_to_unlock) * 15,  # ~15s per profile
            user_tier=user_tier
        )

        if not enqueue_result.get('success'):
            error_type = enqueue_result.get('error', 'enqueue_failed')
            status_code = 429 if error_type == 'quota_exceeded' else 503
            return JSONResponse(
                status_code=status_code,
                content=FastHandoffResponse.error(
                    error_type,
                    enqueue_result.get('message', 'Failed to enqueue bulk unlock job')
                )
            )

        return JSONResponse(
            status_code=202,
            content=FastHandoffResponse.success(
                job_id=enqueue_result['job_id'],
                estimated_completion_seconds=enqueue_result.get('estimated_completion_seconds', len(profiles_to_unlock) * 15),
                queue_position=enqueue_result.get('queue_position', 0),
                message=(
                    f"Bulk unlock queued for {len(profiles_to_unlock)} profiles "
                    f"({len(already_unlocked_ids)} already unlocked, {len(invalid_ids)} invalid)"
                )
            )
        )

    except HTTPException:
        raise
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