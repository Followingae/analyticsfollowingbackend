"""
Stripe Webhook Handler - Automatic subscription event processing
Handles subscription updates, cancellations, payment events, and credit system sync
"""
import logging
import os
import collections
import stripe
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import json
from uuid import UUID
from datetime import date

from app.services.stripe_subscription_service import stripe_subscription_service
from app.database.connection import get_session
from app.database.unified_models import User, CreditWallet, CreditTransaction as CreditTransactionModel
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stripe", tags=["Stripe Webhooks"])

# Webhook secret from environment
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Stripe price ID to tier mapping
STRIPE_PRICE_TO_TIER = {
    'price_1SGatNADTNbHc8P6fCY0pBLS': 'free',
    'price_1SGasqADTNbHc8P6v7VNl7sc': 'standard',
    'price_1SGatBADTNbHc8P6FlTcQbWI': 'premium',
}

# Tier to monthly credit allocation — import canonical values
from app.models.teams import SUBSCRIPTION_TIER_LIMITS, SubscriptionTier

def _get_tier_credits(tier: str) -> int:
    """Get monthly credits for a tier from canonical SUBSCRIPTION_TIER_LIMITS"""
    tier_key = getattr(SubscriptionTier, tier.upper(), tier)
    tier_limits = SUBSCRIPTION_TIER_LIMITS.get(tier_key, SUBSCRIPTION_TIER_LIMITS.get(SubscriptionTier.FREE, {}))
    return tier_limits.get('monthly_credits', 125)

# Bounded set for webhook idempotency (in-memory, max 10k events)
_MAX_PROCESSED_EVENTS = 10_000
_processed_event_ids: collections.OrderedDict = collections.OrderedDict()


def _mark_event_processed(event_id: str) -> None:
    """Record an event ID, evicting oldest entries if at capacity."""
    _processed_event_ids[event_id] = True
    while len(_processed_event_ids) > _MAX_PROCESSED_EVENTS:
        _processed_event_ids.popitem(last=False)


