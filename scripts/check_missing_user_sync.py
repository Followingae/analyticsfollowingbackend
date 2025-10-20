"""
Check Missing User Sync - Find user_profile_access records without public.users mapping

This script looks for user_profile_access records that might exist but are orphaned
due to missing public.users records.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session, init_database

async def check_missing_user_sync():
    """Check for orphaned user_profile_access records"""
    print("Checking Missing User Sync Issue")
    print("=" * 50)

    # Test user from logs
    test_auth_user_id = "f9dc7e70-adee-46db-930a-4d82a9c754a8"

    async with get_session() as db:
        try:
            from sqlalchemy import text

            # Check if there are user_profile_access records for this auth user directly
            print(f"1. Checking user_profile_access records with auth user ID directly...")
            direct_access_query = text("""
                SELECT
                    upa.id,
                    upa.user_id,
                    upa.granted_at,
                    upa.expires_at,
                    p.username,
                    p.full_name,
                    (upa.expires_at > NOW()) as is_active
                FROM user_profile_access upa
                JOIN profiles p ON p.id = upa.profile_id
                WHERE upa.user_id::text = :auth_user_id
                ORDER BY upa.granted_at DESC
            """)

            direct_result = await db.execute(direct_access_query, {
                "auth_user_id": test_auth_user_id
            })

            direct_records = direct_result.fetchall()
            print(f"   Found {len(direct_records)} records with auth user ID directly:")

            for record in direct_records:
                access_id, user_id, granted_at, expires_at, username, full_name, is_active = record
                status = "ACTIVE" if is_active else "EXPIRED"
                print(f"     {username} ({full_name}) - {status}")
                print(f"       User ID: {user_id}")
                print(f"       Granted: {granted_at}")
                print(f"       Expires: {expires_at}")

            # Check all user_profile_access records to see the format of user_id
            print(f"\n2. Checking all user_profile_access records to understand user_id format...")
            all_access_query = text("""
                SELECT
                    upa.user_id,
                    u.email,
                    u.supabase_user_id,
                    p.username,
                    (upa.expires_at > NOW()) as is_active
                FROM user_profile_access upa
                LEFT JOIN users u ON u.id = upa.user_id
                JOIN profiles p ON p.id = upa.profile_id
                ORDER BY upa.granted_at DESC
                LIMIT 10
            """)

            all_access_result = await db.execute(all_access_query)
            all_access_records = all_access_result.fetchall()

            print(f"   Found {len(all_access_records)} total access records:")
            for record in all_access_records:
                user_id, email, supabase_user_id, username, is_active = record
                status = "ACTIVE" if is_active else "EXPIRED"
                user_info = f"{email} (Supabase: {supabase_user_id})" if email else "NO USER RECORD"
                print(f"     {username} - {status}")
                print(f"       User ID: {user_id}")
                print(f"       User Info: {user_info}")

            # Check if there are any access records with our specific auth user ID as a UUID
            print(f"\n3. Looking for records with auth user ID as UUID...")
            uuid_access_query = text("""
                SELECT
                    upa.id,
                    upa.user_id,
                    p.username,
                    upa.granted_at,
                    upa.expires_at
                FROM user_profile_access upa
                JOIN profiles p ON p.id = upa.profile_id
                WHERE upa.user_id = :auth_user_id::uuid
                ORDER BY upa.granted_at DESC
            """)

            try:
                uuid_result = await db.execute(uuid_access_query, {
                    "auth_user_id": test_auth_user_id
                })

                uuid_records = uuid_result.fetchall()
                print(f"   Found {len(uuid_records)} records with UUID conversion:")

                for record in uuid_records:
                    access_id, user_id, username, granted_at, expires_at = record
                    print(f"     {username} - User ID: {user_id}")
                    print(f"       Granted: {granted_at}")
                    print(f"       Expires: {expires_at}")

            except Exception as uuid_error:
                print(f"   UUID conversion failed: {uuid_error}")

            # Check how laurazaraa unlock transaction was recorded
            print(f"\n4. Checking credit transactions for laurazaraa unlock...")
            transaction_query = text("""
                SELECT
                    ct.id,
                    ct.user_id,
                    ct.amount,
                    ct.action_type,
                    ct.description,
                    ct.created_at,
                    u.email,
                    u.supabase_user_id
                FROM credit_transactions ct
                LEFT JOIN users u ON u.id = ct.user_id
                WHERE ct.description ILIKE '%laurazaraa%'
                ORDER BY ct.created_at DESC
                LIMIT 5
            """)

            transaction_result = await db.execute(transaction_query)
            transaction_records = transaction_result.fetchall()

            print(f"   Found {len(transaction_records)} credit transactions for laurazaraa:")
            for record in transaction_records:
                ct_id, user_id, amount, action_type, description, created_at, email, supabase_user_id = record
                user_info = f"{email} (Supabase: {supabase_user_id})" if email else "NO USER RECORD"
                print(f"     Transaction: {action_type} - {amount} credits")
                print(f"       User ID: {user_id}")
                print(f"       User Info: {user_info}")
                print(f"       Description: {description}")
                print(f"       Created: {created_at}")

        except Exception as e:
            print(f"ERROR during check: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")

async def main():
    """Main function"""
    print("Starting Missing User Sync Check...")
    await init_database()
    await check_missing_user_sync()
    print("\nMissing User Sync Check Complete")

if __name__ == "__main__":
    asyncio.run(main())