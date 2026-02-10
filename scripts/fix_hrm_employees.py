"""
Fix HRM employees with empty employee codes
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database.connection import SessionLocal, init_database
import logging

logger = logging.getLogger(__name__)


async def fix_empty_employee_codes():
    """Fix employees with empty employee codes"""
    await init_database()

    async with SessionLocal() as db:
        try:
            # First, check if there are any employees with empty employee codes
            check_query = text("""
                SELECT id, full_name, email, employee_code
                FROM hrm_employees
                WHERE employee_code IS NULL OR employee_code = ''
            """)
            result = await db.execute(check_query)
            employees_to_fix = result.fetchall()

            if not employees_to_fix:
                print("✅ No employees with empty employee codes found")
                return

            print(f"Found {len(employees_to_fix)} employees with empty employee codes:")
            for emp in employees_to_fix:
                print(f"  - {emp.full_name} ({emp.email})")

            # Generate unique employee codes for each
            import random
            import string
            from datetime import datetime

            for idx, emp in enumerate(employees_to_fix, 1):
                # Generate a unique code
                year = datetime.now().year
                random_num = ''.join(random.choices(string.digits, k=3))
                new_code = f"EMP{year}{random_num:03d}"

                # Check if this code already exists
                check_code = text("""
                    SELECT COUNT(*) FROM hrm_employees
                    WHERE employee_code = :code
                """)
                exists = await db.execute(check_code, {"code": new_code})

                # If exists, try again with different number
                while exists.scalar() > 0:
                    random_num = ''.join(random.choices(string.digits, k=4))
                    new_code = f"EMP{year}{random_num}"
                    exists = await db.execute(check_code, {"code": new_code})

                # Update the employee code
                update_query = text("""
                    UPDATE hrm_employees
                    SET employee_code = :new_code
                    WHERE id = :emp_id
                """)
                await db.execute(update_query, {"new_code": new_code, "emp_id": emp.id})
                print(f"✅ Updated {emp.full_name} with code: {new_code}")

            await db.commit()
            print("\n✅ Successfully fixed all employee codes")

        except Exception as e:
            logger.error(f"Error fixing employee codes: {e}")
            print(f"❌ Error: {e}")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(fix_empty_employee_codes())