def _is_event_processed(event_id: str) -> bool:
    """Check whether an event has already been processed."""
    return event_id in _processed_event_ids


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

        # ── Webhook signature verification ──────────────────────────────
        if STRIPE_WEBHOOK_SECRET:
            if stripe_signature:
                try:
                    event = stripe.Webhook.construct_event(
                        payload=body,
                        sig_header=stripe_signature,
                        secret=STRIPE_WEBHOOK_SECRET,
                    )
                except stripe.SignatureVerificationError as e:
                    logger.error(f"Webhook signature verification failed: {e}")
                    raise HTTPException(status_code=400, detail="Invalid webhook signature")
                except ValueError as e:
                    logger.error(f"Invalid webhook payload: {e}")
                    raise HTTPException(status_code=400, detail="Invalid payload")
            else:
                logger.warning("Webhook received without stripe-signature header but secret is configured — rejecting")
                raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        else:
            # Dev mode: no webhook secret configured, parse manually
            logger.warning("STRIPE_WEBHOOK_SECRET not configured — accepting unverified webhook (dev mode)")
            try:
                event = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in webhook payload")
                raise HTTPException(status_code=400, detail="Invalid JSON")

        # ── Idempotency check ───────────────────────────────────────────
        event_id = event.get('id') if isinstance(event, dict) else getattr(event, 'id', None)
        if event_id:
            if _is_event_processed(event_id):
                logger.info(f"Duplicate webhook event {event_id} — skipping")
                return JSONResponse(content={"status": "already_processed"}, status_code=200)

        # Handle different event types
        event_type = event.get('type') if isinstance(event, dict) else getattr(event, 'type', None)
        if isinstance(event, dict):
            event_data = event.get('data', {}).get('object', {})
        else:
            event_data = event.data.object if hasattr(event, 'data') else {}
            # Convert Stripe object to dict for consistent downstream handling
            if hasattr(event_data, 'to_dict_recursive'):
                event_data = event_data.to_dict_recursive()
            elif hasattr(event_data, '__dict__'):
                event_data = dict(event_data)

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

        # Mark event as processed after successful handling
        if event_id:
            _mark_event_processed(event_id)

        return JSONResponse(content={"status": "success"}, status_code=200)

    except HTTPException:
        raise
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
    """Handle successful payment and provision credits for the billing cycle"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return

        # Get subscription details to find user
        from app.services.stripe_service import stripe_service
        subscription = await stripe_service._make_request("GET", f"subscriptions/{subscription_id}")

        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            return

        user_uuid = UUID(user_id)

        # Determine the tier from the subscription price
        tier = 'free'
        try:
            price_id = subscription['items']['data'][0]['price']['id']
            tier = STRIPE_PRICE_TO_TIER.get(price_id, 'free')
        except (KeyError, IndexError):
            logger.warning(f"Could not extract price_id from subscription for user {user_id}")

        credits_to_add = _get_tier_credits(tier)

        # Provision credits for the new billing cycle
        async with get_session() as session:
            result = await session.execute(
                select(CreditWallet).where(CreditWallet.user_id == user_uuid)
            )
            wallet = result.scalar_one_or_none()

            if wallet and credits_to_add > 0:
                balance_before = wallet.current_balance

                await session.execute(
                    update(CreditWallet)
                    .where(CreditWallet.user_id == user_uuid)
                    .values(
                        current_balance=CreditWallet.current_balance + credits_to_add,
                        total_earned_this_cycle=CreditWallet.total_earned_this_cycle + credits_to_add,
                        lifetime_earned=CreditWallet.lifetime_earned + credits_to_add,
                    )
                )

                # Record credit provisioning transaction
                txn = CreditTransactionModel(
                    wallet_id=wallet.id,
                    user_id=user_uuid,
                    transaction_type='earned',
                    action_type='subscription_payment',
                    amount=credits_to_add,
                    description=f"Subscription payment successful - {tier} tier ({credits_to_add} credits) - Invoice {invoice.get('id')}",
                    balance_before=balance_before,
                    balance_after=balance_before + credits_to_add,
                    billing_cycle_date=date.today(),
                    transaction_metadata={
                        'stripe_invoice_id': invoice.get('id'),
                        'stripe_subscription_id': subscription_id,
                        'amount_paid': invoice.get('amount_paid', 0) / 100,
                        'tier': tier,
                        'credits_provisioned': credits_to_add,
                    },
                )
                session.add(txn)

            await session.commit()

        logger.info(f"Processed successful payment for user {user_id}: provisioned {credits_to_add} credits ({tier} tier)")

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
        subscription = await stripe_service._make_request("GET", f"subscriptions/{subscription_id}")

        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            return

        user_uuid = UUID(user_id)

        # Log failed payment as a transaction record (no balance change)
        async with get_session() as session:
            result = await session.execute(
                select(CreditWallet).where(CreditWallet.user_id == user_uuid)
            )
            wallet = result.scalar_one_or_none()

            if wallet:
                # Use a minimal earned transaction with 0-equivalent to record the event
                # Note: CreditTransaction has a check constraint amount != 0, so we log
                # the failure only in the metadata of the subscription status update
                logger.warning(
                    f"Payment failed for user {user_id}, invoice {invoice.get('id')}, "
                    f"amount_due=${invoice.get('amount_due', 0) / 100:.2f}"
                )

            await session.commit()

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
                balance_before = wallet.current_balance

                # Update wallet balance
                await session.execute(
                    update(CreditWallet)
                    .where(CreditWallet.user_id == user_uuid)
                    .values(
                        current_balance=CreditWallet.current_balance + credits_amount,
                        total_purchased_this_cycle=CreditWallet.total_purchased_this_cycle + credits_amount,
                        lifetime_earned=CreditWallet.lifetime_earned + credits_amount,
                    )
                )

                # Create credit transaction record for audit trail
                txn = CreditTransactionModel(
                    wallet_id=wallet.id,
                    user_id=user_uuid,
                    transaction_type='earned',
                    action_type='topup_purchase',
                    amount=credits_amount,
                    description=f"Credit topup purchase - {topup_type} package",
                    balance_before=balance_before,
                    balance_after=balance_before + credits_amount,
                    billing_cycle_date=date.today(),
                    transaction_metadata={
                        'topup_type': topup_type,
                        'stripe_payment_id': payment_data.get('id'),
                        'credits_added': credits_amount,
                    },
                )
                session.add(txn)

                await session.commit()

                logger.info(f"Processed topup for user {user_id}: {credits_amount} credits added")

    except Exception as e:
        logger.error(f"Error handling topup payment: {e}")

async def reset_credit_wallet_for_new_cycle(user_id: UUID, subscription: Dict[str, Any]):
    """Reset credit wallet for new billing cycle"""
    try:
        # Determine tier from price ID using direct mapping
        tier = 'free'
        try:
            price_id = subscription['items']['data'][0]['price']['id']
            tier = STRIPE_PRICE_TO_TIER.get(price_id, 'free')
        except (KeyError, IndexError):
            logger.warning(f"Could not extract price_id from subscription for user {user_id}, defaulting to free")

        # Get tier allowances from canonical source (imported at module level)
        monthly_credits = _get_tier_credits(tier)

        # Reset wallet for new cycle
        async with get_session() as session:
            # Get current wallet for balance_before tracking
            result = await session.execute(
                select(CreditWallet).where(CreditWallet.user_id == user_id)
            )
            wallet = result.scalar_one_or_none()
            balance_before = wallet.current_balance if wallet else 0
            wallet_id = wallet.id if wallet else None

            await session.execute(
                update(CreditWallet)
                .where(CreditWallet.user_id == user_id)
                .values(
                    current_balance=monthly_credits,
                    total_earned_this_cycle=monthly_credits,
                    lifetime_earned=CreditWallet.lifetime_earned + monthly_credits,
                    total_spent_this_cycle=0,
                )
            )

            # Record transaction for audit trail
            if wallet_id and monthly_credits > 0:
                txn = CreditTransactionModel(
                    wallet_id=wallet_id,
                    user_id=user_id,
                    transaction_type='earned',
                    action_type='monthly_reset',
                    amount=monthly_credits,
                    description=f"Monthly credit reset - {tier} tier ({monthly_credits} credits)",
                    balance_before=balance_before,
                    balance_after=monthly_credits,
                    billing_cycle_date=date.today(),
                    transaction_metadata={
                        'tier': tier,
                        'billing_cycle_reset': True,
                        'stripe_subscription_id': subscription.get('id'),
                    },
                )
                session.add(txn)

            await session.commit()

        logger.info(f"Reset credit wallet for user {user_id}: {monthly_credits} credits for {tier} tier")

    except Exception as e:
        logger.error(f"Error resetting credit wallet: {e}")