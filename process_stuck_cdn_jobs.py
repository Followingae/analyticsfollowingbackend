"""
Synchronous CDN Job Processor - NO REDIS REQUIRED
Processes stuck CDN jobs directly using R2 storage
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def reset_and_process_stuck_jobs():
    """Reset stuck jobs and process them directly"""
    from app.database.connection import init_database, get_session
    from sqlalchemy import text
    from app.infrastructure.r2_storage_client import R2StorageClient
    import aiohttp
    from PIL import Image
    import io
    from datetime import datetime, timezone

    # Initialize database
    await init_database()

    # Initialize R2 client with credentials from environment
    import os
    r2_client = R2StorageClient(
        account_id=os.getenv('CF_ACCOUNT_ID', '189e3487e64c5c71c8bdae14f475f075'),
        access_key=os.getenv('R2_ACCESS_KEY_ID', '7768411e7f4215f7e11d47a384b88b23'),
        secret_key=os.getenv('R2_SECRET_ACCESS_KEY', '04efa5adb9692b618ff6ce6053c41c0093566a74518a4f3a5970a49932aa888c'),
        bucket_name=os.getenv('R2_BUCKET_NAME', 'thumbnails-prod')
    )

    logger.info("🔧 Starting stuck CDN jobs processor...")

    async with get_session() as db:
        # Step 1: Find stuck or failed jobs
        logger.info("📊 Finding stuck/failed CDN jobs...")
        stuck_jobs_query = text("""
            SELECT
                j.id,
                j.asset_id,
                j.source_url,
                j.output_format,
                j.target_sizes,
                a.source_id,
                a.source_type,
                a.media_id,
                j.started_at,
                j.status,
                EXTRACT(EPOCH FROM (NOW() - COALESCE(j.started_at, j.created_at)))/3600 as hours_stuck
            FROM cdn_image_jobs j
            JOIN cdn_image_assets a ON j.asset_id = a.id
            WHERE (j.status = 'processing' AND j.started_at < NOW() - INTERVAL '5 minutes')
               OR (j.status = 'failed')
               OR (j.status = 'queued')
               OR (j.status = 'pending')
            ORDER BY j.created_at
        """)

        result = await db.execute(stuck_jobs_query)
        stuck_jobs = result.fetchall()

        if not stuck_jobs:
            logger.info("✅ No stuck jobs found!")
            return

        logger.info(f"🔍 Found {len(stuck_jobs)} stuck/failed CDN jobs")

        # Step 2: Reset jobs to queued
        logger.info("🔄 Resetting stuck/failed jobs to queued status...")
        reset_query = text("""
            UPDATE cdn_image_jobs
            SET status = 'queued',
                started_at = NULL,
                error_message = NULL,
                updated_at = NOW()
            WHERE (status = 'processing' AND started_at < NOW() - INTERVAL '5 minutes')
               OR status = 'failed'
               OR status = 'pending'
        """)
        await db.execute(reset_query)
        await db.commit()
        logger.info("✅ Stuck/failed jobs reset to queued")

        # Step 3: Process each job directly
        successful = 0
        failed = 0

        async with aiohttp.ClientSession() as session:
            for job in stuck_jobs:
                job_id = str(job.id)
                source_url = job.source_url
                asset_id = str(job.asset_id)
                source_type = job.source_type
                media_id = job.media_id
                source_id = str(job.source_id)

                logger.info(f"\n{'='*60}")
                logger.info(f"🖼️  Processing Job: {job_id}")
                logger.info(f"   Type: {source_type}")
                logger.info(f"   Media ID: {media_id}")
                logger.info(f"   Hours stuck: {job.hours_stuck:.1f}")

                try:
                    # Update job to processing (use NOW() to avoid timezone issues)
                    await db.execute(
                        text("""
                            UPDATE cdn_image_jobs
                            SET status = 'processing',
                                started_at = NOW(),
                                updated_at = NOW()
                            WHERE id = :job_id
                        """),
                        {'job_id': job_id}
                    )
                    await db.commit()

                    # Download image
                    logger.info(f"📥 Downloading image from Instagram...")
                    async with session.get(source_url, timeout=30) as response:
                        if response.status != 200:
                            raise Exception(f"Download failed with status {response.status}")

                        image_data = await response.read()
                        logger.info(f"✅ Downloaded {len(image_data)} bytes")

                    # Process image (resize to 512px)
                    logger.info(f"🎨 Processing image to 512px WebP...")
                    img = Image.open(io.BytesIO(image_data))

                    # Convert to RGB if needed
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')

                    # Resize maintaining aspect ratio
                    img.thumbnail((512, 512), Image.Resampling.LANCZOS)

                    # Save as WebP
                    output = io.BytesIO()
                    img.save(output, format='WEBP', quality=85, method=6)
                    output.seek(0)
                    processed_data = output.read()

                    logger.info(f"✅ Processed to {len(processed_data)} bytes")

                    # Upload to R2
                    if source_type == 'profile_avatar':
                        r2_key = f"profiles/{source_id}/avatar-512.webp"
                    else:
                        r2_key = f"posts/{media_id}/thumbnail-512.webp"

                    logger.info(f"☁️  Uploading to R2: {r2_key}")

                    upload_success = await r2_client.upload_object(
                        key=r2_key,
                        content=processed_data,
                        content_type='image/webp',
                        metadata={
                            'processed-at': datetime.now(timezone.utc).isoformat(),
                            'source-type': source_type,
                            'job-id': job_id
                        }
                    )

                    if not upload_success:
                        raise Exception(f"R2 upload failed")

                    cdn_url = f"https://cdn.following.ae/{r2_key}"
                    logger.info(f"✅ Uploaded to CDN: {cdn_url}")

                    # Update asset with CDN URL
                    await db.execute(
                        text("""
                            UPDATE cdn_image_assets
                            SET cdn_url_512 = :cdn_url,
                                cdn_path_512 = :r2_key,
                                processing_status = 'completed',
                                processing_completed_at = NOW(),
                                updated_at = NOW()
                            WHERE id = :asset_id
                        """),
                        {
                            'asset_id': asset_id,
                            'cdn_url': cdn_url,
                            'r2_key': r2_key
                        }
                    )

                    # Update job to completed
                    await db.execute(
                        text("""
                            UPDATE cdn_image_jobs
                            SET status = 'completed',
                                completed_at = NOW(),
                                updated_at = NOW()
                            WHERE id = :job_id
                        """),
                        {'job_id': job_id}
                    )

                    # If this is a post thumbnail, update the posts table
                    if source_type == 'post_thumbnail':
                        await db.execute(
                            text("""
                                UPDATE posts
                                SET cdn_thumbnail_url = :cdn_url
                                WHERE instagram_post_id = :media_id
                            """),
                            {
                                'cdn_url': cdn_url,
                                'media_id': media_id  # Already has shortcode_ prefix
                            }
                        )

                    await db.commit()

                    successful += 1
                    logger.info(f"✅ JOB COMPLETED SUCCESSFULLY!")

                except Exception as e:
                    logger.error(f"❌ Job failed: {e}")

                    # Update job to failed
                    await db.execute(
                        text("""
                            UPDATE cdn_image_jobs
                            SET status = 'failed',
                                error_message = :error,
                                completed_at = NOW(),
                                updated_at = NOW()
                            WHERE id = :job_id
                        """),
                        {'job_id': job_id, 'error': str(e)}
                    )
                    await db.commit()
                    failed += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 PROCESSING COMPLETE!")
        logger.info(f"   ✅ Successful: {successful}")
        logger.info(f"   ❌ Failed: {failed}")
        logger.info(f"   📊 Total: {len(stuck_jobs)}")
        logger.info(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(reset_and_process_stuck_jobs())
