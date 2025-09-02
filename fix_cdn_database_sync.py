#!/usr/bin/env python3
"""
Fix CDN Database Synchronization Issues
Reconciles database state with actual R2 storage content
"""

import asyncio
import logging
from typing import Dict, List, Any
from uuid import UUID
import re
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CDNDatabaseSyncFixer:
    """Fix CDN database synchronization issues"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def sync_r2_with_database(self, r2_objects: List[Dict]) -> Dict[str, Any]:
        """Sync R2 storage objects with database records"""
        results = {
            'processed_objects': 0,
            'updated_assets': 0,
            'created_assets': 0,
            'errors': []
        }
        
        try:
            logger.info(f"🔄 Syncing {len(r2_objects)} R2 objects with database")
            
            for r2_obj in r2_objects:
                try:
                    # Parse R2 object key: th/ig/{profile_id}/{media_id}/{size}/{hash}.webp
                    key_parts = r2_obj['key'].split('/')
                    if len(key_parts) != 6 or key_parts[0] != 'th' or key_parts[1] != 'ig':
                        logger.warning(f"Skipping non-standard key: {r2_obj['key']}")
                        continue
                    
                    profile_id = key_parts[2]
                    media_id = key_parts[3]
                    size = key_parts[4]
                    filename = key_parts[5]
                    content_hash = filename.split('.')[0]
                    
                    # Get or create asset record
                    asset = await self._get_or_create_asset_from_r2(
                        profile_id, media_id, r2_obj, content_hash, size
                    )
                    
                    if asset['created']:
                        results['created_assets'] += 1
                    else:
                        results['updated_assets'] += 1
                    
                    results['processed_objects'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing R2 object {r2_obj['key']}: {e}")
                    results['errors'].append({
                        'key': r2_obj['key'],
                        'error': str(e)
                    })
            
            await self.db.commit()
            logger.info(f"✅ Sync completed: {results['created_assets']} created, {results['updated_assets']} updated")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"❌ Sync failed: {e}")
            results['errors'].append({'general_error': str(e)})
        
        return results
    
    async def _get_or_create_asset_from_r2(self, profile_id: str, media_id: str, 
                                         r2_obj: Dict, content_hash: str, size: str) -> Dict[str, Any]:
        """Get or create asset from R2 object data"""
        try:
            # Check if asset exists
            asset_sql = """
                SELECT * FROM cdn_image_assets 
                WHERE source_id = :profile_id AND media_id = :media_id
            """
            
            result = await self.db.execute(
                text(asset_sql),
                {'profile_id': profile_id, 'media_id': media_id}
            )
            
            existing_asset = result.fetchone()
            
            if existing_asset:
                # Update existing asset with R2 data
                await self._update_asset_from_r2(existing_asset.id, r2_obj, content_hash, size)
                return {'created': False, 'asset_id': existing_asset.id}
            else:
                # Create new asset from R2 data
                new_asset_id = await self._create_asset_from_r2(profile_id, media_id, r2_obj)
                return {'created': True, 'asset_id': new_asset_id}
                
        except Exception as e:
            logger.error(f"Error handling asset {profile_id}/{media_id}: {e}")
            raise
    
    async def _create_asset_from_r2(self, profile_id: str, media_id: str, r2_obj: Dict) -> str:
        """Create new asset record from R2 object"""
        try:
            # Determine source type
            source_type = 'profile_avatar' if media_id == 'avatar' else 'post_thumbnail'
            
            # Build CDN paths from R2 key
            base_path = '/'.join(r2_obj['key'].split('/')[:-2])  # Remove size and filename
            cdn_path_256 = f"/{base_path}/256/{r2_obj['key'].split('/')[-1]}"
            cdn_path_512 = f"/{base_path}/512/{r2_obj['key'].split('/')[-1]}"
            
            create_sql = """
                INSERT INTO cdn_image_assets (
                    source_type, source_id, media_id, 
                    processing_status, processing_completed_at,
                    cdn_path_256, cdn_path_512,
                    output_format, file_size_256, file_size_512,
                    original_file_size
                ) VALUES (
                    :source_type, :source_id, :media_id,
                    'completed', :completed_at,
                    :cdn_path_256, :cdn_path_512,
                    'webp', :file_size, :file_size,
                    :file_size
                ) RETURNING id
            """
            
            # Parse datetime string
            completed_at = datetime.fromisoformat(r2_obj['last_modified'].replace('Z', '+00:00'))
            
            result = await self.db.execute(
                text(create_sql),
                {
                    'source_type': source_type,
                    'source_id': profile_id,
                    'media_id': media_id,
                    'completed_at': completed_at,
                    'cdn_path_256': cdn_path_256,
                    'cdn_path_512': cdn_path_512,
                    'file_size': r2_obj['size']
                }
            )
            
            asset_id = result.scalar()
            logger.info(f"✅ Created asset {asset_id} for {profile_id}/{media_id}")
            return asset_id
            
        except Exception as e:
            logger.error(f"Failed to create asset: {e}")
            raise
    
    async def _update_asset_from_r2(self, asset_id: str, r2_obj: Dict, content_hash: str, size: str):
        """Update existing asset with R2 data"""
        try:
            # Build CDN path
            cdn_path = f"/{r2_obj['key']}"
            
            # Update appropriate size column
            if size == '256':
                update_sql = """
                    UPDATE cdn_image_assets 
                    SET processing_status = 'completed',
                        processing_completed_at = :completed_at,
                        cdn_path_256 = :cdn_path,
                        content_hash_256 = :content_hash,
                        file_size_256 = :file_size,
                        output_format = 'webp',
                        updated_at = NOW()
                    WHERE id = :asset_id
                """
            else:  # size == '512'
                update_sql = """
                    UPDATE cdn_image_assets 
                    SET processing_status = 'completed',
                        processing_completed_at = :completed_at,
                        cdn_path_512 = :cdn_path,
                        content_hash_512 = :content_hash,
                        file_size_512 = :file_size,
                        output_format = 'webp',
                        updated_at = NOW()
                    WHERE id = :asset_id
                """
            
            # Parse datetime string
            completed_at = datetime.fromisoformat(r2_obj['last_modified'].replace('Z', '+00:00'))
            
            await self.db.execute(
                text(update_sql),
                {
                    'asset_id': asset_id,
                    'completed_at': completed_at,
                    'cdn_path': cdn_path,
                    'content_hash': content_hash,
                    'file_size': r2_obj['size']
                }
            )
            
            logger.debug(f"✅ Updated asset {asset_id} with R2 data")
            
        except Exception as e:
            logger.error(f"Failed to update asset {asset_id}: {e}")
            raise
    
    async def reset_failed_jobs(self) -> Dict[str, Any]:
        """Reset failed/stuck jobs for retry"""
        try:
            logger.info("🔄 Resetting failed/stuck jobs")
            
            # Reset jobs stuck in processing state for > 1 hour
            reset_stuck_sql = """
                UPDATE cdn_image_jobs 
                SET status = 'queued',
                    started_at = NULL,
                    worker_id = NULL,
                    error_message = NULL
                WHERE status = 'processing' 
                AND started_at < NOW() - INTERVAL '1 hour'
            """
            
            result = await self.db.execute(text(reset_stuck_sql))
            stuck_reset = result.rowcount
            
            # Reset failed jobs with retry count < 3
            reset_failed_sql = """
                UPDATE cdn_image_jobs 
                SET status = 'queued',
                    error_message = NULL
                WHERE status = 'failed' 
                AND retry_count < 3
            """
            
            result = await self.db.execute(text(reset_failed_sql))
            failed_reset = result.rowcount
            
            await self.db.commit()
            
            logger.info(f"✅ Reset {stuck_reset} stuck jobs, {failed_reset} failed jobs")
            
            return {
                'stuck_jobs_reset': stuck_reset,
                'failed_jobs_reset': failed_reset,
                'total_reset': stuck_reset + failed_reset
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"❌ Failed to reset jobs: {e}")
            return {'error': str(e)}
    
    async def clean_orphaned_jobs(self) -> Dict[str, Any]:
        """Clean up orphaned jobs without corresponding assets"""
        try:
            logger.info("🧹 Cleaning orphaned jobs")
            
            cleanup_sql = """
                DELETE FROM cdn_image_jobs 
                WHERE asset_id NOT IN (SELECT id FROM cdn_image_assets)
            """
            
            result = await self.db.execute(text(cleanup_sql))
            cleaned = result.rowcount
            
            await self.db.commit()
            
            logger.info(f"✅ Cleaned {cleaned} orphaned jobs")
            
            return {'orphaned_jobs_cleaned': cleaned}
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"❌ Failed to clean orphaned jobs: {e}")
            return {'error': str(e)}

async def main():
    """Main sync function"""
    from app.database.connection import init_database, get_session
    
    try:
        # Initialize database
        await init_database()
        
        # Sample R2 objects (you should get this from the MCP call)
        r2_objects = [
            {
                'key': 'th/ig/00d6e644-cae5-4e9f-b324-e1e746ba2455/3704146896088119366/256/ad780bafd31df723.webp',
                'last_modified': '2025-08-31T08:56:12.082Z',
                'size': 11198
            },
            {
                'key': 'th/ig/00d6e644-cae5-4e9f-b324-e1e746ba2455/3704146896088119366/512/52710bf3c81c36d4.webp',
                'last_modified': '2025-08-31T08:56:12.274Z',
                'size': 36854
            },
            {
                'key': 'th/ig/06913fd1-2928-46e6-baea-305998e0d228/3709080944583605192/256/fa96ca60e4f1b671.webp',
                'last_modified': '2025-09-01T11:00:13.475Z',
                'size': 9852
            },
            {
                'key': 'th/ig/06913fd1-2928-46e6-baea-305998e0d228/3709080944583605192/512/024737d090e5be7b.webp',
                'last_modified': '2025-09-01T11:00:14.063Z',
                'size': 24816
            },
            {
                'key': 'th/ig/ed993e51-56fa-4211-9c35-c221b5c7c9e6/avatar/256/a665121415c497af.webp',
                'last_modified': '2025-08-31T08:41:00.912Z',
                'size': 6986
            },
            {
                'key': 'th/ig/ed993e51-56fa-4211-9c35-c221b5c7c9e6/avatar/512/72f8bf3569d65b48.webp',
                'last_modified': '2025-08-31T08:41:01.110Z',
                'size': 15596
            }
        ]
        
        # Get database session and sync
        async with get_session() as db_session:
            fixer = CDNDatabaseSyncFixer(db_session)
            
            # 1. Sync R2 with database
            sync_results = await fixer.sync_r2_with_database(r2_objects)
            print(f"Sync Results: {sync_results}")
            
            # 2. Reset failed jobs
            reset_results = await fixer.reset_failed_jobs()
            print(f"Job Reset Results: {reset_results}")
            
            # 3. Clean orphaned jobs
            clean_results = await fixer.clean_orphaned_jobs()
            print(f"Cleanup Results: {clean_results}")
        
        print("CDN database sync completed successfully!")
        
    except Exception as e:
        print(f"CDN sync failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())