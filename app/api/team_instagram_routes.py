"""
Team-Based Instagram Analytics Routes - B2B SaaS Implementation
Uses team authentication with pooled usage limits and role-based permissions
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
import logging

from app.middleware.team_auth_middleware import (
    get_team_context, get_any_team_member_context, 
    TeamContext, validate_team_usage, record_team_usage,
    team_usage_gate, TeamUsageLimitError
)
from app.database.connection import get_db
from app.database.comprehensive_service import comprehensive_service
from app.database.unified_models import Profile, Post
from app.models.teams import TeamContextResponse
from app.services.engagement_rate_service import EngagementRateService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team/instagram", tags=["Team Instagram Analytics"])

# =============================================================================
# CORE PROFILE ANALYSIS - TEAM POOLED USAGE
# =============================================================================

@router.get("/profile/{username}")
@team_usage_gate("profiles", 1)  # Uses team's pooled profile limit
async def analyze_instagram_profile_team(
    username: str = Path(..., description="Instagram username"),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Team-based Instagram profile analysis with pooled usage limits
    
    Features:
    - Uses team's pooled monthly profile limit (Standard: 500, Premium: 2000)
    - Same comprehensive analytics for all subscription tiers
    - Shared access across all team members
    - Usage tracked per individual for analytics
    """
    try:
        logger.info(f"Team profile analysis: {username} for team {team_context.team_name}")
        
        # STEP 1: Check if profile exists in database (database-first strategy)
        existing_profile = await comprehensive_service.get_profile_by_username(db, username)
        
        if existing_profile:
            logger.info(f"Profile {username} exists in database - granting team access")
            
            # Grant team access to existing profile
            await comprehensive_service.grant_team_profile_access(
                db, team_context.team_id, team_context.user_id, username
            )
            
            # Return existing data with team context
            return await _format_team_profile_response(existing_profile, team_context)
        
        # STEP 2: Profile doesn't exist - fetch fresh data
        logger.info(f"Profile {username} not in database - fetching fresh data")
        
        # Fetch from external API
        from app.scrapers.enhanced_decodo_client import EnhancedDecodoClient
        from app.core.config import settings
        
        async with EnhancedDecodoClient(
            settings.SMARTPROXY_USERNAME, 
            settings.SMARTPROXY_PASSWORD
        ) as decodo_client:
            raw_data = await decodo_client.get_instagram_profile_comprehensive(username)
        
        # Store complete profile data
        profile, is_new = await comprehensive_service.store_complete_profile(
            db, username, raw_data
        )
        
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Failed to fetch profile data for {username}"
            )
        
        # Grant team access to new profile
        await comprehensive_service.grant_team_profile_access(
            db, team_context.team_id, team_context.user_id, username
        )
        
        # Schedule background AI analysis
        from app.services.ai_background_task_manager import ai_background_task_manager
        ai_task = ai_background_task_manager.schedule_profile_analysis(
            str(profile.id), username
        )
        
        logger.info(f"Profile {username} stored and team access granted")
        
        # Usage will be recorded by @team_usage_gate decorator after successful completion
        return await _format_team_profile_response(profile, team_context, ai_task)
        
    except TeamUsageLimitError:
        raise  # Let the usage limit error pass through
    except Exception as e:
        logger.error(f"Team profile analysis failed for {username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Profile analysis failed: {str(e)}"
        )

