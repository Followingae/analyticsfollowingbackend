#!/usr/bin/env python3
"""
Process CDN jobs directly
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

async def process_cdn_jobs_direct():
    """Process CDN jobs directly using the service layer"""
    try:
        print("Processing CDN jobs directly...")
        
        # Initialize database
        from app.database.connection import init_database, get_session
        await init_database()
        
        # Import services
        from app.services.image_transcoder_service import ImageTranscoderService
        from app.infrastructure.r2_storage_client import R2StorageClient
        from app.core.config import settings
        from sqlalchemy import text
        
        # Create R2 client
        r2_client = R2StorageClient(
            account_id=settings.CF_ACCOUNT_ID,
            access_key=settings.R2_ACCESS_KEY_ID,
            secret_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME
        )
        
        # Create transcoder service
        transcoder = ImageTranscoderService(r2_client)
        
        async with get_session() as db:
            # Get queued jobs
            result = await db.execute(text("""
                SELECT cij.id, cij.asset_id, cia.source_url, cia.media_id, cia.source_id
                FROM cdn_image_jobs cij
                JOIN cdn_image_assets cia ON cij.asset_id = cia.id
                WHERE cij.status = 'queued'
                AND cia.source_url IS NOT NULL
                AND cia.source_url != ''
                AND cia.source_url != 'test'
                LIMIT 5
            """))
            
            jobs = result.fetchall()
            print(f"Found {len(jobs)} valid jobs to process")
            
            processed = 0
            for job in jobs:
                try:
                    job_id = str(job[0])
                    asset_id = str(job[1]) 
                    source_url = job[2]
                    media_id = job[3]
                    profile_id = str(job[4])
                    
                    print(f"Processing job {job_id[:8]} - asset {asset_id[:8]}")
                    print(f"  URL: {source_url[:80]}...")
                    
                    # Create job data
                    job_data = {
                        'asset_id': asset_id,
                        'source_url': source_url,
                        'media_id': media_id,
                        'profile_id': profile_id,
                        'target_sizes': [256, 512]
                    }
                    
                    # Process the job
                    result = await transcoder.process_job(job_data)
                    
                    if result and result.success:
                        # Update job status
                        await db.execute(text("""
                            UPDATE cdn_image_jobs 
                            SET status = 'completed', updated_at = NOW()
                            WHERE id = :job_id
                        """), {"job_id": job_id})
                        
                        processed += 1
                        print(f"  Success: Job {job_id[:8]} completed")
                    else:
                        print(f"  Failed: Job {job_id[:8]} failed: {result}")
                        
                except Exception as e:
                    print(f"  Error processing job: {e}")
                    continue
            
            await db.commit()
            print(f"\nProcessed {processed}/{len(jobs)} jobs successfully")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(process_cdn_jobs_direct())