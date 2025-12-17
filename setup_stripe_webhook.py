"""
Setup Stripe Webhook for Analytics Following Platform
This script creates the webhook endpoint in Stripe and configures all necessary events
"""

import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe with your secret key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_webhook_endpoint():
    """Create webhook endpoint in Stripe"""

    try:
        # Define the webhook endpoint URL
        # Change this to your production URL when deploying
        webhook_url = "https://api.following.ae/api/v1/billing/webhook"

        # For local testing, you can use ngrok:
        # webhook_url = "https://your-ngrok-url.ngrok.io/api/v1/billing/webhook"

        print(f"Creating webhook endpoint: {webhook_url}")

        # Create the webhook endpoint
        webhook_endpoint = stripe.WebhookEndpoint.create(
            url=webhook_url,
            enabled_events=[
                # Checkout events
                "checkout.session.completed",
                "checkout.session.expired",

                # Subscription events
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
                "customer.subscription.paused",
                "customer.subscription.resumed",
                "customer.subscription.trial_will_end",

                # Payment events
                "invoice.payment_succeeded",
                "invoice.payment_failed",
                "invoice.payment_action_required",
                "invoice.upcoming",
                "invoice.finalized",

                # Customer events
                "customer.created",
                "customer.updated",
                "customer.deleted",

                # Payment method events
                "payment_method.attached",
                "payment_method.detached",
                "payment_method.updated",

                # Charge events (for one-time payments if needed)
                "charge.succeeded",
                "charge.failed",
                "charge.refunded",

                # Billing portal events
                "billing_portal.session.created",
                "billing_portal.configuration.created",
                "billing_portal.configuration.updated"
            ],
            description="Analytics Following Platform - Production Webhook",
            metadata={
                "environment": "production",
                "platform": "analytics_following"
            }
        )

        print("\n[SUCCESS] Webhook endpoint created successfully!")
        print(f"Webhook ID: {webhook_endpoint.id}")
        print(f"Webhook URL: {webhook_endpoint.url}")
        print(f"Webhook Secret: {webhook_endpoint.secret}")
        print(f"Status: {webhook_endpoint.status}")

        # Save the webhook secret to a file for easy copying
        with open('.env.webhook', 'w') as f:
            f.write(f"# Add this to your .env file:\n")
            f.write(f"STRIPE_WEBHOOK_SECRET={webhook_endpoint.secret}\n")
            f.write(f"STRIPE_WEBHOOK_ID={webhook_endpoint.id}\n")

        print("\n[INFO] Webhook secret saved to .env.webhook file")
        print("Copy the STRIPE_WEBHOOK_SECRET to your .env file")

        return webhook_endpoint

    except stripe.error.StripeError as e:
        print(f"[ERROR] Error creating webhook: {e}")
        return None

def list_existing_webhooks():
    """List existing webhook endpoints"""

    try:
        print("\n[INFO] Checking existing webhooks...")
        webhooks = stripe.WebhookEndpoint.list(limit=10)

        if webhooks.data:
            print(f"Found {len(webhooks.data)} existing webhook(s):")
            for webhook in webhooks.data:
                print(f"\n  - ID: {webhook.id}")
                print(f"    URL: {webhook.url}")
                print(f"    Status: {webhook.status}")
                print(f"    Created: {webhook.created}")

                # Check if this is our production webhook
                if "api.following.ae" in webhook.url:
                    print(f"    [WARNING]  This appears to be your production webhook")
                    print(f"    Secret: {webhook.secret}")

                    # Update the .env.webhook file
                    with open('.env.webhook', 'w') as f:
                        f.write(f"# Existing webhook found:\n")
                        f.write(f"STRIPE_WEBHOOK_SECRET={webhook.secret}\n")
                        f.write(f"STRIPE_WEBHOOK_ID={webhook.id}\n")

                    return webhook
        else:
            print("No existing webhooks found")

        return None

    except stripe.error.StripeError as e:
        print(f"[ERROR] Error listing webhooks: {e}")
        return None

def update_webhook_endpoint(webhook_id):
    """Update an existing webhook endpoint with all necessary events"""

    try:
        print(f"\n[INFO] Updating webhook {webhook_id}...")

        webhook_endpoint = stripe.WebhookEndpoint.modify(
            webhook_id,
            enabled_events=[
                # Essential events for subscription management
                "checkout.session.completed",
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
                "invoice.payment_succeeded",
                "invoice.payment_failed",
                "customer.created",
                "customer.updated"
            ]
        )

        print(f"[SUCCESS] Webhook updated successfully!")
        print(f"Webhook Secret: {webhook_endpoint.secret}")

        # Save the webhook secret
        with open('.env.webhook', 'w') as f:
            f.write(f"# Updated webhook configuration:\n")
            f.write(f"STRIPE_WEBHOOK_SECRET={webhook_endpoint.secret}\n")
            f.write(f"STRIPE_WEBHOOK_ID={webhook_endpoint.id}\n")

        return webhook_endpoint

    except stripe.error.StripeError as e:
        print(f"[ERROR] Error updating webhook: {e}")
        return None

def test_webhook_endpoint(webhook_id):
    """Send a test event to the webhook"""

    try:
        print(f"\n[INFO] Testing webhook {webhook_id}...")

        # Note: Stripe doesn't have a direct test method via API
        # You need to use Stripe CLI for testing

        print("\nTo test your webhook:")
        print("1. Install Stripe CLI: https://stripe.com/docs/stripe-cli")
        print("2. Login: stripe login")
        print("3. Forward events to local server:")
        print("   stripe listen --forward-to localhost:8000/api/v1/billing/webhook")
        print("4. Trigger test event:")
        print("   stripe trigger checkout.session.completed")

    except Exception as e:
        print(f"[ERROR] Error: {e}")

def main():
    """Main function to set up Stripe webhook"""

    print(" Stripe Webhook Setup for Analytics Following")
    print("=" * 50)

    # Check for existing webhooks
    existing_webhook = list_existing_webhooks()

    if existing_webhook and "api.following.ae" in existing_webhook.url:
        print("\n[SUCCESS] Production webhook already exists!")

        # Ask if user wants to update it
        response = input("\nDo you want to update the webhook events? (y/n): ")
        if response.lower() == 'y':
            update_webhook_endpoint(existing_webhook.id)
    else:
        # Create new webhook
        response = input("\nNo production webhook found. Create one? (y/n): ")
        if response.lower() == 'y':
            webhook = create_webhook_endpoint()

            if webhook:
                print("\n[SUCCESS] Setup complete!")
                print("\n[WARNING]  IMPORTANT NEXT STEPS:")
                print("1. Copy STRIPE_WEBHOOK_SECRET from .env.webhook to your .env file")
                print("2. Restart your backend server")
                print("3. Deploy your backend to production")
                print("4. Test the webhook using Stripe's webhook testing tool")

if __name__ == "__main__":
    main()