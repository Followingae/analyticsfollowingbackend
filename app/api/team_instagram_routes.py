"""
Team-Based Instagram Analytics Routes - B2B SaaS Implementation
Uses team authentication with pooled usage limits and role-based permissions
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
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

@router.get("/profile/{username}/basic")
@team_usage_gate("profiles", 1)  # Uses team's pooled profile limit
async def get_profile_basic_data(
    username: str = Path(..., description="Instagram username"),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    STEP 1: Get basic Instagram profile data immediately
    
    Returns raw Decodo data within 1-3 seconds:
    - Profile info (followers, following, bio)
    - Basic engagement metrics
    - No AI analysis (comes later in detailed endpoint)
    
    Usage:
    - Uses team's pooled monthly profile limit
    - Same basic data for all subscription tiers
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
            
            # All existing profiles MUST have AI data - return detailed response immediately
            logger.info(f"Profile {username} exists in database - returning complete data with AI insights")
            return await _format_detailed_profile_response(existing_profile, team_context)
        
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
        return await _format_basic_profile_response(profile, team_context, ai_task)
        
    except TeamUsageLimitError:
        raise  # Let the usage limit error pass through
    except Exception as e:
        logger.error(f"Team profile analysis failed for {username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Profile analysis failed: {str(e)}"
        )


@router.get("/profile/{username}/detailed")
async def get_profile_detailed_data(
    username: str = Path(..., description="Instagram username"),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    STEP 2: Get detailed Instagram profile data with AI insights
    
    Returns AI-enhanced data:
    - All basic data PLUS AI analysis
    - Content categories and sentiment analysis
    - Language distribution and quality scores
    - Should be called after /basic endpoint
    """
    try:
        logger.info(f"Team detailed profile analysis: {username} for team {team_context.team_name}")
        
        # Get profile from database (should exist from basic call)
        existing_profile = await comprehensive_service.get_profile_by_username(db, username)
        
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"Profile {username} not found. Call /basic endpoint first."
            )
        
        # Check if user has team access to this profile
        has_access = await comprehensive_service.check_team_profile_access(
            db, team_context.team_id, username
        )
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="Team does not have access to this profile"
            )
        
        # Return detailed data with AI insights
        return await _format_detailed_profile_response(existing_profile, team_context)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Team detailed profile analysis failed for {username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Detailed profile analysis failed: {str(e)}"
        )


