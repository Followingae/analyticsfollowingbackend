"""
Create HRM (Human Resource Management) tables in the database
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the PGBouncer-safe engine creator
from app.database.pgbouncer_fix import create_pgbouncer_engine


async def create_hrm_tables():
    """Create all HRM tables"""
    try:
        logger.info("Creating HRM tables...")

        # Get database URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not found in environment variables")

        # Use the PGBouncer-safe engine
        engine = create_pgbouncer_engine(DATABASE_URL)

        async with engine.begin() as conn:
            # Create only HRM tables
            from app.models.hrm import (
                HRMEmployee, HRMAttendanceRaw, HRMAttendanceProcessed,
                HRMTimesheet, HRMPayroll, HRMLeave, HRMLeaveBalance, HRMHoliday
            )

            # Get HRM tables metadata
            hrm_tables = [
                HRMEmployee.__table__,
                HRMAttendanceRaw.__table__,
                HRMAttendanceProcessed.__table__,
                HRMTimesheet.__table__,
                HRMPayroll.__table__,
                HRMLeave.__table__,
                HRMLeaveBalance.__table__,
                HRMHoliday.__table__
            ]

            # Create each HRM table
            for table in hrm_tables:
                try:
                    await conn.run_sync(table.create, checkfirst=True)
                    logger.info(f"Created table: {table.name}")
                except Exception as e:
                    logger.warning(f"Table {table.name} might already exist: {e}")

        await engine.dispose()
        logger.info("✅ HRM tables created successfully!")

        # List created tables
        logger.info("Created tables:")
        logger.info("- hrm_employees")
        logger.info("- hrm_attendance_raw")
        logger.info("- hrm_attendance_processed")
        logger.info("- hrm_timesheets")
        logger.info("- hrm_payroll")
        logger.info("- hrm_leaves")
        logger.info("- hrm_leave_balances")
        logger.info("- hrm_holidays")

    except Exception as e:
        logger.error(f"Error creating HRM tables: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_hrm_tables())