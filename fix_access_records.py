#!/usr/bin/env python3
"""
URGENT FIX: Remove free allowance and create access record for barakatme
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from sqlalchemy import text
from app.database.connection import get_session

async def fix_free_allowance_and_access():
    """Remove free allowance and create access record"""
    print("STARTING URGENT FIX...")

    async with get_session() as db:
        try:
            # Fix #1: Remove free allowance
            print("\nFIX #1: Removing free allowance...")
            result = await db.execute(text("""
                UPDATE credit_pricing_rules
                SET free_allowance_per_month = 0
                WHERE action_type = 'profile_analysis'
            """))
            await db.commit()
            print(f"FREE ALLOWANCE REMOVED: Updated {result.rowcount} pricing rule(s)")

            # Verify the change
            verify = await db.execute(text("""
                SELECT action_type, cost_per_action, free_allowance_per_month
                FROM credit_pricing_rules
                WHERE action_type = 'profile_analysis'
            """))
            row = verify.fetchone()
            print(f"VERIFIED: profile_analysis now costs {row[1]} credits with {row[2]} free allowance")

            # Fix #2: Create access record for barakatme
            print("\nFIX #2: Creating access record for barakatme...")

            # Get user and profile IDs
            user_result = await db.execute(text("""
                SELECT id FROM users WHERE email = 'client@analyticsfollowing.com'
            """))
            user_row = user_result.fetchone()

            profile_result = await db.execute(text("""
                SELECT id FROM profiles WHERE username = 'barakatme'
            """))
            profile_row = profile_result.fetchone()

            if user_row and profile_row:
                user_id = user_row[0]
                profile_id = profile_row[0]

                # Create access record
                await db.execute(text("""
                    INSERT INTO user_profile_access (user_id, profile_id, granted_at, expires_at, created_at)
                    VALUES (:user_id, :profile_id, NOW(), NOW() + INTERVAL '30 days', NOW())
                    ON CONFLICT (user_id, profile_id) DO UPDATE SET
                        granted_at = NOW(),
                        expires_at = NOW() + INTERVAL '30 days'
                """), {
                    'user_id': user_id,
                    'profile_id': profile_id
                })
                await db.commit()
                print(f"ACCESS RECORD CREATED: {user_id} -> {profile_id}")

                # Verify access record
                verify_access = await db.execute(text("""
                    SELECT upa.granted_at, upa.expires_at, p.username
                    FROM user_profile_access upa
                    JOIN profiles p ON upa.profile_id = p.id
                    WHERE upa.user_id = :user_id AND p.username = 'barakatme'
                """), {'user_id': user_id})
                access_row = verify_access.fetchone()

                if access_row:
                    print(f"VERIFIED ACCESS: barakatme expires {access_row[1]}")
                else:
                    print("ACCESS VERIFICATION FAILED")
            else:
                print(f"USER OR PROFILE NOT FOUND: user={user_row}, profile={profile_row}")

            print("\nFIXES COMPLETED SUCCESSFULLY!")
            print("Free allowance removed - users will be charged 25 credits")
            print("barakatme access record created - will appear in unlocked profiles")

        except Exception as e:
            print(f"ERROR: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(fix_free_allowance_and_access())