"""
Stripe Subscription Integration - B2B SaaS Billing
Handles Stripe Customer Portal integration and subscription management
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, Dict, Any
from uuid import UUID
import logging
import os
import json
import hmac
import hashlib

from app.middleware.team_auth_middleware import (
    get_team_owner_context, get_any_team_member_context,
    TeamContext
)
from app.database.connection import get_db
from app.database.unified_models import User, Team
from app.core.config import settings
from app.models.teams import SUBSCRIPTION_TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscription", tags=["Stripe Subscription Management"])

# Stripe integration - install with: pip install stripe
try:
    import stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    
    # Subscription pricing configuration with monthly and annual options
    SUBSCRIPTION_PRICE_IDS = {
        'free': {
            'monthly': os.getenv('STRIPE_FREE_MONTHLY_PRICE_ID', 'price_1Sf1loAubhSg1bPI00UODTEY')
        },
        'standard': {
            'monthly': os.getenv('STRIPE_STANDARD_MONTHLY_PRICE_ID', 'price_1Sf1lpAubhSg1bPIiTWvBncS'),
            'annual': os.getenv('STRIPE_STANDARD_ANNUAL_PRICE_ID', 'price_1SfDzAAubhSg1bPIwl0bIgs8')
        },
        'premium': {
            'monthly': os.getenv('STRIPE_PREMIUM_MONTHLY_PRICE_ID', 'price_1Sf1lqAubhSg1bPIJIcqgHu1'),
            'annual': os.getenv('STRIPE_PREMIUM_ANNUAL_PRICE_ID', 'price_1SfDzLAubhSg1bPIuSB7Tz5R')
        }
    }
    
    logger.info("Stripe integration initialized")
except ImportError:
    logger.warning("Stripe not installed. Install with: pip install stripe")
    stripe = None
except Exception as e:
    logger.warning(f"Stripe initialization failed: {e}")
    stripe = None

# =============================================================================
# STRIPE CUSTOMER MANAGEMENT
# =============================================================================

@router.post("/create-customer")
async def create_stripe_customer(
    team_context: TeamContext = Depends(get_team_owner_context),  # Only team owners
    db: AsyncSession = Depends(get_db)
):
    """
    Create Stripe customer for team owner
    Called during initial subscription setup
    """
    if not stripe:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        logger.info(f"Creating Stripe customer for team {team_context.team_name}")
        
        # Get team owner user details
        user_query = select(User).where(User.id == team_context.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create Stripe customer
        stripe_customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or f"Team Owner - {team_context.team_name}",
            metadata={
                'user_id': str(team_context.user_id),
                'team_id': str(team_context.team_id),
                'team_name': team_context.team_name
            }
        )
        
        # Store Stripe customer ID in user record
        await db.execute(
            update(User).where(User.id == team_context.user_id).values(
                stripe_customer_id=stripe_customer.id
            )
        )
        await db.commit()
        
        logger.info(f"Stripe customer created: {stripe_customer.id}")
        
        return {
            "success": True,
            "customer_id": stripe_customer.id,
            "message": "Stripe customer created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating Stripe customer: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Stripe customer: {str(e)}"
        )

@router.get("/portal-url")
async def get_customer_portal_url(
    return_url: Optional[str] = None,
    team_context: TeamContext = Depends(get_team_owner_context),  # Only team owners
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Stripe Customer Portal URL for subscription management
    
    The Customer Portal allows users to:
    - Upgrade/downgrade subscription plans
    - Update payment methods
    - View billing history and invoices
    - Cancel subscriptions
    """
    if not stripe:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        logger.info(f"Generating portal URL for team {team_context.team_name}")
        
        # Get user's Stripe customer ID
        user_query = select(User.stripe_customer_id).where(User.id == team_context.user_id)
        user_result = await db.execute(user_query)
        stripe_customer_id = user_result.scalar()
        
        if not stripe_customer_id:
            raise HTTPException(
                status_code=400,
                detail="No Stripe customer found. Please create customer first."
            )
        
        # Default return URL to your frontend dashboard
        portal_return_url = return_url or f"{settings.FRONTEND_URL}/dashboard/subscription"
        
        # Create Customer Portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=portal_return_url
        )
        
        logger.info(f"Portal URL generated for customer {stripe_customer_id}")
        
        return {
            "success": True,
            "portal_url": portal_session.url,
            "expires_at": portal_session.created + 3600,  # Portal URLs expire after 1 hour
            "return_url": portal_return_url
        }
        
    except Exception as e:
        logger.error(f"Error generating portal URL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate portal URL: {str(e)}"
        )

