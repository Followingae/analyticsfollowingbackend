"""
Stripe Checkout Routes - Handle subscription checkout with monthly/annual billing
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Literal
import logging
import os

from app.middleware.team_auth_middleware import get_team_owner_context, TeamContext
from app.database.connection import get_db
from app.services.stripe_billing_service import StripeBillingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/checkout", tags=["Stripe Checkout"])

# Initialize Stripe service
stripe_service = StripeBillingService()

class CreateCheckoutRequest(BaseModel):
    """Request model for creating checkout session"""
    tier: Literal["free", "standard", "premium"]
    billing_interval: Literal["monthly", "annual"] = "monthly"
    success_url: str
    cancel_url: str

class CheckoutSessionResponse(BaseModel):
    """Response model for checkout session"""
    success: bool
    checkout_url: str
    session_id: str
    tier: str
    billing_interval: str
    amount: int
    savings: Optional[int] = None

@router.post("/create-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    team_context: TeamContext = Depends(get_team_owner_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Stripe checkout session for subscription

    - **tier**: Subscription tier (free, standard, premium)
    - **billing_interval**: Billing frequency (monthly or annual)
    - **success_url**: URL to redirect after successful payment
    - **cancel_url**: URL to redirect if user cancels

    Annual billing offers 20% discount on Standard and Premium tiers.
    """
    try:
        # Import here to avoid circular dependency
        from app.services.stripe_billing_service import STRIPE_PRODUCTS

        # Validate tier
        if request.tier not in STRIPE_PRODUCTS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier: {request.tier}"
            )

        # Get product configuration
        product = STRIPE_PRODUCTS[request.tier]

        # Check if billing interval is available for this tier
        if request.tier == "free" and request.billing_interval == "annual":
            raise HTTPException(
                status_code=400,
                detail="Free tier does not support annual billing"
            )

        # Get the appropriate price based on billing interval
        if request.billing_interval == "annual" and "annual" in product:
            price_info = product["annual"]
        else:
            price_info = product.get("monthly", product.get("monthly"))

        if not price_info:
            raise HTTPException(
                status_code=400,
                detail=f"Billing interval '{request.billing_interval}' not available for {request.tier} tier"
            )

        # Get user's Stripe customer ID or create one
        from sqlalchemy import select
        from app.database.unified_models import User

        user_query = select(User).where(User.id == team_context.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create customer if doesn't exist
        if not user.stripe_customer_id:
            import stripe
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

            stripe_customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name or f"Team {team_context.team_name}",
                metadata={
                    'user_id': str(team_context.user_id),
                    'team_id': str(team_context.team_id),
                    'team_name': team_context.team_name
                }
            )

            # Save customer ID
            from sqlalchemy import update
            await db.execute(
                update(User).where(User.id == team_context.user_id).values(
                    stripe_customer_id=stripe_customer.id
                )
            )
            await db.commit()
            customer_id = stripe_customer.id
        else:
            customer_id = user.stripe_customer_id

        # Create checkout session
        session_data = await stripe_service.create_checkout_session(
            customer_id=customer_id,
            price_id=price_info["price_id"],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            user_id=str(team_context.user_id),
            subscription_tier=request.tier,
            billing_interval=request.billing_interval
        )

        logger.info(f"Checkout session created for {request.tier} ({request.billing_interval})")

        return CheckoutSessionResponse(
            success=True,
            checkout_url=session_data["url"],
            session_id=session_data["session_id"],
            tier=request.tier,
            billing_interval=request.billing_interval,
            amount=price_info["amount"],
            savings=price_info.get("savings")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {str(e)}"
        )

@router.get("/pricing")
async def get_pricing_info():
    """
    Get all available pricing options with monthly and annual rates

    Returns pricing information for all tiers including savings for annual billing.
    """
    from app.services.stripe_billing_service import STRIPE_PRODUCTS

    pricing = {}

    for tier, product in STRIPE_PRODUCTS.items():
        tier_info = {
            "name": product["name"],
            "credits": product["credits"],
            "pricing": {}
        }

        # Add monthly pricing if available
        if "monthly" in product:
            tier_info["pricing"]["monthly"] = {
                "amount": product["monthly"]["amount"],
                "interval": "month",
                "price_id": product["monthly"]["price_id"]
            }
        elif "price_id" in product:  # Legacy format for free tier
            tier_info["pricing"]["monthly"] = {
                "amount": product.get("amount", 0),
                "interval": "month",
                "price_id": product["price_id"]
            }

        # Add annual pricing if available
        if "annual" in product:
            tier_info["pricing"]["annual"] = {
                "amount": product["annual"]["amount"],
                "interval": "year",
                "savings": product["annual"]["savings"],
                "monthly_equivalent": product["annual"]["amount"] // 12,
                "price_id": product["annual"]["price_id"]
            }

        # Add special features
        if "topup_discount" in product:
            tier_info["topup_discount"] = product["topup_discount"]

        pricing[tier] = tier_info

    return {
        "success": True,
        "pricing": pricing,
        "currency": "USD",
        "annual_discount": 0.20,  # 20% discount
        "notes": {
            "annual_billing": "Save 20% with annual billing on Standard and Premium plans",
            "topup_discount": "Premium tier includes 20% discount on all credit topups"
        }
    }