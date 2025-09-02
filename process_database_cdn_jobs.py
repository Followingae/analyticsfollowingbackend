#!/usr/bin/env python3
"""
Process CDN jobs directly from database
"""
import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def process_database_cdn_jobs():
    """Process CDN jobs from database"""
    try:
        print("Processing CDN jobs from database...")
        
        # Setup database and services
        from app.database.database import get_async_session
        from app.services.image_transcoder_service import get_transcoder_service
        from sqlalchemy import select, text
        
        async with get_async_session() as db:
            # Get queued jobs from database
            result = await db.execute(text("""
                SELECT cij.id, cij.asset_id, cij.job_data, cij.status
                FROM cdn_image_jobs cij
                WHERE cij.status = 'queued'
                ORDER BY cij.created_at
                LIMIT 10
            """))
            
            jobs = result.fetchall()
            print(f"Found {len(jobs)} queued jobs")
            
            if not jobs:
                print("No queued jobs found")
                return
            
            # Get transcoder service
            transcoder_service = get_transcoder_service()
            
            processed = 0
            for job in jobs:
                try:
                    job_id = str(job[0])
                    asset_id = str(job[1])
                    job_data = job[2] or {}
                    
                    print(f"Processing job {job_id} for asset {asset_id}")
                    
                    # Process the job
                    if isinstance(job_data, dict) and 'asset_id' not in job_data:
                        job_data['asset_id'] = asset_id
                    
                    result = await transcoder_service.process_job(job_data)
                    
                    if result and result.get('success'):
                        # Update job status to completed
                        await db.execute(text("""
                            UPDATE cdn_image_jobs 
                            SET status = 'completed', updated_at = NOW()
                            WHERE id = :job_id
                        """), {"job_id": job_id})
                        
                        processed += 1
                        print(f"✅ Job {job_id} completed successfully")
                    else:
                        print(f"❌ Job {job_id} failed: {result}")
                        
                except Exception as e:
                    print(f"❌ Error processing job {job_id}: {e}")
                    continue
            
            await db.commit()
            print(f"✅ Processed {processed}/{len(jobs)} jobs successfully")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(process_database_cdn_jobs())