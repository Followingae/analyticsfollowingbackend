"""
Brand User Access Control & Credit-Based Features
Advanced permission system for brand users with subscription tiers and credit gates
"""
from functools import wraps
from typing import Optional, List, Dict, Any, Union, Tuple
import logging
from fastapi import HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID
from datetime import datetime, date, timedelta

from app.models.auth import UserInDB
from app.database.connection import get_db
from app.database.unified_models import (
    Users, SubscriptionFeatures, UserLimits, FeatureUsageTracking,
    CreditWallets, CreditTransactions, UnlockedInfluencers, Profiles
)
from app.middleware.role_based_auth import (
    get_current_user_with_permissions, 
    auth_service,
    FeatureAccessError
)

logger = logging.getLogger(__name__)

class SubscriptionTiers:
    """Subscription tier constants - Updated structure"""
    FREE = "free"
    STANDARD = "standard"  # $199/month, 2 team members, 500 profiles, 250 emails, 125 posts
    PREMIUM = "premium"    # $499/month, 5 team members, 2000 profiles, 800 emails, 300 posts
    # Enterprise tier removed - only 3 tiers now

class CreditActions:
    """Monthly limit actions for subscription tiers"""
    PROFILE_ANALYSIS = ("profile_analysis", "Monthly profile analysis")
    EMAIL_UNLOCK = ("email_unlock", "Monthly email unlock")
    POST_ANALYTICS = ("post_analytics", "Monthly post analytics")
    # Export is included free for all paid tiers - no credits required
    # Topups available with discount for Premium tier

