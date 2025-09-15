#!/usr/bin/env python3
"""
Reset Stuck CDN Jobs - Reset processing jobs back to queued state
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

async def reset_stuck_jobs():
    """Reset stuck CDN jobs using direct database connection"""
    try:
        # Add app to path
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))

        from app.database.connection import init_database, get_session
        from sqlalchemy import text

        print("Resetting stuck CDN jobs...")

        # Initialize database
        await init_database()

        async with get_session() as db:
            # Check current job status
            status_query = text("""
                SELECT status, COUNT(*) as count
                FROM cdn_image_jobs
                GROUP BY status
                ORDER BY count DESC
            """)

            status_result = await db.execute(status_query)
            statuses = status_result.fetchall()

            print("\nCurrent job status:")
            for status in statuses:
                print(f"   {status.status}: {status.count} jobs")

            # Reset stuck processing jobs (older than 1 hour)
            reset_query = text("""
                UPDATE cdn_image_jobs
                SET status = 'queued',
                    started_at = NULL,
                    worker_id = NULL,
                    error_message = 'Reset from stuck processing state',
                    updated_at = :now
                WHERE status = 'processing'
                AND started_at < :cutoff_time
            """)

            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            reset_result = await db.execute(reset_query, {
                'now': datetime.now(timezone.utc),
                'cutoff_time': cutoff_time
            })

            await db.commit()

            reset_count = reset_result.rowcount
            print(f"\nReset {reset_count} stuck jobs from 'processing' to 'queued'")

            # Check new status
            new_status_result = await db.execute(status_query)
            new_statuses = new_status_result.fetchall()

            print("\nUpdated job status:")
            for status in new_statuses:
                print(f"   {status.status}: {status.count} jobs")

            print(f"\nReady to process jobs with fixed CDN worker!")

    except Exception as e:
        print(f"Error resetting jobs: {e}")
        return 1

    return 0

if __name__ == '__main__':
    exit_code = asyncio.run(reset_stuck_jobs())
    sys.exit(exit_code)