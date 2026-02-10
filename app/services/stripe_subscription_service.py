"""
Stripe Subscription Service - Complete subscription management
Handles subscriptions, billing cycles, upgrades/downgrades, and integration with credit system
"""
import logging
import os
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.database.connection import get_session
from app.database.unified_models import User, CreditWallet, Team
from app.models.teams import SUBSCRIPTION_TIER_LIMITS
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class StripeSubscriptionService:
    """
    Complete Stripe subscription management service
    """

    def __init__(self):
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
        if not self.stripe_secret_key:
            raise ValueError("STRIPE_SECRET_KEY environment variable is required")

        # Price IDs from environment (using monthly subscription prices)
        self.price_ids = {
            'free': os.getenv('STRIPE_FREE_MONTHLY_PRICE_ID'),
            'standard': os.getenv('STRIPE_STANDARD_MONTHLY_PRICE_ID'),
            'premium': os.getenv('STRIPE_PREMIUM_MONTHLY_PRICE_ID')
        }

        self.topup_price_ids = {
            'starter': os.getenv('STRIPE_STARTER_TOPUP_PRICE_ID'),
            'professional': os.getenv('STRIPE_PROFESSIONAL_TOPUP_PRICE_ID'),
            'enterprise': os.getenv('STRIPE_ENTERPRISE_TOPUP_PRICE_ID')
        }

    # =========================================================================
    # CUSTOMER MANAGEMENT
    # =========================================================================

    async def create_customer_for_user(self, user_id: UUID, email: str, name: str = None) -> Dict:
        """Create a Stripe customer for a user"""
        try:
            # Check if customer already exists
            existing_customer = await self.get_customer_by_user(user_id)
            if existing_customer:
                return existing_customer

            from app.services.stripe_service import stripe_service
            customer = stripe_service.create_customer(
                email=email,
                name=name,
                metadata={
                    'user_id': str(user_id),
                    'platform': 'analytics_following'
                }
            )

            # Store customer ID in database
            async with get_session() as session:
                result = await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(stripe_customer_id=customer['id'])
                )
                await session.commit()

            logger.info(f"Created Stripe customer {customer['id']} for user {user_id}")
            return customer

        except Exception as e:
            logger.error(f"Error creating Stripe customer for user {user_id}: {e}")
            raise

    async def get_customer_by_user(self, user_id: UUID) -> Optional[Dict]:
        """Get Stripe customer for a user"""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(User.stripe_customer_id)
                    .where(User.id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user or not user.stripe_customer_id:
                    return None

                from app.services.stripe_service import stripe_service
                return stripe_service._make_request("GET", f"customers/{user.stripe_customer_id}")

        except Exception as e:
            logger.error(f"Error getting customer for user {user_id}: {e}")
            return None

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def create_subscription(self, user_id: UUID, tier: str, trial_days: int = None) -> Dict:
        """Create a subscription for a user"""
        try:
            # Get or create customer
            async with get_session() as session:
                result = await session.execute(
                    select(User)
                    .where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    raise ValidationError("User not found")

            customer = await self.get_customer_by_user(user_id)
            if not customer:
                customer = await self.create_customer_for_user(
                    user_id, user.email, user.full_name
                )

            # Get price ID for tier
            price_id = self.price_ids.get(tier)
            if not price_id:
                raise ValidationError(f"Invalid subscription tier: {tier}")

            # Create subscription
            from app.services.stripe_service import stripe_service
            subscription = stripe_service.create_subscription(
                customer_id=customer['id'],
                price_id=price_id,
                trial_period_days=trial_days,
                metadata={
                    'user_id': str(user_id),
                    'tier': tier,
                    'platform': 'analytics_following'
                }
            )

            # Update user's subscription info
            await self.update_user_subscription_from_stripe(user_id, subscription)

            logger.info(f"Created {tier} subscription {subscription['id']} for user {user_id}")
            return subscription

        except Exception as e:
            logger.error(f"Error creating subscription for user {user_id}: {e}")
            raise

    async def get_user_subscription(self, user_id: UUID) -> Optional[Dict]:
        """Get user's active subscription from Stripe"""
        try:
            customer = await self.get_customer_by_user(user_id)
            if not customer:
                return None

            from app.services.stripe_service import stripe_service
            subscriptions = stripe_service.list_customer_subscriptions(customer['id'])

            # Return the first active subscription
            for subscription in subscriptions.get('data', []):
                if subscription['status'] in ['active', 'trialing']:
                    return subscription

            return None

        except Exception as e:
            logger.error(f"Error getting subscription for user {user_id}: {e}")
            return None

    async def update_user_subscription_from_stripe(self, user_id: UUID, subscription: Dict):
        """Update user's subscription data from Stripe subscription"""
        try:
            # Extract subscription data
            status = subscription['status']
            current_period_start = datetime.fromtimestamp(subscription['current_period_start'])
            current_period_end = datetime.fromtimestamp(subscription['current_period_end'])

            # Determine tier from price ID
            tier = 'free'
            price_id = subscription['items']['data'][0]['price']['id']
            for t, pid in self.price_ids.items():
                if pid == price_id:
                    tier = t
                    break

            # Update user record
            async with get_session() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        subscription_tier=tier,
                        subscription_status=status,
                        stripe_subscription_id=subscription['id']
                    )
                )

                # Update credit wallet with new billing cycle
                await session.execute(
                    update(CreditWallet)
                    .where(CreditWallet.user_id == user_id)
                    .values(
                        current_billing_cycle_start=current_period_start.date(),
                        current_billing_cycle_end=current_period_end,
                        next_reset_date=current_period_end.date(),
                        subscription_status=status,
                        subscription_active=status in ['active', 'trialing']
                    )
                )

                await session.commit()

            logger.info(f"Updated user {user_id} subscription data: {tier} ({status})")

        except Exception as e:
            logger.error(f"Error updating user subscription data: {e}")
            raise

    # =========================================================================
    # SUBSCRIPTION CHANGES
    # =========================================================================

    async def upgrade_subscription(self, user_id: UUID, new_tier: str) -> Dict:
        """Upgrade user's subscription"""
        try:
            # Get current subscription
            current_subscription = await self.get_user_subscription(user_id)
            if not current_subscription:
                # Create new subscription
                return await self.create_subscription(user_id, new_tier)

            # Get new price ID
            new_price_id = self.price_ids.get(new_tier)
            if not new_price_id:
                raise ValidationError(f"Invalid subscription tier: {new_tier}")

            # Update subscription
            from app.services.stripe_service import stripe_service
            updated_subscription = stripe_service._make_request(
                "POST",
                f"subscriptions/{current_subscription['id']}",
                {
                    "items[0][id]": current_subscription['items']['data'][0]['id'],
                    "items[0][price]": new_price_id,
                    "proration_behavior": "create_prorations"
                }
            )

            # Update local data
            await self.update_user_subscription_from_stripe(user_id, updated_subscription)

            logger.info(f"Upgraded user {user_id} subscription to {new_tier}")
            return updated_subscription

        except Exception as e:
            logger.error(f"Error upgrading subscription for user {user_id}: {e}")
            raise

    async def downgrade_subscription(self, user_id: UUID, new_tier: str) -> Dict:
        """Downgrade user's subscription at period end"""
        try:
            current_subscription = await self.get_user_subscription(user_id)
            if not current_subscription:
                raise ValidationError("No active subscription found")

            new_price_id = self.price_ids.get(new_tier)
            if not new_price_id:
                raise ValidationError(f"Invalid subscription tier: {new_tier}")

            # Schedule downgrade at period end
            from app.services.stripe_service import stripe_service
            updated_subscription = stripe_service._make_request(
                "POST",
                f"subscriptions/{current_subscription['id']}",
                {
                    "items[0][id]": current_subscription['items']['data'][0]['id'],
                    "items[0][price]": new_price_id,
                    "proration_behavior": "none"
                }
            )

            logger.info(f"Scheduled downgrade for user {user_id} to {new_tier} at period end")
            return updated_subscription

        except Exception as e:
            logger.error(f"Error downgrading subscription for user {user_id}: {e}")
            raise

    async def cancel_subscription(self, user_id: UUID, at_period_end: bool = True) -> Dict:
        """Cancel user's subscription"""
        try:
            subscription = await self.get_user_subscription(user_id)
            if not subscription:
                raise ValidationError("No active subscription found")

            from app.services.stripe_service import stripe_service
            cancelled_subscription = stripe_service.cancel_subscription(
                subscription['id'],
                at_period_end=at_period_end
            )

            if not at_period_end:
                # Update user immediately
                await self.update_user_subscription_from_stripe(user_id, cancelled_subscription)

            logger.info(f"Cancelled subscription for user {user_id}")
            return cancelled_subscription

        except Exception as e:
            logger.error(f"Error cancelling subscription for user {user_id}: {e}")
            raise

    # =========================================================================
    # TOPUP MANAGEMENT
    # =========================================================================

    async def create_topup_payment_link(self, user_id: UUID, topup_type: str) -> Dict:
        """Create a payment link for credit topup"""
        try:
            price_id = self.topup_price_ids.get(topup_type)
            if not price_id:
                raise ValidationError(f"Invalid topup type: {topup_type}")

            # Get credit amounts
            credit_amounts = {
                'starter': 1000,
                'professional': 2500,
                'enterprise': 10000
            }

            customer = await self.get_customer_by_user(user_id)

            from app.services.stripe_service import stripe_service
            payment_link = stripe_service._make_request(
                "POST",
                "payment_links",
                {
                    "line_items[0][price]": price_id,
                    "line_items[0][quantity]": 1,
                    "metadata[user_id]": str(user_id),
                    "metadata[topup_type]": topup_type,
                    "metadata[credits]": credit_amounts[topup_type],
                    "after_completion[type]": "redirect",
                    "after_completion[redirect][url]": f"{os.getenv('FRONTEND_URL', 'https://analytics.following.ae')}/billing?topup=success"
                }
            )

            logger.info(f"Created topup payment link for user {user_id}: {topup_type}")
            return payment_link

        except Exception as e:
            logger.error(f"Error creating topup payment link: {e}")
            raise

    # =========================================================================
    # BILLING INFORMATION
    # =========================================================================

    async def get_billing_summary(self, user_id: UUID) -> Dict:
        """Get comprehensive billing summary for user"""
        try:
            # Get subscription data
            subscription = await self.get_user_subscription(user_id)

            # Get customer data
            customer = await self.get_customer_by_user(user_id)

            # Get user's current tier and limits
            async with get_session() as session:
                result = await session.execute(
                    select(User, CreditWallet)
                    .join(CreditWallet, User.id == CreditWallet.user_id, isouter=True)
                    .where(User.id == user_id)
                )
                user_data = result.first()

            if not user_data:
                raise ValidationError("User not found")

            user, wallet = user_data

            # Get tier limits
            tier = user.subscription_tier or 'free'
            tier_limits = SUBSCRIPTION_TIER_LIMITS.get(tier, SUBSCRIPTION_TIER_LIMITS['free'])

            billing_summary = {
                'subscription': {
                    'tier': tier,
                    'status': subscription['status'] if subscription else 'inactive',
                    'current_period_start': subscription['current_period_start'] if subscription else None,
                    'current_period_end': subscription['current_period_end'] if subscription else None,
                    'cancel_at_period_end': subscription.get('cancel_at_period_end', False) if subscription else False,
                    'trial_end': subscription.get('trial_end') if subscription else None
                },
                'customer': {
                    'stripe_customer_id': customer['id'] if customer else None,
                    'email': customer['email'] if customer else user.email
                },
                'limits': tier_limits,
                'current_usage': {
                    'credits_used_this_cycle': wallet.total_spent_this_cycle if wallet else 0,
                    'credits_remaining': wallet.current_balance if wallet else 0
                },
                'billing_cycle': {
                    'start': wallet.current_billing_cycle_start.isoformat() if wallet and wallet.current_billing_cycle_start else None,
                    'end': wallet.current_billing_cycle_end.isoformat() if wallet and wallet.current_billing_cycle_end else None,
                    'next_reset': wallet.next_reset_date.isoformat() if wallet and wallet.next_reset_date else None
                }
            }

            return billing_summary

        except Exception as e:
            logger.error(f"Error getting billing summary for user {user_id}: {e}")
            raise

# Global service instance
stripe_subscription_service = StripeSubscriptionService()