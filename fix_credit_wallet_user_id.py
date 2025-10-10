#!/usr/bin/env python3
"""
Fix Credit Wallet User ID Mismatch
Updates credit_wallets.user_id from auth.users.id to users.id for client@analyticsfollowing.com
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import get_session

async def fix_credit_wallet_user_ids():
    """Fix the user ID mismatch between auth.users.id and users.id"""

    print("🔧 FIXING CREDIT WALLET USER ID MISMATCH")
    print("=" * 50)

    async with get_session() as db:
        try:
            # Step 1: Identify the mismatch for client@analyticsfollowing.com
            print("\n1. Checking current state...")

            # Get auth.users.id for client@analyticsfollowing.com
            result = await db.execute(
                text("SELECT id FROM auth.users WHERE email = 'client@analyticsfollowing.com'")
            )
            auth_user_id = result.fetchone()
            auth_id = auth_user_id[0] if auth_user_id else None
            print(f"   auth.users.id: {auth_id}")

            # Get users.id for client@analyticsfollowing.com
            result = await db.execute(
                text("SELECT id FROM users WHERE email = 'client@analyticsfollowing.com'")
            )
            app_user = result.fetchone()
            app_user_id = app_user[0] if app_user else None
            print(f"   users.id: {app_user_id}")

            if not auth_id or not app_user_id:
                print("❌ ERROR: Could not find user in both tables")
                return False

            # Check current credit wallet
            result = await db.execute(
                text("SELECT user_id, current_balance FROM credit_wallets WHERE user_id = :auth_id"),
                {"auth_id": str(auth_id)}
            )
            wallet = result.fetchone()

            if not wallet:
                print("❌ ERROR: No credit wallet found for auth.users.id")
                return False

            print(f"   Current wallet: user_id={wallet[0]}, balance={wallet[1]}")

            # Step 2: Update the wallet to use users.id
            print("\n2. Updating credit wallet...")

            await db.execute(
                text("""
                    UPDATE credit_wallets
                    SET user_id = :app_user_id
                    WHERE user_id = :auth_id
                """),
                {
                    "app_user_id": str(app_user_id),
                    "auth_id": str(auth_id)
                }
            )

            # Step 3: Update any credit transactions
            print("3. Updating credit transactions...")

            result = await db.execute(
                text("SELECT COUNT(*) FROM credit_transactions WHERE user_id = :auth_id"),
                {"auth_id": str(auth_id)}
            )
            transaction_count = result.fetchone()[0]
            print(f"   Found {transaction_count} transactions to update")

            if transaction_count > 0:
                await db.execute(
                    text("""
                        UPDATE credit_transactions
                        SET user_id = :app_user_id
                        WHERE user_id = :auth_id
                    """),
                    {
                        "app_user_id": str(app_user_id),
                        "auth_id": str(auth_id)
                    }
                )

            # Step 4: Commit changes
            await db.commit()

            # Step 5: Verify the fix
            print("\n4. Verifying fix...")

            result = await db.execute(
                text("SELECT user_id, current_balance FROM credit_wallets WHERE user_id = :app_user_id"),
                {"app_user_id": str(app_user_id)}
            )
            updated_wallet = result.fetchone()

            if updated_wallet:
                print(f"✅ SUCCESS: Wallet now uses users.id: {updated_wallet[0]}")
                print(f"   Balance preserved: {updated_wallet[1]} credits")
                return True
            else:
                print("❌ ERROR: Wallet update verification failed")
                return False

        except Exception as e:
            print(f"❌ ERROR: {e}")
            await db.rollback()
            return False

async def main():
    """Run the fix"""
    success = await fix_credit_wallet_user_ids()

    if success:
        print("\n🎉 CREDIT WALLET FIX COMPLETED SUCCESSFULLY!")
        print("The billing page should now display correct data.")
    else:
        print("\n💥 FIX FAILED!")
        print("Please check the errors above and try again.")

    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)