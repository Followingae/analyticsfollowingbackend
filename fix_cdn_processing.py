#!/usr/bin/env python3
"""
CDN Processing Fix
Retry failed CDN jobs with improved SmartProxy download
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_cdn_processing():
    """Fix CDN processing by retrying failed jobs"""
    print("Starting CDN Processing Fix...")
    print("-" * 60)
    
    # Initialize database
    from app.database.connection import init_database, get_session
    from sqlalchemy import text
    
    await init_database()
    
    async with get_session() as db_session:
        # Get failed CDN jobs
        failed_jobs_sql = """
            SELECT j.id, j.asset_id, a.source_url, a.media_id, j.error_message
            FROM cdn_image_jobs j
            JOIN cdn_image_assets a ON j.asset_id = a.id
            WHERE j.status = 'failed'
            ORDER BY j.created_at DESC
            LIMIT 10
        """
        
        result = await db_session.execute(text(failed_jobs_sql))
        failed_jobs = result.fetchall()
        
        print(f"Found {len(failed_jobs)} failed CDN jobs to retry")
        print()
        
        if not failed_jobs:
            print("[OK] No failed jobs to retry")
            return True
        
        # Initialize services with improved download
        from app.infrastructure.r2_storage_client import R2StorageClient
        from app.services.image_transcoder_service import ImageTranscoderService
        from app.core.config import settings
        
        r2_client = R2StorageClient(
            account_id=settings.CF_ACCOUNT_ID,
            access_key=settings.R2_ACCESS_KEY_ID,
            secret_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME
        )
        
        transcoder = ImageTranscoderService(r2_client)
        
        success_count = 0
        fail_count = 0
        
        try:
            for i, job in enumerate(failed_jobs, 1):
                job_id = str(job[0])
                asset_id = str(job[1])
                source_url = job[2]
                media_id = job[3]
                previous_error = job[4]
                
                print(f"Retry {i}/{len(failed_jobs)}: Job {job_id}")
                print(f"   Asset: {asset_id}")
                print(f"   Media: {media_id}")
                print(f"   URL: {source_url[:80]}...")
                print(f"   Previous Error: {previous_error}")
                
                try:
                # Prepare job data
                job_data = {
                    'asset_id': asset_id,
                    'source_url': source_url,
                    'target_sizes': [256, 512],
                    'profile_id': asset_id,  # Using asset_id as placeholder
                    'media_id': media_id
                }
                
                # Process with improved download
                processing_result = await transcoder.process_job(job_data)
                
                if processing_result.success:
                    # Update job status to completed
                    update_job_sql = """
                        UPDATE cdn_image_jobs 
                        SET status = 'completed', 
                            completed_at = NOW(),
                            processing_duration_ms = :duration,
                            retry_count = retry_count + 1,
                            error_message = NULL
                        WHERE id = :job_id
                    """
                    
                    await db_session.execute(
                        text(update_job_sql),
                        {
                            'job_id': job_id,
                            'duration': processing_result.processing_stats.get('total_time_ms', 0)
                        }
                    )
                    
                    # Update asset with results
                    derivatives = processing_result.derivatives
                    
                    update_asset_sql = """
                        UPDATE cdn_image_assets 
                        SET 
                            processing_status = 'completed',
                            processing_completed_at = NOW(),
                            cdn_url_256 = :cdn_url_256,
                            cdn_url_512 = :cdn_url_512,
                            cdn_path_256 = :cdn_path_256,
                            cdn_path_512 = :cdn_path_512,
                            processing_attempts = processing_attempts + 1,
                            processing_error = NULL,
                            updated_at = NOW()
                        WHERE id = :asset_id
                    """
                    
                    await db_session.execute(
                        text(update_asset_sql),
                        {
                            'asset_id': asset_id,
                            'cdn_url_256': derivatives.get(256, {}).get('cdn_url'),
                            'cdn_url_512': derivatives.get(512, {}).get('cdn_url'),
                            'cdn_path_256': derivatives.get(256, {}).get('path'),
                            'cdn_path_512': derivatives.get(512, {}).get('path')
                        }
                    )
                    
                    await db_session.commit()
                    
                    print(f"   [SUCCESS] Job completed successfully")
                    success_count += 1
                    
                else:
                    # Update job as failed
                    update_failed_sql = """
                        UPDATE cdn_image_jobs 
                        SET retry_count = retry_count + 1,
                            error_message = :error_message
                        WHERE id = :job_id
                    """
                    
                    await db_session.execute(
                        text(update_failed_sql),
                        {
                            'job_id': job_id,
                            'error_message': processing_result.error
                        }
                    )
                    
                    await db_session.commit()
                    
                    print(f"   [FAIL] Job failed: {processing_result.error}")
                    fail_count += 1
                    
            except Exception as e:
                print(f"   [FAIL] Processing error: {e}")
                fail_count += 1
            
            print()
        
        # Summary
        print("=" * 60)
        print(f"CDN PROCESSING FIX RESULTS:")
        print(f"   Successful: {success_count}/{len(failed_jobs)}")
        print(f"   Failed: {fail_count}/{len(failed_jobs)}")
        
        if success_count > 0:
            print(f"   [OK] CDN processing is now working!")
            
            # Test CDN URLs
            print(f"\n   Testing CDN URL generation...")
            successful_assets_sql = """
                SELECT cdn_url_256, cdn_url_512 
                FROM cdn_image_assets 
                WHERE processing_status = 'completed' 
                AND cdn_url_256 IS NOT NULL
                LIMIT 3
            """
            
            result = await db_session.execute(text(successful_assets_sql))
            successful_assets = result.fetchall()
            
            print(f"   Sample CDN URLs generated:")
            for asset in successful_assets:
                print(f"     256px: {asset[0]}")
                print(f"     512px: {asset[1]}")
                print()
            
            return True
        else:
            print(f"   [FAIL] All retry attempts failed")
            return False
        
        finally:
            # Clean up transcoder
            if 'transcoder' in locals():
                await transcoder.close()

if __name__ == "__main__":
    success = asyncio.run(fix_cdn_processing())
    if not success:
        sys.exit(1)
    print("\n[OK] CDN processing fix completed!")