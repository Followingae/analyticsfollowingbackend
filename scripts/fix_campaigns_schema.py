"""
Fix campaigns table schema - Add missing columns
Run this script to add missing columns to the campaigns table
"""
import asyncio
import asyncpg
from app.core.config import settings

async def add_missing_columns():
    """Add missing columns to campaigns table"""

    # Connect to database
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        print("🔧 Adding missing columns to campaigns table...")

        # Add all missing columns
        await conn.execute("""
            ALTER TABLE campaigns
              ADD COLUMN IF NOT EXISTS description TEXT,
              ADD COLUMN IF NOT EXISTS budget NUMERIC(12, 2),
              ADD COLUMN IF NOT EXISTS spent NUMERIC(12, 2) DEFAULT 0,
              ADD COLUMN IF NOT EXISTS start_date TIMESTAMP WITH TIME ZONE,
              ADD COLUMN IF NOT EXISTS end_date TIMESTAMP WITH TIME ZONE,
              ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}',
              ADD COLUMN IF NOT EXISTS created_by VARCHAR(20) DEFAULT 'user',
              ADD COLUMN IF NOT EXISTS proposal_id UUID,
              ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE;
        """)

        print("✅ Columns added successfully")

        # Add indexes
        print("🔧 Adding indexes...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_campaigns_proposal_id ON campaigns(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_campaigns_archived_at ON campaigns(archived_at);
        """)

        print("✅ Indexes added successfully")

        # Add check constraint
        print("🔧 Adding status check constraint...")
        await conn.execute("""
            ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_status_check;
            ALTER TABLE campaigns ADD CONSTRAINT campaigns_status_check
              CHECK (status IN ('draft', 'active', 'paused', 'in_review', 'completed', 'archived'));
        """)

        print("✅ Constraint added successfully")

        # Verify
        print("\n📊 Verifying campaigns table structure...")
        rows = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'campaigns'
            AND table_schema = 'public'
            ORDER BY ordinal_position;
        """)

        print("\nCampaigns table columns:")
        for row in rows:
            print(f"  - {row['column_name']}: {row['data_type']} (nullable: {row['is_nullable']})")

        print("\n✅ Migration completed successfully!")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_missing_columns())
