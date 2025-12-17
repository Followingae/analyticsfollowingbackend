"""
Manually create user account for completed Stripe payment
This simulates what the webhook would do
"""
import asyncio
import stripe
import sys
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.connection import async_sessionmaker
from app.database.unified_models import User
from app.services.supabase_auth_service import supabase_auth_service
from app.models.auth import UserCreate, BillingType, UserRole
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_user_from_session(session_id: str):
    """Create user account from completed checkout session"""

    # Get session from Stripe
    session = stripe.checkout.Session.retrieve(session_id)
    print(f"Session ID: {session.id}")
    print(f"Payment Status: {session.payment_status}")
    print(f"Customer Email: {session.customer_details.email if session.customer_details else 'N/A'}")

    if session.payment_status != 'paid':
        print("❌ Payment not completed!")
        return

    # Get metadata (if available)
    metadata = session.metadata or {}
    email = metadata.get('email') or session.customer_details.email

    if not email:
        print("❌ No email found in session!")
        return

    print(f"\n✅ Payment verified for: {email}")

    # Create user data
    user_data = UserCreate(
        email=email,
        password=metadata.get('password', 'TempPassword123!'),  # Should be in metadata
        full_name=metadata.get('full_name', email.split('@')[0]),
        role=UserRole.STANDARD if metadata.get('plan') == 'standard' else UserRole.PREMIUM,
        billing_type=BillingType.ONLINE_PAYMENT,
        company=metadata.get('company'),
        job_title=metadata.get('job_title'),
        phone_number=metadata.get('phone_number'),
        timezone=metadata.get('timezone', 'UTC'),
        language=metadata.get('language', 'en')
    )

    print(f"Creating user account for: {email} (Plan: {metadata.get('plan', 'standard')})")

    try:
        # Register user in Supabase
        user_response = await supabase_auth_service.register_user(user_data)
        print(f"✅ User created in Supabase: {user_response['user']['id']}")

        # Update user with Stripe IDs
        async with async_session_maker() as db:
            await db.execute(
                update(User)
                .where(User.email == email)
                .values(
                    stripe_customer_id=session.customer,
                    stripe_subscription_id=session.subscription,
                    subscription_status='active',
                    status='active'
                )
            )
            await db.commit()
            print(f"✅ User updated with Stripe IDs")

        print(f"\n🎉 SUCCESS! User account created for {email}")
        print(f"The user can now login with their credentials")

    except Exception as e:
        print(f"❌ Error creating user: {e}")

if __name__ == "__main__":
    # The session ID from the frontend
    session_id = "cs_test_a16wz9u7lLdoq8AHTl4VeisWoVuFY6vyFG1G9qMpZSphBTtQL15WZoHSop"
    asyncio.run(create_user_from_session(session_id))