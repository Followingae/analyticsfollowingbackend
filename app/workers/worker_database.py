"""
Direct asyncpg database connection for background workers
Bypasses SQLAlchemy ORM to avoid prepared statement issues with pgbouncer
"""

import asyncpg
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class WorkerDatabase:
    """Direct asyncpg connection for background workers - no prepared statements"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        # USE DIRECT CONNECTION FOR WORKERS (No pgbouncer)
        self.database_url = os.getenv("DIRECT_DATABASE_URL", "")
        if not self.database_url:
            # Fallback to regular DATABASE_URL if DIRECT not set
            self.database_url = os.getenv("DATABASE_URL", "")
        # Convert postgres:// to postgresql:// if needed
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://")

    async def initialize(self):
        """Initialize the connection pool with pgbouncer-compatible settings"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=2,
                statement_cache_size=0,  # CRITICAL: No prepared statements for pgbouncer
                command_timeout=60,
                server_settings={
                    'application_name': 'post_analytics_worker'
                }
            )
            logger.info("[SUCCESS] Worker database connection pool initialized (no prepared statements)")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize worker database pool: {e}")
            raise

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Worker database connection pool closed")

    async def execute_query(self, query: str, *args) -> Optional[list]:
        """Execute a query and return results"""
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows] if rows else None
        except Exception as e:
            logger.error(f"[ERROR] Failed to execute query: {e}")
            return None

    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next pending post analytics job"""
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Get and lock the next job
                    row = await conn.fetchrow("""
                        SELECT id, user_id, job_type, params::text as params, status, priority
                        FROM job_queue
                        WHERE job_type = 'post_analytics_campaign'
                        AND status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    """)

                    if not row:
                        return None

                    # Mark as processing
                    await conn.execute("""
                        UPDATE job_queue
                        SET status = 'processing',
                            started_at = $1
                        WHERE id = $2
                    """, datetime.now(timezone.utc), row['id'])

                    return {
                        "id": str(row['id']),
                        "user_id": str(row['user_id']),
                        "params": json.loads(row['params']) if row['params'] else {},
                        "priority": row['priority']
                    }
        except Exception as e:
            logger.error(f"Failed to get next job: {e}")
            return None

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        """Update job status in the database"""
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                now = datetime.now(timezone.utc)

                # Build update query based on status
                if status == 'completed':
                    await conn.execute("""
                        UPDATE job_queue
                        SET status = $1,
                            completed_at = $2,
                            result = $3::jsonb
                        WHERE id = $4::uuid
                    """, status, now, json.dumps(result) if result else None, job_id)

                elif status == 'failed':
                    await conn.execute("""
                        UPDATE job_queue
                        SET status = $1,
                            failed_at = $2,
                            error = $3
                        WHERE id = $4::uuid
                    """, status, now, error, job_id)

                else:
                    await conn.execute("""
                        UPDATE job_queue
                        SET status = $1
                        WHERE id = $2::uuid
                    """, status, job_id)

                logger.info(f"Updated job {job_id} status to {status}")

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")

    async def update_job_progress(
        self,
        job_id: str,
        progress_percent: int,
        current_stage: str
    ):
        """Update job progress for status polling"""
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE job_queue
                    SET progress_percent = $1,
                        current_stage = $2
                    WHERE id = $3::uuid
                """, progress_percent, current_stage, job_id)

        except Exception as e:
            logger.error(f"Failed to update job {job_id} progress: {e}")

# Global instance
worker_db = WorkerDatabase()