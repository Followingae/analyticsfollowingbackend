"""
Team Authentication Middleware - B2B SaaS Team Context
Extracts team context from user authentication and provides team-based access control
"""
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date, datetime

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.database.unified_models import Team, TeamMember, MonthlyUsageTracking

logger = logging.getLogger(__name__)

class TeamRoles:
    """Team role constants"""
    OWNER = "owner"
    MEMBER = "member"

class TeamContext:
    """Team context data structure"""
    def __init__(
        self,
        team_id: UUID,
        team_name: str,
        user_role: str,
        subscription_tier: str,
        subscription_status: str,
        monthly_limits: Dict[str, int],
        current_usage: Dict[str, int],
        user_id: UUID,
        user_permissions: Dict[str, bool]
    ):
        self.team_id = team_id
        self.team_name = team_name
        self.user_role = user_role
        self.subscription_tier = subscription_tier
        self.subscription_status = subscription_status
        self.monthly_limits = monthly_limits
        self.current_usage = current_usage
        self.user_id = user_id
        self.user_permissions = user_permissions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": str(self.team_id),
            "team_name": self.team_name,
            "user_role": self.user_role,
            "subscription_tier": self.subscription_tier,
            "subscription_status": self.subscription_status,
            "monthly_limits": self.monthly_limits,
            "current_usage": self.current_usage,
            "user_id": str(self.user_id),
            "user_permissions": self.user_permissions,
            "remaining_capacity": {
                "profiles": max(0, self.monthly_limits.get("profiles", 0) - self.current_usage.get("profiles", 0)),
                "emails": max(0, self.monthly_limits.get("emails", 0) - self.current_usage.get("emails", 0)),
                "posts": max(0, self.monthly_limits.get("posts", 0) - self.current_usage.get("posts", 0))
            }
        }

class TeamAuthenticationError(HTTPException):
    """Team authentication specific error"""
    def __init__(self, detail: str = "Team authentication failed"):
        super().__init__(status_code=401, detail=detail)

class TeamPermissionError(HTTPException):
    """Team permission specific error"""
    def __init__(self, detail: str = "Insufficient team permissions"):
        super().__init__(status_code=403, detail=detail)

class TeamUsageLimitError(HTTPException):
    """Team usage limit exceeded error"""
    def __init__(self, detail: str = "Team usage limit exceeded", headers: Dict[str, str] = None):
        super().__init__(status_code=402, detail=detail, headers=headers or {})

