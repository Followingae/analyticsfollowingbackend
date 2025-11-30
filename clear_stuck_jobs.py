#!/usr/bin/env python3
"""Clear all stuck jobs from the queue"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.job_queue import job_queue
from app.database.connection import async_engine

async def clear_all_jobs():
    """Clear all stuck jobs from the database"""
    print("=" * 60)
    print("CLEARING STUCK JOBS FROM QUEUE")
    print("=" * 60)

    try:
        # Job queue is a global singleton
        jq = job_queue

        # Get all jobs
        jobs = await jq.get_all_jobs()
        print(f"\nFound {len(jobs)} total jobs in queue")

        if not jobs:
            print("✅ No jobs to clear!")
            return

        # Show job details
        print("\nJob Details:")
        print("-" * 40)
        for job in jobs:
            print(f"ID: {job['id']}")
            print(f"  Type: {job['type']}")
            print(f"  Status: {job['status']}")
            print(f"  Created: {job.get('created_at', 'Unknown')}")
            print(f"  Progress: {job.get('progress', 0)}%")
            print(f"  Message: {job.get('message', 'No message')}")
            print("-" * 40)

        # Ask for confirmation
        response = input("\nDo you want to clear ALL these jobs? (yes/no): ")

        if response.lower() == 'yes':
            # Clear all jobs
            for job in jobs:
                try:
                    await jq.update_job_status(
                        job['id'],
                        'failed',
                        error="Manually cleared due to stuck queue"
                    )
                    print(f"✅ Cleared job: {job['id']}")
                except Exception as e:
                    print(f"❌ Failed to clear job {job['id']}: {e}")

            print("\n✅ All jobs cleared successfully!")

            # Check queue again
            remaining = await jq.get_all_jobs()
            print(f"\nRemaining jobs in queue: {len(remaining)}")

        else:
            print("❌ Operation cancelled")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        # Close database connection
        if async_engine:
            await async_engine.dispose()

if __name__ == "__main__":
    print("Starting job cleanup...")
    asyncio.run(clear_all_jobs())
    print("\nDone!")