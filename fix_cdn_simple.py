#!/usr/bin/env python3
"""
Simple CDN Fix Script
Test improved Instagram image download with SmartProxy
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

async def test_cdn_fix():
    """Test CDN fix with one failed job"""
    print("Testing CDN Fix with SmartProxy...")
    print("-" * 50)
    
    # Initialize database
    from app.database.connection import init_database, get_session
    from sqlalchemy import text
    
    await init_database()
    
    async with get_session() as db_session:
        # Get one failed job to test
        failed_job_sql = """
            SELECT j.id, j.asset_id, a.source_url, a.media_id
            FROM cdn_image_jobs j
            JOIN cdn_image_assets a ON j.asset_id = a.id
            WHERE j.status = 'failed'
            LIMIT 1
        """
        
        result = await db_session.execute(text(failed_job_sql))
        job = result.fetchone()
        
        if not job:
            print("[INFO] No failed jobs to test")
            return
        
        job_id, asset_id, source_url, media_id = job
        
        print(f"Testing Job: {job_id}")
        print(f"Asset: {asset_id}")
        print(f"Media: {media_id}")
        print(f"URL: {source_url[:80]}...")
        print()
        
        # Initialize improved transcoder
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
        
        try:
            # Test processing
            job_data = {
                'asset_id': str(asset_id),
                'source_url': source_url,
                'target_sizes': [256, 512],
                'profile_id': str(asset_id),
                'media_id': media_id
            }
            
            print("Processing with improved SmartProxy download...")
            result = await transcoder.process_job(job_data)
            
            if result.success:
                print("[SUCCESS] Image processed successfully!")
                print(f"Derivatives: {list(result.derivatives.keys())}")
                print(f"Processing time: {result.processing_stats.get('total_time_ms')}ms")
                
                # Show CDN URLs
                for size, info in result.derivatives.items():
                    print(f"{size}px CDN URL: {info['cdn_url']}")
                
                print()
                print("✅ CDN SYSTEM IS NOW WORKING!")
                return True
            else:
                print(f"[FAIL] Processing failed: {result.error}")
                return False
                
        except Exception as e:
            print(f"[FAIL] Test failed: {e}")
            return False
        
        finally:
            await transcoder.close()

if __name__ == "__main__":
    success = asyncio.run(test_cdn_fix())
    if success:
        print("\n🎉 CDN fix successful! SmartProxy bypass is working.")
    else:
        print("\n❌ CDN fix failed. Instagram blocking is still active.")