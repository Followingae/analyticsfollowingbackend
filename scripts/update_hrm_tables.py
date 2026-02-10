"""
Script to update HRM tables with new fields
Run this to add the new columns for documents, salary history, etc.
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import init_database, async_engine
from sqlalchemy import text

async def update_hrm_tables():
    """Add new columns to HRM tables"""

    # Initialize database connection
    await init_database()

    if not async_engine:
        print("ERROR: Database connection failed!")
        return

    async with async_engine.begin() as conn:
        print("Updating HRM tables with new features...")

        # First, create the ENUM type if it doesn't exist
        try:
            await conn.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE employeestatus AS ENUM ('active', 'on_leave', 'terminated');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            print("SUCCESS: EmployeeStatus enum created/verified")
        except Exception as e:
            print(f"Note: EmployeeStatus enum might already exist: {e}")

        # Add new columns to hrm_employees table
        alter_statements = [
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS profile_picture_url VARCHAR(500)",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS date_of_birth DATE",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS nationality VARCHAR(100)",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS visa_status VARCHAR(100)",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS visa_expiry DATE",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS passport_number VARCHAR(50)",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS passport_expiry DATE",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS national_id VARCHAR(50)",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS marital_status VARCHAR(50)",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS home_address TEXT",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS current_total_package FLOAT",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS last_increment_date DATE",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS last_increment_percentage FLOAT",
            "ALTER TABLE hrm_employees ADD COLUMN IF NOT EXISTS next_review_date DATE"
        ]

        for stmt in alter_statements:
            try:
                await conn.execute(text(stmt))
                print(f"SUCCESS: {stmt.split('EXISTS')[1].split()[0]} column added/verified")
            except Exception as e:
                print(f"Note: Column might already exist: {e}")

        # Create new tables for documents and salary history

        # Employee Documents table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS hrm_employee_documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                employee_id UUID NOT NULL REFERENCES hrm_employees(id) ON DELETE CASCADE,
                document_type VARCHAR(100) NOT NULL,
                document_name VARCHAR(255) NOT NULL,
                file_url VARCHAR(500) NOT NULL,
                file_size INTEGER,
                mime_type VARCHAR(100),
                expiry_date DATE,
                is_verified BOOLEAN DEFAULT FALSE,
                verified_by UUID,
                verified_at TIMESTAMP,
                notes TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("SUCCESS: hrm_employee_documents table created/verified")

        # Salary History table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS hrm_salary_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                employee_id UUID NOT NULL REFERENCES hrm_employees(id) ON DELETE CASCADE,
                previous_salary FLOAT NOT NULL,
                new_salary FLOAT NOT NULL,
                increment_amount FLOAT,
                increment_percentage FLOAT,
                effective_date DATE NOT NULL,
                reason VARCHAR(255),
                approved_by UUID,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("SUCCESS: hrm_salary_history table created/verified")

        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_hrm_documents_employee ON hrm_employee_documents(employee_id)",
            "CREATE INDEX IF NOT EXISTS idx_hrm_documents_expiry ON hrm_employee_documents(expiry_date)",
            "CREATE INDEX IF NOT EXISTS idx_hrm_salary_employee ON hrm_salary_history(employee_id)",
            "CREATE INDEX IF NOT EXISTS idx_hrm_salary_date ON hrm_salary_history(effective_date DESC)"
        ]

        for idx in indexes:
            try:
                await conn.execute(text(idx))
                print(f"SUCCESS: Index created: {idx.split('INDEX')[1].split('ON')[0].strip()}")
            except Exception as e:
                print(f"Note: Index might already exist: {e}")

        print("\nSUCCESS: HRM tables successfully updated with new features!")
        print("- Profile pictures")
        print("- Personal information fields")
        print("- Document storage")
        print("- Salary history tracking")
        print("- Compensation management")

if __name__ == "__main__":
    asyncio.run(update_hrm_tables())