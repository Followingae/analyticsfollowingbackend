"""
Fix missing columns in credit and user_profile_access tables - Direct database connection
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_missing_columns():
    """Add missing columns to database tables"""

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return

    # Connect directly to database
    conn = await asyncpg.connect(database_url, statement_cache_size=0)

    try:
        print("Connected to database. Fixing schema issues...")

        # Fix user_profile_access table
        print("\n1. Fixing user_profile_access table...")

        # Check if columns exist
        existing_columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user_profile_access'
        """)
        existing_column_names = [row['column_name'] for row in existing_columns]

        # Add access_type column if missing
        if 'access_type' not in existing_column_names:
            print("   Adding access_type column...")
            await conn.execute("""
                ALTER TABLE user_profile_access
                ADD COLUMN access_type VARCHAR(50) DEFAULT 'profile_unlock'
            """)
            print("   [OK] access_type column added")
        else:
            print("   [EXISTS] access_type column already exists")

        # Add credits_spent column if missing
        if 'credits_spent' not in existing_column_names:
            print("   Adding credits_spent column...")
            await conn.execute("""
                ALTER TABLE user_profile_access
                ADD COLUMN credits_spent INTEGER DEFAULT 25
            """)
            print("   [OK] credits_spent column added")
        else:
            print("   [EXISTS] credits_spent column already exists")

        # Fix credit_wallets table
        print("\n2. Fixing credit_wallets table...")

        # Check credit_wallets columns
        wallet_columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'credit_wallets'
        """)
        wallet_column_names = [row['column_name'] for row in wallet_columns]

        # Add test_mode column if missing
        if 'test_mode' not in wallet_column_names:
            print("   Adding test_mode column...")
            await conn.execute("""
                ALTER TABLE credit_wallets
                ADD COLUMN test_mode BOOLEAN DEFAULT FALSE
            """)
            print("   [OK] test_mode column added")
        else:
            print("   [EXISTS] test_mode column already exists")

        # Add other missing wallet columns
        wallet_columns_to_add = [
            ('total_earned_this_cycle', 'INTEGER DEFAULT 0'),
            ('total_purchased_this_cycle', 'INTEGER DEFAULT 0'),
            ('total_spent_this_cycle', 'INTEGER DEFAULT 0'),
            ('lifetime_earned', 'INTEGER DEFAULT 0'),
            ('lifetime_spent', 'INTEGER DEFAULT 0'),
            ('current_billing_cycle_start', 'DATE'),
            ('current_billing_cycle_end', 'DATE'),
            ('next_reset_date', 'DATE'),
            ('next_credit_refresh_date', 'DATE'),
            ('rollover_months_allowed', 'INTEGER DEFAULT 0'),
            ('subscription_status', "VARCHAR(50) DEFAULT 'active'"),
            ('subscription_active', 'BOOLEAN DEFAULT TRUE'),
            ('auto_refresh_enabled', 'BOOLEAN DEFAULT TRUE'),
            ('is_locked', 'BOOLEAN DEFAULT FALSE')
        ]

        for column_name, column_type in wallet_columns_to_add:
            if column_name not in wallet_column_names:
                print(f"   Adding {column_name} column...")
                await conn.execute(f"""
                    ALTER TABLE credit_wallets
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"   [OK] {column_name} column added")
            else:
                print(f"   [EXISTS] {column_name} column already exists")

        print("\n[SUCCESS] Database schema fixes complete!")

    except Exception as e:
        print(f"[ERROR] Error fixing schema: {e}")
    finally:
        await conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    asyncio.run(fix_missing_columns())