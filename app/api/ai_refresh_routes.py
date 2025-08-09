"""
AI Data Refresh API Routes
Endpoints for managing AI data refresh operations
"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import Optional, Dict, Any
import logging

from app.services.ai_refresh_service import ai_refresh_service
# AI refresh is now manual-only, no automatic scheduler
from app.middleware.auth_middleware import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/refresh", tags=["AI Data Refresh"])


@router.get("/status")
async def get_ai_refresh_status():
    """Get current AI data refresh status and statistics (manual refresh only)"""
    try:
        stats = await ai_refresh_service.get_ai_refresh_statistics()
        return {
            "success": True,
            "data": {
                "refresh_mode": "manual_only",
                "automatic_scheduler": "disabled",
                "statistics": stats
            }
        }
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Error getting status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get refresh status: {str(e)}")


@router.get("/statistics")
async def get_ai_refresh_statistics():
    """Get detailed statistics on AI data completeness (missing data only)"""
    try:
        stats = await ai_refresh_service.get_ai_refresh_statistics()
        
        # Calculate completion percentages
        profile_completion_rate = (
            (stats['total_profiles'] - stats['profiles_missing_ai']) / stats['total_profiles'] * 100
        ) if stats['total_profiles'] > 0 else 100
        
        post_completion_rate = (
            (stats['total_posts'] - stats['posts_missing_ai']) / stats['total_posts'] * 100
        ) if stats['total_posts'] > 0 else 100
        
        return {
            "success": True,
            "data": {
                **stats,
                "profile_completion_rate": round(profile_completion_rate, 2),
                "post_completion_rate": round(post_completion_rate, 2),
                "refresh_mode": "manual_only"
            }
        }
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/trigger")
async def trigger_manual_refresh(
    batch_size: int = Query(5, ge=1, le=50, description="Number of profiles to refresh in this batch"),
    current_user = Depends(get_optional_user)
):
    """Manually trigger AI data refresh for profiles with missing data"""
    try:
        logger.info(f"AI_REFRESH_API: Manual refresh triggered by user {getattr(current_user, 'email', 'anonymous')} (batch_size={batch_size})")
        
        result = await ai_refresh_service.run_batch_ai_refresh(batch_size=batch_size)
        
        return {
            "success": True,
            "data": result,
            "message": f"Manual refresh complete - {result['successful']}/{result['attempted']} profiles refreshed"
        }
            
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Error triggering manual refresh: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger refresh: {str(e)}")


@router.post("/profile/{username}")
async def refresh_profile_ai_data(
    username: str = Path(..., description="Instagram username to refresh"),
    current_user = Depends(get_optional_user)
):
    """Refresh AI data for a specific profile"""
    try:
        logger.info(f"AI_REFRESH_API: Profile refresh requested for '{username}' by user {getattr(current_user, 'email', 'anonymous')}")
        
        from app.database.connection import SessionLocal
        from app.database.unified_models import Profile
        from sqlalchemy import select
        
        async with SessionLocal() as db:
            # Find profile by username
            result = await db.execute(
                select(Profile).where(Profile.username.ilike(username))
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                raise HTTPException(status_code=404, detail=f"Profile '{username}' not found")
            
            # Check if refresh is needed
            completeness = await ai_refresh_service.check_profile_ai_completeness(profile)
            
            if completeness['profile_ai_complete'] and not completeness['profile_ai_missing']:
                return {
                    "success": True,
                    "data": {
                        "username": username,
                        "refresh_performed": False,
                        "refresh_needed": False
                    },
                    "message": f"Profile '{username}' AI data is already complete"
                }
            
            # Perform refresh
            success = await ai_refresh_service.refresh_profile_ai_data(profile)
            
            if success:
                return {
                    "success": True,
                    "data": {
                        "username": username,
                        "refresh_performed": True,
                        "refresh_needed": True
                    },
                    "message": f"Successfully refreshed AI data for profile '{username}'"
                }
            else:
                raise HTTPException(status_code=500, detail=f"Failed to refresh AI data for profile '{username}'")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Error refreshing profile '{username}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh profile: {str(e)}")


@router.get("/profiles/incomplete")
async def get_profiles_needing_refresh(
    limit: int = Query(20, ge=1, le=100, description="Number of profiles to return"),
    current_user = Depends(get_optional_user)
):
    """Get list of profiles that need AI data refresh"""
    try:
        profiles = await ai_refresh_service.find_profiles_needing_ai_refresh(limit=limit)
        
        profile_data = []
        for profile in profiles:
            # Check completeness status
            completeness = await ai_refresh_service.check_profile_ai_completeness(profile)
            
            profile_data.append({
                "id": str(profile.id),
                "username": profile.username,
                "full_name": profile.full_name,
                "followers_count": profile.followers_count,
                "ai_status": {
                    "ai_complete": completeness['profile_ai_complete'],
                    "ai_missing": completeness['profile_ai_missing'],
                    "last_analyzed": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
                    "primary_content_type": profile.ai_primary_content_type
                }
            })
        
        return {
            "success": True,
            "data": {
                "profiles": profile_data,
                "count": len(profile_data),
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Error getting incomplete profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profiles: {str(e)}")


@router.get("/posts/incomplete")
async def get_posts_needing_refresh(
    profile_id: Optional[str] = Query(None, description="Filter by specific profile ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of posts to return"),
    current_user = Depends(get_optional_user)
):
    """Get list of posts that need AI data refresh"""
    try:
        posts = await ai_refresh_service.find_posts_needing_ai_refresh(
            profile_id=profile_id,
            limit=limit
        )
        
        post_data = []
        for post in posts:
            # Check completeness status
            completeness = await ai_refresh_service.check_post_ai_completeness(post)
            
            post_data.append({
                "id": str(post.id),
                "profile_id": str(post.profile_id),
                "caption": (post.caption[:100] + "...") if post.caption and len(post.caption) > 100 else post.caption,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "ai_status": {
                    "ai_complete": completeness['post_ai_complete'],
                    "ai_missing": completeness['post_ai_missing'],
                    "last_analyzed": post.ai_analyzed_at.isoformat() if post.ai_analyzed_at else None,
                    "content_category": post.ai_content_category,
                    "sentiment": post.ai_sentiment,
                    "language": post.ai_language_code
                }
            })
        
        return {
            "success": True,
            "data": {
                "posts": post_data,
                "count": len(post_data),
                "limit": limit,
                "filtered_by_profile": profile_id
            }
        }
        
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Error getting incomplete posts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get posts: {str(e)}")


# Automatic scheduler removed - using manual refresh only


@router.get("/health")
async def ai_refresh_health_check():
    """Health check endpoint for AI refresh system (manual refresh only)"""
    try:
        stats = await ai_refresh_service.get_ai_refresh_statistics()
        
        return {
            "success": True,
            "data": {
                "service_status": "healthy",
                "refresh_mode": "manual_only",
                "automatic_scheduler": "disabled",
                "profiles_missing_ai": stats['profiles_missing_ai'],
                "posts_missing_ai": stats['posts_missing_ai'],
                "total_profiles": stats['total_profiles'],
                "total_posts": stats['total_posts']
            },
            "message": "AI refresh system is operational (manual refresh only)"
        }
    except Exception as e:
        logger.error(f"AI_REFRESH_API: Health check failed: {e}")
        return {
            "success": False,
            "data": {
                "service_status": "unhealthy",
                "error": str(e)
            },
            "message": "AI refresh system has issues"
        }