#!/usr/bin/env python3
"""
Process ALL remaining CDN jobs to convert everything to our CDN
"""
import asyncio
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

async def process_all_cdn_jobs():
    """Process all remaining CDN jobs in batches"""
    try:
        print("Processing ALL remaining CDN jobs...")
        print("=" * 50)
        
        # Initialize database
        from app.database.connection import init_database, get_session
        await init_database()
        
        # Import services
        from app.services.image_transcoder_service import ImageTranscoderService
        from app.infrastructure.r2_storage_client import R2StorageClient
        from app.core.config import settings
        from sqlalchemy import text
        
        # Create R2 client and transcoder
        r2_client = R2StorageClient(
            account_id=settings.CF_ACCOUNT_ID,
            access_key=settings.R2_ACCESS_KEY_ID,
            secret_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME
        )
        
        transcoder = ImageTranscoderService(r2_client)
        
        total_processed = 0
        batch_size = 10
        batch_num = 1
        
        while True:
            async with get_session() as db:
                # Get next batch of jobs
                result = await db.execute(text("""
                    SELECT cij.id, cij.asset_id, cia.source_url, cia.media_id, cia.source_id
                    FROM cdn_image_jobs cij
                    JOIN cdn_image_assets cia ON cij.asset_id = cia.id
                    WHERE cij.status = 'queued'
                    AND cia.source_url IS NOT NULL
                    AND cia.source_url != ''
                    AND cia.source_url != 'test'
                    ORDER BY cij.created_at
                    LIMIT :batch_size
                """), {"batch_size": batch_size})
                
                jobs = result.fetchall()
                
                if not jobs:
                    print(f"\nNo more jobs to process!")
                    break
                
                print(f"\nBatch {batch_num}: Processing {len(jobs)} jobs...")
                batch_processed = 0
                
                for i, job in enumerate(jobs, 1):
                    try:
                        job_id = str(job[0])
                        asset_id = str(job[1])
                        source_url = job[2]
                        media_id = job[3]
                        profile_id = str(job[4])
                        
                        print(f"  [{i}/{len(jobs)}] Processing {media_id[:15]}...")
                        
                        job_data = {
                            'asset_id': asset_id,
                            'source_url': source_url,
                            'media_id': media_id,
                            'profile_id': profile_id,
                            'target_sizes': [256, 512]
                        }
                        
                        # Process the job
                        start_time = time.time()
                        result = await transcoder.process_job(job_data)
                        process_time = time.time() - start_time
                        
                        if result and result.success:
                            # Update job status
                            await db.execute(text("""
                                UPDATE cdn_image_jobs 
                                SET status = 'completed', updated_at = NOW()
                                WHERE id = :job_id
                            """), {"job_id": job_id})
                            
                            batch_processed += 1
                            total_processed += 1
                            print(f"    Success in {process_time:.1f}s")
                        else:
                            print(f"    Failed: {result}")
                            # Mark as failed to avoid reprocessing
                            await db.execute(text("""
                                UPDATE cdn_image_jobs 
                                SET status = 'failed', updated_at = NOW()
                                WHERE id = :job_id
                            """), {"job_id": job_id})
                            
                    except Exception as e:
                        print(f"    Error: {e}")
                        continue
                
                await db.commit()
                print(f"Batch {batch_num} complete: {batch_processed}/{len(jobs)} successful")
                
                # Small delay between batches to avoid overwhelming services
                await asyncio.sleep(2)
                batch_num += 1
        
        print(f"\n{'='*50}")
        print(f"ALL JOBS COMPLETE!")
        print(f"Total processed: {total_processed}")
        print(f"{'='*50}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(process_all_cdn_jobs())