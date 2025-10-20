#!/usr/bin/env python3
"""
Create the job_queue table in the database
"""
import asyncio
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_job_queue_table():
    """Create the job_queue table"""
    try:
        from app.database.optimized_pools import optimized_pools
        from sqlalchemy import text

        # Initialize pools
        await optimized_pools.initialize()

        # Create the table
        schema_sql = """
        -- Job queue table with comprehensive tracking
        CREATE TABLE IF NOT EXISTS job_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            job_type VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            priority INTEGER NOT NULL DEFAULT 50,
            queue_name VARCHAR(50) NOT NULL,
            params JSONB NOT NULL,
            result JSONB,
            error_details JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            estimated_duration INTEGER,
            actual_duration INTEGER,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            idempotency_key VARCHAR(255) UNIQUE,
            worker_id VARCHAR(100),
            user_tier VARCHAR(20),
            progress_percent INTEGER DEFAULT 0,
            progress_message TEXT,

            -- Constraints
            CONSTRAINT valid_status CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'retrying', 'cancelled')),
            CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 100),
            CONSTRAINT valid_progress CHECK (progress_percent BETWEEN 0 AND 100)
        );

        -- Performance indexes
        CREATE INDEX IF NOT EXISTS idx_job_queue_status_priority ON job_queue (status, priority DESC);
        CREATE INDEX IF NOT EXISTS idx_job_queue_user_created ON job_queue (user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_job_queue_queue_status ON job_queue (queue_name, status);
        CREATE INDEX IF NOT EXISTS idx_job_queue_idempotency ON job_queue (idempotency_key);
        CREATE INDEX IF NOT EXISTS idx_job_queue_worker_processing ON job_queue (worker_id, status) WHERE status = 'processing';
        CREATE INDEX IF NOT EXISTS idx_job_queue_retry_eligible ON job_queue (status, retry_count, created_at) WHERE status = 'failed';

        -- Dead letter queue for failed jobs
        CREATE TABLE IF NOT EXISTS job_dead_letter_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            original_job_id UUID NOT NULL,
            job_data JSONB NOT NULL,
            failure_reason TEXT NOT NULL,
            failure_count INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_retry_at TIMESTAMPTZ
        );

        -- Job execution metrics for monitoring
        CREATE TABLE IF NOT EXISTS job_execution_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_type VARCHAR(100) NOT NULL,
            queue_name VARCHAR(50) NOT NULL,
            user_tier VARCHAR(20),
            duration_seconds INTEGER,
            success BOOLEAN NOT NULL,
            error_category VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """

        async with optimized_pools.get_user_session() as session:
            await session.execute(text(schema_sql))
            await session.commit()

        print("SUCCESS: job_queue table created successfully")
        return True

    except Exception as e:
        print(f"ERROR: Failed to create job_queue table: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(create_job_queue_table())
    sys.exit(0 if success else 1)