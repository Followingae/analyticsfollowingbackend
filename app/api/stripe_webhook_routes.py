"""
Stripe Webhook Handler - Automatic subscription event processing
Handles subscription updates, cancellations, payment events, and credit system sync
"""
import logging
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import json
from uuid import UUID

from app.services.stripe_subscription_service import stripe_subscription_service
from app.services.credit_transaction_service import credit_transaction_service
from app.database.connection import get_session
from app.database.unified_models import User, CreditWallet
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stripe", tags=["Stripe Webhooks"])

# Webhook secret from environment
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

@router.post("/webhook")
async def stripe_webhook_handler(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events for subscription management
    Automatically syncs subscription changes with internal credit system
    """
    try:
        # Get the raw body
        body = await request.body()

        # Verify webhook signature (when webhook secret is configured)
        if STRIPE_WEBHOOK_SECRET and stripe_signature:
            # TODO: Implement signature verification when webhook secret is available
            # For now, we'll process events but log the missing verification
            logger.warning("Webhook signature verification not implemented - webhook secret needed")

        # Parse the event
        try:
            event = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Handle different event types
        event_type = event.get('type')
        event_data = event.get('data', {}).get('object', {})

        logger.info(f"Processing Stripe webhook: {event_type}")

        if event_type == 'customer.subscription.created':
            await handle_subscription_created(event_data)
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(event_data)
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_cancelled(event_data)
        elif event_type == 'invoice.payment_succeeded':
            await handle_payment_succeeded(event_data)
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(event_data)
        elif event_type in ['checkout.session.completed', 'payment_intent.succeeded']:
            await handle_topup_payment_completed(event_data)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")

        return JSONResponse(content={"status": "success"}, status_code=200)

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

async def handle_subscription_created(subscription: Dict[str, Any]):
    """Handle new subscription creation"""
    try:
        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            logger.warning("Subscription created without user_id metadata")
            return

        user_uuid = UUID(user_id)

        # Update user subscription from Stripe data
        await stripe_subscription_service.update_user_subscription_from_stripe(user_uuid, subscription)

        # Reset credit wallet for new billing cycle
        await reset_credit_wallet_for_new_cycle(user_uuid, subscription)

        logger.info(f"Processed subscription creation for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling subscription creation: {e}")

async def handle_subscription_updated(subscription: Dict[str, Any]):
    """Handle subscription updates (upgrades, downgrades, renewals)"""
    try:
        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            logger.warning("Subscription updated without user_id metadata")
            return

        user_uuid = UUID(user_id)

        # Update user subscription from Stripe data
        await stripe_subscription_service.update_user_subscription_from_stripe(user_uuid, subscription)

        # If this is a new billing period, reset credits
        if subscription.get('status') == 'active':
            await reset_credit_wallet_for_new_cycle(user_uuid, subscription)

        logger.info(f"Processed subscription update for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling subscription update: {e}")

async def handle_subscription_cancelled(subscription: Dict[str, Any]):
    """Handle subscription cancellation"""
    try:
        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            logger.warning("Subscription cancelled without user_id metadata")
            return

        user_uuid = UUID(user_id)

        # Update user to free tier
        async with get_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_uuid)
                .values(
                    subscription_tier='free',
                    subscription_status='cancelled',
                    stripe_subscription_id=None
                )
            )

            # Update credit wallet
            await session.execute(
                update(CreditWallet)
                .where(CreditWallet.user_id == user_uuid)
                .values(
                    subscription_status='cancelled',
                    subscription_active=False
                )
            )

            await session.commit()

        logger.info(f"Processed subscription cancellation for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {e}")

async def handle_payment_succeeded(invoice: Dict[str, Any]):
    """Handle successful payment"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return

        # Get subscription details to find user
        from app.services.stripe_service import stripe_service
        subscription = stripe_service._make_request("GET", f"subscriptions/{subscription_id}")

        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            return

        user_uuid = UUID(user_id)

        # Log successful payment
        await credit_transaction_service.log_transaction(
            user_id=user_uuid,
            transaction_type='subscription_payment',
            amount=0,  # No credit change for subscription payments
            description=f"Subscription payment successful - Invoice {invoice.get('id')}",
            metadata={
                'stripe_invoice_id': invoice.get('id'),
                'stripe_subscription_id': subscription_id,
                'amount_paid': invoice.get('amount_paid', 0) / 100  # Convert from cents
            }
        )

        logger.info(f"Processed successful payment for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling payment success: {e}")

async def handle_payment_failed(invoice: Dict[str, Any]):
    """Handle failed payment"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return

        # Get subscription details to find user
        from app.services.stripe_service import stripe_service
        subscription = stripe_service._make_request("GET", f"subscriptions/{subscription_id}")

        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            return

        user_uuid = UUID(user_id)

        # Log failed payment
        await credit_transaction_service.log_transaction(
            user_id=user_uuid,
            transaction_type='subscription_payment_failed',
            amount=0,
            description=f"Subscription payment failed - Invoice {invoice.get('id')}",
            metadata={
                'stripe_invoice_id': invoice.get('id'),
                'stripe_subscription_id': subscription_id,
                'amount_due': invoice.get('amount_due', 0) / 100
            }
        )

        logger.warning(f"Payment failed for user {user_id}, invoice {invoice.get('id')}")

    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")

async def handle_topup_payment_completed(payment_data: Dict[str, Any]):
    """Handle completed topup payments"""
    try:
        # Extract metadata to identify topup
        metadata = payment_data.get('metadata', {})
        user_id = metadata.get('user_id')
        topup_type = metadata.get('topup_type')
        credits_amount = metadata.get('credits')

        if not all([user_id, topup_type, credits_amount]):
            logger.warning("Topup payment completed without required metadata")
            return

        user_uuid = UUID(user_id)
        credits_amount = int(credits_amount)

        # Add credits to user's wallet
        async with get_session() as session:
            # Get current wallet
            result = await session.execute(
                select(CreditWallet)
                .where(CreditWallet.user_id == user_uuid)
            )
            wallet = result.scalar_one_or_none()

            if wallet:
                # Update wallet balance
                await session.execute(
                    update(CreditWallet)
                    .where(CreditWallet.user_id == user_uuid)
                    .values(
                        current_balance=CreditWallet.current_balance + credits_amount,
                        total_earned=CreditWallet.total_earned + credits_amount
                    )
                )

                # Log the transaction
                await credit_transaction_service.log_transaction(
                    user_id=user_uuid,
                    transaction_type='topup_purchase',
                    amount=credits_amount,
                    description=f"Credit topup purchase - {topup_type} package",
                    metadata={
                        'topup_type': topup_type,
                        'stripe_payment_id': payment_data.get('id'),
                        'credits_added': credits_amount
                    }
                )

                await session.commit()

                logger.info(f"Processed topup for user {user_id}: {credits_amount} credits added")

    except Exception as e:
        logger.error(f"Error handling topup payment: {e}")

async def reset_credit_wallet_for_new_cycle(user_id: UUID, subscription: Dict[str, Any]):
    """Reset credit wallet for new billing cycle"""
    try:
        # Determine tier and credit allowance
        tier = 'free'
        price_id = subscription['items']['data'][0]['price']['id']

        # Map price ID to tier
        stripe_service = stripe_subscription_service
        for t, pid in stripe_service.price_ids.items():
            if pid == price_id:
                tier = t
                break

        # Get tier allowances from existing system
        from app.models.teams import SUBSCRIPTION_TIER_LIMITS
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(tier, SUBSCRIPTION_TIER_LIMITS['free'])
        monthly_credits = tier_limits.get('monthly_credits', 0)

        # Reset wallet for new cycle
        async with get_session() as session:
            await session.execute(
                update(CreditWallet)
                .where(CreditWallet.user_id == user_id)
                .values(
                    current_balance=monthly_credits,
                    total_earned=CreditWallet.total_earned + monthly_credits,
                    total_spent_this_cycle=0
                )
            )
            await session.commit()

        # Log the reset
        await credit_transaction_service.log_transaction(
            user_id=user_id,
            transaction_type='monthly_reset',
            amount=monthly_credits,
            description=f"Monthly credit reset - {tier} tier ({monthly_credits} credits)",
            metadata={
                'tier': tier,
                'billing_cycle_reset': True,
                'stripe_subscription_id': subscription.get('id')
            }
        )

        logger.info(f"Reset credit wallet for user {user_id}: {monthly_credits} credits for {tier} tier")

    except Exception as e:
        logger.error(f"Error resetting credit wallet: {e}")