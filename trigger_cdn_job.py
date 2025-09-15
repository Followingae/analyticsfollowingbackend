#!/usr/bin/env python3
"""
Trigger CDN Job - Submit a CDN job manually to test the worker
"""
import asyncio
import sys
import os
from celery import Celery

async def trigger_cdn_job():
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app.database.connection import init_database, get_session
        from sqlalchemy import text

        print("Triggering CDN job...")
        await init_database()

        # Create Celery client
        celery_client = Celery(
            'test_client',
            broker='redis://localhost:6379/0',
            backend='redis://localhost:6379/0'
        )

        async with get_session() as db:
            # Get a queued job
            result = await db.execute(text("""
                SELECT j.id, j.source_url, a.source_id
                FROM cdn_image_jobs j
                JOIN cdn_image_assets a ON j.asset_id = a.id
                WHERE j.status = 'queued'
                ORDER BY j.created_at ASC
                LIMIT 1
            """))

            job = result.fetchone()
            if not job:
                print("No queued jobs found. Creating a test job...")

                # Get jisele_a profile
                profile_result = await db.execute(text("""
                    SELECT id FROM profiles WHERE username = 'jisele_a'
                """))
                profile = profile_result.fetchone()

                if profile:
                    # Create a test CDN asset and job
                    test_url = "https://scontent-lga3-3.cdninstagram.com/v/t51.2885-19/491468991_18501136993052362_8985048294383627149_n.jpg?stp=dst-jpg_s150x150_tt6"

                    # Insert test asset
                    await db.execute(text("""
                        INSERT INTO cdn_image_assets (source_type, source_id, media_id, source_url, processing_status, created_at)
                        VALUES ('profile', :profile_id, 'profile_pic', :source_url, 'pending', NOW())
                        ON CONFLICT (source_type, source_id, media_id) DO UPDATE SET
                            source_url = EXCLUDED.source_url,
                            processing_status = 'pending'
                    """), {'profile_id': profile.id, 'source_url': test_url})

                    # Get the asset ID
                    asset_result = await db.execute(text("""
                        SELECT id FROM cdn_image_assets
                        WHERE source_type = 'profile' AND source_id = :profile_id AND media_id = 'profile_pic'
                    """), {'profile_id': profile.id})
                    asset = asset_result.fetchone()

                    if asset:
                        # Insert test job
                        await db.execute(text("""
                            INSERT INTO cdn_image_jobs (asset_id, job_type, source_url, target_sizes, output_format, status, created_at)
                            VALUES (:asset_id, 'ingest', :source_url, ARRAY[512], 'webp', 'queued', NOW())
                        """), {'asset_id': asset.id, 'source_url': test_url})

                        await db.commit()

                        # Get the new job
                        job_result = await db.execute(text("""
                            SELECT j.id, j.source_url, a.source_id
                            FROM cdn_image_jobs j
                            JOIN cdn_image_assets a ON j.asset_id = a.id
                            WHERE j.status = 'queued' AND j.asset_id = :asset_id
                            ORDER BY j.created_at DESC
                            LIMIT 1
                        """), {'asset_id': asset.id})
                        job = job_result.fetchone()

            if job:
                print(f"Submitting CDN job: {job.id}")
                print(f"Source URL: {job.source_url}")
                print(f"Source ID: {job.source_id}")

                # Submit job to worker
                task = celery_client.send_task(
                    'cdn_worker.process_image_job',
                    args=[str(job.id)],
                    queue='cdn_processing'
                )

                print(f"Task submitted: {task.id}")
                print("Check CDN worker logs for progress...")
                return True
            else:
                print("Could not create or find CDN job")
                return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == '__main__':
    success = asyncio.run(trigger_cdn_job())
    if success:
        print("SUCCESS: CDN job triggered")
    else:
        print("FAILED: Could not trigger CDN job")