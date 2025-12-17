"""
Stripe Billing Service - Complete subscription and payment management
"""
import stripe
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
import os
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.unified_models import User
from app.models.auth import BillingType

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Product/Price mapping from Stripe dashboard with monthly and annual options
STRIPE_PRODUCTS = {
    "free": {
        "name": "Analytics Following Starter",
        "monthly": {
            "price_id": os.getenv("STRIPE_FREE_MONTHLY_PRICE_ID", "price_1Sf1loAubhSg1bPI00UODTEY"),
            "amount": 0,
            "interval": "month"
        },
        "credits": 125
    },
    "standard": {
        "name": "Analytics Following Professional",
        "monthly": {
            "price_id": os.getenv("STRIPE_STANDARD_MONTHLY_PRICE_ID", "price_1Sf1lpAubhSg1bPIiTWvBncS"),
            "amount": 199,
            "interval": "month"
        },
        "annual": {
            "price_id": os.getenv("STRIPE_STANDARD_ANNUAL_PRICE_ID", "price_1SfDzAAubhSg1bPIwl0bIgs8"),
            "amount": 1908,  # $159/month when paid annually
            "interval": "year",
            "savings": 480  # Save $480/year
        },
        "credits": 500
    },
    "premium": {
        "name": "Analytics Following Enterprise",
        "monthly": {
            "price_id": os.getenv("STRIPE_PREMIUM_MONTHLY_PRICE_ID", "price_1Sf1lqAubhSg1bPIJIcqgHu1"),
            "amount": 499,
            "interval": "month"
        },
        "annual": {
            "price_id": os.getenv("STRIPE_PREMIUM_ANNUAL_PRICE_ID", "price_1SfDzLAubhSg1bPIuSB7Tz5R"),
            "amount": 4788,  # $399/month when paid annually
            "interval": "year",
            "savings": 1200  # Save $1,200/year
        },
        "credits": 2000,
        "topup_discount": 0.20  # 20% discount on credit topups
    }
}

