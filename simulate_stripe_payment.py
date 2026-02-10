"""
Simulate Stripe payment completion for test checkouts
This simulates what happens when a user completes payment on Stripe's checkout page
"""
import stripe
import os
import sys
import asyncio
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def complete_checkout_session(session_id):
    """Complete a Stripe checkout session for testing"""
    try:
        # Retrieve the session
        print(f"[INFO] Retrieving session: {session_id}")
        session = stripe.checkout.Session.retrieve(session_id)

        print(f"[INFO] Session status: {session.status}")
        print(f"[INFO] Customer email: {session.customer_email}")
        print(f"[INFO] Payment status: {session.payment_status}")

        if session.status == "expired":
            print("[ERROR] Session has expired")
            return False

        if session.payment_status == "paid":
            print("[SUCCESS] Payment already completed")
            return True

        # In test mode, we can't directly complete the payment programmatically
        # The user needs to go to the checkout URL and complete it
        # Or we can use Stripe CLI to trigger the webhook

        print("\n" + "="*50)
        print("TO COMPLETE PAYMENT:")
        print("="*50)
        print(f"1. Open this URL in your browser:")
        print(f"   {session.url}")
        print(f"\n2. Use test card details:")
        print(f"   Number: 4242 4242 4242 4242")
        print(f"   Expiry: 04/44")
        print(f"   CVC: 444")
        print(f"   Name: Zain Khan")
        print(f"\n3. Complete the payment")
        print("\nOR use Stripe CLI to trigger webhook:")
        print(f"stripe trigger checkout.session.completed --add checkout_session:id={session_id}")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to process session: {e}")
        return False

async def trigger_webhook_for_session(session_id):
    """Trigger webhook completion using Stripe CLI"""
    import subprocess

    try:
        # Check if Stripe CLI is available
        result = subprocess.run(["stripe", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("[ERROR] Stripe CLI not found. Please install it first.")
            return False

        print(f"[INFO] Triggering webhook for session: {session_id}")

        # Trigger the webhook
        cmd = [
            "stripe",
            "trigger",
            "checkout.session.completed",
            "--add",
            f"checkout_session:id={session_id}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("[SUCCESS] Webhook triggered successfully")
            print(result.stdout)
            return True
        else:
            print(f"[ERROR] Failed to trigger webhook: {result.stderr}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to trigger webhook: {e}")
        return False

async def main():
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
    else:
        session_id = input("Enter the Stripe checkout session ID: ").strip()

    if not session_id:
        print("[ERROR] No session ID provided")
        return

    print("\n" + "="*50)
    print("STRIPE PAYMENT SIMULATOR")
    print("="*50)

    # Try to complete the session
    success = await complete_checkout_session(session_id)

    if success:
        print("\n[INFO] Attempting to trigger webhook...")
        await trigger_webhook_for_session(session_id)

if __name__ == "__main__":
    asyncio.run(main())