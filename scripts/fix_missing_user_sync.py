"""
Fix Missing User Sync - Create missing public.users record

This script creates the missing user record in public.users table for the auth user
who successfully unlocked a profile but can't see it due to missing sync.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session, init_database

async def create_missing_user():
    """Create missing user record in public.users table"""
    print("Creating Missing User Record")
    print("=" * 40)

    # User from logs who unlocked laurazaraa but can't see it
    auth_user_id = "f9dc7e70-adee-46db-930a-4d82a9c754a8"

    async with get_session() as db:
        try:
            from sqlalchemy import text
            from uuid import uuid4

            # Check if user already exists
            check_user_query = text("""
                SELECT id, email, supabase_user_id FROM users
                WHERE supabase_user_id = :auth_user_id
            """)

            existing_result = await db.execute(check_user_query, {
                "auth_user_id": auth_user_id
            })

            existing_user = existing_result.fetchone()

            if existing_user:
                print(f"User already exists:")
                print(f"  ID: {existing_user[0]}")
                print(f"  Email: {existing_user[1]}")
                print(f"  Supabase ID: {existing_user[2]}")
                return

            # Create new user record with realistic data
            print(f"Creating new user record for auth user: {auth_user_id}")

            new_user_id = uuid4()
            email = f"user_{auth_user_id[:8]}@temp.local"  # Temporary email

            insert_user_query = text("""
                INSERT INTO users (
                    id,
                    supabase_user_id,
                    email,
                    full_name,
                    role,
                    status,
                    credits,
                    credits_used_this_month,
                    subscription_tier,
                    preferences,
                    notification_preferences,
                    created_at,
                    updated_at
                ) VALUES (
                    :user_id,
                    :supabase_user_id,
                    :email,
                    :full_name,
                    :role,
                    :status,
                    :credits,
                    :credits_used_this_month,
                    :subscription_tier,
                    :preferences,
                    :notification_preferences,
                    :created_at,
                    :updated_at
                ) RETURNING id, email
            """)

            now = datetime.now(timezone.utc)

            user_result = await db.execute(insert_user_query, {
                "user_id": new_user_id,
                "supabase_user_id": auth_user_id,
                "email": email,
                "full_name": "Analytics User",
                "role": "user",
                "status": "active",
                "credits": 0,  # Start with 0 credits since they already spent some
                "credits_used_this_month": 25,  # They used 25 credits for laurazaraa
                "subscription_tier": "free",
                "preferences": '{"theme": "light", "notifications": true}',  # Basic preferences
                "notification_preferences": '{"weekly_reports": true, "security_alerts": true, "marketing_emails": false, "push_notifications": true, "email_notifications": true}',  # Default notifications
                "created_at": now,
                "updated_at": now
            })

            created_user = user_result.fetchone()

            if created_user:
                created_id, created_email = created_user
                print(f"SUCCESS: Created user record")
                print(f"  New ID: {created_id}")
                print(f"  Email: {created_email}")
                print(f"  Supabase ID: {auth_user_id}")

                # Create credit wallet for the user
                print("\nCreating credit wallet...")

                wallet_insert_query = text("""
                    INSERT INTO credit_wallets (
                        id,
                        user_id,
                        current_balance,
                        total_earned,
                        total_spent,
                        created_at,
                        updated_at
                    ) VALUES (
                        :wallet_id,
                        :user_id,
                        :current_balance,
                        :total_earned,
                        :total_spent,
                        :created_at,
                        :updated_at
                    ) RETURNING id
                """)

                wallet_id = uuid4()
                wallet_result = await db.execute(wallet_insert_query, {
                    "wallet_id": wallet_id,
                    "user_id": auth_user_id,  # Use auth user ID for wallet mapping
                    "current_balance": 0,  # They spent their credits
                    "total_earned": 25,  # They had 25 credits initially
                    "total_spent": 25,  # They spent 25 on laurazaraa
                    "created_at": now,
                    "updated_at": now
                })

                created_wallet = wallet_result.fetchone()
                if created_wallet:
                    print(f"  Wallet created: {created_wallet[0]}")

                # Now manually create the UserProfileAccess record that should have been created
                print("\nCreating missing UserProfileAccess record for laurazaraa...")

                # Get laurazaraa profile ID
                profile_query = text("""
                    SELECT id FROM profiles WHERE username = 'laurazaraa'
                """)

                profile_result = await db.execute(profile_query)
                profile_record = profile_result.fetchone()

                if profile_record:
                    profile_id = profile_record[0]

                    access_insert_query = text("""
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

                    access_id = uuid4()
                    access_result = await db.execute(access_insert_query, {
                        "access_id": access_id,
                        "user_id": new_user_id,  # Use the new public.users.id
                        "profile_id": profile_id,
                        "granted_at": now,
                        "expires_at": now.replace(day=now.day + 30) if now.day <= 28 else now.replace(month=now.month + 1, day=30 - (30 - now.day)),  # 30 days from now
                        "created_at": now
                    })

                    created_access = access_result.fetchone()
                    if created_access:
                        print(f"  Access record created: {created_access[0]}")
                        print(f"  User can now see laurazaraa profile!")
                    else:
                        print("  Failed to create access record")

                else:
                    print("  laurazaraa profile not found!")

                await db.commit()
                print("\nAll changes committed successfully!")

            else:
                print("Failed to create user record")

        except Exception as e:
            print(f"ERROR during user creation: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            await db.rollback()

async def main():
    """Main function"""
    print("Starting Missing User Sync Fix...")
    await init_database()
    await create_missing_user()
    print("\nMissing User Sync Fix Complete")

if __name__ == "__main__":
    asyncio.run(main())