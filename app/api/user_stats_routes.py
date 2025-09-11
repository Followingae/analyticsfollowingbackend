"""
User Statistics API Routes - Frontend Data Source
Single source of truth for user subscription and usage data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Dict, Any
from datetime import datetime, date
import logging

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user
from app.database.unified_models import User, Team, TeamMember, MonthlyUsageTracking
from app.models.auth import UserInDB
from app.models.teams import SUBSCRIPTION_TIER_LIMITS

router = APIRouter(prefix="/api/v1/user", tags=["User Statistics"])
logger = logging.getLogger(__name__)

@router.get("/dashboard-stats")
async def get_user_dashboard_stats(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    🎯 SINGLE SOURCE OF TRUTH - User Dashboard Statistics
    
    Returns complete user subscription and usage data for frontend
    This endpoint should be used by both dashboard and analytics components
    """
    try:
        logger.info(f"Getting dashboard stats for user: {current_user.email}")
        
        # Get user data
        user_query = select(User).where(User.email == current_user.email)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user is part of a team
        team_query = select(Team, TeamMember).join(
            TeamMember, Team.id == TeamMember.team_id
        ).where(TeamMember.user_id == user.id)
        team_result = await db.execute(team_query)
        team_data = team_result.first()
        
        # Determine subscription tier (team takes precedence)
        if team_data:
            team, team_member = team_data
            subscription_tier = team.subscription_tier
            team_info = {
                "team_id": str(team.id),
                "team_name": team.name,
                "role": team_member.role
            }
        else:
            # Individual subscription - CRITICAL FIX: Accept all valid subscription tiers
            valid_tiers = ["free", "standard", "premium", "professional", "enterprise", "brand_free", "brand_standard", "brand_premium", "brand_enterprise"]
            subscription_tier = user.subscription_tier if user.subscription_tier in valid_tiers else "free"
            team_info = None
        
        # Get subscription limits
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(subscription_tier, SUBSCRIPTION_TIER_LIMITS["free"])
        
        # Get current month usage
        current_month = date.today().replace(day=1)
        usage_query = select(MonthlyUsageTracking).where(
            and_(
                MonthlyUsageTracking.user_id == user.id,
                MonthlyUsageTracking.billing_month == current_month
            )
        )
        usage_result = await db.execute(usage_query)
        usage = usage_result.scalar_one_or_none()
        
        # Calculate usage stats
        profiles_used = usage.profiles_analyzed if usage else 0
        posts_used = usage.posts_analyzed if usage else 0
        emails_used = usage.emails_unlocked if usage else 0
        
        profiles_limit = tier_limits["monthly_profile_limit"]
        posts_limit = tier_limits["monthly_posts_limit"] 
        emails_limit = tier_limits["monthly_email_limit"]
        
        # Build response
        response = {
            "success": True,
            "user_info": {
                "email": user.email,
                "full_name": user.full_name,
                "subscription_tier": subscription_tier,
                "credits": user.credits,
                "credits_used_this_month": user.credits_used_this_month
            },
            "team_info": team_info,
            "subscription": {
                "tier": subscription_tier,
                "limits": {
                    "profiles_limit": profiles_limit,
                    "posts_limit": posts_limit,
                    "emails_limit": emails_limit,
                    "team_members_limit": tier_limits["max_team_members"]
                },
                "features": tier_limits["features"],
                "price_per_month": tier_limits["price_per_month"],
                "topup_discount": tier_limits.get("topup_discount", 0.0)
            },
            "usage_limits": {
                "profiles_limit": profiles_limit,
                "profiles_used": profiles_used,
                "profiles_remaining": max(0, profiles_limit - profiles_used),
                "posts_limit": posts_limit,
                "posts_used": posts_used,
                "posts_remaining": max(0, posts_limit - posts_used),
                "emails_limit": emails_limit,
                "emails_used": emails_used,
                "emails_remaining": max(0, emails_limit - emails_used)
            },
            "usage_percentage": {
                "profiles": round((profiles_used / profiles_limit * 100), 1) if profiles_limit > 0 else 0,
                "posts": round((posts_used / posts_limit * 100), 1) if posts_limit > 0 else 0,
                "emails": round((emails_used / emails_limit * 100), 1) if emails_limit > 0 else 0
            },
            "billing_info": {
                "current_month": current_month.isoformat(),
                "next_reset": (current_month.replace(month=current_month.month + 1 if current_month.month < 12 else 1, 
                                                   year=current_month.year + (1 if current_month.month == 12 else 0))).isoformat()
            }
        }
        
        logger.info(f"Dashboard stats retrieved for {user.email}: {subscription_tier} tier")
        return response
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")

@router.get("/subscription-status")
async def get_subscription_status(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    📊 QUICK SUBSCRIPTION CHECK
    
    Lightweight endpoint for quick subscription tier verification
    """
    try:
        # Get user data
        user_query = select(User).where(User.email == current_user.email)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            return {"subscription_tier": "free", "verified": False}
        
        # Check team membership for authoritative tier
        team_query = select(Team.subscription_tier).join(
            TeamMember, Team.id == TeamMember.team_id
        ).where(TeamMember.user_id == user.id)
        team_result = await db.execute(team_query)
        team_tier = team_result.scalar_one_or_none()
        
        # CRITICAL FIX: Accept all valid subscription tiers
        valid_tiers = ["free", "standard", "premium", "professional", "enterprise", "brand_free", "brand_standard", "brand_premium", "brand_enterprise"]
        subscription_tier = team_tier or (user.subscription_tier if user.subscription_tier in valid_tiers else "free")
        
        return {
            "subscription_tier": subscription_tier,
            "verified": True,
            "source": "team" if team_tier else "individual"
        }
        
    except Exception as e:
        logger.error(f"Error checking subscription for {current_user.email}: {e}")
        return {"subscription_tier": "free", "verified": False, "error": str(e)}