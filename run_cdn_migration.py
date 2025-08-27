"""
CDN Database Migration Script
Run this to create the CDN tables in your database
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    print('Running CDN database migration...')
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        
        with open('database/migrations/013_cdn_image_system.sql', 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        await conn.execute(migration_sql)
        await conn.close()
        
        print('✅ CDN migration completed successfully')
        print('Created tables: cdn_image_assets, cdn_image_jobs, cdn_processing_stats')
        
    except Exception as e:
        print(f'❌ Migration failed: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_migration())