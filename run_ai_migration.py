"""
AI Content Analysis Migration Runner
"""
import asyncio
import asyncpg
import os
from pathlib import Path

async def run_ai_migration():
    """Run the AI content analysis database migration"""
    try:
        # Use environment variables or fallback
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.vkbuxemkprorqxmzzkuu:Hhotmail8991%40@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
        
        print("Connecting to database...")
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Read migration SQL
        migration_path = Path("database/migrations/add_ai_content_analysis_columns.sql")
        if not migration_path.exists():
            print(f"ERROR: Migration file not found at {migration_path}")
            return
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("Running AI content analysis migration...")
        await conn.execute(migration_sql)
        print("SUCCESS: AI content analysis columns migration completed!")
        
        # Verify the new columns exist
        posts_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'posts' AND column_name LIKE 'ai_%'
            ORDER BY column_name
        """)
        
        profiles_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'profiles' AND column_name LIKE 'ai_%'
            ORDER BY column_name  
        """)
        
        print(f"\nAdded {len(posts_columns)} AI columns to posts table:")
        for col in posts_columns:
            print(f"  - {col['column_name']} ({col['data_type']})")
            
        print(f"\nAdded {len(profiles_columns)} AI columns to profiles table:")
        for col in profiles_columns:
            print(f"  - {col['column_name']} ({col['data_type']})")
        
        # Check for instagram_business_category column
        business_cat_check = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'profiles' AND column_name = 'instagram_business_category'
        """)
        
        if business_cat_check:
            print("\nSUCCESS: instagram_business_category column created for backwards compatibility")
        
        await conn.close()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run_ai_migration())