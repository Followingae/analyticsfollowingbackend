"""
AI/ML Content Analysis API Routes
Provides endpoints for AI-powered content intelligence features
"""
from fastapi import APIRouter, HTTPException, Depends, Path, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.services.ai.content_intelligence_service import content_intelligence_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ai/analyze/post/{post_id}")
async def analyze_post_content(
    post_id: str = Path(..., description="Post UUID"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze individual post content with AI
    
    Performs sentiment analysis, content categorization, and language detection
    """
    try:
        from app.database.unified_models import Post
        from sqlalchemy import select
        
        # Get post
        result = await db.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Check if user has access to this post's profile
        from app.database.comprehensive_service import comprehensive_service
        profile_access = await comprehensive_service.get_user_profile_access(
            db, current_user.id, post.profile.username
        )
        
        if not profile_access:
            raise HTTPException(
                status_code=403, 
                detail="You don't have access to analyze this post. Please search for the profile first."
            )
        
        # Perform AI analysis
        analysis_result = await content_intelligence_service.analyze_post_content(post)
        
        if "error" in analysis_result:
            raise HTTPException(status_code=500, detail=analysis_result["error"])
        
        # Update post with results
        success = await content_intelligence_service.update_post_ai_analysis(
            db, post_id, analysis_result
        )
        
        if not success:
            logger.warning(f"Failed to update post {post_id} with AI analysis")
        
        return JSONResponse(content={
            "success": True,
            "post_id": post_id,
            "analysis": analysis_result,
            "message": "Post content analyzed successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing post {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/ai/analyze/profile/{username}/content")
async def analyze_profile_content(
    background_tasks: BackgroundTasks,
    username: str = Path(..., description="Instagram username"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze all posts for a profile and generate AI insights
    
    This runs in the background and updates the profile's AI analytics
    """
    try:
        from app.database.unified_models import Profile
        from sqlalchemy import select
        
        # Get profile
        result = await db.execute(
            select(Profile).where(Profile.username == username.lower())
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Check user access
        from app.database.comprehensive_service import comprehensive_service
        profile_access = await comprehensive_service.get_user_profile_access(
            db, current_user.id, username
        )
        
        if not profile_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to analyze this profile. Please search for it first."
            )
        
        # Start background analysis
        background_tasks.add_task(
            content_intelligence_service.analyze_profile_content,
            db,
            str(profile.id)
        )
        
        return JSONResponse(content={
            "success": True,
            "profile_id": str(profile.id),
            "username": username,
            "message": "Profile content analysis started in background",
            "status": "processing"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting profile analysis for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")

@router.post("/ai/analyze/bulk")
async def bulk_analyze_content(
    background_tasks: BackgroundTasks,
    limit: int = Query(10, ge=1, le=50, description="Maximum profiles to analyze"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk analyze content for profiles that haven't been analyzed yet
    
    Only processes profiles that the user has access to
    """
    try:
        from app.database.unified_models import Profile, UserProfileAccess
        from sqlalchemy import select, and_
        
        # Get profiles user has access to that haven't been analyzed
        result = await db.execute(
            select(Profile)
            .join(UserProfileAccess, Profile.id == UserProfileAccess.profile_id)
            .where(
                and_(
                    UserProfileAccess.user_id == current_user.id,
                    Profile.ai_profile_analyzed_at.is_(None)
                )
            )
            .limit(limit)
        )
        profiles = result.scalars().all()
        
        if not profiles:
            return JSONResponse(content={
                "success": True,
                "message": "No profiles found that need AI analysis",
                "profiles_to_analyze": 0
            })
        
        # Start background analysis for each profile
        for profile in profiles:
            background_tasks.add_task(
                content_intelligence_service.analyze_profile_content,
                db,
                str(profile.id)
            )
        
        return JSONResponse(content={
            "success": True,
            "profiles_to_analyze": len(profiles),
            "profile_usernames": [p.username for p in profiles],
            "message": f"Bulk analysis started for {len(profiles)} profiles",
            "status": "processing"
        })
        
    except Exception as e:
        logger.error(f"Error in bulk content analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk analysis failed: {str(e)}")

@router.get("/ai/analysis/stats")
async def get_ai_analysis_stats(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI analysis statistics
    """
    try:
        stats = await content_intelligence_service.get_ai_analytics_stats(db)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return JSONResponse(content={
            "success": True,
            "ai_analysis_stats": stats
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI analysis stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.get("/ai/models/status")
async def get_ai_models_status(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get AI models status and information
    """
    try:
        # Initialize service if needed
        if not content_intelligence_service.initialized:
            await content_intelligence_service.initialize()
        
        models_info = {}
        if content_intelligence_service.models_manager:
            models_info = content_intelligence_service.models_manager.get_model_info()
        
        return JSONResponse(content={
            "success": True,
            "ai_service_initialized": content_intelligence_service.initialized,
            "models_info": models_info,
            "supported_features": {
                "sentiment_analysis": True,
                "language_detection": True,
                "content_categorization": True,
                "profile_insights": True
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting AI models status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get models status: {str(e)}")

@router.get("/ai/profile/{username}/insights")
async def get_profile_ai_insights(
    username: str = Path(..., description="Instagram username"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI insights for a specific profile
    """
    try:
        from app.database.unified_models import Profile
        from sqlalchemy import select
        
        # Check user access first
        from app.database.comprehensive_service import comprehensive_service
        profile_access = await comprehensive_service.get_user_profile_access(
            db, current_user.id, username
        )
        
        if not profile_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this profile's AI insights"
            )
        
        # Get profile with AI data
        result = await db.execute(
            select(Profile).where(Profile.username == username.lower())
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        ai_insights = {
            "username": profile.username,
            "ai_primary_content_type": profile.ai_primary_content_type,
            "ai_content_distribution": profile.ai_content_distribution,
            "ai_avg_sentiment_score": profile.ai_avg_sentiment_score,
            "ai_language_distribution": profile.ai_language_distribution,
            "ai_content_quality_score": profile.ai_content_quality_score,
            "ai_profile_analyzed_at": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
            "has_ai_analysis": profile.ai_profile_analyzed_at is not None
        }
        
        return JSONResponse(content={
            "success": True,
            "ai_insights": ai_insights
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI insights for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")

@router.delete("/ai/analysis/cache")
async def clear_ai_models_cache(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Clear AI models cache to free memory (admin function)
    """
    try:
        if content_intelligence_service.models_manager:
            content_intelligence_service.models_manager.clear_cache()
        
        return JSONResponse(content={
            "success": True,
            "message": "AI models cache cleared successfully"
        })
        
    except Exception as e:
        logger.error(f"Error clearing AI cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")