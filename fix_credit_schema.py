"""
Fix missing columns in credit and user_profile_access tables
"""
import asyncio
from sqlalchemy import text
from app.database.connection import get_db

async def fix_missing_columns():
    """Add missing columns to database tables"""

    async for db in get_db():
        try:
            print("Fixing database schema issues...")

            # Fix user_profile_access table
            print("\n1. Fixing user_profile_access table...")

            # Check if columns exist
            check_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'user_profile_access'
            """)
            result = await db.execute(check_query)
            existing_columns = [row[0] for row in result]

            # Add access_type column if missing
            if 'access_type' not in existing_columns:
                print("   Adding access_type column...")
                await db.execute(text("""
                    ALTER TABLE user_profile_access
                    ADD COLUMN IF NOT EXISTS access_type VARCHAR(50) DEFAULT 'profile_unlock'
                """))
                await db.commit()
                print("   ✅ access_type column added")
            else:
                print("   ✓ access_type column already exists")

            # Add credits_spent column if missing
            if 'credits_spent' not in existing_columns:
                print("   Adding credits_spent column...")
                await db.execute(text("""
                    ALTER TABLE user_profile_access
                    ADD COLUMN IF NOT EXISTS credits_spent INTEGER DEFAULT 25
                """))
                await db.commit()
                print("   ✅ credits_spent column added")
            else:
                print("   ✓ credits_spent column already exists")

            # Fix credit_wallets table
            print("\n2. Fixing credit_wallets table...")

            # Check credit_wallets columns
            check_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'credit_wallets'
            """)
            result = await db.execute(check_query)
            wallet_columns = [row[0] for row in result]

            # Add test_mode column if missing
            if 'test_mode' not in wallet_columns:
                print("   Adding test_mode column...")
                await db.execute(text("""
                    ALTER TABLE credit_wallets
                    ADD COLUMN IF NOT EXISTS test_mode BOOLEAN DEFAULT FALSE
                """))
                await db.commit()
                print("   ✅ test_mode column added")
            else:
                print("   ✓ test_mode column already exists")

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
                if column_name not in wallet_columns:
                    print(f"   Adding {column_name} column...")
                    await db.execute(text(f"""
                        ALTER TABLE credit_wallets
                        ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                    """))
                    await db.commit()
                    print(f"   ✅ {column_name} column added")
                else:
                    print(f"   ✓ {column_name} column already exists")

            print("\n✅ Database schema fixes complete!")

        except Exception as e:
            print(f"❌ Error fixing schema: {e}")
            await db.rollback()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(fix_missing_columns())