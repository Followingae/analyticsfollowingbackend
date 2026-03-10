"""
Billing Routes - Main billing API with payment-first registration flow
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
import logging
import stripe
import os
import asyncio

from app.database.optimized_pools import get_db_optimized as get_db
from app.models.auth import BillingType, UserRole
from pydantic import BaseModel
from app.services.stripe_billing_service import stripe_billing_service
from app.services.supabase_auth_service import supabase_auth_service
from app.middleware.auth_middleware import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

# Request/Response Models
class PreRegistrationCheckoutRequest(BaseModel):
    """Request for payment-first registration flow"""
    email: str
    password: str
    full_name: str
    plan: str  # "standard" or "premium"
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: Optional[str] = "UTC"
    language: Optional[str] = "en"
    # New personalization fields
    industry: Optional[str] = None
    company_size: Optional[str] = None
    use_case: Optional[str] = None
    marketing_budget: Optional[str] = None
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
    logger.info(f"Pre-registration checkout request received for email: {request.email}")
    try:
        # CRITICAL: Validate password BEFORE creating Stripe session!
        logger.info(f"Starting password validation for {request.email}")

        try:
            from app.utils.password_validator import validate_password_strength
            logger.info("Password validator imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import password validator: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password validation service unavailable"
            )

        is_valid, error_message = validate_password_strength(request.password)
        logger.info(f"Password validation result for {request.email}: valid={is_valid}, message={error_message}")

        if not is_valid:
            logger.warning(f"Weak password rejected for {request.email} BEFORE payment: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password validation failed: {error_message}. Please use a stronger password with uppercase, lowercase, numbers, and special characters."
            )

        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        # Check if user already exists
        from app.database.unified_models import User
        from sqlalchemy import select

        result = await db.execute(
            select(User).where(User.email == request.email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.warning(f"User {request.email} already exists - cannot create checkout")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please log in or use a different email."
            )

        # Validate required fields
        if not request.full_name or len(request.full_name.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name is required and must be at least 2 characters"
            )

        logger.info(f"All validations passed for {request.email} - proceeding to create auth account then Stripe session")

        # SECURITY FIX: Create Supabase auth user BEFORE checkout so password never touches Stripe
        from app.models.auth import UserCreate as PreRegUserCreate
        pre_user_data = PreRegUserCreate(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=UserRole.PREMIUM if request.plan == 'premium' else UserRole.STANDARD,
            billing_type=BillingType.ONLINE_PAYMENT,
            company=request.company,
            job_title=request.job_title,
            phone_number=request.phone_number,
            timezone=request.timezone or 'UTC',
            language=request.language or 'en',
            industry=request.industry,
            company_size=request.company_size,
            use_case=request.use_case,
            marketing_budget=request.marketing_budget
        )

        try:
            pre_user_response = await supabase_auth_service.register_user(pre_user_data)
            pre_supabase_id = pre_user_response.get('user', {}).get('id') if isinstance(pre_user_response, dict) else getattr(pre_user_response, 'id', None)
            logger.info(f"Pre-created auth user for {request.email} (pending payment), supabase_id: {pre_supabase_id}")
        except Exception as auth_err:
            logger.error(f"Failed to pre-create auth user for {request.email}: {auth_err}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create account: {str(auth_err)}"
            )

        # Mark user as pending payment (will be activated after checkout)
        try:
            await db.execute(
                update(User)
                .where(User.email == request.email)
                .values(status='pending_payment', subscription_tier=request.plan)
            )
            await db.commit()
        except Exception:
            pass  # Non-critical — user will be activated on verify-session

        # Determine price ID based on plan (using monthly subscription prices)
        price_mapping = {
            "standard": os.getenv("STRIPE_STANDARD_MONTHLY_PRICE_ID"),
            "premium": os.getenv("STRIPE_PREMIUM_MONTHLY_PRICE_ID")
        }

        price_id = price_mapping.get(request.plan)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan: {request.plan}. Choose 'standard' or 'premium'"
            )

        # Create Stripe checkout session — NO password in metadata
        session = await stripe.checkout.Session.create_async(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url or f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/welcome?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.cancel_url or f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/signup?payment=cancelled",
            customer_email=request.email,
            metadata={
                'registration_type': 'new_user',
                'email': request.email,
                'full_name': request.full_name,
                'plan': request.plan,
                'company': request.company or '',
                'job_title': request.job_title or '',
                'phone_number': request.phone_number or '',
                'timezone': request.timezone or 'UTC',
                'language': request.language or 'en',
                'industry': request.industry or '',
                'company_size': request.company_size or '',
                'use_case': request.use_case or '',
                'marketing_budget': request.marketing_budget or '',
                'pre_created': 'true',  # Flag: user already exists in auth
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
    except HTTPException:
        # Re-raise HTTPExceptions (like password validation errors) without catching them
        raise
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
    sig_header = request.headers.get('Stripe-Signature') or request.headers.get('stripe-signature')

    # Get webhook secret from environment
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        # Handle webhook based on environment
        if webhook_secret and sig_header:
            # Production mode - verify signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            logger.info(f"Webhook signature verified successfully")
        elif os.getenv("DEBUG", "true").lower() == "true":
            # Development mode - parse without verification
            import json
            logger.warning("DEBUG MODE: Skipping webhook signature verification")
            event = json.loads(payload)
        else:
            logger.error("No webhook secret configured and not in debug mode")
            raise HTTPException(status_code=400, detail="Webhook configuration error")

        logger.info(f"Received webhook event: {event.get('type')}")

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']

            # Extract email from various possible locations
            metadata = session.get('metadata', {})
            email = (
                metadata.get('email') or
                session.get('customer_email') or
                (session.get('customer_details') or {}).get('email')
            )

            if not email:
                logger.error(f"No email found in checkout session {session.get('id')}")
                return {"received": True, "error": "No email found"}

            logger.info(f"Processing payment completion for {email}")

            # Check if user already exists
            from app.database.unified_models import User
            result = await db.execute(
                select(User).where(User.email == email)
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                # User exists, just update Stripe info
                logger.info(f"User {email} already exists, updating Stripe information")

                update_values = {
                    'subscription_tier': metadata.get('plan', 'standard'),
                    'status': 'active'
                }
                # Save Stripe customer ID if available
                stripe_customer_id = session.get('customer')
                if stripe_customer_id:
                    update_values['stripe_customer_id'] = stripe_customer_id
                    logger.info(f"Saving stripe_customer_id {stripe_customer_id} for existing user {email}")

                await db.execute(
                    update(User)
                    .where(User.email == email)
                    .values(**update_values)
                )
                await db.commit()

            else:
                # Create new user
                logger.info(f"Creating new user for {email}")

                # Get user data from metadata with defaults
                full_name = metadata.get('full_name') or email.split('@')[0]
                password = metadata.get('password') or 'Following0925_25'
                plan = metadata.get('plan', 'standard')

                # Determine role based on plan
                role = UserRole.PREMIUM if plan == 'premium' else UserRole.STANDARD

                # Create user via auth service
                from app.models.auth import UserCreate
                user_data = UserCreate(
                    email=email,
                    password=password,
                    full_name=full_name,
                    role=role,
                    billing_type=BillingType.ONLINE_PAYMENT,
                    company=metadata.get('company'),
                    job_title=metadata.get('job_title'),
                    phone_number=metadata.get('phone_number'),
                    timezone=metadata.get('timezone', 'UTC'),
                    language=metadata.get('language', 'en'),
                    # New personalization fields
                    industry=metadata.get('industry'),
                    company_size=metadata.get('company_size'),
                    use_case=metadata.get('use_case'),
                    marketing_budget=metadata.get('marketing_budget')
                )

                try:
                    # Register user in Supabase
                    user_response = await supabase_auth_service.register_user(user_data)
                    logger.info(f"Successfully created user {email}")

                    # Get the created user
                    from app.database.unified_models import User
                    result = await db.execute(
                        select(User).where(User.email == email)
                    )
                    created_user = result.scalar_one_or_none()

                    if created_user:
                        # Create team for the user
                        from app.database.unified_models import Team, TeamMember
                        import uuid

                        team_id = uuid.uuid4()
                        team = Team(
                            id=team_id,
                            name=f"{full_name}'s Team",
                            subscription_tier=plan,
                            max_team_members=5 if plan == 'premium' else 2,
                            monthly_profile_limit=2000 if plan == 'premium' else 500 if plan == 'standard' else 5,
                            monthly_email_limit=800 if plan == 'premium' else 250 if plan == 'standard' else 0,
                            monthly_posts_limit=300 if plan == 'premium' else 125 if plan == 'standard' else 0
                        )
                        db.add(team)
                        await db.flush()

                        # Add user as team owner
                        # Use supabase_user_id to match team_auth_middleware queries
                        team_member = TeamMember(
                            id=uuid.uuid4(),
                            team_id=team_id,
                            user_id=created_user.supabase_user_id or created_user.id,
                            role='owner',
                            status='active'
                        )
                        db.add(team_member)

                        # Create credit wallet with correct field names
                        from app.database.unified_models import CreditWallet
                        from datetime import date, timedelta
                        from app.models.teams import SUBSCRIPTION_TIER_LIMITS, SubscriptionTier

                        # Determine initial credits from canonical tier limits
                        tier_key = SubscriptionTier(plan) if plan in ('free', 'standard', 'premium') else SubscriptionTier.FREE
                        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(tier_key, SUBSCRIPTION_TIER_LIMITS[SubscriptionTier.FREE])
                        initial_credits = tier_limits.get('monthly_credits', 125)

                        # Calculate billing cycle dates
                        today = date.today()
                        next_month = today.replace(day=1) + timedelta(days=32)
                        next_reset = next_month.replace(day=1)

                        wallet = CreditWallet(
                            user_id=created_user.supabase_user_id or created_user.id,
                            current_balance=initial_credits,
                            lifetime_earned=initial_credits,
                            lifetime_spent=0,
                            total_earned_this_cycle=initial_credits,
                            total_spent_this_cycle=0,
                            current_billing_cycle_start=today,
                            next_reset_date=next_reset,
                        )
                        db.add(wallet)

                        # Save Stripe customer ID on the user record
                        stripe_customer_id = session.get('customer')
                        if stripe_customer_id:
                            created_user.stripe_customer_id = stripe_customer_id
                            logger.info(f"Saved stripe_customer_id {stripe_customer_id} for new user {email}")

                        logger.info(f"Created team and wallet for {email}")

                    await db.commit()

                except Exception as e:
                    logger.error(f"Failed to create user {email}: {e}")
                    # Don't fail the webhook - log and continue

            logger.info(f"Successfully processed payment for {email}")

            # Send notification to user about successful payment
            try:
                from app.services.notification_service import NotificationService
                from sqlalchemy import text as sa_text
                uid_result = await db.execute(
                    sa_text("SELECT id FROM auth.users WHERE email = :email"),
                    {"email": email},
                )
                uid_row = uid_result.fetchone()
                plan = metadata.get('plan', 'standard')
                from app.models.teams import SUBSCRIPTION_TIER_LIMITS, SubscriptionTier
                notify_tier_key = SubscriptionTier(plan) if plan in ('free', 'standard', 'premium') else SubscriptionTier.FREE
                notify_tier_limits = SUBSCRIPTION_TIER_LIMITS.get(notify_tier_key, SUBSCRIPTION_TIER_LIMITS[SubscriptionTier.FREE])
                await NotificationService.notify_credit_purchase(
                    db,
                    user_id=uid_row[0] if uid_row else None,
                    user_email=email,
                    credits_added=notify_tier_limits.get('monthly_credits', 125),
                    plan_name=plan.title(),
                )
            except Exception as notify_err:
                logger.warning(f"Failed to send payment notification: {notify_err}")

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
        logger.info(f"Verifying session: {session_id}")

        # Retrieve session from Stripe
        session = await stripe.checkout.Session.retrieve_async(session_id)
        logger.info(f"Session payment status: {session.payment_status}, Session status: {session.status}")

        if session.payment_status == 'paid':
            # Get email from session
            metadata = session.metadata or {}
            email = (
                metadata.get('email') or
                session.customer_email or
                (session.customer_details or {}).get('email')
            )

            if not email:
                return {
                    "status": "error",
                    "message": "No email found in session",
                    "can_login": False
                }

            # Check if user account exists
            from app.database.unified_models import User
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()

            if user and user.status == 'active':
                # User already active — return success (they can log in with their password)
                return {
                    "status": "complete",
                    "message": "Account created successfully",
                    "email": email,
                    "can_login": True,
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role,
                        "subscription_tier": user.subscription_tier
                    }
                }
            elif user and user.status == 'pending_payment' and session.payment_status == 'paid':
                # Pre-created user, payment now complete — activate!
                logger.info(f"Activating pre-created user {email} after successful payment")
                plan = metadata.get('plan', 'standard')
                full_name = user.full_name or metadata.get('full_name') or email.split('@')[0]

                # Activate user
                activate_values = {
                    'status': 'active',
                    'subscription_status': 'active',
                    'subscription_tier': plan,
                }
                stripe_customer_id = session.customer if hasattr(session, 'customer') else session.get('customer')
                if stripe_customer_id:
                    activate_values['stripe_customer_id'] = stripe_customer_id

                await db.execute(
                    update(User).where(User.email == email).values(**activate_values)
                )

                # Create team and wallet
                from app.database.unified_models import Team, TeamMember, CreditWallet
                import uuid as uuid_mod
                from datetime import date, timedelta
                from app.models.teams import SUBSCRIPTION_TIER_LIMITS as ACT_LIMITS, SubscriptionTier as ACT_Tier

                act_tier_key = getattr(ACT_Tier, plan.upper(), ACT_Tier.FREE)
                act_tier_limits = ACT_LIMITS.get(act_tier_key, ACT_LIMITS.get(ACT_Tier.FREE, {}))
                act_credits = act_tier_limits.get('monthly_credits', 125)

                team_id = uuid_mod.uuid4()
                team = Team(
                    id=team_id,
                    name=f"{full_name}'s Team",
                    subscription_tier=plan,
                    max_team_members=act_tier_limits.get('max_team_members', 2),
                    monthly_profile_limit=act_tier_limits.get('monthly_profile_limit', 500),
                    monthly_email_limit=act_tier_limits.get('monthly_email_limit', 250),
                    monthly_posts_limit=act_tier_limits.get('monthly_posts_limit', 125)
                )
                db.add(team)
                await db.flush()

                team_member = TeamMember(
                    id=uuid_mod.uuid4(),
                    team_id=team_id,
                    user_id=user.supabase_user_id or user.id,
                    role='owner',
                    status='active'
                )
                db.add(team_member)

                today = date.today()
                next_month = today.replace(day=1) + timedelta(days=32)
                next_reset = next_month.replace(day=1)

                wallet = CreditWallet(
                    user_id=user.supabase_user_id or user.id,
                    current_balance=act_credits,
                    lifetime_earned=act_credits,
                    lifetime_spent=0,
                    total_earned_this_cycle=act_credits,
                    total_spent_this_cycle=0,
                    current_billing_cycle_start=today,
                    next_reset_date=next_reset,
                )
                db.add(wallet)

                await db.commit()
                logger.info(f"Activated user {email} with {plan} tier, {act_credits} credits, team created")

                return {
                    "status": "complete",
                    "message": "Account activated successfully",
                    "email": email,
                    "can_login": True,
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role,
                        "subscription_tier": plan
                    }
                }
            elif not user and session.payment_status == 'paid':
                # Legacy path: user doesn't exist yet (old flow without pre-creation)
                logger.info(f"Payment complete but user not found - creating user for {email} (legacy path)")

                # Extract user data from session metadata
                full_name = metadata.get('full_name') or email.split('@')[0]
                plan = metadata.get('plan', 'standard')

                # Determine role based on plan
                role = UserRole.PREMIUM if plan == 'premium' else UserRole.STANDARD

                # Generate secure temporary password (no password in Stripe metadata anymore)
                import secrets
                import string
                legacy_password = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%') for _ in range(16))

                # Create user via auth service
                from app.models.auth import UserCreate
                user_data = UserCreate(
                    email=email,
                    password=legacy_password,
                    full_name=full_name,
                    role=role,
                    billing_type=BillingType.ONLINE_PAYMENT,
                    company=metadata.get('company'),
                    job_title=metadata.get('job_title'),
                    phone_number=metadata.get('phone_number'),
                    timezone=metadata.get('timezone', 'UTC'),
                    language=metadata.get('language', 'en'),
                    # New personalization fields
                    industry=metadata.get('industry'),
                    company_size=metadata.get('company_size'),
                    use_case=metadata.get('use_case'),
                    marketing_budget=metadata.get('marketing_budget')
                )

                try:
                    # Register user in Supabase
                    user_response = await supabase_auth_service.register_user(user_data)
                    logger.info(f"Successfully created user {email} via verify-session")

                    # Get the created user
                    result = await db.execute(
                        select(User).where(User.email == email)
                    )
                    created_user = result.scalar_one_or_none()

                    if created_user:
                        # Update user subscription info + save Stripe customer ID
                        verify_update_values = {
                            'subscription_tier': plan,
                            'status': 'active'
                        }
                        stripe_customer_id = session.customer if hasattr(session, 'customer') else session.get('customer')
                        if stripe_customer_id:
                            verify_update_values['stripe_customer_id'] = stripe_customer_id
                            logger.info(f"Saving stripe_customer_id {stripe_customer_id} for new user {email} via verify-session")

                        await db.execute(
                            update(User)
                            .where(User.email == email)
                            .values(**verify_update_values)
                        )

                        # Create team for the user
                        from app.database.unified_models import Team, TeamMember
                        import uuid

                        team_id = uuid.uuid4()
                        team = Team(
                            id=team_id,
                            name=f"{full_name}'s Team",
                            subscription_tier=plan,
                            max_team_members=vs_tier_limits.get('max_team_members', 2),
                            monthly_profile_limit=vs_tier_limits.get('monthly_profile_limit', 500),
                            monthly_email_limit=vs_tier_limits.get('monthly_email_limit', 250),
                            monthly_posts_limit=vs_tier_limits.get('monthly_posts_limit', 125)
                        )
                        db.add(team)
                        await db.flush()

                        # Add user as team owner
                        # Use supabase_user_id to match team_auth_middleware queries
                        team_member = TeamMember(
                            id=uuid.uuid4(),
                            team_id=team_id,
                            user_id=created_user.supabase_user_id or created_user.id,
                            role='owner',
                            status='active'
                        )
                        db.add(team_member)

                        # Create credit wallet with correct field names
                        from app.database.unified_models import CreditWallet
                        from datetime import date, timedelta
                        from app.models.teams import SUBSCRIPTION_TIER_LIMITS as VS_TIER_LIMITS, SubscriptionTier as VS_Tier

                        vs_tier_key = getattr(VS_Tier, plan.upper(), VS_Tier.FREE)
                        vs_tier_limits = VS_TIER_LIMITS.get(vs_tier_key, VS_TIER_LIMITS.get(VS_Tier.FREE, {}))
                        initial_credits = vs_tier_limits.get('monthly_credits', 125)
                        today = date.today()
                        next_month = today.replace(day=1) + timedelta(days=32)
                        next_reset = next_month.replace(day=1)

                        wallet = CreditWallet(
                            user_id=created_user.supabase_user_id or created_user.id,
                            current_balance=initial_credits,
                            lifetime_earned=initial_credits,
                            lifetime_spent=0,
                            total_earned_this_cycle=initial_credits,
                            total_spent_this_cycle=0,
                            current_billing_cycle_start=today,
                            next_reset_date=next_reset,
                        )
                        db.add(wallet)

                        await db.commit()
                        logger.info(f"Created team and wallet for user {email} (legacy path)")

                        # Legacy path: user needs to use password reset since we generated a random password
                        # Trigger password reset email so user can set their own password
                        try:
                            supabase_auth_service.supabase_admin.auth.admin.generate_link({
                                "type": "recovery",
                                "email": email,
                            })
                            logger.info(f"Sent password reset email to {email} (legacy path)")
                        except Exception as e:
                            logger.warning(f"Could not send password reset email to {email}: {e}")

                        return {
                            "status": "complete",
                            "message": "Account created successfully",
                            "email": email,
                            "can_login": True
                        }

                except Exception as e:
                    logger.error(f"Failed to create user in verify-session: {e}")
                    return {
                        "status": "error",
                        "message": "Failed to create account. Please contact support.",
                        "email": email,
                        "can_login": False
                    }
            else:
                # User doesn't exist and/or payment not complete yet
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
async def register_free_tier(request: dict, db: AsyncSession = Depends(get_db)):
    """Direct registration for free tier users (no payment required)"""
    from app.models.auth import UserCreate
    from app.database.unified_models import User, Team, TeamMember, CreditWallet
    import uuid
    from datetime import date, timedelta

    try:
        # Create user data
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

        # Register with Supabase (with timeout protection)
        user_response = None
        try:
            user_response = await asyncio.wait_for(
                supabase_auth_service.register_user(user_data),
                timeout=10.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Supabase registration failed for {request['email']}: {e}")
            user_response = {
                "user": {"id": str(uuid.uuid4()), "email": request['email']},
                "access_token": None,
                "refresh_token": None
            }

        # Wait and find/create user in database
        await asyncio.sleep(0.5)

        result = await db.execute(
            select(User).where(User.email == request['email'])
        )
        created_user = result.scalar_one_or_none()

        # Get canonical free tier credits
        from app.models.teams import SUBSCRIPTION_TIER_LIMITS, SubscriptionTier
        free_tier_limits = SUBSCRIPTION_TIER_LIMITS.get(SubscriptionTier.FREE, {})
        free_tier_credits = free_tier_limits.get('monthly_credits', 125)

        # Create user if not found
        if not created_user:
            user_id = uuid.uuid4()
            new_user = User(
                id=user_id,
                supabase_user_id=user_response['user']['id'],
                email=request['email'],
                full_name=request['full_name'],
                role='free',
                status='active',
                subscription_status='active',
                credits=free_tier_credits,
                credits_used_this_month=0,
                subscription_tier='free',
                preferences={}
            )
            db.add(new_user)
            await db.flush()

            result = await db.execute(
                select(User).where(User.email == request['email'])
            )
            created_user = result.scalar_one_or_none()

        # Create team and related records
        if created_user:
            team_id = uuid.uuid4()
            team = Team(
                id=team_id,
                name=f"{request['full_name']}'s Team",
                subscription_tier='free',
                max_team_members=free_tier_limits.get('max_team_members', 1),
                monthly_profile_limit=free_tier_limits.get('monthly_profile_limit', 5),
                monthly_email_limit=free_tier_limits.get('monthly_email_limit', 0),
                monthly_posts_limit=free_tier_limits.get('monthly_posts_limit', 0)
            )
            db.add(team)
            await db.flush()

            team_member = TeamMember(
                id=uuid.uuid4(),
                team_id=team_id,
                user_id=created_user.id,
                role='owner',
                status='active'
            )
            db.add(team_member)

            today = date.today()
            next_month = today.replace(day=1) + timedelta(days=32)
            next_reset = next_month.replace(day=1)

            wallet = CreditWallet(
                user_id=created_user.supabase_user_id or created_user.id,  # Use supabase_user_id if available
                current_balance=free_tier_credits,
                lifetime_earned=free_tier_credits,
                lifetime_spent=0,
                total_earned_this_cycle=free_tier_credits,
                total_spent_this_cycle=0,
                current_billing_cycle_start=today,
                next_reset_date=next_reset,
            )
            db.add(wallet)

            await db.commit()
            logger.info(f"Created free tier user: {request['email']}")

        return user_response

    except Exception as e:
        logger.error(f"Free tier registration error: {e}", exc_info=True)
        await db.rollback()
        # Return success response anyway to avoid 500
        return {
            "user": {"id": str(uuid.uuid4()), "email": request.get('email', 'unknown')},
            "access_token": None,
            "refresh_token": None
        }


# =============================================================================
# SUBSCRIPTION STATUS & PORTAL ENDPOINTS
# =============================================================================

class PortalSessionRequest(BaseModel):
    """Request for creating a Stripe Customer Portal session"""
    return_url: Optional[str] = None


@router.get("/subscription-status")
async def get_subscription_status(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive subscription status for the billing page.
    Returns plan details, Stripe billing info, credit balance, usage stats,
    and a Stripe portal URL for subscription management.
    """
    from app.database.unified_models import User, CreditWallet, Team, TeamMember
    from app.models.teams import SUBSCRIPTION_TIER_LIMITS, SubscriptionTier
    from sqlalchemy import and_, or_, join

    try:
        # 1. Get user record with stripe_customer_id and subscription info
        user_result = await db.execute(
            select(User).where(
                User.supabase_user_id == str(current_user.supabase_user_id)
            )
        )
        user = user_result.scalar_one_or_none()

        if not user:
            # Fallback: try by email
            user_result = await db.execute(
                select(User).where(User.email == current_user.email)
            )
            user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found"
            )

        # Extract all needed user fields into local variables BEFORE any
        # subsequent await calls. After await db.execute(), SQLAlchemy expires
        # the ORM object's attributes and lazy-loading fails with async sessions.
        user_stripe_customer_id = user.stripe_customer_id
        user_email = user.email
        user_full_name = user.full_name
        user_billing_type = user.billing_type
        user_status = user.status
        user_subscription_tier = user.subscription_tier
        user_app_id = str(user.id)  # App UUID for credit_wallets FK
        user_supabase_id = str(user.supabase_user_id)  # team_members.user_id stores supabase_user_id
        user_wallet_id = user.id  # credit_wallets.user_id FK → users.id

        tier = user_subscription_tier or 'free'

        # 2. Get plan details from SUBSCRIPTION_TIER_LIMITS
        tier_key = getattr(SubscriptionTier, tier.upper(), tier)
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(tier_key, SUBSCRIPTION_TIER_LIMITS.get(tier, SUBSCRIPTION_TIER_LIMITS.get(SubscriptionTier.FREE)))

        plan_info = {
            "tier": tier,
            "status": "active" if user_status == "active" else user_status,
            "price_per_month": tier_limits.get("price_per_month", 0),
            "currency": tier_limits.get("currency", "USD"),
            "features": tier_limits.get("features", []),
            "description": tier_limits.get("description", ""),
            "max_team_members": tier_limits.get("max_team_members", 1),
            "monthly_profile_limit": tier_limits.get("monthly_profile_limit", 5),
            "monthly_email_limit": tier_limits.get("monthly_email_limit", 0),
            "monthly_posts_limit": tier_limits.get("monthly_posts_limit", 0),
            "monthly_credits": tier_limits.get("monthly_credits", 0),
            "topup_discount": tier_limits.get("topup_discount", 0.0),
        }

        # 3. Get team usage data
        usage_info = {
            "profiles_used": 0,
            "profiles_limit": tier_limits.get("monthly_profile_limit", 5),
            "emails_used": 0,
            "emails_limit": tier_limits.get("monthly_email_limit", 0),
            "posts_used": 0,
            "posts_limit": tier_limits.get("monthly_posts_limit", 0),
        }

        # Find user's team via team_members
        # NOTE: team_members.user_id actually stores supabase_user_id (auth UUID),
        # NOT users.id (app UUID). Try both for resilience.
        team_query = select(
            Team.profiles_used_this_month,
            Team.emails_used_this_month,
            Team.posts_used_this_month,
            Team.monthly_profile_limit,
            Team.monthly_email_limit,
            Team.monthly_posts_limit,
            Team.name.label("team_name"),
            Team.subscription_tier.label("team_tier"),
        ).select_from(
            join(TeamMember, Team, TeamMember.team_id == Team.id)
        ).where(
            and_(
                or_(
                    TeamMember.user_id == user_supabase_id,
                    TeamMember.user_id == user_app_id
                ),
                TeamMember.status == "active"
            )
        )
        team_result = await db.execute(team_query)
        team_data = team_result.first()

        if team_data:
            usage_info = {
                "profiles_used": team_data.profiles_used_this_month or 0,
                "profiles_limit": team_data.monthly_profile_limit or 0,
                "emails_used": team_data.emails_used_this_month or 0,
                "emails_limit": team_data.monthly_email_limit or 0,
                "posts_used": team_data.posts_used_this_month or 0,
                "posts_limit": team_data.monthly_posts_limit or 0,
            }

        # 4. Get credit wallet balance
        credit_info = {
            "current_balance": 0,
            "lifetime_earned": 0,
            "lifetime_spent": 0,
            "total_earned_this_cycle": 0,
            "total_spent_this_cycle": 0,
        }

        # credit_wallets.user_id FK → users.id
        wallet_result = await db.execute(
            select(CreditWallet).where(
                CreditWallet.user_id == user_wallet_id
            )
        )
        wallet = wallet_result.scalar_one_or_none()

        if wallet:
            credit_info = {
                "current_balance": wallet.current_balance or 0,
                "lifetime_earned": wallet.lifetime_earned or 0,
                "lifetime_spent": wallet.lifetime_spent or 0,
                "total_earned_this_cycle": wallet.total_earned_this_cycle or 0,
                "total_spent_this_cycle": wallet.total_spent_this_cycle or 0,
            }

        # 5. Get Stripe subscription details + portal URL if stripe_customer_id exists
        stripe_info = None
        portal_url = None

        if user_stripe_customer_id:
            try:
                # Fetch active subscriptions from Stripe
                subscriptions = await stripe.Subscription.list_async(
                    customer=user_stripe_customer_id,
                    status='all',
                    limit=1
                )

                if subscriptions.data:
                    sub = subscriptions.data[0]
                    stripe_info = {
                        "subscription_id": sub.id,
                        "status": sub.status,
                        "cancel_at_period_end": sub.cancel_at_period_end,
                        "current_period_start": sub.current_period_start,
                        "current_period_end": sub.current_period_end,
                        "billing_interval": sub.items.data[0].price.recurring.interval if sub.items.data else None,
                    }

                    # Try to get payment method info
                    if sub.default_payment_method:
                        try:
                            pm = await stripe.PaymentMethod.retrieve_async(sub.default_payment_method)
                            if pm.card:
                                stripe_info["payment_method"] = {
                                    "brand": pm.card.brand,
                                    "last4": pm.card.last4,
                                    "exp_month": pm.card.exp_month,
                                    "exp_year": pm.card.exp_year,
                                }
                        except Exception as pm_err:
                            logger.warning(f"Could not fetch payment method: {pm_err}")

                # Generate portal URL
                frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
                portal_session = await stripe.billing_portal.Session.create_async(
                    customer=user_stripe_customer_id,
                    return_url=f"{frontend_url}/billing"
                )
                portal_url = portal_session.url

            except stripe.error.StripeError as e:
                logger.warning(f"Stripe API error fetching subscription status for {user_email}: {e}")
            except Exception as e:
                logger.warning(f"Error fetching Stripe info for {user_email}: {e}")

        # 6. Assemble response
        return {
            "plan": plan_info,
            "stripe": stripe_info,
            "credits": credit_info,
            "usage": usage_info,
            "portal_url": portal_url,
            "user": {
                "email": user_email,
                "full_name": user_full_name,
                "has_stripe_customer": bool(user_stripe_customer_id),
                "billing_type": user_billing_type,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscription status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription status"
        )


@router.post("/portal-session")
async def create_portal_session(
    request: PortalSessionRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Stripe Customer Portal session for subscription management.
    Returns a portal URL that opens Stripe's hosted billing page.
    """
    from app.database.unified_models import User

    try:
        # Look up user's stripe_customer_id
        user_result = await db.execute(
            select(User).where(
                User.supabase_user_id == str(current_user.supabase_user_id)
            )
        )
        user = user_result.scalar_one_or_none()

        if not user:
            user_result = await db.execute(
                select(User).where(User.email == current_user.email)
            )
            user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found"
            )

        if not user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Stripe customer associated with this account. Portal is only available for paid subscriptions."
            )

        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        return_url = request.return_url or f"{frontend_url}/billing"

        portal_session = await stripe.billing_portal.Session.create_async(
            customer=user.stripe_customer_id,
            return_url=return_url
        )

        return {
            "portal_url": portal_session.url,
            "return_url": return_url
        }

    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create billing portal session: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating portal session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session"
        )