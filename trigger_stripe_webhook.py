"""
Trigger Stripe webhook for checkout completion
This simulates what happens when a payment is completed
"""
import subprocess
import sys
import json
import time

def trigger_checkout_completed(session_id):
    """
    Trigger checkout.session.completed event using Stripe CLI
    """
    print(f"\n[INFO] Triggering webhook for session: {session_id}")

    # Build the command
    cmd = [
        "./stripe_new/stripe.exe",  # Path to Stripe CLI
        "trigger",
        "checkout.session.completed",
        "--add",
        f"checkout_session:id={session_id}",
        "--api-key",
        "sk_test_51Sf0ElAubhSg1bPIu0gnb86BfHI2iKO3P5YO9uaJZhtAEFNeQuzRcfwRjkuBba8dbInYafGmZCHqoNY5W0qbMgjg00eYoazmFC"
    ]

    try:
        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("[SUCCESS] Webhook triggered successfully!")
            print(result.stdout)
            return True
        else:
            print(f"[ERROR] Failed to trigger webhook:")
            print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("[ERROR] Command timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to run command: {e}")
        return False

def main():
    """Main function to trigger webhooks for test sessions"""

    # Test sessions from our signup tests
    test_sessions = [
        "cs_test_a1V75d9mt4Uqst7jJ7mfTcGksquz6Q3cJndOALIceBET6m4gW434qntrsp",  # Standard
        "cs_test_a1BhPgg4pRjPaZJV2IO0mQLc0OSse9OGiwUXnFUzQ5B7n25A2WX4lDoZ4D"   # Premium
    ]

    if len(sys.argv) > 1:
        # Use provided session ID
        test_sessions = [sys.argv[1]]

    print("="*50)
    print("STRIPE WEBHOOK TRIGGER")
    print("="*50)

    for session_id in test_sessions:
        success = trigger_checkout_completed(session_id)
        if success:
            print(f"[SUCCESS] Triggered webhook for {session_id[:20]}...")
        else:
            print(f"[FAILED] Could not trigger webhook for {session_id[:20]}...")

        # Small delay between triggers
        if len(test_sessions) > 1:
            time.sleep(2)

    print("\n[INFO] All webhooks triggered")
    print("[INFO] Check your application logs to see if they were processed")

if __name__ == "__main__":
    main()