@router.get("/profile/{username}/posts")
@team_usage_gate("posts", 1)  # Uses team's pooled posts limit  
async def get_profile_posts_team(
    username: str = Path(..., description="Instagram username"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Get profile posts using team's pooled posts analytics limit
    
    Features:
    - Uses team's pooled monthly posts limit (Standard: 125, Premium: 300)
    - Returns paginated posts with full analytics
    - Shared access across team members
    """
    try:
        logger.info(f"Team posts analysis: {username} for team {team_context.team_name}")
        
        # Check if team has access to this profile
        team_profile_access = await comprehensive_service.get_team_profile_access(
            db, team_context.team_id, username
        )
        
        if not team_profile_access:
            raise HTTPException(
                status_code=403,
                detail=f"Team doesn't have access to {username}. Analyze the profile first."
            )
        
        # Get posts for the profile
        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Get paginated posts
        posts_query = select(Post).where(
            Post.profile_id == profile.id
        ).order_by(Post.created_at.desc()).offset(offset).limit(limit)
        
        posts_result = await db.execute(posts_query)
        posts = posts_result.scalars().all()
        
        # Format posts response with team context
        posts_data = []
        for post in posts:
            post_data = {
                "id": str(post.id),
                "instagram_post_id": post.instagram_post_id,
                "caption": post.caption,
                "media_type": post.media_type,
                "likes_count": post.likes_count or 0,
                "comments_count": post.comments_count or 0,
                "engagement_rate": post.engagement_rate or 0.0,
                "created_at": post.created_at.isoformat(),
                "hashtags": post.hashtags or [],
                "mentions": post.mentions or [],
                # AI analysis - same for all tiers
                "ai_analysis": {
                    "content_category": post.ai_content_category,
                    "sentiment": post.ai_sentiment,
                    "sentiment_score": post.ai_sentiment_score,
                    "language": post.ai_language_code,
                    "confidence": post.ai_sentiment_confidence
                },
                "media_urls": post.media_urls or []
            }
            posts_data.append(post_data)
        
        # Usage recorded by @team_usage_gate decorator
        return {
            "success": True,
            "profile_username": username,
            "posts": posts_data,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(posts_data)
            },
            "team_context": team_context.to_dict()
        }
        
    except TeamUsageLimitError:
        raise
    except Exception as e:
        logger.error(f"Team posts analysis failed for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profile/{username}/emails")  
@team_usage_gate("emails", 1)  # Uses team's pooled email unlock limit
async def unlock_profile_emails_team(
    username: str = Path(..., description="Instagram username"),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Unlock profile email contacts using team's pooled email limit
    
    Features:
    - Uses team's pooled monthly email limit (Standard: 250, Premium: 800)
    - Extracts available email addresses from profile data
    - Shared access across team members
    """
    try:
        logger.info(f"Team email unlock: {username} for team {team_context.team_name}")
        
        # Check team access to profile
        team_profile_access = await comprehensive_service.get_team_profile_access(
            db, team_context.team_id, username
        )
        
        if not team_profile_access:
            raise HTTPException(
                status_code=403,
                detail=f"Team doesn't have access to {username}. Analyze the profile first."
            )
        
        # Get profile data
        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Extract email information
        emails_found = []
        
        # Check various profile fields for email addresses
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Check biography
        if profile.biography:
            biography_emails = re.findall(email_pattern, profile.biography)
            for email in biography_emails:
                emails_found.append({
                    "email": email,
                    "source": "biography",
                    "confidence": 0.9
                })
        
        # Check external URL (often contains contact info)
        if profile.external_url:
            # This would require fetching the external URL content
            # For now, just indicate if there's a website
            emails_found.append({
                "email": None,
                "source": "external_website",
                "website": profile.external_url,
                "confidence": 0.5,
                "note": "Check website for contact information"
            })
        
        # Record email unlock in team's email_unlocks table
        from app.database.unified_models import EmailUnlock
        from uuid import uuid4
        
        email_unlock = EmailUnlock(
            id=uuid4(),
            team_id=team_context.team_id,
            user_id=team_context.user_id,
            profile_id=profile.id,
            email_address=emails_found[0]["email"] if emails_found and emails_found[0]["email"] else None,
            email_source="profile_analysis",
            confidence_score=emails_found[0]["confidence"] if emails_found else 0.0
        )
        db.add(email_unlock)
        await db.commit()
        
        # Usage recorded by @team_usage_gate decorator
        return {
            "success": True,
            "profile_username": username,
            "emails_found": len([e for e in emails_found if e.get("email")]),
            "email_data": emails_found,
            "team_context": team_context.to_dict()
        }
        
    except TeamUsageLimitError:
        raise
    except Exception as e:
        logger.error(f"Team email unlock failed for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# TEAM MANAGEMENT ENDPOINTS  
# =============================================================================

@router.get("/team/context")
async def get_team_context_info(
    team_context: TeamContext = Depends(get_any_team_member_context)
):
    """Get current team context and usage information"""
    return TeamContextResponse(**team_context.to_dict())

@router.get("/team/usage")
async def get_team_usage_summary(
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed team usage summary with member breakdown"""
    try:
        from app.database.unified_models import MonthlyUsageTracking, TeamMember
        from datetime import date
        
        current_month = date.today().replace(day=1)
        
        # Get usage by team member
        usage_query = select(
            MonthlyUsageTracking.user_id,
            MonthlyUsageTracking.profiles_analyzed,
            MonthlyUsageTracking.emails_unlocked,
            MonthlyUsageTracking.posts_analyzed,
            TeamMember.role
        ).select_from(
            MonthlyUsageTracking.join(TeamMember, MonthlyUsageTracking.user_id == TeamMember.user_id)
        ).where(
            and_(
                MonthlyUsageTracking.team_id == team_context.team_id,
                MonthlyUsageTracking.billing_month == current_month
            )
        )
        
        result = await db.execute(usage_query)
        member_usage = result.fetchall()
        
        # Format member usage data
        usage_by_member = []
        for usage in member_usage:
            usage_by_member.append({
                "user_id": str(usage.user_id),
                "role": usage.role,
                "profiles_analyzed": usage.profiles_analyzed,
                "emails_unlocked": usage.emails_unlocked,
                "posts_analyzed": usage.posts_analyzed
            })
        
        # Calculate usage percentages
        usage_percentage = {
            "profiles": (team_context.current_usage["profiles"] / team_context.monthly_limits["profiles"]) * 100 if team_context.monthly_limits["profiles"] > 0 else 0,
            "emails": (team_context.current_usage["emails"] / team_context.monthly_limits["emails"]) * 100 if team_context.monthly_limits["emails"] > 0 else 0,
            "posts": (team_context.current_usage["posts"] / team_context.monthly_limits["posts"]) * 100 if team_context.monthly_limits["posts"] > 0 else 0
        }
        
        return {
            "team_id": str(team_context.team_id),
            "team_name": team_context.team_name,
            "subscription_tier": team_context.subscription_tier,
            "billing_month": current_month.isoformat(),
            "monthly_limits": team_context.monthly_limits,
            "current_usage": team_context.current_usage,
            "remaining_capacity": team_context.to_dict()["remaining_capacity"],
            "usage_percentage": usage_percentage,
            "member_usage": usage_by_member
        }
        
    except Exception as e:
        logger.error(f"Error getting team usage summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage summary")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _format_team_profile_response(
    profile: Profile,
    team_context: TeamContext,
    ai_task: Optional[Dict] = None
) -> Dict[str, Any]:
    """Format profile response with team context"""
    return {
        "success": True,
        "profile": {
            "id": str(profile.id),
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers_count": profile.followers_count or 0,
            "following_count": profile.following_count or 0,
            "posts_count": profile.posts_count or 0,
            "is_verified": profile.is_verified or False,
            "is_business": profile.is_business or False,
            "engagement_rate": profile.engagement_rate,
            # Complete analytics - same for all subscription tiers
            "analytics": {
                "avg_likes": profile.avg_likes,
                "avg_comments": profile.avg_comments,
                "posting_frequency": profile.posting_frequency,
                "best_posting_times": profile.best_posting_times,
                "ai_insights": {
                    "content_category": profile.ai_primary_content_type,
                    "content_distribution": profile.ai_content_distribution,
                    "average_sentiment": profile.ai_avg_sentiment_score,
                    "language_distribution": profile.ai_language_distribution,
                    "content_quality_score": profile.ai_content_quality_score
                }
            },
            "last_updated": profile.updated_at.isoformat() if profile.updated_at else None
        },
        "team_context": team_context.to_dict(),
        "ai_processing": ai_task if ai_task else {"status": "completed"},
        "access_info": {
            "access_type": "team_shared",
            "shared_with_team": True,
            "access_expires": "30_days_from_analysis"
        }
    }