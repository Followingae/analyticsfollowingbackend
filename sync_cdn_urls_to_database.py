#!/usr/bin/env python3
"""
Sync CDN URLs from R2 bucket back to database
For cases where images were processed but database wasn't updated
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def sync_cdn_urls():
    """Sync CDN URLs from R2 bucket metadata to database"""
    try:
        print("Syncing CDN URLs from R2 bucket to database...")
        
        # Initialize database
        from app.database.connection import init_database, get_session
        await init_database()
        
        # Import R2 client
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
        
        # Get all objects from R2
        objects = await r2_client.list_objects(max_keys=1000)
        print(f"Found {len(objects)} objects in R2 bucket")
        
        # Group by profile and media ID
        cdn_urls = {}
        for obj in objects:
            key = obj['key']  # th/ig/profile_id/media_id/size/hash.webp
            
            parts = key.split('/')
            if len(parts) >= 5 and parts[0] == 'th' and parts[1] == 'ig':
                profile_id = parts[2]
                media_id = parts[3]
                size = parts[4]
                
                cdn_url = f"https://cdn.following.ae/{key}"
                
                if profile_id not in cdn_urls:
                    cdn_urls[profile_id] = {}
                if media_id not in cdn_urls[profile_id]:
                    cdn_urls[profile_id][media_id] = {}
                    
                cdn_urls[profile_id][media_id][f"cdn_url_{size}"] = cdn_url
        
        print(f"Grouped CDN URLs for {len(cdn_urls)} profiles")
        
        async with get_session() as db:
            updated = 0
            for profile_id, profile_media in cdn_urls.items():
                for media_id, urls in profile_media.items():
                    try:
                        # Update the database record
                        update_data = {}
                        if "cdn_url_256" in urls:
                            update_data["cdn_url_256"] = urls["cdn_url_256"]
                        if "cdn_url_512" in urls:
                            update_data["cdn_url_512"] = urls["cdn_url_512"]
                        
                        if update_data:
                            # Build dynamic update query
                            set_clauses = []
                            params = {"profile_id": profile_id, "media_id": media_id}
                            
                            for field, value in update_data.items():
                                set_clauses.append(f"{field} = :{field}")
                                params[field] = value
                            
                            set_clauses.append("processing_status = 'completed'")
                            set_clauses.append("updated_at = NOW()")
                            
                            query = f"""
                                UPDATE cdn_image_assets 
                                SET {', '.join(set_clauses)}
                                WHERE source_id = :profile_id 
                                AND media_id = :media_id
                                AND (cdn_url_256 IS NULL OR cdn_url_512 IS NULL)
                            """
                            
                            result = await db.execute(text(query), params)
                            if result.rowcount > 0:
                                updated += 1
                                print(f"Updated {profile_id[:8]}/{media_id}: {list(update_data.keys())}")
                        
                    except Exception as e:
                        print(f"Error updating {profile_id}/{media_id}: {e}")
                        continue
            
            await db.commit()
            print(f"\nSync complete: Updated {updated} database records with CDN URLs")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(sync_cdn_urls())