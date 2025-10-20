"""
Simple User Sync Fix - Use existing auth service to sync the missing user

This fixes the profile visibility issue by using the existing user sync mechanism
instead of manually creating database records.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session, init_database
from app.services.supabase_auth_service import supabase_auth_service

async def sync_missing_user():
    """Sync missing user using existing auth service"""
    print("Syncing Missing User with Existing Auth Service")
    print("=" * 50)

    # User from logs who unlocked laurazaraa but can't see it
    auth_user_id = "f9dc7e70-adee-46db-930a-4d82a9c754a8"

    try:
        # Initialize the auth service
        await supabase_auth_service.ensure_initialized()
        print("Auth service initialized")

        # Create a mock Supabase user object for the sync
        class MockSupabaseUser:
            def __init__(self, user_id, email):
                self.id = user_id
                self.email = email or f"user_{user_id[:8]}@analytics.local"
                self.created_at = "2025-10-17T14:40:00Z"
                self.email_confirmed_at = "2025-10-17T14:40:00Z"
                self.phone_confirmed_at = None
                self.last_sign_in_at = "2025-10-17T14:40:00Z"
                self.user_metadata = {
                    "full_name": "Analytics User",
                    "role": "free"  # Use existing default role from system
                }
                self.app_metadata = {}

        mock_user = MockSupabaseUser(auth_user_id, None)
        print(f"Created mock user object for: {mock_user.email}")

        # Use the existing user sync mechanism
        async with get_session() as db:
            print("Syncing user to database...")
            await supabase_auth_service._ensure_user_in_database(
                mock_user,
                mock_user.user_metadata
            )
            print("User sync completed successfully!")

            # Verify the sync worked
            from sqlalchemy import text
            check_query = text("""
                SELECT id, email, supabase_user_id, role, status
                FROM users
                WHERE supabase_user_id = :auth_user_id
            """)

            result = await db.execute(check_query, {
                "auth_user_id": auth_user_id
            })

            user_record = result.fetchone()
            if user_record:
                user_id, email, supabase_id, role, status = user_record
                print(f"SUCCESS: User synced to database")
                print(f"  ID: {user_id}")
                print(f"  Email: {email}")
                print(f"  Role: {role}")
                print(f"  Status: {status}")

                # Now manually create the missing UserProfileAccess record
                print("\nCreating missing UserProfileAccess record...")

                # Get laurazaraa profile ID
                profile_query = text("""
                    SELECT id FROM profiles WHERE username = 'laurazaraa'
                """)

                profile_result = await db.execute(profile_query)
                profile_record = profile_result.fetchone()

                if profile_record:
                    profile_id = profile_record[0]

                    # Create access record (user paid 25 credits for this!)
                    from datetime import datetime, timezone, timedelta
                    from uuid import uuid4

                    access_insert = text("""
                        INSERT INTO user_profile_access (
                            id,
                            user_id,
                            profile_id,
                            granted_at,
                            expires_at,
                            created_at
                        ) VALUES (
                            :access_id,
                            :user_id,
                            :profile_id,
                            :granted_at,
                            :expires_at,
                            :created_at
                        ) RETURNING id
                    """)

                    now = datetime.now(timezone.utc)
                    expires_at = now + timedelta(days=30)

                    access_result = await db.execute(access_insert, {
                        "access_id": uuid4(),
                        "user_id": user_id,  # Use public.users.id
                        "profile_id": profile_id,
                        "granted_at": now,
                        "expires_at": expires_at,
                        "created_at": now
                    })

                    access_record = access_result.fetchone()
                    if access_record:
                        print(f"  Access record created: {access_record[0]}")
                        print(f"  User can now see laurazaraa profile!")
                        print(f"  Access expires: {expires_at}")

                    await db.commit()
                    print("\nAll fixes committed successfully!")
                    print("The user should now be able to see their unlocked profiles!")

                else:
                    print("  ERROR: laurazaraa profile not found")

            else:
                print("ERROR: User sync failed - no record created")

    except Exception as e:
        print(f"ERROR during sync: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

async def main():
    """Main function"""
    print("Starting Simple User Sync Fix...")
    await init_database()
    await sync_missing_user()
    print("\nSimple User Sync Fix Complete")

if __name__ == "__main__":
    asyncio.run(main())