class StripeBillingService:
    """Handle all Stripe billing operations"""

    def __init__(self):
        self.stripe = stripe
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    async def create_customer(self, user_email: str, user_name: str, user_id: str) -> str:
        """Create a Stripe customer for a new user"""
        try:
            customer = stripe.Customer.create(
                email=user_email,
                name=user_name,
                metadata={
                    "user_id": user_id,
                    "platform": "analytics_following"
                }
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create billing profile: {str(e)}"
            )

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        user_id: str,
        subscription_tier: str,
        billing_interval: str = "monthly"  # "monthly" or "annual"
    ) -> Dict[str, Any]:
        """Create embedded checkout session for subscription"""
        try:
            # Create checkout session for embedded iframe
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                ui_mode='embedded',  # For iframe integration
                return_url=success_url,  # Required for embedded mode
                metadata={
                    'user_id': user_id,
                    'subscription_tier': subscription_tier
                },
                subscription_data={
                    'metadata': {
                        'user_id': user_id,
                        'subscription_tier': subscription_tier
                    }
                },
                # Allow promotion codes
                allow_promotion_codes=True,
                # Collect billing address
                billing_address_collection='required',
                # Save payment method for future use
                payment_intent_data={
                    'setup_future_usage': 'off_session'
                }
            )

            logger.info(f"Created checkout session {session.id} for user {user_id}")

            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "client_secret": session.client_secret,  # For embedded checkout
                "expires_at": datetime.fromtimestamp(session.expires_at, tz=timezone.utc).isoformat()
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create checkout session: {str(e)}"
            )

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> Dict[str, Any]:
        """Create customer portal session for subscription management"""
        try:
            # Create portal session for subscription management
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )

            logger.info(f"Created portal session for customer {customer_id}")

            return {
                "portal_url": session.url,
                "session_id": session.id
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal session: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create portal session: {str(e)}"
            )

    async def get_subscription(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get active subscription for customer"""
        try:
            # List all subscriptions for customer
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='active',
                limit=1
            )

            if not subscriptions.data:
                return None

            sub = subscriptions.data[0]

            return {
                "subscription_id": sub.id,
                "status": sub.status,
                "current_period_start": datetime.fromtimestamp(sub.current_period_start, tz=timezone.utc).isoformat(),
                "current_period_end": datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat(),
                "cancel_at_period_end": sub.cancel_at_period_end,
                "items": [
                    {
                        "price_id": item.price.id,
                        "product_id": item.price.product,
                        "amount": item.price.unit_amount,
                        "currency": item.price.currency,
                        "interval": item.price.recurring.interval if item.price.recurring else None
                    }
                    for item in sub.items.data
                ]
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting subscription: {e}")
            return None

    async def cancel_subscription(self, subscription_id: str, immediate: bool = False) -> Dict[str, Any]:
        """Cancel subscription immediately or at period end"""
        try:
            if immediate:
                # Cancel immediately
                sub = stripe.Subscription.cancel(subscription_id)
            else:
                # Cancel at period end
                sub = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )

            logger.info(f"Cancelled subscription {subscription_id} (immediate={immediate})")

            return {
                "subscription_id": sub.id,
                "status": sub.status,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "canceled_at": datetime.fromtimestamp(sub.canceled_at, tz=timezone.utc).isoformat() if sub.canceled_at else None,
                "current_period_end": datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat()
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to cancel subscription: {str(e)}"
            )

    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )

            logger.info(f"Processing webhook event: {event['type']}")

            # Handle different event types
            if event['type'] == 'checkout.session.completed':
                # Payment successful, provision subscription
                session = event['data']['object']
                await self._handle_checkout_completed(session)

            elif event['type'] == 'customer.subscription.created':
                # New subscription created
                subscription = event['data']['object']
                await self._handle_subscription_created(subscription)

            elif event['type'] == 'customer.subscription.updated':
                # Subscription updated (upgrade/downgrade)
                subscription = event['data']['object']
                await self._handle_subscription_updated(subscription)

            elif event['type'] == 'customer.subscription.deleted':
                # Subscription cancelled/expired
                subscription = event['data']['object']
                await self._handle_subscription_deleted(subscription)

            elif event['type'] == 'invoice.payment_succeeded':
                # Recurring payment successful
                invoice = event['data']['object']
                await self._handle_payment_succeeded(invoice)

            elif event['type'] == 'invoice.payment_failed':
                # Payment failed
                invoice = event['data']['object']
                await self._handle_payment_failed(invoice)

            return {"status": "success", "event": event['type']}

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Webhook processing failed: {str(e)}"
            )

    async def _handle_checkout_completed(self, session: Dict[str, Any]):
        """Handle successful checkout"""
        from app.database.connection import SessionLocal

        user_id = session['metadata'].get('user_id')
        subscription_id = session['subscription']
        customer_id = session['customer']

        logger.info(f"Checkout completed for user {user_id}, subscription {subscription_id}")

        # Update user in database
        async with SessionLocal() as db:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    subscription_status='active',
                    subscription_activated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

    async def _handle_subscription_created(self, subscription: Dict[str, Any]):
        """Handle new subscription creation"""
        from app.database.connection import SessionLocal

        user_id = subscription['metadata'].get('user_id')
        tier = subscription['metadata'].get('subscription_tier')

        if not user_id:
            logger.warning(f"No user_id in subscription {subscription['id']} metadata")
            return

        # Update user subscription info
        async with SessionLocal() as db:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    subscription_tier=tier,
                    subscription_status='active',
                    subscription_expires_at=datetime.fromtimestamp(
                        subscription['current_period_end'],
                        tz=timezone.utc
                    ),
                    credits=STRIPE_PRODUCTS.get(tier, {}).get('credits', 0)
                )
            )
            await db.commit()

        logger.info(f"Activated {tier} subscription for user {user_id}")

    async def _handle_subscription_updated(self, subscription: Dict[str, Any]):
        """Handle subscription updates (upgrades/downgrades)"""
        from app.database.connection import SessionLocal

        user_id = subscription['metadata'].get('user_id')

        if not user_id:
            return

        # Determine new tier from price ID
        price_id = subscription['items']['data'][0]['price']['id']
        tier = None
        for t, config in STRIPE_PRODUCTS.items():
            if config['price_id'] == price_id:
                tier = t
                break

        if tier:
            async with SessionLocal() as db:
                await db.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        subscription_tier=tier,
                        subscription_status=subscription['status'],
                        subscription_expires_at=datetime.fromtimestamp(
                            subscription['current_period_end'],
                            tz=timezone.utc
                        )
                    )
                )
                await db.commit()

            logger.info(f"Updated subscription to {tier} for user {user_id}")

    async def _handle_subscription_deleted(self, subscription: Dict[str, Any]):
        """Handle subscription cancellation/deletion"""
        from app.database.connection import SessionLocal

        user_id = subscription['metadata'].get('user_id')

        if not user_id:
            return

        async with SessionLocal() as db:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    subscription_status='cancelled',
                    subscription_tier='free',
                    credits=0
                )
            )
            await db.commit()

        logger.info(f"Cancelled subscription for user {user_id}")

    async def _handle_payment_succeeded(self, invoice: Dict[str, Any]):
        """Handle successful recurring payment"""
        customer_id = invoice['customer']

        # Reset monthly credits on successful payment
        from app.database.connection import SessionLocal

        async with SessionLocal() as db:
            result = await db.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()

            if user:
                tier = user.subscription_tier
                credits = STRIPE_PRODUCTS.get(tier, {}).get('credits', 0)

                await db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(
                        credits=credits,
                        credits_used_this_month=0,
                        last_payment_at=datetime.now(timezone.utc)
                    )
                )
                await db.commit()

                logger.info(f"Reset credits to {credits} for user {user.id} after payment")

    async def _handle_payment_failed(self, invoice: Dict[str, Any]):
        """Handle failed payment"""
        customer_id = invoice['customer']

        from app.database.connection import SessionLocal

        async with SessionLocal() as db:
            result = await db.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()

            if user:
                await db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(
                        subscription_status='past_due',
                        last_payment_failed_at=datetime.now(timezone.utc)
                    )
                )
                await db.commit()

                logger.info(f"Marked subscription as past_due for user {user.id}")

# Singleton instance
stripe_billing_service = StripeBillingService()