async def get_team_context(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> TeamContext:
    """
    Get comprehensive team context for the current user
    This is the main dependency for team-based authentication
    """
    try:
        user_id = UUID(str(current_user.id))
        
        # Get user's team membership
        team_member_query = select(
            TeamMember.team_id,
            TeamMember.role,
            TeamMember.permissions,
            TeamMember.status,
            Team.name.label("team_name"),
            Team.subscription_tier,
            Team.subscription_status,
            Team.monthly_profile_limit,
            Team.monthly_email_limit,
            Team.monthly_posts_limit,
            Team.profiles_used_this_month,
            Team.emails_used_this_month,
            Team.posts_used_this_month,
            Team.subscription_expires_at
        ).select_from(
            TeamMember.join(Team, TeamMember.team_id == Team.id)
        ).where(
            and_(
                TeamMember.user_id == user_id,
                TeamMember.status == "active"
            )
        )
        
        result = await db.execute(team_member_query)
        team_data = result.first()
        
        if not team_data:
            raise TeamAuthenticationError("User is not a member of any active team")
        
        # Check subscription status
        if team_data.subscription_status not in ["active", "trial"]:
            raise TeamAuthenticationError(f"Team subscription is {team_data.subscription_status}")
        
        # Check subscription expiration
        if team_data.subscription_expires_at and team_data.subscription_expires_at < datetime.now():
            raise TeamAuthenticationError("Team subscription has expired")
        
        # Build team context
        team_context = TeamContext(
            team_id=team_data.team_id,
            team_name=team_data.team_name,
            user_role=team_data.role,
            subscription_tier=team_data.subscription_tier,
            subscription_status=team_data.subscription_status,
            monthly_limits={
                "profiles": team_data.monthly_profile_limit,
                "emails": team_data.monthly_email_limit,
                "posts": team_data.monthly_posts_limit
            },
            current_usage={
                "profiles": team_data.profiles_used_this_month,
                "emails": team_data.emails_used_this_month,
                "posts": team_data.posts_used_this_month
            },
            user_id=user_id,
            user_permissions=team_data.permissions or {}
        )
        
        logger.debug(f"Team context loaded for user {user_id}: {team_context.team_name} ({team_context.subscription_tier})")
        return team_context
        
    except TeamAuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Error getting team context for user {current_user.id}: {e}")
        raise TeamAuthenticationError(f"Failed to load team context: {str(e)}")

def requires_team_role(required_role: str):
    """
    Decorator to require specific team role
    Usage: @requires_team_role(TeamRoles.OWNER)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract team_context from kwargs
            team_context = None
            for key, value in kwargs.items():
                if isinstance(value, TeamContext):
                    team_context = value
                    break
            
            if not team_context:
                raise TeamAuthenticationError("Team context required")
            
            if team_context.user_role != required_role:
                raise TeamPermissionError(f"Requires {required_role} role, user has {team_context.user_role}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

async def validate_team_usage(
    team_context: TeamContext,
    action_type: str,
    quantity: int = 1,
    db: AsyncSession = None
) -> bool:
    """
    Validate if team can perform action within pooled limits
    
    Args:
        team_context: Team context from middleware
        action_type: Type of action ("profiles", "emails", "posts")
        quantity: How many units to consume
        db: Database session for real-time updates
    
    Returns:
        True if allowed, raises TeamUsageLimitError if not
    """
    try:
        current_usage = team_context.current_usage.get(action_type, 0)
        limit = team_context.monthly_limits.get(action_type, 0)
        
        if current_usage + quantity > limit:
            # Get fresh usage data if database session provided
            if db:
                current_month = date.today().replace(day=1)
                usage_query = select(
                    Team.profiles_used_this_month,
                    Team.emails_used_this_month,  
                    Team.posts_used_this_month
                ).where(Team.id == team_context.team_id)
                
                result = await db.execute(usage_query)
                fresh_usage = result.first()
                
                if fresh_usage:
                    usage_map = {
                        "profiles": fresh_usage.profiles_used_this_month,
                        "emails": fresh_usage.emails_used_this_month,
                        "posts": fresh_usage.posts_used_this_month
                    }
                    current_usage = usage_map.get(action_type, 0)
            
            # Final check with fresh data
            if current_usage + quantity > limit:
                remaining = max(0, limit - current_usage)
                raise TeamUsageLimitError(
                    detail=f"Team {action_type} limit exceeded. Used: {current_usage}/{limit}, "
                           f"Requested: {quantity}, Available: {remaining}",
                    headers={
                        "X-Usage-Type": action_type,
                        "X-Current-Usage": str(current_usage),
                        "X-Limit": str(limit),
                        "X-Available": str(remaining),
                        "X-Subscription-Tier": team_context.subscription_tier
                    }
                )
        
        return True
        
    except TeamUsageLimitError:
        raise
    except Exception as e:
        logger.error(f"Error validating team usage: {e}")
        raise TeamAuthenticationError("Failed to validate team usage limits")

async def record_team_usage(
    team_context: TeamContext,
    action_type: str,
    quantity: int = 1,
    db: AsyncSession = None,
    details: Dict[str, Any] = None
) -> bool:
    """
    Record usage for team's pooled limits
    
    Args:
        team_context: Team context from middleware
        action_type: Type of action ("profiles", "emails", "posts")
        quantity: How many units consumed
        db: Database session
        details: Additional details for tracking
    
    Returns:
        True if successful
    """
    try:
        if not db:
            logger.warning("No database session provided for usage recording")
            return False
        
        current_month = date.today().replace(day=1)
        
        # Update team-level usage counters
        if action_type == "profiles":
            await db.execute(
                f"UPDATE teams SET profiles_used_this_month = profiles_used_this_month + {quantity}, "
                f"updated_at = now() WHERE id = '{team_context.team_id}'"
            )
        elif action_type == "emails":
            await db.execute(
                f"UPDATE teams SET emails_used_this_month = emails_used_this_month + {quantity}, "
                f"updated_at = now() WHERE id = '{team_context.team_id}'"
            )
        elif action_type == "posts":
            await db.execute(
                f"UPDATE teams SET posts_used_this_month = posts_used_this_month + {quantity}, "
                f"updated_at = now() WHERE id = '{team_context.team_id}'"
            )
        
        # Update individual usage tracking
        usage_query = select(MonthlyUsageTracking).where(
            and_(
                MonthlyUsageTracking.team_id == team_context.team_id,
                MonthlyUsageTracking.user_id == team_context.user_id,
                MonthlyUsageTracking.billing_month == current_month
            )
        )
        result = await db.execute(usage_query)
        usage_record = result.scalar_one_or_none()
        
        if not usage_record:
            from uuid import uuid4
            usage_record = MonthlyUsageTracking(
                id=uuid4(),
                team_id=team_context.team_id,
                user_id=team_context.user_id,
                billing_month=current_month,
                profiles_analyzed=0,
                emails_unlocked=0,
                posts_analyzed=0
            )
            db.add(usage_record)
        
        # Update individual counters
        if action_type == "profiles":
            usage_record.profiles_analyzed += quantity
        elif action_type == "emails":
            usage_record.emails_unlocked += quantity
        elif action_type == "posts":
            usage_record.posts_analyzed += quantity
        
        usage_record.updated_at = datetime.now()
        
        await db.commit()
        
        logger.debug(f"Recorded {quantity} {action_type} usage for team {team_context.team_id} user {team_context.user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error recording team usage: {e}")
        try:
            await db.rollback()
        except:
            pass
        return False

# Convenience functions for specific permissions
async def get_team_owner_context(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> TeamContext:
    """Get team context and ensure user is team owner"""
    team_context = await get_team_context(current_user, db)
    if team_context.user_role != TeamRoles.OWNER:
        raise TeamPermissionError("This action requires team owner permissions")
    return team_context

async def get_any_team_member_context(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> TeamContext:
    """Get team context for any team member (owner or member)"""
    return await get_team_context(current_user, db)

def team_usage_gate(action_type: str, quantity: int = 1):
    """
    Decorator to validate team usage before endpoint execution
    Usage: @team_usage_gate("profiles", 1)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract team_context and db from kwargs
            team_context = None
            db = None
            
            for key, value in kwargs.items():
                if isinstance(value, TeamContext):
                    team_context = value
                elif hasattr(value, 'execute'):  # AsyncSession
                    db = value
            
            if not team_context:
                raise TeamAuthenticationError("Team context required for usage validation")
            
            # Validate usage limits
            await validate_team_usage(team_context, action_type, quantity, db)
            
            # Execute the endpoint
            result = await func(*args, **kwargs)
            
            # Record usage after successful execution
            await record_team_usage(team_context, action_type, quantity, db)
            
            return result
        return wrapper
    return decorator