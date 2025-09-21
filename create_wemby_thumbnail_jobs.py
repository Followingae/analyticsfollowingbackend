#!/usr/bin/env python3
"""
Create CDN jobs for wemby's missing post thumbnails
"""
import asyncio
import sys
import os
from uuid import uuid4

async def create_wemby_thumbnail_jobs():
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app.database.connection import init_database, get_session
        from sqlalchemy import text

        print("Creating CDN jobs for wemby's missing post thumbnails...")
        await init_database()

        async with get_session() as db:
            # Get wemby's profile and posts with display_url but no CDN assets
            posts_query = """
                SELECT p.id as post_id, p.instagram_post_id, p.shortcode, p.display_url, pr.id as profile_id, pr.username
                FROM posts p
                JOIN profiles pr ON p.profile_id = pr.id
                WHERE pr.username = 'wemby'
                AND p.display_url IS NOT NULL
                AND p.display_url != ''
                ORDER BY p.created_at DESC
            """

            posts_result = await db.execute(text(posts_query))
            posts = posts_result.fetchall()

            print(f"Found {len(posts)} posts for wemby with display URLs")

            jobs_created = 0

            for post in posts:
                print(f"Processing post {post.shortcode}...")

                # Check if CDN asset already exists
                asset_check = """
                    SELECT id FROM cdn_image_assets
                    WHERE source_type = 'post_thumbnail'
                    AND media_id = :instagram_post_id
                """

                asset_result = await db.execute(text(asset_check), {
                    'instagram_post_id': post.instagram_post_id
                })
                existing_asset = asset_result.fetchone()

                if existing_asset:
                    print(f"  [OK] CDN asset already exists for {post.shortcode}")
                    continue

                # Create CDN asset entry
                asset_insert = """
                    INSERT INTO cdn_image_assets (
                        source_type, source_id, media_id, source_url,
                        processing_status, created_at
                    ) VALUES (
                        'post_thumbnail', :source_id, :media_id, :source_url,
                        'pending', NOW()
                    ) RETURNING id
                """

                asset_result = await db.execute(text(asset_insert), {
                    'source_id': post.profile_id,
                    'media_id': post.instagram_post_id,
                    'source_url': post.display_url
                })

                asset_id = asset_result.scalar()
                print(f"  [OK] Created CDN asset {asset_id}")

                # Create CDN job
                job_insert = """
                    INSERT INTO cdn_image_jobs (
                        asset_id, job_type, source_url, target_sizes,
                        output_format, status, created_at
                    ) VALUES (
                        :asset_id, 'ingest', :source_url, ARRAY[512],
                        'webp', 'queued', NOW()
                    ) RETURNING id
                """

                job_result = await db.execute(text(job_insert), {
                    'asset_id': asset_id,
                    'source_url': post.display_url
                })

                job_id = job_result.scalar()
                print(f"  [OK] Created CDN job {job_id}")

                # Submit to Celery queue
                try:
                    from app.workers.cdn_background_worker import celery_app

                    task = celery_app.send_task(
                        'cdn_worker.process_image_job',
                        args=[str(job_id)],
                        queue='cdn_processing'
                    )
                    print(f"  [OK] Submitted to Celery: {task.id}")
                    jobs_created += 1

                except Exception as celery_error:
                    print(f"  [ERROR] Celery error: {celery_error}")
                    # Continue with next post

            await db.commit()

            print(f"\nSUCCESS: Created {jobs_created} CDN jobs for wemby's thumbnails")
            print("Check CDN worker logs for processing progress...")
            return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == '__main__':
    success = asyncio.run(create_wemby_thumbnail_jobs())
    if success:
        print("CDN jobs creation completed")
    else:
        print("CDN jobs creation failed")