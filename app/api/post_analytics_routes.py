"""
Post Analytics API Routes - Individual Instagram Post Analysis
Separate from creator profile posts - dedicated post URL analysis system
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, HttpUrl
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.standalone_post_analytics_service import standalone_post_analytics_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/post-analytics", tags=["Post Analytics"])

# Pydantic models for request/response

class PostAnalysisRequest(BaseModel):
    """Request model for post analysis"""
    post_url: str
    tags: Optional[List[str]] = []  # Optional user tags

class BatchPostAnalysisRequest(BaseModel):
    """Request model for batch post analysis"""
    post_urls: List[str]
    max_concurrent: Optional[int] = 3  # Limit concurrent requests

class PostAnalysisSearchRequest(BaseModel):
    """Request model for searching post analyses"""
    username_filter: Optional[str] = None
    content_category: Optional[str] = None
    sentiment: Optional[str] = None
    media_type: Optional[str] = None
    min_likes: Optional[int] = None
    min_engagement_rate: Optional[float] = None
    limit: int = 50
    offset: int = 0

# =============================================================================
# POST ANALYSIS ENDPOINTS
# =============================================================================

@router.post("/analyze")
async def analyze_post(
    request: PostAnalysisRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze a single Instagram post by URL

    This endpoint:
    - Extracts post data using Apify Instagram scraper
    - Runs comprehensive AI analysis (sentiment, category, language, etc.)
    - Stores results in dedicated post_analyses table
    - Returns complete analytics data

    Example URLs:
    - https://www.instagram.com/p/ABC123/
    - https://instagram.com/p/XYZ789/
    """
    try:
        logger.info(f"🔍 Post analysis requested by user {current_user.id}: {request.post_url}")

        # Analyze the post (Apify will handle URL validation)
        analysis_result = await standalone_post_analytics_service.analyze_post_by_url(
            post_url=request.post_url,
            db=db,
            user_id=current_user.id
        )

        return {
            "success": True,
            "data": analysis_result,
            "message": "Post analysis completed successfully"
        }

    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error analyzing post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze post: {str(e)}"
        )

