"""
Billing API Routes - Stripe integration for subscriptions

IMPORTANT: API STRUCTURE AS OF DECEMBER 2024
================================================
NEW REGISTRATIONS: Use V2 endpoints (payment-first flow)
- /api/v1/billing/v2/pre-registration-checkout - Payment before registration
- /api/v1/billing/v2/free-tier-registration - Direct registration for free tier
- /api/v1/billing/v2/webhook/complete-registration - Webhook for account creation

EXISTING USERS: Use V1 endpoints below
- /api/v1/billing/products - View available products
- /api/v1/billing/upgrade-subscription - Upgrade existing subscription
- /api/v1/billing/create-portal-session - Manage subscription
- /api/v1/billing/subscription - View subscription status
- /api/v1/billing/cancel-subscription - Cancel subscription
- /api/v1/billing/webhook - Handle Stripe webhooks

ADMIN BILLING: Use admin endpoints
- /api/v1/admin/billing/* - Manage offline/admin-managed accounts
================================================
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timezone

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.stripe_billing_service import stripe_billing_service, STRIPE_PRODUCTS
from app.database.unified_models import User
from app.models.auth import BillingType
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/billing",
    tags=["billing"]
)

# Request/Response Models
class CreateCheckoutRequest(BaseModel):
    """Request to create checkout session"""
    subscription_tier: str  # "free", "standard", "premium"
    success_url: str = "https://app.following.ae/dashboard?checkout=success"
    cancel_url: str = "https://app.following.ae/pricing?checkout=cancelled"


class CheckoutSessionResponse(BaseModel):
    """Checkout session response"""
    session_id: str
    client_secret: str  # For embedded checkout
    checkout_url: str  # For redirect (backup)
    expires_at: str


class SubscriptionResponse(BaseModel):
    """User subscription details"""
    subscription_id: Optional[str]
    customer_id: Optional[str]
    status: str  # active, past_due, cancelled, none
    tier: str  # free, standard, premium
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    cancel_at_period_end: bool
    credits_remaining: int
    credits_used: int


@router.get("/products")
async def get_products():
    """Get available subscription products with pricing"""
    try:
        products = []
        for tier, config in STRIPE_PRODUCTS.items():
            products.append({
                "tier": tier,
                "name": config["name"],
                "price": config["amount"],
                "price_display": f"${config['amount']}/month" if config["amount"] > 0 else "Free",
                "credits": config["credits"],
                "features": _get_tier_features(tier),
                "price_id": config["price_id"]
            })

        return {
            "products": products,
            "currency": "USD",
            "billing_period": "monthly"
        }

    except Exception as e:
        logger.error(f"Error getting products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load products"
        )


# DEPRECATED: Use /api/v1/billing/v2/pre-registration-checkout for new registrations
# This endpoint is only kept for existing users who want to upgrade their subscription
@router.post("/upgrade-subscription", response_model=CheckoutSessionResponse)
async def upgrade_subscription(
    request: CreateCheckoutRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upgrade existing user's subscription tier.
    For NEW registrations, use /api/v1/billing/v2/pre-registration-checkout
    """
    try:
        # This endpoint is only for EXISTING users upgrading their plan
        if not current_user or current_user.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint is only for existing active users. New users should use the registration flow."
            )

        # Check billing type
        if current_user.billing_type != BillingType.ONLINE_PAYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account uses admin-managed billing. Contact support for subscription changes."
            )

        # Get or create Stripe customer
        if not current_user.stripe_customer_id:
            customer_id = await stripe_billing_service.create_customer(
                user_email=current_user.email,
                user_name=current_user.full_name or current_user.email,
                user_id=str(current_user.id)
            )

            # Update user with customer ID
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(stripe_customer_id=customer_id)
            )
            await db.commit()
        else:
            customer_id = current_user.stripe_customer_id

        # Get price ID for tier
        if request.subscription_tier not in STRIPE_PRODUCTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription tier: {request.subscription_tier}"
            )

        price_id = STRIPE_PRODUCTS[request.subscription_tier]["price_id"]

        # Create checkout session for upgrade
        session = await stripe_billing_service.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            user_id=str(current_user.id),
            subscription_tier=request.subscription_tier
        )

        return CheckoutSessionResponse(
            session_id=session["session_id"],
            client_secret=session["client_secret"],
            checkout_url=session["checkout_url"],
            expires_at=session["expires_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating upgrade checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create upgrade checkout session"
        )


@router.post("/create-portal-session")
async def create_portal_session(
    current_user=Depends(get_current_user),
    return_url: str = "https://app.following.ae/settings/billing"
):
    """Create customer portal session for subscription management"""
    try:
        if current_user.billing_type != BillingType.ONLINE_PAYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account uses admin-managed billing. Contact support for billing inquiries."
            )

        if not current_user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No billing account found. Please subscribe first."
            )

        # Create portal session
        session = await stripe_billing_service.create_billing_portal_session(
            customer_id=current_user.stripe_customer_id,
            return_url=return_url
        )

        return {
            "portal_url": session["portal_url"],
            "session_id": session["session_id"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's subscription details"""
    try:
        # For admin-managed billing, return different response
        if current_user.billing_type == BillingType.ADMIN_MANAGED:
            return SubscriptionResponse(
                subscription_id=None,
                customer_id=None,
                status="admin_managed",
                tier=current_user.subscription_tier or "free",
                current_period_start=None,
                current_period_end=str(current_user.subscription_expires_at) if current_user.subscription_expires_at else None,
                cancel_at_period_end=False,
                credits_remaining=current_user.credits or 0,
                credits_used=current_user.credits_used_this_month or 0
            )

        # For online payment users, get from Stripe
        if not current_user.stripe_customer_id:
            return SubscriptionResponse(
                subscription_id=None,
                customer_id=None,
                status="none",
                tier="free",
                current_period_start=None,
                current_period_end=None,
                cancel_at_period_end=False,
                credits_remaining=0,
                credits_used=0
            )

        subscription = await stripe_billing_service.get_subscription(current_user.stripe_customer_id)

        if not subscription:
            return SubscriptionResponse(
                subscription_id=None,
                customer_id=current_user.stripe_customer_id,
                status="none",
                tier="free",
                current_period_start=None,
                current_period_end=None,
                cancel_at_period_end=False,
                credits_remaining=0,
                credits_used=0
            )

        return SubscriptionResponse(
            subscription_id=subscription["subscription_id"],
            customer_id=current_user.stripe_customer_id,
            status=subscription["status"],
            tier=current_user.subscription_tier or "free",
            current_period_start=subscription["current_period_start"],
            current_period_end=subscription["current_period_end"],
            cancel_at_period_end=subscription["cancel_at_period_end"],
            credits_remaining=current_user.credits or 0,
            credits_used=current_user.credits_used_this_month or 0
        )

    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscription details"
        )


@router.post("/cancel-subscription")
async def cancel_subscription(
    immediate: bool = False,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel user's subscription"""
    try:
        if current_user.billing_type != BillingType.ONLINE_PAYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account uses admin-managed billing. Contact support to cancel."
            )

        # Get active subscription
        subscription = await stripe_billing_service.get_subscription(current_user.stripe_customer_id)

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription found"
            )

        # Cancel subscription
        result = await stripe_billing_service.cancel_subscription(
            subscription["subscription_id"],
            immediate=immediate
        )

        # Update user status if immediate cancellation
        if immediate:
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(
                    subscription_status='cancelled',
                    subscription_tier='free'
                )
            )
            await db.commit()

        return {
            "status": "success",
            "subscription_id": result["subscription_id"],
            "cancelled_at": result.get("canceled_at"),
            "cancel_at_period_end": result["cancel_at_period_end"],
            "active_until": result["current_period_end"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhook events"""
    try:
        # Get raw body
        payload = await request.body()

        # Process webhook
        result = await stripe_billing_service.handle_webhook(payload, stripe_signature)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Return 200 to acknowledge receipt even on error
        return {"status": "error", "message": str(e)}


def _get_tier_features(tier: str) -> list:
    """Get feature list for subscription tier"""
    features_map = {
        "free": [
            "5 profile searches per month",
            "Basic analytics",
            "Email support",
            "Credit card required"
        ],
        "standard": [
            "500 profile searches per month",
            "Advanced analytics",
            "Campaign management",
            "Priority support",
            "Data export",
            "Team collaboration (2 members)"
        ],
        "premium": [
            "2000 profile searches per month",
            "Enterprise analytics",
            "Unlimited campaigns",
            "Dedicated support",
            "API access",
            "Team collaboration (5 members)",
            "Custom integrations",
            "20% discount on credit topups"
        ]
    }
    return features_map.get(tier, [])