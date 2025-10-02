"""
Campaign AI Insights Endpoint - Comprehensive AI Intelligence Aggregation
Provides aggregated AI analysis across all posts in a campaign
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.campaign_ai_insights_service import campaign_ai_insights_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaign AI Insights"])


@router.get("/{campaign_id}/ai-insights")
async def get_campaign_ai_insights(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated AI insights for campaign

    **Aggregates AI analysis across all posts in the campaign:**

    1. **Sentiment Analysis**: Positive/Neutral/Negative distribution
    2. **Language Detection**: Top languages with percentages
    3. **Category Classification**: Content categories (food, fashion, tech, etc.)
    4. **Audience Quality**: Authenticity scores, bot detection, fake followers
    5. **Visual Content**: Aesthetic scores, professional quality, face detection
    6. **Audience Insights**: Geographic reach, demographics, cultural analysis
    7. **Trend Detection**: Viral potential, trending topics
    8. **Advanced NLP**: Readability, brand mentions, hashtag effectiveness
    9. **Fraud Detection**: Risk levels, trust scores
    10. **Behavioral Patterns**: Posting frequency, engagement consistency

    Returns comprehensive AI intelligence for campaign optimization.
    """
    try:
        ai_insights = await campaign_ai_insights_service.get_campaign_ai_insights(
            db=db,
            campaign_id=campaign_id,
            user_id=current_user.id
        )

        if not ai_insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found or no AI data available"
            )

        return {
            "success": True,
            "data": ai_insights,
            "message": "Campaign AI insights retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving campaign AI insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve campaign AI insights: {str(e)}"
        )
