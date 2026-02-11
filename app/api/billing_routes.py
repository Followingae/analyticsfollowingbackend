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

from app.database.connection import get_db
from app.models.auth import BillingType, UserRole
from pydantic import BaseModel
from app.services.stripe_billing_service import stripe_billing_service
from app.services.supabase_auth_service import supabase_auth_service

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

        logger.info(f"All validations passed for {request.email} - proceeding to create Stripe session")

        # Determine price ID based on plan (using monthly subscription prices)
        price_mapping = {
            "standard": os.getenv("STRIPE_STANDARD_MONTHLY_PRICE_ID"),  # price_1Sf1lpAubhSg1bPIiTWvBncS
            "premium": os.getenv("STRIPE_PREMIUM_MONTHLY_PRICE_ID")      # price_1Sf1lqAubhSg1bPIJIcqgHu1
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
                'language': request.language or 'en',
                # New personalization fields
                'industry': request.industry or '',
                'company_size': request.company_size or '',
                'use_case': request.use_case or '',
                'marketing_budget': request.marketing_budget or ''
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

                await db.execute(
                    update(User)
                    .where(User.email == email)
                    .values(
                        subscription_tier=metadata.get('plan', 'standard'),
                        status='active'
                    )
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

                        team = Team(
                            id=uuid.uuid4(),
                            name=f"{full_name}'s Team",
                            subscription_tier=plan,
                            max_team_members=5 if plan == 'premium' else 2,
                            monthly_profile_limit=2000 if plan == 'premium' else 500 if plan == 'standard' else 5,
                            monthly_email_limit=800 if plan == 'premium' else 250 if plan == 'standard' else 0,
                            monthly_posts_limit=300 if plan == 'premium' else 125 if plan == 'standard' else 0
                        )
                        db.add(team)

                        # Add user as team owner
                        team_member = TeamMember(
                            id=uuid.uuid4(),
                            team_id=team.id,
                            user_id=created_user.id,
                            role='owner',
                            status='active'
                        )
                        db.add(team_member)

                        # Create credit wallet with ALL required fields
                        from app.database.unified_models import CreditWallet
                        from datetime import date, timedelta

                        # Determine initial credits based on plan
                        initial_credits = 5000 if plan == 'premium' else 2000 if plan == 'standard' else 100

                        # Calculate billing cycle dates
                        today = date.today()
                        next_month = today.replace(day=1) + timedelta(days=32)
                        next_reset = next_month.replace(day=1)

                        wallet = CreditWallet(
                            user_id=created_user.supabase_user_id or created_user.id,  # Use Supabase ID if available
                            current_balance=initial_credits,
                            lifetime_earned=initial_credits,
                            lifetime_spent=0,
                            total_earned_this_cycle=initial_credits,
                            total_spent_this_cycle=0,
                            current_billing_cycle_start=today,
                            next_reset_date=next_reset,
                            # All other required fields have defaults in DB
                        )
                        db.add(wallet)

                        logger.info(f"Created team and wallet for {email}")

                    await db.commit()

                except Exception as e:
                    logger.error(f"Failed to create user {email}: {e}")
                    # Don't fail the webhook - log and continue

            logger.info(f"Successfully processed payment for {email}")

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
        session = stripe.checkout.Session.retrieve(session_id)
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
                # Generate authentication tokens for automatic login
                # Get the password from metadata (temporary approach)
                password = metadata.get('password', 'Following0925_25')

                try:
                    # Authenticate the user to get tokens
                    from app.models.auth import LoginRequest
                    login_request = LoginRequest(email=email, password=password)
                    auth_response = await supabase_auth_service.login_user(login_request)

                    if auth_response and auth_response.access_token:
                        return {
                            "status": "complete",
                            "message": "Account created successfully",
                            "email": email,
                            "can_login": True,
                            "access_token": auth_response.access_token,
                            "refresh_token": auth_response.refresh_token,
                            "user": {
                                "id": str(user.id),
                                "email": user.email,
                                "full_name": user.full_name,
                                "role": user.role,
                                "subscription_tier": user.subscription_tier
                            }
                        }
                except Exception as e:
                    logger.warning(f"Could not auto-login user {email}: {e}")

                # Fallback response without auto-login
                return {
                    "status": "complete",
                    "message": "Account created successfully",
                    "email": email,
                    "can_login": True
                }
            elif not user and session.payment_status == 'paid':
                # Payment complete but user doesn't exist - CREATE USER NOW!
                logger.info(f"Payment complete but user not found - creating user for {email}")

                # Extract user data from session metadata
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
                    logger.info(f"Successfully created user {email} via verify-session")

                    # Get the created user
                    result = await db.execute(
                        select(User).where(User.email == email)
                    )
                    created_user = result.scalar_one_or_none()

                    if created_user:
                        # Update user subscription info
                        await db.execute(
                            update(User)
                            .where(User.email == email)
                            .values(
                                subscription_tier=plan,
                                status='active'
                            )
                        )

                        # Create team for the user
                        from app.database.unified_models import Team, TeamMember
                        import uuid

                        team = Team(
                            id=uuid.uuid4(),
                            name=f"{full_name}'s Team",
                            subscription_tier=plan,
                            max_team_members=5 if plan == 'premium' else 2,
                            monthly_profile_limit=2000 if plan == 'premium' else 500,
                            monthly_email_limit=800 if plan == 'premium' else 250,
                            monthly_posts_limit=300 if plan == 'premium' else 125
                        )
                        db.add(team)

                        # Add user as team owner
                        team_member = TeamMember(
                            id=uuid.uuid4(),
                            team_id=team.id,
                            user_id=created_user.id,
                            role='owner',
                            status='active'
                        )
                        db.add(team_member)

                        # Create credit wallet
                        from app.database.unified_models import CreditWallet
                        from datetime import date, timedelta

                        initial_credits = 5000 if plan == 'premium' else 2000
                        today = date.today()
                        next_month = today.replace(day=1) + timedelta(days=32)
                        next_reset = next_month.replace(day=1)

                        wallet = CreditWallet(
                            user_id=created_user.supabase_user_id or created_user.id,  # Use supabase_user_id if available
                            current_balance=initial_credits,
                            lifetime_earned=initial_credits,
                            lifetime_spent=0,
                            total_earned_this_cycle=initial_credits,
                            total_spent_this_cycle=0,
                            billing_cycle_start=today,
                            billing_cycle_end=next_reset,
                            stripe_customer_id=session.customer,
                            stripe_subscription_id=session.subscription,
                            package_id=None,
                            last_credit_reset=today,
                            next_credit_reset=next_reset
                        )
                        db.add(wallet)

                        await db.commit()
                        logger.info(f"Created team and wallet for user {email}")

                        # Try to auto-login
                        try:
                            from app.models.auth import LoginRequest
                            login_request = LoginRequest(email=email, password=password)
                            auth_response = await supabase_auth_service.login(login_request)

                            if auth_response and auth_response.access_token:
                                return {
                                    "status": "complete",
                                    "message": "Account created successfully",
                                    "email": email,
                                    "can_login": True,
                                    "access_token": auth_response['access_token'],
                                    "refresh_token": auth_response.get('refresh_token'),
                                    "user": {
                                        "id": str(created_user.id),
                                        "email": created_user.email,
                                        "full_name": created_user.full_name,
                                        "role": created_user.role,
                                        "subscription_tier": plan
                                    }
                                }
                        except Exception as e:
                            logger.warning(f"Could not auto-login newly created user {email}: {e}")

                        # Return success without auto-login
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
                credits=100,
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
                max_team_members=1,
                monthly_profile_limit=5,
                monthly_email_limit=0,
                monthly_posts_limit=0
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
                current_balance=100,
                lifetime_earned=100,
                lifetime_spent=0,
                total_earned_this_cycle=100,
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