"""
Clean up duplicate tables and fix database storage issues
"""
import asyncio
import asyncpg
from app.core.config import settings

async def cleanup_and_fix_database():
    """
    1. Remove duplicate tables (profiles_enhanced, posts_enhanced)
    2. Fix any storage issues 
    3. Verify database structure
    """
    print("Starting database cleanup and fixes...")
    
    try:
        pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
        
        async with pool.acquire() as conn:
            
            print("Step 1: Checking current table structure...")
            
            # Check which tables exist
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            
            table_names = [t['table_name'] for t in tables]
            print(f"Found tables: {', '.join(table_names)}")
            
            # Check profiles table column count
            profiles_columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'profiles' 
                ORDER BY ordinal_position
            """)
            print(f"Main profiles table has {len(profiles_columns)} columns")
            
            print("\nStep 2: Cleaning up duplicate tables...")
            
            # Remove duplicate enhanced tables if they exist
            if 'profiles_enhanced' in table_names:
                print("  Removing profiles_enhanced table...")
                await conn.execute("DROP TABLE IF EXISTS profiles_enhanced CASCADE")
                print("  ✓ profiles_enhanced removed")
            
            if 'posts_enhanced' in table_names:
                print("  Removing posts_enhanced table...")
                await conn.execute("DROP TABLE IF EXISTS posts_enhanced CASCADE")
                print("  ✓ posts_enhanced removed")
            
            # Remove old backup tables if they exist
            if 'profiles_backup_old' in table_names:
                print("  Removing profiles_backup_old table...")
                await conn.execute("DROP TABLE IF EXISTS profiles_backup_old CASCADE")
                print("  ✓ profiles_backup_old removed")
            
            if 'posts_backup_old' in table_names:
                print("  Removing posts_backup_old table...")
                await conn.execute("DROP TABLE IF EXISTS posts_backup_old CASCADE")
                print("  ✓ posts_backup_old removed")
            
            print("\nStep 3: Verifying main tables structure...")
            
            # Verify profiles table has all required columns
            required_columns = [
                'id', 'username', 'raw_data', 'last_refreshed',
                'instagram_user_id', 'full_name', 'biography', 'external_url',
                'profile_pic_url', 'profile_pic_url_hd', 'followers_count',
                'following_count', 'posts_count', 'is_verified', 'is_private'
            ]
            
            existing_columns = [col['column_name'] for col in profiles_columns]
            missing_columns = [col for col in required_columns if col not in existing_columns]
            
            if missing_columns:
                print(f"  Missing columns: {missing_columns}")
            else:
                print("  ✓ All required columns present")
            
            print("\nStep 4: Testing database storage...")
            
            # Test insert/update functionality
            test_data = {
                'username': 'test_storage_check',
                'instagram_user_id': 'test123',
                'full_name': 'Test User',
                'biography': 'Test bio',
                'followers_count': 1000,
                'is_verified': True,
                'raw_data': '{"test": "data"}'
            }
            
            # Try to insert test data
            try:
                await conn.execute("""
                    INSERT INTO profiles (username, instagram_user_id, full_name, 
                                        biography, followers_count, is_verified, raw_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (username) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    last_refreshed = NOW()
                """, 
                test_data['username'], test_data['instagram_user_id'], 
                test_data['full_name'], test_data['biography'],
                test_data['followers_count'], test_data['is_verified'],
                test_data['raw_data'])
                
                print("  ✓ Database storage test successful")
                
                # Clean up test data
                await conn.execute("DELETE FROM profiles WHERE username = 'test_storage_check'")
                
            except Exception as e:
                print(f"  ✗ Database storage test failed: {e}")
            
            print("\nStep 5: Final verification...")
            
            # Check current profile count
            profile_count = await conn.fetchval("SELECT COUNT(*) FROM profiles")
            print(f"  Total profiles in database: {profile_count}")
            
            # Show recent profiles
            recent = await conn.fetch("""
                SELECT username, full_name, followers_count, last_refreshed 
                FROM profiles 
                ORDER BY last_refreshed DESC 
                LIMIT 5
            """)
            
            print("  Recent profiles:")
            for profile in recent:
                username = profile['username']
                full_name = profile['full_name'] or 'No name'
                followers = profile['followers_count'] or 0
                timestamp = profile['last_refreshed']
                print(f"    - {username} ({full_name}) - {followers:,} followers - {timestamp}")
            
            print("\n✓ Database cleanup and verification complete!")
            
        await pool.close()
        
    except Exception as e:
        print(f"Cleanup failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(cleanup_and_fix_database())