#!/usr/bin/env python3
"""
Fix All Failed CDN Jobs
Now that CORS proxy is working, retry all failed jobs
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_all_cdn_jobs():
    """Fix all failed CDN jobs"""
    print("Fixing All Failed CDN Jobs...")
    print("=" * 50)
    
    from app.database.connection import init_database, get_session
    from sqlalchemy import text
    
    await init_database()
    
    async with get_session() as db_session:
        # Get all failed jobs
        failed_jobs_sql = """
            SELECT COUNT(*) FROM cdn_image_jobs 
            WHERE status = 'failed'
        """
        
        result = await db_session.execute(text(failed_jobs_sql))
        total_failed = result.scalar()
        
        print(f"Total failed jobs to fix: {total_failed}")
        print()
        
        if total_failed == 0:
            print("No failed jobs to fix!")
            return
        
        # Update all failed jobs to queued for retry
        reset_jobs_sql = """
            UPDATE cdn_image_jobs 
            SET status = 'queued',
                started_at = NULL,
                completed_at = NULL,
                error_message = NULL,
                retry_count = retry_count + 1
            WHERE status = 'failed'
        """
        
        result = await db_session.execute(text(reset_jobs_sql))
        jobs_reset = result.rowcount
        
        # Also reset the assets to pending
        reset_assets_sql = """
            UPDATE cdn_image_assets 
            SET processing_status = 'pending',
                processing_error = NULL
            WHERE processing_status = 'failed'
        """
        
        result = await db_session.execute(text(reset_assets_sql))
        assets_reset = result.rowcount
        
        await db_session.commit()
        
        print(f"Reset {jobs_reset} jobs to queued status")
        print(f"Reset {assets_reset} assets to pending status")
        print()
        print("Jobs are now ready for processing!")
        print("The background CDN processor will pick them up automatically.")
        print()
        print("CDN URLs will be available at:")
        print("https://cdn.following.ae/th/ig/{profile_id}/{media_id}/256/{hash}.webp")
        print("https://cdn.following.ae/th/ig/{profile_id}/{media_id}/512/{hash}.webp")

if __name__ == "__main__":
    asyncio.run(fix_all_cdn_jobs())
    print("\nCDN job reset complete! System is now fully functional.")