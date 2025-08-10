"""
AI Fix Routes - Simple, robust AI analysis and repair endpoints
Consolidates all AI functionality into easy-to-use repair endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import logging
from datetime import datetime

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.database.unified_models import Profile, Post
from app.services.ai.content_intelligence_service import content_intelligence_service
from app.database.comprehensive_service import comprehensive_service
from sqlalchemy import select, update, and_, or_, func

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ai/fix/profile/{username}")
async def fix_profile_ai_analysis(
    username: str = Path(..., description="Username to fix"),
    force: bool = Query(False, description="Force re-analysis even if data exists"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fix/complete AI analysis for a profile
    This endpoint handles everything: missing posts analysis, profile aggregation, etc.
    """
    try:
        # Get profile
        profile = await comprehensive_service.get_profile_by_username(db, username)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Check user access
        user_access = await comprehensive_service.get_user_profile_access(db, current_user.id, username)
        if not user_access:
            raise HTTPException(status_code=403, detail="Access denied to this profile")
        
        # Initialize AI service
        await content_intelligence_service.initialize()
        
        # Get posts that need analysis
        query = select(Post).where(Post.profile_id == profile.id)
        if not force:
            query = query.where(Post.ai_analyzed_at.is_(None))
        
        posts_result = await db.execute(query)
        posts_to_analyze = posts_result.scalars().all()
        
        results = {
            "profile_id": str(profile.id),
            "username": username,
            "posts_analyzed": 0,
            "posts_skipped": 0,
            "profile_insights_generated": False,
            "errors": []
        }
        
        # Analyze posts
        category_counts = {}
        sentiment_scores = []
        language_counts = {}
        
        for post in posts_to_analyze:
            try:
                analysis = await content_intelligence_service.analyze_post_content(post)
                
                if analysis and not analysis.get("error"):
                    # Update post
                    await db.execute(
                        update(Post)
                        .where(Post.id == post.id)
                        .values(
                            ai_content_category=analysis.get("ai_content_category"),
                            ai_category_confidence=analysis.get("ai_category_confidence", 0.0),
                            ai_sentiment=analysis.get("ai_sentiment"),
                            ai_sentiment_score=analysis.get("ai_sentiment_score", 0.0),
                            ai_sentiment_confidence=analysis.get("ai_sentiment_confidence", 0.0),
                            ai_language_code=analysis.get("ai_language_code"),
                            ai_language_confidence=analysis.get("ai_language_confidence", 0.0),
                            ai_analysis_raw=analysis,
                            ai_analyzed_at=datetime.now(),
                            ai_analysis_version="1.0.0"
                        )
                    )
                    
                    results["posts_analyzed"] += 1
                    
                    # Collect aggregation data
                    if analysis.get("ai_content_category"):
                        cat = analysis["ai_content_category"]
                        category_counts[cat] = category_counts.get(cat, 0) + 1
                    
                    if analysis.get("ai_sentiment_score") is not None:
                        sentiment_scores.append(analysis["ai_sentiment_score"])
                    
                    if analysis.get("ai_language_code"):
                        lang = analysis["ai_language_code"]
                        language_counts[lang] = language_counts.get(lang, 0) + 1
                else:
                    results["posts_skipped"] += 1
                    if analysis and analysis.get("error"):
                        results["errors"].append(f"Post {post.id}: {analysis['error']}")
                        
            except Exception as e:
                results["errors"].append(f"Post {post.id}: {str(e)}")
                results["posts_skipped"] += 1
        
        # Update profile aggregation if we have data
        if results["posts_analyzed"] > 0 or force:
            try:
                # Get all analyzed posts for aggregation
                all_analyzed = await db.execute(
                    select(Post).where(
                        and_(
                            Post.profile_id == profile.id,
                            Post.ai_analyzed_at.isnot(None)
                        )
                    )
                )
                all_posts = all_analyzed.scalars().all()
                
                if all_posts:
                    # Recalculate aggregation from all analyzed posts
                    agg_categories = {}
                    agg_sentiments = []
                    agg_languages = {}
                    
                    for post in all_posts:
                        if post.ai_content_category:
                            agg_categories[post.ai_content_category] = agg_categories.get(post.ai_content_category, 0) + 1
                        if post.ai_sentiment_score is not None:
                            agg_sentiments.append(post.ai_sentiment_score)
                        if post.ai_language_code:
                            agg_languages[post.ai_language_code] = agg_languages.get(post.ai_language_code, 0) + 1
                    
                    # Calculate insights
                    primary_content = max(agg_categories, key=agg_categories.get) if agg_categories else None
                    avg_sentiment = sum(agg_sentiments) / len(agg_sentiments) if agg_sentiments else 0.0
                    total_analyzed = len(all_posts)
                    
                    content_dist = {k: round(v/total_analyzed, 3) for k, v in agg_categories.items()}
                    lang_dist = {k: round(v/total_analyzed, 3) for k, v in agg_languages.items()}
                    quality_score = min(1.0, total_analyzed / 20.0)
                    
                    # Update profile
                    await db.execute(
                        update(Profile)
                        .where(Profile.id == profile.id)
                        .values(
                            ai_primary_content_type=primary_content,
                            ai_content_distribution=content_dist,
                            ai_avg_sentiment_score=round(avg_sentiment, 3),
                            ai_language_distribution=lang_dist,
                            ai_content_quality_score=quality_score,
                            ai_profile_analyzed_at=datetime.now()
                        )
                    )
                    
                    results["profile_insights_generated"] = True
                    results["profile_insights"] = {
                        "primary_content_type": primary_content,
                        "avg_sentiment": round(avg_sentiment, 3),
                        "total_posts_analyzed": total_analyzed,
                        "quality_score": quality_score
                    }
                    
            except Exception as e:
                results["errors"].append(f"Profile aggregation error: {str(e)}")
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"AI analysis completed for {username}",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error fixing AI analysis for {username}: {e}")
        try:
            await db.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"AI fix failed: {str(e)}")

