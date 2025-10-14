#!/usr/bin/env python3
"""
Apply source_type migration to related_profiles table
"""
import asyncio
import logging
from sqlalchemy import text
from app.database.connection import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def apply_migration():
    """Apply the source_type migration"""
    try:
        async with get_session() as db:
            # Add source_type column
            logger.info("Adding source_type column to related_profiles table...")
            await db.execute(text("""
                ALTER TABLE related_profiles
                ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'user_search'
            """))

            # Create index
            logger.info("Creating index on source_type column...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_related_profiles_source_type
                ON related_profiles(source_type)
            """))

            # Update existing records
            logger.info("Updating existing records to mark as user_search...")
            result = await db.execute(text("""
                UPDATE related_profiles
                SET source_type = 'user_search'
                WHERE source_type IS NULL
            """))

            await db.commit()
            logger.info(f"✅ Migration completed successfully! Updated {result.rowcount} existing records.")

            # Verify the migration
            count_result = await db.execute(text("""
                SELECT
                    source_type,
                    COUNT(*) as count
                FROM related_profiles
                GROUP BY source_type
            """))

            logger.info("Current source_type distribution:")
            for row in count_result.fetchall():
                logger.info(f"  {row[0]}: {row[1]} profiles")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(apply_migration())