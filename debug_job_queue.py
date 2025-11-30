"""
Debug script to investigate job queue state and clean up stuck jobs
"""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import json

# Database connection from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment")
    exit(1)

# Convert to async URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

async def investigate_job_queue():
    """Investigate the current state of job queue"""
    print("🔍 INVESTIGATING JOB QUEUE STATE...")

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # Get all jobs in database
            print("\n📋 ALL JOBS IN DATABASE:")
            result = await session.execute(text("""
                SELECT id, user_id, job_type, status, priority, queue_name,
                       created_at, started_at, completed_at, progress_percent, progress_message
                FROM job_queue
                ORDER BY created_at DESC
                LIMIT 20
            """).execution_options(prepare=False))

            all_jobs = []
            for row in result:
                job = {
                    "id": str(row.id)[:8] + "...",
                    "user_id": str(row.user_id)[:8] + "...",
                    "job_type": row.job_type,
                    "status": row.status,
                    "queue_name": row.queue_name,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "progress_percent": row.progress_percent,
                    "progress_message": row.progress_message,
                    "age_hours": (datetime.now(timezone.utc) - row.created_at).total_seconds() / 3600 if row.created_at else 0
                }
                all_jobs.append(job)

            if all_jobs:
                for job in all_jobs:
                    print(f"  {job['id']} | {job['status']:12} | {job['job_type']:20} | {job['age_hours']:.1f}h old")
            else:
                print("  No jobs found in database")

            # Get job counts by status
            print("\n📊 JOB COUNTS BY STATUS:")
            result = await session.execute(text("""
                SELECT status, COUNT(*) as count
                FROM job_queue
                GROUP BY status
                ORDER BY count DESC
            """).execution_options(prepare=False))

            status_counts = {}
            for row in result:
                status_counts[row.status] = row.count
                print(f"  {row.status}: {row.count} jobs")

            if not status_counts:
                print("  No jobs found")

            # Check for stuck jobs (older than 1 hour and still processing/queued)
            print("\n⚠️  STUCK JOBS (>1 hour old, still active):")
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            result = await session.execute(text("""
                SELECT id, job_type, status, created_at, started_at, progress_message
                FROM job_queue
                WHERE status IN ('queued', 'processing')
                AND created_at < :one_hour_ago
                ORDER BY created_at ASC
            """).execution_options(prepare=False), {"one_hour_ago": one_hour_ago})

            stuck_jobs = []
            for row in result:
                stuck_job = {
                    "id": str(row.id)[:8] + "...",
                    "job_type": row.job_type,
                    "status": row.status,
                    "age_hours": (datetime.now(timezone.utc) - row.created_at).total_seconds() / 3600,
                    "progress_message": row.progress_message
                }
                stuck_jobs.append(stuck_job)
                print(f"  {stuck_job['id']} | {stuck_job['status']:12} | {stuck_job['job_type']:20} | {stuck_job['age_hours']:.1f}h old")

            if not stuck_jobs:
                print("  No stuck jobs found")

            # Return summary for cleanup decision
            return {
                "total_jobs": len(all_jobs),
                "stuck_jobs": stuck_jobs,
                "status_counts": status_counts,
                "all_jobs": all_jobs
            }

    except Exception as e:
        print(f"❌ Error investigating job queue: {e}")
        return None
    finally:
        await engine.dispose()

async def cleanup_stuck_jobs():
    """Clean up jobs that are stuck in processing/queued state for >1 hour"""
    print("\n🧹 CLEANING UP STUCK JOBS...")

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

            # Update stuck jobs to failed status
            result = await session.execute(text("""
                UPDATE job_queue
                SET
                    status = 'failed',
                    completed_at = NOW(),
                    progress_message = 'Auto-failed: stuck for >1 hour'
                WHERE status IN ('queued', 'processing')
                AND created_at < :one_hour_ago
                RETURNING id, job_type
            """).execution_options(prepare=False), {"one_hour_ago": one_hour_ago})

            cleaned_jobs = []
            for row in result:
                cleaned_jobs.append({
                    "id": str(row.id)[:8] + "...",
                    "job_type": row.job_type
                })

            if cleaned_jobs:
                await session.commit()
                print(f"✅ Cleaned up {len(cleaned_jobs)} stuck jobs:")
                for job in cleaned_jobs:
                    print(f"  {job['id']} | {job['job_type']}")
            else:
                print("✅ No stuck jobs to clean up")

            return len(cleaned_jobs)

    except Exception as e:
        print(f"❌ Error cleaning stuck jobs: {e}")
        return 0
    finally:
        await engine.dispose()

async def main():
    print("🔍 JOB QUEUE DIAGNOSTIC TOOL")
    print("=" * 50)

    # Investigate current state
    summary = await investigate_job_queue()

    if summary:
        print(f"\n📋 SUMMARY:")
        print(f"  Total jobs in database: {summary['total_jobs']}")
        print(f"  Stuck jobs found: {len(summary['stuck_jobs'])}")
        print(f"  Status breakdown: {summary['status_counts']}")

        # Offer to clean up stuck jobs
        if summary['stuck_jobs']:
            print(f"\n❓ Found {len(summary['stuck_jobs'])} stuck jobs. Clean them up? (y/N): ", end="")
            response = input().lower().strip()
            if response == 'y':
                cleaned_count = await cleanup_stuck_jobs()
                print(f"\n✅ Cleanup complete: {cleaned_count} jobs cleaned")

                # Re-check after cleanup
                print("\n🔄 RE-CHECKING AFTER CLEANUP...")
                await investigate_job_queue()
            else:
                print("❌ Cleanup skipped")
        else:
            print("\n✅ No stuck jobs to clean up")
    else:
        print("❌ Could not investigate job queue")

if __name__ == "__main__":
    asyncio.run(main())