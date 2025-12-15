"""
User Permission Service
Handles user permissions based on subscription tiers and platform features
"""
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging

from app.database.unified_models import User, CreditWallet, Team, TeamMember
from app.models.subscription import (
    SubscriptionTier, UserRole, BillingType,
    FeaturePermission, TIER_LIMITS
)

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for checking user permissions and feature access"""

    @staticmethod
    async def check_feature_access(
        db: AsyncSession,
        user_id: str,
        feature: FeaturePermission
    ) -> Dict[str, Any]:
        """
        Check if user has access to a specific feature

        Returns:
            {
                "has_access": bool,
                "reason": str,
                "tier_required": str (if no access),
                "user_tier": str
            }
        """
        # Get user and their subscription tier
        user = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()

        if not user:
            return {
                "has_access": False,
                "reason": "User not found",
                "user_tier": None
            }

        # SuperAdmin has access to everything
        if user.role == UserRole.SUPER_ADMIN:
            return {
                "has_access": True,
                "reason": "SuperAdmin has full access",
                "user_tier": "super_admin"
            }

        # Check feature access based on subscription tier
        tier = SubscriptionTier(user.subscription_tier)
        tier_limits = TIER_LIMITS.get(tier)

        if not tier_limits:
            return {
                "has_access": False,
                "reason": "Invalid subscription tier",
                "user_tier": user.subscription_tier
            }

        # Check specific feature permissions based on ACTUAL platform modules
        feature_access = {
            FeaturePermission.CREATOR_SEARCH: True,  # All tiers (includes AI analysis)
            FeaturePermission.POST_ANALYTICS: tier != SubscriptionTier.FREE,
            FeaturePermission.BULK_EXPORT: tier_limits.bulk_export_enabled,
            FeaturePermission.CAMPAIGN_MANAGEMENT: tier_limits.campaign_management_enabled,
            FeaturePermission.TEAM_MANAGEMENT: tier_limits.team_members > 1,
            FeaturePermission.DISCOVERY: True,  # All tiers (uses credits)
            FeaturePermission.API_ACCESS: tier_limits.api_calls_per_month is not None,
            FeaturePermission.EMAIL_UNLOCK: tier != SubscriptionTier.FREE,  # Standard+ can unlock emails
            FeaturePermission.LISTS_MANAGEMENT: tier_limits.lists_enabled
        }

        has_access = feature_access.get(feature, False)

        if not has_access:
            # Determine minimum tier required
            tier_required = None
            if feature in [FeaturePermission.POST_ANALYTICS, FeaturePermission.EMAIL_UNLOCK,
                          FeaturePermission.BULK_EXPORT, FeaturePermission.CAMPAIGN_MANAGEMENT,
                          FeaturePermission.LISTS_MANAGEMENT, FeaturePermission.API_ACCESS]:
                tier_required = "standard"

            return {
                "has_access": False,
                "reason": f"Feature requires {tier_required or 'higher'} tier",
                "tier_required": tier_required,
                "user_tier": user.subscription_tier
            }

        return {
            "has_access": True,
            "reason": "Feature available in current tier",
            "user_tier": user.subscription_tier
        }

    @staticmethod
    async def get_user_limits(
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get user's usage limits based on subscription tier
        """
        user = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()

        if not user:
            return {"error": "User not found"}

        # Check if user is part of a team
        team_member = await db.execute(
            select(TeamMember, Team).join(Team).where(
                and_(
                    TeamMember.user_id == user_id,
                    TeamMember.status == 'active'
                )
            )
        )
        team_data = team_member.first()

        # If user is in a team, use team limits
        if team_data:
            team = team_data[1]
            return {
                "source": "team",
                "team_name": team.name,
                "profiles_per_month": team.monthly_profile_limit,
                "emails_per_month": team.monthly_email_limit,
                "posts_per_month": team.monthly_posts_limit,
                "team_members": team.max_team_members,
                "profiles_used": team.profiles_used_this_month,
                "emails_used": team.emails_used_this_month,
                "posts_used": team.posts_used_this_month
            }

        # Use individual subscription limits
        tier = SubscriptionTier(user.subscription_tier)
        tier_limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])

        # Get usage from credit wallet
        wallet = await db.execute(
            select(CreditWallet).where(CreditWallet.user_id == user_id)
        )
        wallet = wallet.scalar_one_or_none()

        return {
            "source": "individual",
            "subscription_tier": user.subscription_tier,
            "profiles_per_month": tier_limits.profiles_per_month,
            "emails_per_month": tier_limits.emails_per_month,
            "posts_per_month": tier_limits.posts_per_month,
            "team_members": tier_limits.team_members,
            "api_calls_per_month": tier_limits.api_calls_per_month,
            "bulk_export_enabled": tier_limits.bulk_export_enabled,
            "campaign_management_enabled": tier_limits.campaign_management_enabled,
            "lists_enabled": tier_limits.lists_enabled,
            "current_balance": wallet.current_balance if wallet else 0,
            "credits_spent_this_month": wallet.total_spent_this_cycle if wallet else 0
        }

    @staticmethod
    async def get_all_user_permissions(
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive permission matrix for a user
        """
        user = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()

        if not user:
            return {"error": "User not found"}

        # Build permission matrix
        permissions = {}
        for feature in FeaturePermission:
            result = await PermissionService.check_feature_access(db, user_id, feature)
            permissions[feature.value] = {
                "enabled": result["has_access"],
                "reason": result.get("reason", "")
            }

        # Get usage limits
        limits = await PermissionService.get_user_limits(db, user_id)

        return {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "subscription_tier": user.subscription_tier,
            "billing_type": user.billing_type,
            "permissions": permissions,
            "limits": limits,
            "is_super_admin": user.role == UserRole.SUPER_ADMIN
        }

    @staticmethod
    async def can_user_perform_action(
        db: AsyncSession,
        user_id: str,
        action: str,
        resource_count: int = 1
    ) -> Dict[str, Any]:
        """
        Check if user can perform a specific action considering their limits

        Args:
            user_id: User ID
            action: Action type (profile_unlock, email_unlock, post_analysis)
            resource_count: Number of resources to consume

        Returns:
            {
                "can_perform": bool,
                "reason": str,
                "remaining": int (if applicable),
                "requires_credits": bool,
                "credit_cost": int
            }
        """
        limits = await PermissionService.get_user_limits(db, user_id)

        if "error" in limits:
            return {
                "can_perform": False,
                "reason": limits["error"]
            }

        # Define action to limit mapping
        action_limits = {
            "profile_unlock": ("profiles_per_month", "profiles_used", 25),  # 25 credits
            "email_unlock": ("emails_per_month", "emails_used", 1),  # 1 credit
            "post_analysis": ("posts_per_month", "posts_used", 5),  # 5 credits
        }

        if action not in action_limits:
            return {
                "can_perform": False,
                "reason": f"Unknown action: {action}"
            }

        limit_key, used_key, credit_cost = action_limits[action]

        # Check if within monthly limits
        monthly_limit = limits.get(limit_key, 0)
        monthly_used = limits.get(used_key, 0)
        remaining = monthly_limit - monthly_used

        if remaining >= resource_count:
            return {
                "can_perform": True,
                "reason": "Within monthly allowance",
                "remaining": remaining - resource_count,
                "requires_credits": False,
                "credit_cost": 0
            }

        # Check if user has enough credits
        credit_needed = credit_cost * resource_count
        current_balance = limits.get("current_balance", 0)

        if current_balance >= credit_needed:
            return {
                "can_perform": True,
                "reason": "Using credits",
                "remaining": 0,
                "requires_credits": True,
                "credit_cost": credit_needed
            }

        return {
            "can_perform": False,
            "reason": "Insufficient credits or monthly limit reached",
            "remaining": 0,
            "requires_credits": True,
            "credit_cost": credit_needed,
            "current_balance": current_balance
        }