# =============================================================================
# SUBSCRIPTION STATUS & INFORMATION
# =============================================================================

@router.get("/status")
async def get_subscription_status(
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current subscription status from database
    
    This returns locally stored subscription information that's synced
    from Stripe via webhooks. It's fast and doesn't require Stripe API calls.
    """
    try:
        # Get team subscription details
        team_query = select(Team).where(Team.id == team_context.team_id)
        team_result = await db.execute(team_query)
        team = team_result.scalar_one_or_none()
        
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Get subscription tier limits
        from app.models.teams import SUBSCRIPTION_TIER_LIMITS
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(team.subscription_tier, {})
        
        return {
            "subscription": {
                "tier": team.subscription_tier,
                "status": team.subscription_status,
                "expires_at": team.subscription_expires_at.isoformat() if team.subscription_expires_at else None,
                "limits": {
                    "team_members": tier_limits.get("max_team_members", 1),
                    "profiles": tier_limits.get("monthly_profile_limit", 5),
                    "emails": tier_limits.get("monthly_email_limit", 0),
                    "posts": tier_limits.get("monthly_posts_limit", 0)
                },
                "current_usage": {
                    "profiles": team.profiles_used_this_month,
                    "emails": team.emails_used_this_month,
                    "posts": team.posts_used_this_month
                },
                "pricing": {
                    "monthly_cost": tier_limits.get("price_per_month", 0),
                    "features": tier_limits.get("features", [])
                }
            },
            "team": {
                "id": str(team.id),
                "name": team.name,
                "company_name": team.company_name,
                "member_count": 1  # Default to 1, can be enhanced later with proper member count query
            },
            "user": {
                "role": team_context.user_role,
                "permissions": team_context.user_permissions
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get subscription status"
        )

# =============================================================================
# STRIPE WEBHOOKS - SUBSCRIPTION SYNC
# =============================================================================

@router.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhooks to sync subscription changes
    
    Critical events handled:
    - customer.subscription.updated (plan changes)
    - customer.subscription.deleted (cancellations)
    - invoice.payment_succeeded (successful payments)
    - invoice.payment_failed (failed payments)
    """
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Stripe webhooks not configured")
    
    try:
        # Get request body
        payload = await request.body()
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.error("Invalid payload in Stripe webhook")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature in Stripe webhook")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        logger.info(f"Stripe webhook received: {event['type']}")
        
        # Handle specific events
        if event['type'] == 'customer.subscription.updated':
            await _handle_subscription_updated(event['data']['object'], db)
            
        elif event['type'] == 'customer.subscription.deleted':
            await _handle_subscription_cancelled(event['data']['object'], db)
            
        elif event['type'] == 'invoice.payment_succeeded':
            await _handle_payment_succeeded(event['data']['object'], db)
            
        elif event['type'] == 'invoice.payment_failed':
            await _handle_payment_failed(event['data']['object'], db)
            
        else:
            logger.info(f"Unhandled webhook event: {event['type']}")
        
        return {"success": True, "event_type": event['type']}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

# =============================================================================
# WEBHOOK HANDLERS (INTERNAL)
# =============================================================================

async def _handle_subscription_updated(subscription: Dict[str, Any], db: AsyncSession):
    """Handle subscription plan changes or updates"""
    try:
        customer_id = subscription['customer']
        
        # Find user by Stripe customer ID
        user_query = select(User).where(User.stripe_customer_id == customer_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User not found for Stripe customer {customer_id}")
            return
        
        # Get team for this user
        from app.database.unified_models import TeamMember
        team_query = select(Team).join(TeamMember).where(
            TeamMember.user_id == user.id,
            TeamMember.role == 'owner'
        )
        team_result = await db.execute(team_query)
        team = team_result.scalar_one_or_none()
        
        if not team:
            logger.warning(f"Team not found for user {user.id}")
            return
        
        # Map Stripe price ID to subscription tier
        price_id = subscription['items']['data'][0]['price']['id']
        new_tier = 'free'  # Default
        
        for tier, stripe_price_id in SUBSCRIPTION_PRICE_IDS.items():
            if price_id == stripe_price_id:
                new_tier = tier
                break
        
        # Update team subscription
        from app.models.teams import SUBSCRIPTION_TIER_LIMITS
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(new_tier, {})
        
        await db.execute(
            update(Team).where(Team.id == team.id).values(
                subscription_tier=new_tier,
                subscription_status='active' if subscription['status'] == 'active' else subscription['status'],
                monthly_profile_limit=tier_limits.get('monthly_profile_limit', 5),
                monthly_email_limit=tier_limits.get('monthly_email_limit', 0),
                monthly_posts_limit=tier_limits.get('monthly_posts_limit', 0),
                max_team_members=tier_limits.get('max_team_members', 1)
            )
        )
        await db.commit()
        
        logger.info(f"Updated team {team.id} subscription to {new_tier}")
        
    except Exception as e:
        logger.error(f"Error handling subscription update: {e}")
        await db.rollback()

async def _handle_subscription_cancelled(subscription: Dict[str, Any], db: AsyncSession):
    """Handle subscription cancellations"""
    try:
        customer_id = subscription['customer']
        
        # Find and update team to free tier
        user_query = select(User).where(User.stripe_customer_id == customer_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if user:
            from app.database.unified_models import TeamMember
            team_query = select(Team).join(TeamMember).where(
                TeamMember.user_id == user.id,
                TeamMember.role == 'owner'
            )
            team_result = await db.execute(team_query)
            team = team_result.scalar_one_or_none()
            
            if team:
                # Downgrade to free tier
                from app.models.teams import SUBSCRIPTION_TIER_LIMITS
                free_limits = SUBSCRIPTION_TIER_LIMITS['free']
                
                await db.execute(
                    update(Team).where(Team.id == team.id).values(
                        subscription_tier='free',
                        subscription_status='cancelled',
                        monthly_profile_limit=free_limits['monthly_profile_limit'],
                        monthly_email_limit=free_limits['monthly_email_limit'],
                        monthly_posts_limit=free_limits['monthly_posts_limit'],
                        max_team_members=free_limits['max_team_members']
                    )
                )
                await db.commit()
                
                logger.info(f"Cancelled subscription for team {team.id}")
        
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {e}")
        await db.rollback()

async def _handle_payment_succeeded(invoice: Dict[str, Any], db: AsyncSession):
    """Handle successful payments"""
    logger.info(f"Payment succeeded for invoice {invoice['id']}")
    # Additional logic for successful payments if needed

async def _handle_payment_failed(invoice: Dict[str, Any], db: AsyncSession):
    """Handle failed payments"""
    try:
        customer_id = invoice['customer']
        
        # Find team and mark as past due
        user_query = select(User).where(User.stripe_customer_id == customer_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if user:
            from app.database.unified_models import TeamMember
            team_query = select(Team).join(TeamMember).where(
                TeamMember.user_id == user.id,
                TeamMember.role == 'owner'
            )
            team_result = await db.execute(team_query)
            team = team_result.scalar_one_or_none()
            
            if team:
                await db.execute(
                    update(Team).where(Team.id == team.id).values(
                        subscription_status='past_due'
                    )
                )
                await db.commit()
                
                logger.warning(f"Payment failed for team {team.id} - marked as past due")
        
    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")
        await db.rollback()

# =============================================================================
# DEVELOPMENT / TESTING ENDPOINTS
# =============================================================================

@router.get("/config")
async def get_stripe_config():
    """
    Get Stripe configuration for frontend
    Returns publishable key and pricing information
    """
    if not stripe:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    # Get pricing from centralized configuration
    standard_config = SUBSCRIPTION_TIER_LIMITS.get("standard", {})
    premium_config = SUBSCRIPTION_TIER_LIMITS.get("premium", {})

    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "pricing": {
            "standard": {
                "price_id": SUBSCRIPTION_PRICE_IDS.get('standard'),
                "monthly_cost": standard_config.get("price_per_month", 199),
                "features": [
                    f"{standard_config.get('monthly_profile_limit', 500)} profiles/month",
                    f"{standard_config.get('monthly_email_limit', 250)} emails",
                    f"{standard_config.get('monthly_posts_limit', 125)} posts",
                    f"{standard_config.get('max_team_members', 2)} team members"
                ]
            },
            "premium": {
                "price_id": SUBSCRIPTION_PRICE_IDS.get('premium'),
                "monthly_cost": premium_config.get("price_per_month", 499),
                "features": [
                    f"{premium_config.get('monthly_profile_limit', 2000)} profiles/month",
                    f"{premium_config.get('monthly_email_limit', 800)} emails",
                    f"{premium_config.get('monthly_posts_limit', 300)} posts",
                    f"{premium_config.get('max_team_members', 5)} team members",
                    f"{int(premium_config.get('topup_discount', 0.2) * 100)}% topup discount"
                ]
            }
        },
        "currency": standard_config.get("currency", "usd").lower()
    }