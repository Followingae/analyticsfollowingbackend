"""
DIRECT AI ANALYSIS ROUTES - No Celery Dependencies
Provides immediate AI analysis execution with full visibility and logging
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Path, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import logging
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.config import settings
from app.models.auth import UserInDB
from app.database.connection import get_db
from app.database.comprehensive_service import comprehensive_service
from app.middleware.auth_middleware import get_current_user as get_current_active_user

# Import the bulletproof AI system directly
from app.services.ai.bulletproof_content_intelligence import bulletproof_content_intelligence
from app.database.unified_models import Profile, Post

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ai/analyze/direct/{username}")
async def run_direct_ai_analysis(
    username: str = Path(..., description="Instagram username"),
    force_reanalyze: bool = Query(False, description="Re-analyze already processed posts"),
    batch_size: int = Query(10, ge=1, le=50, description="Number of posts to analyze in each batch"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    DIRECT AI ANALYSIS - Runs immediately with full visibility
    No Celery, no background tasks, no mocks - real AI analysis right now
    """
    analysis_start_time = datetime.now(timezone.utc)
    
    try:
        logger.info(f"[START] DIRECT AI ANALYSIS STARTING for {username}")
        
        # Step 1: Get profile from database
        profile = await comprehensive_service.get_profile_by_username(db, username)
        if not profile:
            raise HTTPException(
                status_code=404, 
                detail=f"Profile {username} not found in database. Please fetch the profile first."
            )
        
        logger.info(f"✓ Profile found: {profile.username} (ID: {profile.id})")
        
        # Step 2: Initialize AI service
        logger.info("[AI_INIT] Initializing AI components...")
        if not bulletproof_content_intelligence.initialized:
            init_success = await bulletproof_content_intelligence.initialize()
            if not init_success:
                raise HTTPException(
                    status_code=500,
                    detail="AI service initialization failed. Check server logs for details."
                )
        
        ai_health = bulletproof_content_intelligence.get_system_health()
        logger.info(f"✓ AI System Status: {ai_health.get('overall_status', 'unknown')}")
        logger.info(f"✓ Components: {list(ai_health.get('components', {}).keys())}")
        
        # Step 3: Get posts to analyze
        posts_query = select(Post).where(Post.profile_id == profile.id)
        if not force_reanalyze:
            posts_query = posts_query.where(Post.ai_analyzed_at.is_(None))
        
        posts_result = await db.execute(posts_query.limit(batch_size))
        posts = posts_result.scalars().all()
        
        if not posts:
            return JSONResponse(content={
                "success": True,
                "message": f"No posts to analyze for {username}",
                "posts_analyzed": 0,
                "ai_status": "up_to_date",
                "analysis_time": 0.0
            })
        
        logger.info(f"[POSTS] Found {len(posts)} posts to analyze for {username}")
        
        # Step 4: Prepare posts data for analysis
        posts_data = []
        for post in posts:
            post_data = {
                'id': str(post.id),
                'caption': post.caption or '',
                'hashtags': post.hashtags or [],
                'media_type': post.media_type,
                'likes': post.likes or 0,
                'comments': post.comments or 0
            }
            posts_data.append(post_data)
            logger.debug(f"  - Post {post.id}: {len(post.caption or '')} chars, {len(post.hashtags or [])} hashtags")
        
        # Step 5: Run batch analysis with detailed logging
        logger.info(f"[BATCH] Starting batch AI analysis of {len(posts_data)} posts...")
        
        batch_results = await bulletproof_content_intelligence.batch_analyze_posts(
            posts_data, 
            batch_size=5  # Smaller batches for better logging visibility
        )
        
        logger.info(f"✓ Batch analysis completed: {batch_results.get('success_rate', 0):.2f} success rate")
        
        # Step 6: Update database with results
        successful_updates = 0
        failed_updates = 0
        analysis_details = []
        
        for i, batch_result in enumerate(batch_results.get("batch_results", [])):
            post_id = batch_result["post_id"]
            
            if batch_result.get("success"):
                analysis = batch_result["analysis"]
                logger.info(f"  ✓ Post {i+1}/{len(posts_data)}: {analysis.get('ai_content_category', 'Unknown')} | "
                           f"{analysis.get('ai_sentiment', 'neutral')} ({analysis.get('ai_sentiment_score', 0):.2f}) | "
                           f"{analysis.get('ai_language_code', 'unknown')}")
                
                # Update post with AI analysis
                update_success = await bulletproof_content_intelligence.update_post_ai_analysis(
                    db, post_id, analysis
                )
                
                if update_success:
                    successful_updates += 1
                    analysis_details.append({
                        "post_id": post_id,
                        "category": analysis.get('ai_content_category'),
                        "sentiment": analysis.get('ai_sentiment'),
                        "sentiment_score": analysis.get('ai_sentiment_score'),
                        "language": analysis.get('ai_language_code'),
                        "processing_time": analysis.get('analysis_metadata', {}).get('processing_time_seconds', 0)
                    })
                else:
                    failed_updates += 1
                    logger.warning(f"  [DB_FAIL] Database update failed for post {post_id}")
            else:
                failed_updates += 1
                error_msg = batch_result.get("error", "Unknown error")
                logger.error(f"  [FAIL] Post {i+1}/{len(posts_data)}: Analysis failed - {error_msg}")
        
        # Step 7: Update profile AI insights
        profile_insights_updated = False
        if successful_updates > 0:
            logger.info("📈 Updating profile AI insights...")
            profile_insights_updated = await _update_profile_ai_insights_direct(
                db, str(profile.id), username
            )
            if profile_insights_updated:
                logger.info(f"✓ Profile insights updated for {username}")
            else:
                logger.warning(f"[WARNING] Profile insights update failed for {username}")
        
        # Calculate total analysis time
        total_analysis_time = (datetime.now(timezone.utc) - analysis_start_time).total_seconds()
        
        # Final results
        result = {
            "success": True,
            "profile": {
                "username": username,
                "profile_id": str(profile.id),
                "total_posts": len(posts_data)
            },
            "analysis_results": {
                "posts_analyzed": successful_updates,
                "posts_failed": failed_updates,
                "success_rate": round(successful_updates / len(posts_data), 3) if posts_data else 0,
                "analysis_details": analysis_details
            },
            "profile_insights_updated": profile_insights_updated,
            "ai_system_health": ai_health,
            "performance": {
                "total_analysis_time_seconds": round(total_analysis_time, 2),
                "avg_time_per_post": round(total_analysis_time / len(posts_data), 3) if posts_data else 0,
                "posts_per_minute": round((successful_updates / total_analysis_time) * 60, 1) if total_analysis_time > 0 else 0
            },
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"[COMPLETE] DIRECT AI ANALYSIS COMPLETED for {username}: "
                   f"{successful_updates}/{len(posts_data)} posts in {total_analysis_time:.2f}s")
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"[FAILED] DIRECT AI ANALYSIS FAILED for {username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "direct_ai_analysis_failed",
                "message": f"AI analysis failed for {username}",
                "details": str(e),
                "analysis_time": (datetime.now(timezone.utc) - analysis_start_time).total_seconds()
            }
        )

