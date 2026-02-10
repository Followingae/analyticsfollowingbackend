"""
Add new user profile fields for better personalization
Run this script to add industry, company_size, use_case, and marketing_budget fields
"""
import asyncio
from sqlalchemy import text
from app.database.connection import init_database, get_session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def add_user_profile_fields():
    """Add new fields to users table for signup personalization"""

    # Initialize database first
    await init_database()

    async with get_session() as session:
        try:
            # Add new columns to users table
            alter_statements = [
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS industry VARCHAR(50);
                """,
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS company_size VARCHAR(20);
                """,
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS use_case VARCHAR(100);
                """,
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS marketing_budget VARCHAR(50);
                """,
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;
                """,
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS signup_source VARCHAR(50) DEFAULT 'organic';
                """
            ]

            for statement in alter_statements:
                await session.execute(text(statement))
                logger.info(f"Executed: {statement[:50]}...")

            await session.commit()
            logger.info("✅ Successfully added new user profile fields")

            # Add comments for documentation
            comment_statements = [
                """
                COMMENT ON COLUMN users.industry IS 'User industry: Fashion & Beauty, Food & Beverage, Technology, Health & Fitness, Travel & Hospitality, E-commerce, Agency, Other';
                """,
                """
                COMMENT ON COLUMN users.company_size IS 'Company size: solo, small, growing, large';
                """,
                """
                COMMENT ON COLUMN users.use_case IS 'Primary use case for the platform';
                """,
                """
                COMMENT ON COLUMN users.marketing_budget IS 'Monthly influencer marketing budget range';
                """,
                """
                COMMENT ON COLUMN users.onboarding_completed IS 'Whether user has completed onboarding flow';
                """,
                """
                COMMENT ON COLUMN users.signup_source IS 'How user found the platform: organic, paid, referral, etc';
                """
            ]

            for statement in comment_statements:
                await session.execute(text(statement))

            await session.commit()
            logger.info("✅ Added column comments for documentation")

        except Exception as e:
            logger.error(f"Error adding user profile fields: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(add_user_profile_fields())