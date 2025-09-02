#!/usr/bin/env python3
"""
Trigger CDN processing jobs manually
"""

from app.tasks.cdn_processing_tasks import process_cdn_image_job
from sqlalchemy import text
import asyncio
from app.database.connection import init_database, get_session

async def trigger_jobs():
    await init_database()
    async with get_session() as db:
        result = await db.execute(text("SELECT id FROM cdn_image_jobs WHERE status = 'queued' LIMIT 3"))
        job_ids = [row[0] for row in result.fetchall()]
        print(f'Triggering {len(job_ids)} jobs')
        for job_id in job_ids:
            task = process_cdn_image_job.delay(str(job_id))
            print(f'Triggered job {job_id}: {task.id}')

if __name__ == "__main__":
    asyncio.run(trigger_jobs())