@router.get("/ai/status/profile/{username}")
async def get_profile_ai_status(
    username: str = Path(..., description="Username to check"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed AI analysis status for a profile"""
    try:
        profile = await comprehensive_service.get_profile_by_username(db, username)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Check access
        user_access = await comprehensive_service.get_user_profile_access(db, current_user.id, username)
        if not user_access:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get post analysis stats
        total_posts = await db.execute(
            select(func.count(Post.id)).where(Post.profile_id == profile.id)
        )
        
        analyzed_posts = await db.execute(
            select(func.count(Post.id)).where(
                and_(
                    Post.profile_id == profile.id,
                    Post.ai_analyzed_at.isnot(None)
                )
            )
        )
        
        total_count = total_posts.scalar()
        analyzed_count = analyzed_posts.scalar()
        
        return {
            "profile_id": str(profile.id),
            "username": username,
            "profile_ai_complete": profile.ai_profile_analyzed_at is not None,
            "profile_analyzed_at": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
            "posts": {
                "total": total_count,
                "analyzed": analyzed_count,
                "completion_percentage": round((analyzed_count / max(1, total_count)) * 100, 1)
            },
            "profile_insights": {
                "primary_content_type": profile.ai_primary_content_type,
                "avg_sentiment_score": profile.ai_avg_sentiment_score,
                "content_quality_score": profile.ai_content_quality_score,
                "has_content_distribution": profile.ai_content_distribution is not None,
                "has_language_distribution": profile.ai_language_distribution is not None
            },
            "needs_repair": (
                profile.ai_profile_analyzed_at is None or
                analyzed_count < total_count or
                profile.ai_primary_content_type is None
            )
        }
        
    except Exception as e:
        logger.error(f"Error getting AI status for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/ai/fix/batch")
async def fix_profiles_batch(
    limit: int = Query(10, description="Number of profiles to fix", le=50),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Find and fix profiles that need AI analysis
    This is the ultimate repair endpoint - finds problems and fixes them
    """
    try:
        # Find profiles that need fixing
        profiles_needing_fix = await db.execute(
            select(Profile).where(
                or_(
                    Profile.ai_profile_analyzed_at.is_(None),
                    Profile.ai_primary_content_type.is_(None),
                    Profile.ai_content_distribution.is_(None)
                )
            ).limit(limit)
        )
        
        profiles = profiles_needing_fix.scalars().all()
        
        results = {
            "profiles_processed": 0,
            "profiles_fixed": 0,
            "profiles_failed": 0,
            "details": []
        }
        
        for profile in profiles:
            try:
                # Check if user has access to this profile
                user_access = await comprehensive_service.get_user_profile_access(db, current_user.id, profile.username)
                if not user_access:
                    continue
                
                results["profiles_processed"] += 1
                
                # Use the same fix logic as single profile
                fix_result = await fix_profile_ai_analysis(profile.username, False, current_user, db)
                
                if fix_result.get("success"):
                    results["profiles_fixed"] += 1
                    results["details"].append({
                        "username": profile.username,
                        "status": "fixed",
                        "posts_analyzed": fix_result.get("results", {}).get("posts_analyzed", 0)
                    })
                else:
                    results["profiles_failed"] += 1
                    results["details"].append({
                        "username": profile.username,
                        "status": "failed",
                        "error": "Fix operation failed"
                    })
                    
            except Exception as e:
                results["profiles_failed"] += 1
                results["details"].append({
                    "username": profile.username,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "success": True,
            "message": f"Batch repair completed: {results['profiles_fixed']}/{results['profiles_processed']} profiles fixed",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in batch AI fix: {e}")
        raise HTTPException(status_code=500, detail=f"Batch fix failed: {str(e)}")