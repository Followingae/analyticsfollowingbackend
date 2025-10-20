"""
Check Users Table Schema - Get required fields for user creation
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session, init_database

async def check_users_schema():
    """Check users table schema and existing user data"""
    print("Checking Users Table Schema")
    print("=" * 35)

    async with get_session() as db:
        try:
            from sqlalchemy import text

            # Get table schema
            schema_query = text("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)

            schema_result = await db.execute(schema_query)
            schema_records = schema_result.fetchall()

            print("Users table schema:")
            for record in schema_records:
                column_name, data_type, is_nullable, column_default = record
                nullable_text = "NULL" if is_nullable == "YES" else "NOT NULL"
                default_text = f"DEFAULT {column_default}" if column_default else ""
                print(f"  {column_name:<30} {data_type:<20} {nullable_text:<10} {default_text}")

            # Get sample existing user
            sample_query = text("""
                SELECT * FROM users LIMIT 1
            """)

            sample_result = await db.execute(sample_query)
            sample_record = sample_result.fetchone()

            if sample_record:
                print(f"\nSample existing user:")
                columns = sample_result.keys()
                for i, column in enumerate(columns):
                    value = sample_record[i]
                    print(f"  {column:<30} = {value}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")

async def main():
    """Main function"""
    await init_database()
    await check_users_schema()

if __name__ == "__main__":
    asyncio.run(main())