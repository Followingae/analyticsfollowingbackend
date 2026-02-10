"""
User Subscription Management Service
Handles subscription tiers, billing cycles, and credit allocation
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload

from app.database.connection import get_session
from app.database.unified_models import User, CreditWallet, CreditPackage
from app.models.auth import UserRole
from app.services.credit_wallet_service import CreditWalletService

logger = logging.getLogger(__name__)


class UserSubscriptionService:
    """
    Comprehensive subscription and billing management
    """

    # Credit allocations based on subscription tier
    TIER_CREDITS = {
        "free": {
            "monthly_credits": 125,  # 5 profiles * 25 credits
            "profile_unlocks": 5,
            "email_unlocks": 0,
            "post_analytics": 0
        },
        "standard": {
            "monthly_credits": 12500,  # 500 profiles * 25 credits
            "profile_unlocks": 500,
            "email_unlocks": 250,
            "post_analytics": 125
        },
        "premium": {
            "monthly_credits": 50000,  # 2000 profiles * 25 credits
            "profile_unlocks": 2000,
            "email_unlocks": 800,
            "post_analytics": 300
        }
    }

    def __init__(self):
        self.wallet_service = CreditWalletService()

    async def setup_user_subscription(
        self,
        user_id: UUID,
        subscription_tier: str = "free",
        billing_type: str = "admin_managed",
        initial_billing_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Set up subscription and credits for a new user

        Args:
            user_id: User UUID
            subscription_tier: free, standard, or premium
            billing_type: admin_managed or online_payment
            initial_billing_date: Start of billing cycle (defaults to today)

        Returns:
            Dictionary with subscription setup details
        """
        try:
            if initial_billing_date is None:
                initial_billing_date = date.today()

            # Get tier configuration
            tier_config = self.TIER_CREDITS.get(subscription_tier.lower(), self.TIER_CREDITS["free"])

            async with get_session() as session:
                # Update user's subscription tier
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        subscription_tier=subscription_tier,
                        billing_type=billing_type,
                        updated_at=datetime.utcnow()
                    )
                )

                # Check if wallet exists
                wallet_result = await session.execute(
                    select(CreditWallet).where(CreditWallet.user_id == user_id)
                )
                wallet = wallet_result.scalar_one_or_none()

                if not wallet:
                    # Create new wallet with tier-based credits
                    wallet = CreditWallet(
                        user_id=user_id,
                        current_balance=tier_config["monthly_credits"],
                        total_earned_this_cycle=tier_config["monthly_credits"],
                        current_billing_cycle_start=initial_billing_date,
                        current_billing_cycle_end=initial_billing_date + timedelta(days=30),
                        next_reset_date=initial_billing_date + timedelta(days=30),
                        subscription_status="active",
                        auto_refresh_enabled=True
                    )
                    session.add(wallet)
                else:
                    # Update existing wallet
                    wallet.current_balance = tier_config["monthly_credits"]
                    wallet.total_earned_this_cycle = tier_config["monthly_credits"]
                    wallet.current_billing_cycle_start = initial_billing_date
                    wallet.current_billing_cycle_end = initial_billing_date + timedelta(days=30)
                    wallet.next_reset_date = initial_billing_date + timedelta(days=30)
                    wallet.updated_at = datetime.utcnow()

                await session.commit()

                return {
                    "success": True,
                    "subscription_tier": subscription_tier,
                    "billing_type": billing_type,
                    "credits_allocated": tier_config["monthly_credits"],
                    "billing_cycle_start": initial_billing_date.isoformat(),
                    "billing_cycle_end": (initial_billing_date + timedelta(days=30)).isoformat(),
                    "next_billing_date": (initial_billing_date + timedelta(days=30)).isoformat(),
                    "tier_benefits": tier_config
                }

        except Exception as e:
            logger.error(f"Failed to setup user subscription: {e}")
            raise

    async def get_user_billing_info(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive billing information for a user

        Args:
            user_id: User UUID

        Returns:
            Dictionary with billing details
        """
        try:
            async with get_session() as session:
                # First get the user to find their auth ID
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()

                if not user:
                    raise ValueError(f"User {user_id} not found")

                # Get the auth.users ID for this user
                auth_user_query = text("""
                    SELECT id FROM auth.users WHERE email = :email
                """)
                auth_result = await session.execute(auth_user_query, {"email": user.email})
                auth_user = auth_result.fetchone()
                auth_user_id = auth_user.id if auth_user else None

                # Now get the wallet using auth.users ID
                wallet = None
                if auth_user_id:
                    wallet_result = await session.execute(
                        select(CreditWallet).where(CreditWallet.user_id == auth_user_id)
                    )
                    wallet = wallet_result.scalar_one_or_none()

                # Format result as tuple for compatibility
                result = await session.execute(
                    select(User, CreditWallet)
                    .outerjoin(CreditWallet, CreditWallet.user_id == auth_user_id)
                    .where(User.id == user_id)
                )
                user_wallet = result.first()

                if not user_wallet:
                    raise ValueError(f"User {user_id} not found")

                user, wallet = user_wallet

                # Calculate days until next billing
                days_until_billing = None
                if wallet and wallet.next_reset_date:
                    days_until_billing = (wallet.next_reset_date - date.today()).days

                # Get tier configuration
                tier_config = self.TIER_CREDITS.get(
                    user.subscription_tier.lower() if user.subscription_tier else "free",
                    self.TIER_CREDITS["free"]
                )

                return {
                    "user_id": str(user_id),
                    "email": user.email,
                    "subscription_tier": user.subscription_tier or "free",
                    "billing_type": user.billing_type,
                    "current_balance": wallet.current_balance if wallet else 0,
                    "monthly_allowance": tier_config["monthly_credits"],
                    "billing_cycle_start": wallet.current_billing_cycle_start.isoformat() if wallet and wallet.current_billing_cycle_start else None,
                    "billing_cycle_end": wallet.current_billing_cycle_end.isoformat() if wallet and wallet.current_billing_cycle_end else None,
                    "next_billing_date": wallet.next_reset_date.isoformat() if wallet and wallet.next_reset_date else None,
                    "days_until_billing": days_until_billing,
                    "subscription_active": wallet.subscription_status == "active" if wallet else False,
                    "tier_benefits": tier_config
                }

        except Exception as e:
            logger.error(f"Failed to get user billing info: {e}")
            raise

    async def get_all_users_billing(
        self,
        billing_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get billing information for all users (admin view)

        Args:
            billing_type: Filter by billing type (admin_managed or online_payment)
            page: Page number
            page_size: Results per page

        Returns:
            Dictionary with paginated billing data
        """
        try:
            async with get_session() as session:
                # Build query
                query = select(User, CreditWallet).outerjoin(
                    CreditWallet, CreditWallet.user_id == User.id
                )

                if billing_type:
                    query = query.where(User.billing_type == billing_type)

                # Add pagination
                offset = (page - 1) * page_size
                query = query.offset(offset).limit(page_size)

                # Execute query
                result = await session.execute(query)
                users_billing = result.all()

                # Format results
                billing_list = []
                for user, wallet in users_billing:
                    days_until_billing = None
                    if wallet and wallet.next_reset_date:
                        days_until_billing = (wallet.next_reset_date - date.today()).days

                    billing_list.append({
                        "user_id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                        "subscription_tier": user.subscription_tier or "free",
                        "billing_type": user.billing_type,
                        "status": user.status,
                        "current_balance": wallet.current_balance if wallet else 0,
                        "next_billing_date": wallet.next_reset_date.isoformat() if wallet and wallet.next_reset_date else None,
                        "days_until_billing": days_until_billing,
                        "billing_cycle_start": wallet.current_billing_cycle_start.isoformat() if wallet and wallet.current_billing_cycle_start else None,
                        "subscription_active": wallet.subscription_status == "active" if wallet else False,
                        "created_at": user.created_at.isoformat() if user.created_at else None
                    })

                # Get total count
                count_query = select(User)
                if billing_type:
                    count_query = count_query.where(User.billing_type == billing_type)

                count_result = await session.execute(select(text("COUNT(*)")).select_from(count_query.subquery()))
                total_count = count_result.scalar() or 0

                return {
                    "users": billing_list,
                    "total_count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size
                }

        except Exception as e:
            logger.error(f"Failed to get all users billing: {e}")
            raise

    async def update_billing_cycle(
        self,
        user_id: UUID,
        new_billing_date: date
    ) -> Dict[str, Any]:
        """
        Update billing cycle for admin-managed user

        Args:
            user_id: User UUID
            new_billing_date: New billing cycle start date

        Returns:
            Updated billing information
        """
        try:
            async with get_session() as session:
                # Get wallet
                result = await session.execute(
                    select(CreditWallet).where(CreditWallet.user_id == user_id)
                )
                wallet = result.scalar_one_or_none()

                if not wallet:
                    raise ValueError(f"No wallet found for user {user_id}")

                # Update billing cycle
                wallet.current_billing_cycle_start = new_billing_date
                wallet.current_billing_cycle_end = new_billing_date + timedelta(days=30)
                wallet.next_reset_date = new_billing_date + timedelta(days=30)
                wallet.updated_at = datetime.utcnow()

                await session.commit()

                return {
                    "success": True,
                    "billing_cycle_start": new_billing_date.isoformat(),
                    "billing_cycle_end": (new_billing_date + timedelta(days=30)).isoformat(),
                    "next_billing_date": (new_billing_date + timedelta(days=30)).isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to update billing cycle: {e}")
            raise