#!/usr/bin/env python3
"""
Simple script to reset stuck CDN jobs using direct SQL
"""
import asyncio
import sys
import os

async def reset_jobs():
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app.database.connection import init_database, get_session
        from sqlalchemy import text

        print("Resetting stuck CDN jobs...")
        await init_database()

        async with get_session() as db:
            # Simple reset without datetime operations
            reset_result = await db.execute(text("""
                UPDATE cdn_image_jobs
                SET status = 'queued',
                    started_at = NULL,
                    worker_id = NULL,
                    error_message = 'Reset from stuck state'
                WHERE status = 'processing'
            """))

            await db.commit()
            print(f"Reset {reset_result.rowcount} jobs from processing to queued")

            # Check final status
            status_result = await db.execute(text("""
                SELECT status, COUNT(*) as count
                FROM cdn_image_jobs
                GROUP BY status
                ORDER BY count DESC
            """))

            print("\nFinal job status:")
            for row in status_result.fetchall():
                print(f"   {row.status}: {row.count} jobs")

    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(asyncio.run(reset_jobs()))