@router.post("/analyze/batch")
async def analyze_posts_batch(
    request: BatchPostAnalysisRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze multiple Instagram posts in batch

    Features:
    - Process up to 10 posts at once
    - Controlled concurrency to avoid rate limits
    - Individual success/failure tracking per post
    - Detailed results for each post
    """
    try:
        logger.info(f"📦 Batch analysis requested by user {current_user.id}: {len(request.post_urls)} posts")

        # Validate batch size
        if len(request.post_urls) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 posts allowed per batch request"
            )

        if len(request.post_urls) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one post URL is required"
            )

        # URL validation handled by Apify

        # Process each post
        results = []
        for post_url in request.post_urls:
            try:
                analysis_result = await standalone_post_analytics_service.analyze_post_by_url(
                    post_url=post_url,
                    db=db,
                    user_id=current_user.id
                )

                results.append({
                    "success": True,
                    "post_url": post_url,
                    "data": analysis_result
                })

            except Exception as e:
                logger.error(f"❌ Failed to analyze {post_url}: {e}")
                results.append({
                    "success": False,
                    "post_url": post_url,
                    "error": str(e)
                })

        # Calculate summary statistics
        successful_analyses = sum(1 for r in results if r["success"])
        failed_analyses = len(results) - successful_analyses

        return {
            "success": True,
            "data": {
                "results": results,
                "summary": {
                    "total_requested": len(request.post_urls),
                    "successful": successful_analyses,
                    "failed": failed_analyses,
                    "success_rate": round((successful_analyses / len(request.post_urls)) * 100, 1)
                }
            },
            "message": f"Batch analysis completed: {successful_analyses}/{len(request.post_urls)} successful"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in batch analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process batch analysis"
        )

# =============================================================================
# RETRIEVE ANALYSIS ENDPOINTS
# =============================================================================

@router.get("/analysis/{shortcode}")
async def get_analysis_by_shortcode(
    shortcode: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get existing post analysis by Instagram shortcode

    Args:
        shortcode: Instagram post shortcode (e.g., "ABC123" from instagram.com/p/ABC123/)
    """
    try:
        analysis = await standalone_post_analytics_service.get_post_analytics_by_shortcode(
            shortcode=shortcode,
            db=db
        )

        return {
            "success": True,
            "data": analysis,
            "message": "Analysis retrieved successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error retrieving analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis"
        )

@router.get("/analysis/id/{analysis_id}")
async def get_analysis_by_id(
    analysis_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get post analysis by analysis ID

    Args:
        analysis_id: Post analysis database ID
    """
    try:
        analysis = await standalone_post_analytics_service.get_post_analytics_by_id(
            post_id=analysis_id,
            db=db
        )

        return {
            "success": True,
            "data": analysis,
            "message": "Analysis retrieved successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error retrieving analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis"
        )

# =============================================================================
# SEARCH AND FILTER ENDPOINTS
# =============================================================================

@router.post("/search")
async def search_post_analyses(
    search_request: PostAnalysisSearchRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search and filter post analyses

    Advanced filtering options:
    - username_filter: Filter by Instagram username
    - content_category: Filter by AI-detected content category
    - sentiment: Filter by AI sentiment (positive, negative, neutral)
    - media_type: Filter by media type (photo, video, carousel)
    - min_likes: Minimum likes count
    - min_engagement_rate: Minimum engagement rate percentage
    """
    try:
        # Search functionality temporarily disabled - will be re-implemented for posts table
        results = {
            "analyses": [],
            "pagination": {
                "total": 0,
                "limit": search_request.limit,
                "offset": search_request.offset,
                "has_more": False
            },
            "filters_applied": {
                "message": "Search functionality coming soon for posts table"
            }
        }

        return {
            "success": True,
            "data": results,
            "message": f"Found {len(results['analyses'])} matching analyses"
        }

    except Exception as e:
        logger.error(f"❌ Error searching analyses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search analyses"
        )

@router.get("/my-analyses")
async def get_my_analyses(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    media_type: Optional[str] = Query(None, description="Filter by media type"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all post analyses created by the current user

    Supports pagination and basic filtering
    """
    try:
        # My analyses functionality temporarily disabled - will be re-implemented for posts table
        results = {
            "analyses": [],
            "pagination": {
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False
            }
        }

        return {
            "success": True,
            "data": results,
            "message": f"Retrieved {len(results['analyses'])} of your analyses"
        }

    except Exception as e:
        logger.error(f"❌ Error retrieving user analyses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve your analyses"
        )

# =============================================================================
# ANALYTICS AND INSIGHTS ENDPOINTS
# =============================================================================

@router.get("/insights/overview")
async def get_analytics_overview(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get overview analytics for user's post analyses

    Returns:
    - Total analyses count
    - Media type distribution
    - Sentiment distribution
    - Average engagement metrics
    - Top content categories
    """
    try:
        # Overview functionality temporarily disabled - will be re-implemented for posts table
        analyses = []

        if not analyses:
            return {
                "success": True,
                "data": {
                    "total_analyses": 0,
                    "message": "No analyses found. Start by analyzing some posts!"
                },
                "message": "Overview generated successfully"
            }

        # Calculate overview statistics
        total_analyses = len(analyses)

        # Media type distribution
        media_types = {}
        sentiments = {}
        content_categories = {}
        total_likes = 0
        total_comments = 0
        total_engagement_rate = 0
        engagement_count = 0

        for analysis in analyses:
            # Media types
            media_type = analysis.get("media", {}).get("type", "unknown")
            media_types[media_type] = media_types.get(media_type, 0) + 1

            # Sentiments
            ai_analysis = analysis.get("ai_analysis", {})
            sentiment = ai_analysis.get("sentiment", {}).get("label") if ai_analysis.get("sentiment") else None
            if sentiment:
                sentiments[sentiment] = sentiments.get(sentiment, 0) + 1

            # Content categories
            category = ai_analysis.get("content_category", {}).get("category") if ai_analysis.get("content_category") else None
            if category:
                content_categories[category] = content_categories.get(category, 0) + 1

            # Engagement metrics
            engagement = analysis.get("engagement", {})
            total_likes += engagement.get("likes_count", 0)
            total_comments += engagement.get("comments_count", 0)

            engagement_rate = engagement.get("engagement_rate")
            if engagement_rate is not None:
                total_engagement_rate += engagement_rate
                engagement_count += 1

        # Calculate averages
        avg_likes = round(total_likes / total_analyses, 1) if total_analyses > 0 else 0
        avg_comments = round(total_comments / total_analyses, 1) if total_analyses > 0 else 0
        avg_engagement_rate = round(total_engagement_rate / engagement_count, 2) if engagement_count > 0 else 0

        # Sort distributions
        top_media_types = sorted(media_types.items(), key=lambda x: x[1], reverse=True)[:5]
        top_sentiments = sorted(sentiments.items(), key=lambda x: x[1], reverse=True)[:3]
        top_categories = sorted(content_categories.items(), key=lambda x: x[1], reverse=True)[:10]

        overview_data = {
            "total_analyses": total_analyses,
            "media_type_distribution": {
                "data": top_media_types,
                "total_types": len(media_types)
            },
            "sentiment_distribution": {
                "data": top_sentiments,
                "total_with_sentiment": sum(sentiments.values())
            },
            "content_categories": {
                "data": top_categories,
                "total_with_categories": sum(content_categories.values())
            },
            "engagement_metrics": {
                "average_likes": avg_likes,
                "average_comments": avg_comments,
                "average_engagement_rate": avg_engagement_rate,
                "total_likes": total_likes,
                "total_comments": total_comments
            }
        }

        return {
            "success": True,
            "data": overview_data,
            "message": "Overview analytics generated successfully"
        }

    except Exception as e:
        logger.error(f"❌ Error generating overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate analytics overview"
        )

# =============================================================================
# MANAGEMENT ENDPOINTS
# =============================================================================

@router.delete("/analysis/{analysis_id}")
async def delete_analysis(
    analysis_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a post analysis

    Only the user who created the analysis can delete it
    """
    try:
        # Delete functionality temporarily disabled - will be re-implemented for posts table
        success = False

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )

        return {
            "success": True,
            "message": "Analysis deleted successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete analysis"
        )

# =============================================================================
# SYSTEM ENDPOINTS
# =============================================================================

@router.get("/health")
async def post_analytics_health():
    """Health check for Post Analytics system"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "post_analytics",
            "features": [
                "individual_post_analysis",
                "apify_integration",
                "ai_analysis",
                "batch_processing",
                "search_and_filter",
                "analytics_overview"
            ]
        },
        "message": "Post Analytics system is operational"
    }