async def _update_profile_ai_insights_direct(db: AsyncSession, profile_id: str, profile_username: str) -> bool:
    """Update profile with aggregated AI insights - Direct implementation"""
    try:
        # Get all analyzed posts for this profile
        analyzed_posts_query = select(Post).where(
            Post.profile_id == profile_id,
            Post.ai_analyzed_at.isnot(None)
        )
        
        posts_result = await db.execute(analyzed_posts_query)
        analyzed_posts = posts_result.scalars().all()
        
        if not analyzed_posts:
            logger.warning(f"No analyzed posts found for profile {profile_username}")
            return False
        
        logger.info(f"Calculating insights from {len(analyzed_posts)} analyzed posts")
        
        # Calculate aggregated insights
        category_counts = {}
        sentiment_scores = []
        language_counts = {}
        
        for post in analyzed_posts:
            # Category distribution
            if post.ai_content_category:
                category_counts[post.ai_content_category] = category_counts.get(post.ai_content_category, 0) + 1
            
            # Sentiment scores
            if post.ai_sentiment_score is not None:
                sentiment_scores.append(float(post.ai_sentiment_score))
            
            # Language distribution
            if post.ai_language_code:
                language_counts[post.ai_language_code] = language_counts.get(post.ai_language_code, 0) + 1
        
        total_analyzed = len(analyzed_posts)
        
        # Calculate insights
        primary_content_type = None
        content_distribution = {}
        if category_counts:
            primary_content_type = max(category_counts, key=category_counts.get)
            content_distribution = {
                category: round(count / total_analyzed, 2)
                for category, count in category_counts.items()
            }
            logger.info(f"Primary content type: {primary_content_type}")
            logger.info(f"Content distribution: {content_distribution}")
        
        avg_sentiment_score = 0.0
        if sentiment_scores:
            avg_sentiment_score = round(sum(sentiment_scores) / len(sentiment_scores), 3)
            logger.info(f"Average sentiment score: {avg_sentiment_score}")
        
        language_distribution = {}
        if language_counts:
            language_distribution = {
                lang: round(count / total_analyzed, 2)
                for lang, count in language_counts.items()
            }
            logger.info(f"Language distribution: {language_distribution}")
        
        # Content quality score (based on sentiment and category consistency)
        content_quality_score = _calculate_content_quality_score_direct(
            content_distribution, avg_sentiment_score, len(sentiment_scores), total_analyzed
        )
        logger.info(f"Content quality score: {content_quality_score}")
        
        # Update profile with insights
        from sqlalchemy import update
        await db.execute(
            update(Profile)
            .where(Profile.id == profile_id)
            .values(
                ai_primary_content_type=primary_content_type,
                ai_content_distribution=content_distribution,
                ai_avg_sentiment_score=avg_sentiment_score,
                ai_language_distribution=language_distribution,
                ai_content_quality_score=content_quality_score,
                ai_profile_analyzed_at=datetime.now(timezone.utc)
            )
        )
        
        await db.commit()
        logger.info(f"✓ Profile insights updated successfully for {profile_username}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update profile insights for {profile_username}: {e}")
        try:
            await db.rollback()
        except:
            pass
        return False

