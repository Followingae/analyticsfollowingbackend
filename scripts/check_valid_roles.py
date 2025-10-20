"""
Check Valid Roles - See what roles are allowed in the database
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session, init_database

async def check_valid_roles():
    """Check what roles exist in the system"""
    print("Checking Valid Roles")
    print("=" * 20)

    async with get_session() as db:
        try:
            from sqlalchemy import text

            # Check roles of existing users
            roles_query = text("""
                SELECT DISTINCT role, COUNT(*) as count
                FROM users
                GROUP BY role
                ORDER BY count DESC
            """)

            roles_result = await db.execute(roles_query)
            roles_records = roles_result.fetchall()

            print("Existing roles in database:")
            for record in roles_records:
                role, count = record
                print(f"  {role:<15} ({count} users)")

            # Check if there's a check constraint on role
            constraint_query = text("""
                SELECT
                    conname,
                    consrc
                FROM pg_constraint
                WHERE conrelid = 'users'::regclass
                AND contype = 'c'
                AND conname LIKE '%role%'
            """)

            constraint_result = await db.execute(constraint_query)
            constraint_records = constraint_result.fetchall()

            print("\nRole constraints:")
            for record in constraint_records:
                constraint_name, constraint_src = record
                print(f"  {constraint_name}: {constraint_src}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")

async def main():
    """Main function"""
    await init_database()
    await check_valid_roles()

if __name__ == "__main__":
    asyncio.run(main())