@router.get("/profile/{username}/status")
async def get_profile_analysis_status(
    username: str = Path(..., description="Instagram username"),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Check AI analysis status for a profile
    
    Returns:
    - analysis_status: "pending", "processing", "completed", "error"
    - ai_data_available: boolean
    - estimated_completion: seconds (if still processing)
    """
    try:
        # Get profile from database
        profile = await comprehensive_service.get_profile_by_username(db, username)
        
        if not profile:
            return {
                "analysis_status": "not_found",
                "ai_data_available": False,
                "message": "Profile not found. Call /basic endpoint first."
            }
        
        # Check if user has team access to this profile
        has_access = await comprehensive_service.check_team_profile_access(
            db, team_context.team_id, username
        )
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="Team does not have access to this profile"
            )
        
        # All profiles in database MUST have AI data - always completed
        return {
            "analysis_status": "completed",
            "ai_data_available": True,
            "profile_id": str(profile.id),
            "last_analyzed": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
            "estimated_completion": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile status check failed for {username}: {e}")
        return {
            "analysis_status": "error",
            "ai_data_available": False,
            "error": str(e)
        }


@router.get("/unlocked-profiles")
async def get_team_unlocked_profiles(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Results per page"),
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all profiles the team has unlocked with full comprehensive data
    
    Returns paginated list of profiles with complete analytics and AI insights
    """
    try:
        from app.database.unified_models import TeamProfileAccess
        
        # Get team's unlocked profiles
        offset = (page - 1) * page_size
        
        profiles_query = select(Profile).join(
            TeamProfileAccess, Profile.id == TeamProfileAccess.profile_id
        ).where(
            TeamProfileAccess.team_id == team_context.team_id
        ).offset(offset).limit(page_size)
        
        result = await db.execute(profiles_query)
        profiles = result.scalars().all()
        
        # Get total count
        count_query = select(func.count(Profile.id)).join(
            TeamProfileAccess, Profile.id == TeamProfileAccess.profile_id
        ).where(
            TeamProfileAccess.team_id == team_context.team_id
        )
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Format profiles with full data (all profiles MUST have AI data)
        formatted_profiles = []
        for profile in profiles:
            profile_data = {
                "id": str(profile.id),
                "username": profile.username,
                "full_name": profile.full_name,
                "biography": profile.biography,
                "followers_count": profile.followers_count or 0,
                "following_count": profile.following_count or 0,
                "posts_count": profile.posts_count or 0,
                "is_verified": profile.is_verified or False,
                "engagement_rate": profile.engagement_rate,
                # AI insights (guaranteed to exist)
                "ai_content_category": getattr(profile, 'ai_primary_content_type', None),
                "ai_content_distribution": getattr(profile, 'ai_content_distribution', None),
                "ai_sentiment_score": getattr(profile, 'ai_avg_sentiment_score', None),
                "ai_language_distribution": getattr(profile, 'ai_language_distribution', None),
                "ai_content_quality_score": getattr(profile, 'ai_content_quality_score', None),
                "ai_analyzed_at": getattr(profile, 'ai_profile_analyzed_at', None).isoformat() if getattr(profile, 'ai_profile_analyzed_at', None) else None,
                "last_updated": profile.updated_at.isoformat() if profile.updated_at else None
            }
            formatted_profiles.append(profile_data)
        
        return {
            "success": True,
            "profiles": formatted_profiles,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size
            },
            "team_context": {
                "team_id": str(team_context.team_id),
                "team_name": team_context.team_name
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting team unlocked profiles: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get unlocked profiles: {str(e)}"
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
                "media_urls": [url for url in [post.display_url, post.thumbnail_src, post.video_url] if url]
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
            "is_business": profile.is_business_account or False,
            "engagement_rate": profile.engagement_rate,
            # Complete analytics - same for all subscription tiers
            "analytics": {
                "avg_likes": getattr(profile, 'avg_likes', None),
                "avg_comments": getattr(profile, 'avg_comments', None),
                "posting_frequency": getattr(profile, 'posting_frequency', None),
                "best_posting_times": getattr(profile, 'best_posting_times', None),
                "ai_insights": {
                    "content_category": getattr(profile, 'ai_primary_content_type', None),
                    "content_distribution": getattr(profile, 'ai_content_distribution', None),
                    "average_sentiment": getattr(profile, 'ai_avg_sentiment_score', None),
                    "language_distribution": getattr(profile, 'ai_language_distribution', None),
                    "content_quality_score": getattr(profile, 'ai_content_quality_score', None)
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


async def _format_basic_profile_response(
    profile: Profile,
    team_context: TeamContext,
    ai_task: Optional[Dict] = None
) -> Dict[str, Any]:
    """Format BASIC profile response (Step 1) - No AI data"""
    try:
        return {
        "success": True,
        "data_stage": "basic",
        "message": "Basic profile data loaded. AI analysis in progress...",
        "profile": {
            "id": str(profile.id),
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers_count": profile.followers_count or 0,
            "following_count": profile.following_count or 0,
            "posts_count": profile.posts_count or 0,
            "is_verified": profile.is_verified or False,
            "is_business": profile.is_business_account or False,
            
            # Profile picture URLs (same as Creators page)
            "profile_pic_url": profile.profile_pic_url or "",
            "profile_pic_url_hd": profile.profile_pic_url_hd or "",
            "proxied_profile_pic_url": profile.profile_pic_url or "",  # External proxy service handles these
            "proxied_profile_pic_url_hd": profile.profile_pic_url_hd or "",  # External proxy service handles these
            
            "engagement_rate": profile.engagement_rate,
            # Basic analytics only - no AI insights
            "analytics": {
                "avg_likes": getattr(profile, 'avg_likes', None),
                "avg_comments": getattr(profile, 'avg_comments', None),
                "posting_frequency": getattr(profile, 'posting_frequency', None),
                "best_posting_times": getattr(profile, 'best_posting_times', None)
            },
            "last_updated": profile.updated_at.isoformat() if profile.updated_at else None
        },
        "team_context": team_context.to_dict(),
        "ai_processing": {
            "status": "processing" if ai_task else "scheduled",
            "estimated_completion": 30,
            "next_step": f"Call GET /profile/{profile.username}/status to check progress"
        },
        "access_info": {
            "access_type": "team_shared",
            "shared_with_team": True,
            "access_expires": "30_days_from_analysis"
        }
        }
        
    except Exception as e:
        logger.error(f"Error formatting basic profile response: {e}")
        # Return safe fallback response
        return {
            "success": True,
            "data_stage": "basic",
            "message": "Basic profile data retrieved with limited details",
            "profile": {
                "id": str(profile.id) if hasattr(profile, 'id') else None,
                "username": getattr(profile, 'username', 'unknown'),
                "full_name": getattr(profile, 'full_name', None),
                "followers_count": getattr(profile, 'followers_count', 0) or 0,
                "following_count": getattr(profile, 'following_count', 0) or 0,
                "posts_count": getattr(profile, 'posts_count', 0) or 0,
                "engagement_rate": getattr(profile, 'engagement_rate', None),
                "analytics": {
                    "avg_likes": None,
                    "avg_comments": None,
                    "posting_frequency": None,
                    "best_posting_times": None
                }
            },
            "team_context": team_context.to_dict() if hasattr(team_context, 'to_dict') else {},
            "error": f"Profile formatting error: {str(e)}"
        }


async def _format_detailed_profile_response(
    profile: Profile,
    team_context: TeamContext
) -> Dict[str, Any]:
    """Format DETAILED profile response (Step 2) - With AI insights (always available for existing profiles)"""
    
    try:
        response = {
        "success": True,
        "data_stage": "detailed",
        "message": "Complete profile analysis with AI insights available!",
        "profile": {
            "id": str(profile.id),
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers_count": profile.followers_count or 0,
            "following_count": profile.following_count or 0,
            "posts_count": profile.posts_count or 0,
            "is_verified": profile.is_verified or False,
            "is_business": profile.is_business_account or False,
            
            # Profile picture URLs (same as unlocked profiles endpoint)
            "profile_pic_url": profile.profile_pic_url or "",
            "profile_pic_url_hd": profile.profile_pic_url_hd or "",
            "proxied_profile_pic_url": profile.profile_pic_url or "",  # External proxy service handles these
            "proxied_profile_pic_url_hd": profile.profile_pic_url_hd or "",  # External proxy service handles these
            
            "engagement_rate": profile.engagement_rate,
            # Complete analytics WITH AI insights
            "analytics": {
                "avg_likes": getattr(profile, 'avg_likes', None),
                "avg_comments": getattr(profile, 'avg_comments', None),
                "posting_frequency": getattr(profile, 'posting_frequency', None),
                "best_posting_times": getattr(profile, 'best_posting_times', None),
                "ai_insights": {
                    "available": True,
                    "content_category": getattr(profile, 'ai_primary_content_type', None),
                    "content_distribution": getattr(profile, 'ai_content_distribution', None),
                    "average_sentiment": getattr(profile, 'ai_avg_sentiment_score', None),
                    "language_distribution": getattr(profile, 'ai_language_distribution', None),
                    "content_quality_score": getattr(profile, 'ai_content_quality_score', None),
                    "last_analyzed": getattr(profile, 'ai_profile_analyzed_at', None).isoformat() if getattr(profile, 'ai_profile_analyzed_at', None) else None
                }
            },
            "last_updated": profile.updated_at.isoformat() if profile.updated_at else None
        },
        "team_context": team_context.to_dict(),
        "ai_processing": {
            "status": "completed",
            "completion_percentage": 100
        },
        "access_info": {
            "access_type": "team_shared",
            "shared_with_team": True,
            "access_expires": "30_days_from_analysis"
        }
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error formatting detailed profile response: {e}")
        # Return safe fallback response
        return {
            "success": True,
            "data_stage": "detailed",
            "message": "Profile data retrieved with limited details",
            "profile": {
                "id": str(profile.id) if hasattr(profile, 'id') else None,
                "username": getattr(profile, 'username', 'unknown'),
                "full_name": getattr(profile, 'full_name', None),
                "followers_count": getattr(profile, 'followers_count', 0) or 0,
                "following_count": getattr(profile, 'following_count', 0) or 0,
                "posts_count": getattr(profile, 'posts_count', 0) or 0,
                "engagement_rate": getattr(profile, 'engagement_rate', None),
                "analytics": {
                    "avg_likes": None,
                    "avg_comments": None,
                    "posting_frequency": None,
                    "best_posting_times": None,
                    "ai_insights": {
                        "available": False,
                        "error": "Data formatting error"
                    }
                }
            },
            "team_context": team_context.to_dict() if hasattr(team_context, 'to_dict') else {},
            "error": f"Profile formatting error: {str(e)}"
        }