class BrandAccessControlService:
    """Advanced access control service for brand users"""
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes
        
    async def check_subscription_access(
        self,
        user_id: UUID,
        feature_name: str,
        db: AsyncSession,
        required_tier: str = None
    ) -> Dict[str, Any]:
        """Check if user's subscription tier allows feature access"""
        
        # Get user subscription info
        user_query = select(
            Users.subscription_tier,
            Users.subscription_expires_at,
            Users.account_status
        ).where(Users.id == user_id)
        
        user_result = await db.execute(user_query)
        user_data = user_result.first()
        
        if not user_data:
            return {
                "allowed": False,
                "reason": "User not found",
                "upgrade_required": None
            }
        
        # Check account status
        if user_data.account_status != "active":
            return {
                "allowed": False,
                "reason": f"Account status: {user_data.account_status}",
                "upgrade_required": None
            }
        
        # Check subscription expiration
        if (user_data.subscription_expires_at and 
            user_data.subscription_expires_at < datetime.utcnow()):
            return {
                "allowed": False,
                "reason": "Subscription expired",
                "upgrade_required": user_data.subscription_tier
            }
        
        # Check if specific tier is required
        if required_tier:
            tier_hierarchy = {
                SubscriptionTiers.FREE: 0,
                SubscriptionTiers.STANDARD: 1,
                SubscriptionTiers.PREMIUM: 2,
                SubscriptionTiers.BRAND_ENTERPRISE: 3
            }
            
            current_level = tier_hierarchy.get(user_data.subscription_tier, 0)
            required_level = tier_hierarchy.get(required_tier, 0)
            
            if current_level < required_level:
                return {
                    "allowed": False,
                    "reason": f"Requires {required_tier} or higher",
                    "upgrade_required": required_tier,
                    "current_tier": user_data.subscription_tier
                }
        
        # Check feature-specific subscription access
        feature_query = select(SubscriptionFeatures).where(
            and_(
                SubscriptionFeatures.subscription_tier == user_data.subscription_tier,
                SubscriptionFeatures.feature_name == feature_name
            )
        )
        
        feature_result = await db.execute(feature_query)
        feature = feature_result.scalar()
        
        if not feature:
            # Feature not defined for this tier - check if it's available in higher tiers
            higher_tier_query = select(SubscriptionFeatures.subscription_tier).where(
                SubscriptionFeatures.feature_name == feature_name
            ).order_by(SubscriptionFeatures.subscription_tier)
            
            higher_tier_result = await db.execute(higher_tier_query)
            available_tiers = [row[0] for row in higher_tier_result.all()]
            
            if available_tiers:
                return {
                    "allowed": False,
                    "reason": f"Feature not available in {user_data.subscription_tier}",
                    "upgrade_required": available_tiers[0],
                    "available_in": available_tiers
                }
            else:
                return {
                    "allowed": False,
                    "reason": "Feature not available",
                    "upgrade_required": None
                }
        
        if not feature.feature_enabled:
            return {
                "allowed": False,
                "reason": "Feature temporarily disabled",
                "upgrade_required": None
            }
        
        return {
            "allowed": True,
            "feature_limit": feature.feature_limit,
            "subscription_tier": user_data.subscription_tier
        }
    
    async def check_usage_limits(
        self,
        user_id: UUID,
        feature_name: str,
        db: AsyncSession,
        increment: int = 1
    ) -> Dict[str, Any]:
        """Check and enforce usage limits for features"""
        
        # Get feature subscription info
        subscription_access = await self.check_subscription_access(
            user_id, feature_name, db
        )
        
        if not subscription_access["allowed"]:
            return subscription_access
        
        feature_limit = subscription_access.get("feature_limit")
        
        # If unlimited (None), allow access
        if feature_limit is None:
            return {
                "allowed": True,
                "unlimited": True,
                "current_usage": 0,
                "limit": None
            }
        
        # Check current usage for the period (monthly)
        today = datetime.utcnow().date()
        month_start = today.replace(day=1)
        
        usage_query = select(
            func.sum(FeatureUsageTracking.usage_count)
        ).where(
            and_(
                FeatureUsageTracking.user_id == user_id,
                FeatureUsageTracking.feature_name == feature_name,
                FeatureUsageTracking.usage_date >= month_start
            )
        )
        
        usage_result = await db.execute(usage_query)
        current_usage = int(usage_result.scalar() or 0)
        
        # Check if usage would exceed limit
        if current_usage + increment > feature_limit:
            return {
                "allowed": False,
                "reason": f"Usage limit exceeded ({current_usage}/{feature_limit})",
                "current_usage": current_usage,
                "limit": feature_limit,
                "upgrade_required": self._get_next_tier(subscription_access["subscription_tier"])
            }
        
        return {
            "allowed": True,
            "current_usage": current_usage,
            "limit": feature_limit,
            "remaining": feature_limit - current_usage - increment
        }
    
    async def track_feature_usage(
        self,
        user_id: UUID,
        feature_name: str,
        db: AsyncSession,
        usage_count: int = 1,
        credits_spent: int = 0,
        session_id: str = None,
        details: Dict[str, Any] = None
    ):
        """Track feature usage for analytics and limit enforcement"""
        
        try:
            today = datetime.utcnow().date()
            
            # Check if usage record exists for today
            existing_usage_query = select(FeatureUsageTracking).where(
                and_(
                    FeatureUsageTracking.user_id == user_id,
                    FeatureUsageTracking.feature_name == feature_name,
                    FeatureUsageTracking.usage_date == today
                )
            )
            
            existing_result = await db.execute(existing_usage_query)
            existing_usage = existing_result.scalar()
            
            if existing_usage:
                # Update existing record
                existing_usage.usage_count += usage_count
                existing_usage.credits_spent += credits_spent
                if details:
                    existing_details = existing_usage.usage_details or {}
                    existing_details.update(details)
                    existing_usage.usage_details = existing_details
            else:
                # Create new record
                new_usage = FeatureUsageTracking(
                    user_id=user_id,
                    feature_name=feature_name,
                    usage_date=today,
                    usage_count=usage_count,
                    credits_spent=credits_spent,
                    session_id=session_id,
                    usage_details=details or {}
                )
                db.add(new_usage)
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to track feature usage: {e}")
            await db.rollback()
    
    async def check_credit_balance(
        self,
        user_id: UUID,
        required_credits: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Check if user has sufficient credits for an action"""
        
        # Get user's credit wallet
        wallet_query = select(CreditWallets).where(
            CreditWallets.user_id == user_id
        )
        
        wallet_result = await db.execute(wallet_query)
        wallet = wallet_result.scalar()
        
        if not wallet:
            return {
                "allowed": False,
                "reason": "Credit wallet not found",
                "current_balance": 0,
                "required": required_credits
            }
        
        if wallet.is_locked:
            return {
                "allowed": False,
                "reason": "Credit wallet is locked",
                "current_balance": wallet.balance,
                "required": required_credits
            }
        
        if wallet.balance < required_credits:
            return {
                "allowed": False,
                "reason": "Insufficient credits",
                "current_balance": wallet.balance,
                "required": required_credits,
                "needed": required_credits - wallet.balance
            }
        
        return {
            "allowed": True,
            "current_balance": wallet.balance,
            "required": required_credits,
            "remaining_after": wallet.balance - required_credits
        }
    
    async def spend_credits(
        self,
        user_id: UUID,
        amount: int,
        action_type: str,
        db: AsyncSession,
        description: str = None,
        resource_id: UUID = None
    ) -> Dict[str, Any]:
        """Spend credits and create transaction record"""
        
        try:
            # Get wallet
            wallet_query = select(CreditWallets).where(
                CreditWallets.user_id == user_id
            )
            
            wallet_result = await db.execute(wallet_query)
            wallet = wallet_result.scalar()
            
            if not wallet or wallet.balance < amount:
                return {
                    "success": False,
                    "reason": "Insufficient credits or wallet not found"
                }
            
            # Update wallet balance
            old_balance = wallet.balance
            wallet.balance -= amount
            wallet.total_spent_this_cycle += amount
            
            # Create transaction record
            transaction = CreditTransactions(
                user_id=user_id,
                wallet_id=wallet.id,
                transaction_type="spend",
                credits=-amount,  # Negative for spending
                description=description or f"Credits spent on {action_type}",
                reference_id=resource_id,
                metadata={"action_type": action_type}
            )
            
            db.add(transaction)
            await db.commit()
            
            return {
                "success": True,
                "old_balance": old_balance,
                "new_balance": wallet.balance,
                "amount_spent": amount,
                "transaction_id": str(transaction.id)
            }
            
        except Exception as e:
            logger.error(f"Failed to spend credits: {e}")
            await db.rollback()
            return {
                "success": False,
                "reason": f"Transaction failed: {str(e)}"
            }
    
    async def check_influencer_access(
        self,
        user_id: UUID,
        profile_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Check if user has access to specific influencer profile"""
        
        # Check if profile is already unlocked
        unlock_query = select(UnlockedInfluencers).where(
            and_(
                UnlockedInfluencers.user_id == user_id,
                UnlockedInfluencers.profile_id == profile_id
            )
        )
        
        unlock_result = await db.execute(unlock_query)
        unlock_record = unlock_result.scalar()
        
        if unlock_record:
            return {
                "allowed": True,
                "already_unlocked": True,
                "unlocked_at": unlock_record.unlocked_at,
                "access_level": unlock_record.access_level
            }
        
        # Check if profile requires premium access
        profile_query = select(
            Profiles.access_tier_required,
            Profiles.is_premium_content
        ).where(Profiles.id == profile_id)
        
        profile_result = await db.execute(profile_query)
        profile_data = profile_result.first()
        
        if not profile_data:
            return {
                "allowed": False,
                "reason": "Profile not found"
            }
        
        # If free access profile
        if (not profile_data.is_premium_content and 
            profile_data.access_tier_required == "free"):
            return {
                "allowed": True,
                "free_access": True,
                "access_level": "basic"
            }
        
        # For premium content, check subscription tier
        user_query = select(Users.subscription_tier).where(Users.id == user_id)
        user_result = await db.execute(user_query)
        user_tier = user_result.scalar()
        
        tier_hierarchy = {
            "free": 0,
            SubscriptionTiers.BRAND_FREE: 0,
            SubscriptionTiers.BRAND_STANDARD: 1,
            SubscriptionTiers.BRAND_PREMIUM: 2,
            SubscriptionTiers.BRAND_ENTERPRISE: 3
        }
        
        required_level = tier_hierarchy.get(profile_data.access_tier_required, 1)
        user_level = tier_hierarchy.get(user_tier, 0)
        
        if user_level < required_level:
            return {
                "allowed": False,
                "reason": f"Requires {profile_data.access_tier_required} subscription",
                "upgrade_required": profile_data.access_tier_required,
                "current_tier": user_tier
            }
        
        return {
            "allowed": True,
            "requires_credits": True,
            "credit_cost": CreditActions.INFLUENCER_UNLOCK[1],
            "access_level": "full"
        }
    
    def _get_next_tier(self, current_tier: str) -> str:
        """Get the next subscription tier for upgrade suggestions"""
        tier_upgrades = {
            SubscriptionTiers.BRAND_FREE: SubscriptionTiers.BRAND_STANDARD,
            SubscriptionTiers.BRAND_STANDARD: SubscriptionTiers.BRAND_PREMIUM,
            SubscriptionTiers.BRAND_PREMIUM: SubscriptionTiers.BRAND_ENTERPRISE,
            SubscriptionTiers.BRAND_ENTERPRISE: SubscriptionTiers.BRAND_ENTERPRISE
        }
        return tier_upgrades.get(current_tier, SubscriptionTiers.BRAND_PREMIUM)

# Global service instance
brand_access_service = BrandAccessControlService()

# Decorator Functions

def requires_subscription_tier(minimum_tier: str):
    """Decorator to require minimum subscription tier"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_id = UUID(current_user["id"])
            access_check = await brand_access_service.check_subscription_access(
                user_id, "tier_access", db, minimum_tier
            )
            
            if not access_check["allowed"]:
                raise FeatureAccessError(
                    detail=access_check["reason"],
                    upgrade_required=access_check.get("upgrade_required")
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def requires_feature_access(feature_name: str, track_usage: bool = True):
    """Decorator to require feature access and optionally track usage"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            request = kwargs.get("request")
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_id = UUID(current_user["id"])
            
            # Check subscription access
            subscription_check = await brand_access_service.check_subscription_access(
                user_id, feature_name, db
            )
            
            if not subscription_check["allowed"]:
                raise FeatureAccessError(
                    detail=subscription_check["reason"],
                    upgrade_required=subscription_check.get("upgrade_required")
                )
            
            # Check usage limits
            usage_check = await brand_access_service.check_usage_limits(
                user_id, feature_name, db
            )
            
            if not usage_check["allowed"]:
                raise FeatureAccessError(
                    detail=usage_check["reason"],
                    upgrade_required=usage_check.get("upgrade_required")
                )
            
            # Execute the function
            try:
                result = await func(*args, **kwargs)
                
                # Track usage if successful and requested
                if track_usage:
                    session_id = request.headers.get("x-session-id") if request else None
                    await brand_access_service.track_feature_usage(
                        user_id, feature_name, db, session_id=session_id
                    )
                
                return result
                
            except Exception as e:
                # Don't track usage on failure
                raise e
        
        return wrapper
    return decorator

def requires_credits(action_name: str, credit_cost: int = None):
    """Decorator to require credit spending for actions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_id = UUID(current_user["id"])
            
            # Get credit cost (from parameter or predefined action)
            if credit_cost is None:
                # Look up predefined action cost
                action_costs = {
                    name: cost for name, cost in [
                        CreditActions.INFLUENCER_UNLOCK,
                        CreditActions.POST_ANALYTICS,
                        CreditActions.DISCOVERY_PAGINATION,
                        CreditActions.BULK_EXPORT,
                        CreditActions.ADVANCED_SEARCH,
                        CreditActions.CONTACT_INFO_ACCESS,
                        CreditActions.HISTORICAL_DATA,
                        CreditActions.COMPETITOR_ANALYSIS
                    ]
                }
                required_credits = action_costs.get(action_name, 0)
            else:
                required_credits = credit_cost
            
            if required_credits <= 0:
                # No credits required, just execute
                return await func(*args, **kwargs)
            
            # Check credit balance
            balance_check = await brand_access_service.check_credit_balance(
                user_id, required_credits, db
            )
            
            if not balance_check["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=balance_check["reason"],
                    headers={
                        "X-Credit-Balance": str(balance_check["current_balance"]),
                        "X-Credits-Required": str(required_credits),
                        "X-Credits-Needed": str(balance_check.get("needed", 0))
                    }
                )
            
            # Execute function first (to ensure success before spending credits)
            try:
                result = await func(*args, **kwargs)
                
                # Only spend credits after successful execution
                spend_result = await brand_access_service.spend_credits(
                    user_id, required_credits, action_name, db,
                    f"Credits spent on {action_name}"
                )
                
                if not spend_result["success"]:
                    logger.error(f"Failed to spend credits after successful action: {spend_result}")
                    # Don't fail the request, but log the issue
                
                # Add credit info to response headers if possible
                if hasattr(result, "headers"):
                    result.headers["X-Credits-Spent"] = str(required_credits)
                    result.headers["X-New-Balance"] = str(spend_result.get("new_balance", 0))
                
                return result
                
            except Exception as e:
                # Don't spend credits on failure
                raise e
        
        return wrapper
    return decorator

def requires_influencer_access(profile_param: str = "profile_id"):
    """Decorator to check access to specific influencer profile"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_id = UUID(current_user["id"])
            profile_id = kwargs.get(profile_param)
            
            if not profile_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing {profile_param} parameter"
                )
            
            # Convert to UUID if needed
            if isinstance(profile_id, str):
                profile_id = UUID(profile_id)
            
            # Check influencer access
            access_check = await brand_access_service.check_influencer_access(
                user_id, profile_id, db
            )
            
            if not access_check["allowed"]:
                raise FeatureAccessError(
                    detail=access_check["reason"],
                    upgrade_required=access_check.get("upgrade_required")
                )
            
            # If credits required, check and spend
            if access_check.get("requires_credits"):
                credit_cost = access_check.get("credit_cost", 0)
                
                balance_check = await brand_access_service.check_credit_balance(
                    user_id, credit_cost, db
                )
                
                if not balance_check["allowed"]:
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail=balance_check["reason"],
                        headers={
                            "X-Credit-Balance": str(balance_check["current_balance"]),
                            "X-Credits-Required": str(credit_cost)
                        }
                    )
                
                # Execute function and spend credits on success
                result = await func(*args, **kwargs)
                
                spend_result = await brand_access_service.spend_credits(
                    user_id, credit_cost, "influencer_unlock", db,
                    f"Unlocked influencer profile {profile_id}",
                    profile_id
                )
                
                # Create unlock record
                unlock_record = UnlockedInfluencers(
                    user_id=user_id,
                    profile_id=profile_id,
                    access_level="full",
                    credits_spent=credit_cost
                )
                db.add(unlock_record)
                await db.commit()
                
                return result
            
            # Free access, just execute
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator