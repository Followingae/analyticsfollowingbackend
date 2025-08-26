"""
Engagement Calculation API Routes
"""
from fastapi import APIRouter, HTTPException, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.services.engagement_calculator import engagement_calculator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/engagement/calculate/profile/{username}")
async def calculate_profile_engagement(
    username: str = Path(..., description="Instagram username"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate and update engagement rate for a specific profile
    """
    try:
        # Get profile by username
        from app.database.unified_models import Profile
        from sqlalchemy import select
        
        result = await db.execute(
            select(Profile).where(Profile.username == username.lower())
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Calculate engagement
        engagement_metrics = await engagement_calculator.calculate_and_update_profile_engagement(
            db, str(profile.id)
        )
        
        if 'error' in engagement_metrics:
            raise HTTPException(status_code=500, detail=engagement_metrics['error'])
        
        # Calculate influence score
        influence_score = engagement_calculator.calculate_influence_score(
            followers_count=profile.followers_count or 0,
            following_count=profile.following_count or 0,
            engagement_rate=engagement_metrics.get('overall_engagement_rate', 0),
            is_verified=profile.is_verified or False,
            is_business=profile.is_business_account or False,
            posts_count=profile.posts_count or 0
        )
        
        # Update influence score
        profile.influence_score = influence_score
        await db.commit()
        
        return {
            "success": True,
            "username": username,
            "engagement_metrics": engagement_metrics,
            "influence_score": influence_score,
            "message": "Engagement rate calculated and updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating engagement for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate engagement: {str(e)}")

@router.post("/engagement/calculate/bulk")
async def bulk_calculate_engagement(
    limit: int = Query(10, ge=1, le=100, description="Maximum profiles to update"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk calculate engagement rates for profiles with missing calculations
    """
    try:
        results = await engagement_calculator.bulk_update_profile_engagement_rates(
            db, limit=limit
        )
        
        return {
            "success": True,
            "bulk_update_results": results,
            "message": f"Processed {results.get('total_profiles_processed', 0)} profiles"
        }
        
    except Exception as e:
        logger.error(f"Error in bulk engagement calculation: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk calculation failed: {str(e)}")

@router.post("/engagement/calculate/post/{post_id}")
async def calculate_post_engagement(
    post_id: str = Path(..., description="Post UUID"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate and update engagement rate for a specific post
    """
    try:
        engagement_rate = await engagement_calculator.calculate_and_update_post_engagement(
            db, post_id
        )
        
        return {
            "success": True,
            "post_id": post_id,
            "engagement_rate": engagement_rate,
            "message": "Post engagement rate calculated and updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error calculating post engagement for {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate post engagement: {str(e)}")

@router.get("/engagement/stats")
async def get_engagement_stats(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get engagement calculation statistics
    """
    try:
        from app.database.unified_models import Profile, Post
        from sqlalchemy import select, func, and_
        
        # Profile stats
        profile_stats = await db.execute(
            select(
                func.count(Profile.id).label('total_profiles'),
                func.count(Profile.id).filter(Profile.engagement_rate > 0).label('profiles_with_engagement'),
                func.avg(Profile.engagement_rate).filter(Profile.engagement_rate > 0).label('avg_engagement'),
                func.max(Profile.engagement_rate).label('max_engagement'),
                func.count(Profile.id).filter(Profile.influence_score > 0).label('profiles_with_influence')
            )
        )
        
        profile_row = profile_stats.first()
        
        # Post stats
        post_stats = await db.execute(
            select(
                func.count(Post.id).label('total_posts'),
                func.count(Post.id).filter(Post.engagement_rate > 0).label('posts_with_engagement'),
                func.avg(Post.engagement_rate).filter(Post.engagement_rate > 0).label('avg_post_engagement')
            )
        )
        
        post_row = post_stats.first()
        
        return {
            "success": True,
            "stats": {
                "profiles": {
                    "total": profile_row.total_profiles or 0,
                    "with_engagement_calculated": profile_row.profiles_with_engagement or 0,
                    "avg_engagement_rate": round(float(profile_row.avg_engagement or 0), 2),
                    "max_engagement_rate": round(float(profile_row.max_engagement or 0), 2),
                    "with_influence_score": profile_row.profiles_with_influence or 0
                },
                "posts": {
                    "total": post_row.total_posts or 0,
                    "with_engagement_calculated": post_row.posts_with_engagement or 0,
                    "avg_engagement_rate": round(float(post_row.avg_post_engagement or 0), 2)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting engagement stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")