def _calculate_content_quality_score_direct(content_distribution: dict, avg_sentiment: float, 
                                          analyzed_posts: int, total_posts: int) -> float:
    """Calculate overall content quality score"""
    score = 0.0
    
    # Sentiment contribution (positive sentiment is better)
    sentiment_contribution = max(0, (avg_sentiment + 1) / 2)  # Normalize -1,1 to 0,1
    score += sentiment_contribution * 0.4  # 40% weight
    
    # Content consistency (focused content is better)
    consistency_score = 0.0
    if content_distribution:
        max_category_ratio = max(content_distribution.values())
        consistency_score = max_category_ratio
    score += consistency_score * 0.3  # 30% weight
    
    # Analysis coverage (more analyzed posts is better)
    coverage_score = min(1.0, analyzed_posts / max(1, total_posts))
    score += coverage_score * 0.3  # 30% weight
    
    return round(score, 3)

@router.get("/ai/system/health/detailed")
async def get_detailed_ai_system_health(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get detailed AI system health with component diagnostics"""
    try:
        # Initialize if needed
        if not bulletproof_content_intelligence.initialized:
            init_result = await bulletproof_content_intelligence.initialize()
            logger.info(f"AI system initialization result: {init_result}")
        
        # Get comprehensive health status
        health_status = bulletproof_content_intelligence.get_system_health()
        
        # Add additional diagnostics
        health_status["diagnostics"] = {
            "initialization_status": bulletproof_content_intelligence.initialized,
            "initialization_error": bulletproof_content_intelligence.initialization_error,
            "components_health": bulletproof_content_intelligence.components_health,
            "system_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error(f"Failed to get AI system health: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@router.post("/ai/system/reinitialize")
async def reinitialize_ai_system(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Force reinitialize the AI system"""
    try:
        logger.info("[REINIT] Force reinitializing AI system...")
        
        # Reset initialization state
        bulletproof_content_intelligence.initialized = False
        bulletproof_content_intelligence.initialization_error = None
        bulletproof_content_intelligence.components_health = {}
        
        # Reinitialize
        init_result = await bulletproof_content_intelligence.initialize()
        
        if init_result:
            logger.info("✓ AI system reinitialized successfully")
            health_status = bulletproof_content_intelligence.get_system_health()
            
            return JSONResponse(content={
                "success": True,
                "message": "AI system reinitialized successfully",
                "initialization_result": init_result,
                "system_health": health_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        else:
            logger.error("[FAILED] AI system reinitialization failed")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "AI system reinitialization failed",
                    "error": bulletproof_content_intelligence.initialization_error,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
    except Exception as e:
        logger.error(f"AI system reinitialization error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )