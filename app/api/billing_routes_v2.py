"""
Billing Routes V2 - Payment before registration flow
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
import logging
import stripe
import os

from app.database.connection import get_db
from app.models.auth import BillingType, UserRole
from pydantic import BaseModel
from app.services.stripe_billing_service import stripe_billing_service
from app.services.supabase_auth_service import supabase_auth_service
from app.middleware.auth_middleware import get_current_user, get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/billing/v2", tags=["billing_v2"])

# Request/Response Models
class PreRegistrationCheckoutRequest(BaseModel):
    """Request for payment-first registration flow"""
    email: str
    password: str
    full_name: str
    plan: str  # "standard" or "premium" (no payment for "free")
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: Optional[str] = "UTC"
    language: Optional[str] = "en"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class CheckoutSessionResponse(BaseModel):
    sessionId: str
    sessionUrl: str

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/pre-registration-checkout", response_model=CheckoutSessionResponse)
async def create_pre_registration_checkout(
    request: PreRegistrationCheckoutRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create Stripe checkout session BEFORE user registration.
    User account will be created only after successful payment.
    """
    try:
        # Determine price ID based on plan
        price_mapping = {
            "standard": os.getenv("STRIPE_STANDARD_PRICE_ID"),
            "premium": os.getenv("STRIPE_PREMIUM_PRICE_ID")
        }

        price_id = price_mapping.get(request.plan)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan: {request.plan}. Choose 'standard' or 'premium'"
            )

        # Create Stripe checkout session with metadata
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url or f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/welcome?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.cancel_url or f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/signup?payment=cancelled",
            customer_email=request.email,  # Pre-fill email in Stripe checkout
            metadata={
                # Store registration data in metadata to create account after payment
                'registration_type': 'new_user',
                'email': request.email,
                'full_name': request.full_name,
                'password': request.password,  # Note: In production, hash this or use a temporary token
                'plan': request.plan,
                'company': request.company or '',
                'job_title': request.job_title or '',
                'phone_number': request.phone_number or '',
                'timezone': request.timezone or 'UTC',
                'language': request.language or 'en'
            },
            subscription_data={
                'metadata': {
                    'plan': request.plan,
                    'email': request.email
                }
            }
        )

        logger.info(f"Created pre-registration checkout session for {request.email} - Plan: {request.plan}")

        return CheckoutSessionResponse(
            sessionId=session.id,
            sessionUrl=session.url
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment system error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating pre-registration checkout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize payment process"
        )


@router.post("/webhook/complete-registration")
async def handle_payment_success_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook handler for successful payment - creates user account
    Called by Stripe when checkout.session.completed
    """
    payload = await request.body()
    # Try both header cases for compatibility
    sig_header = request.headers.get('Stripe-Signature') or request.headers.get('stripe-signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    if not sig_header:
        logger.error("No Stripe signature header found")
        raise HTTPException(status_code=400, detail="No signature header")

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']

            # Check if this is a registration payment
            if session['metadata'].get('registration_type') == 'new_user':

                # Extract registration data from metadata
                email = session['metadata']['email']
                full_name = session['metadata']['full_name']
                password = session['metadata']['password']
                plan = session['metadata']['plan']
                company = session['metadata'].get('company')
                job_title = session['metadata'].get('job_title')
                phone_number = session['metadata'].get('phone_number')
                timezone = session['metadata'].get('timezone', 'UTC')
                language = session['metadata'].get('language', 'en')

                # Get Stripe customer ID
                customer_id = session['customer']
                subscription_id = session['subscription']

                # Determine role based on plan
                role_mapping = {
                    'standard': UserRole.STANDARD,
                    'premium': UserRole.PREMIUM
                }
                role = role_mapping.get(plan, UserRole.STANDARD)

                # Create user account via Supabase Auth
                from app.models.auth import UserCreate
                user_data = UserCreate(
                    email=email,
                    password=password,
                    full_name=full_name,
                    role=role,
                    billing_type=BillingType.ONLINE_PAYMENT,
                    company=company,
                    job_title=job_title,
                    phone_number=phone_number,
                    timezone=timezone,
                    language=language
                )

                # Register user in Supabase and database
                user_response = await supabase_auth_service.register_user(user_data)

                # Update user with Stripe IDs
                from app.database.unified_models import User
                await db.execute(
                    update(User)
                    .where(User.email == email)
                    .values(
                        stripe_customer_id=customer_id,
                        stripe_subscription_id=subscription_id,
                        subscription_status='active',
                        status='active'  # Ensure user is active
                    )
                )
                await db.commit()

                logger.info(f"Successfully created account for {email} after payment")

                # TODO: Send welcome email with login instructions

        return {"received": True}

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        # Return 200 to prevent Stripe retries for app errors
        return {"received": True, "error": str(e)}


@router.get("/verify-session/{session_id}")
async def verify_checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify if a checkout session was completed and account was created
    Frontend can poll this after redirect from Stripe
    """
    try:
        # Retrieve session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status == 'paid':
            email = session.metadata.get('email')

            # Check if user account exists
            from app.database.unified_models import User
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()

            if user and user.status == 'active':
                return {
                    "status": "complete",
                    "message": "Account created successfully",
                    "email": email,
                    "can_login": True
                }
            else:
                return {
                    "status": "processing",
                    "message": "Account creation in progress",
                    "email": email,
                    "can_login": False
                }
        else:
            return {
                "status": "pending_payment",
                "message": "Payment not completed",
                "can_login": False
            }

    except stripe.error.StripeError as e:
        logger.error(f"Error verifying session: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session"
        )


@router.post("/free-tier-registration")
async def register_free_tier(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Direct registration for free tier users (no payment required)
    """
    from app.models.auth import UserCreate

    user_data = UserCreate(
        email=request['email'],
        password=request['password'],
        full_name=request['full_name'],
        role=UserRole.FREE,
        billing_type=BillingType.ONLINE_PAYMENT,
        company=request.get('company'),
        job_title=request.get('job_title'),
        phone_number=request.get('phone_number'),
        timezone=request.get('timezone', 'UTC'),
        language=request.get('language', 'en')
    )

    # Register user directly (no payment needed for free tier)
    user_response = await supabase_auth_service.register_user(user_data)

    return user_response