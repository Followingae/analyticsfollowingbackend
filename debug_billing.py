#!/usr/bin/env python3
"""
Debug Billing Issue
Test the credit wallet service directly to see what's happening
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from uuid import UUID
from app.services.credit_wallet_service import credit_wallet_service

async def debug_billing():
    """Debug billing issues"""

    print("🔍 DEBUGGING BILLING ISSUE")
    print("=" * 50)

    # Test the exact user ID from the logs
    user_id = UUID('99b1001b-69a0-4d75-9730-3177ba42c642')
    print(f"Testing user ID: {user_id}")
    print(f"User ID type: {type(user_id)}")

    try:
        # Test get_wallet directly
        print("\n1. Testing get_wallet()...")
        wallet = await credit_wallet_service.get_wallet(user_id)
        print(f"Wallet result: {wallet}")

        if wallet:
            print(f"   Wallet ID: {wallet.id}")
            print(f"   Current Balance: {wallet.current_balance}")
            print(f"   Package ID: {wallet.package_id}")
            print(f"   Is Locked: {wallet.is_locked}")
        else:
            print("   ❌ Wallet is None!")

        # Test get_wallet_balance
        print("\n2. Testing get_wallet_balance()...")
        balance = await credit_wallet_service.get_wallet_balance(user_id)
        print(f"Balance result: {balance}")

        if balance:
            print(f"   Balance: {balance.balance}")
            print(f"   Is Locked: {balance.is_locked}")
            print(f"   Next Reset: {balance.next_reset_date}")

        # Test get_wallet_summary
        print("\n3. Testing get_wallet_summary()...")
        summary = await credit_wallet_service.get_wallet_summary(user_id)
        print(f"Summary result: {summary}")

        if summary:
            print(f"   Current Balance: {summary.current_balance}")
            print(f"   Package Credits: {getattr(summary, 'package_credits', 'N/A')}")
            print(f"   Purchased Credits: {getattr(summary, 'purchased_credits', 'N/A')}")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run the debug"""
    await debug_billing()

if __name__ == "__main__":
    asyncio.run(main())