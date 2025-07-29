"""
Database migration script to replace old profiles table with enhanced schema
"""
import asyncio
import asyncpg
import json
from datetime import datetime
from app.core.config import settings

async def migrate_database():
    """
    Professional database migration to enhanced schema
    """
    print("Starting database migration to enhanced schema...")
    
    try:
        # Create connection pool
        pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=3)
        
        async with pool.acquire() as conn:
            # Start transaction for safe migration
            async with conn.transaction():
                
                # Step 1: Backup existing data
                print("Step 1: Backing up existing profiles data...")
                existing_profiles = await conn.fetch("SELECT * FROM profiles")
                print(f"   Found {len(existing_profiles)} existing profiles to migrate")
                
                # Step 2: Rename old table as backup
                print("Step 2: Creating backup of old table...")
                await conn.execute("ALTER TABLE profiles RENAME TO profiles_backup_old")
                
                # Step 3: Rename enhanced table to become the main profiles table
                print("Step 3: Promoting enhanced table to main profiles table...")
                await conn.execute("ALTER TABLE profiles_enhanced RENAME TO profiles")
                
                # Step 4: Update foreign key references in other tables
                print("Step 4: Updating foreign key references...")
                
                # Update posts table to reference new profiles table
                await conn.execute("""
                    ALTER TABLE posts 
                    DROP CONSTRAINT IF EXISTS posts_profile_id_fkey
                """)
                await conn.execute("""
                    ALTER TABLE posts 
                    ADD CONSTRAINT posts_profile_id_fkey 
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                """)
                
                # Update related_profiles table
                await conn.execute("""
                    ALTER TABLE related_profiles 
                    DROP CONSTRAINT IF EXISTS related_profiles_profile_id_fkey
                """)
                await conn.execute("""
                    ALTER TABLE related_profiles 
                    ADD CONSTRAINT related_profiles_profile_id_fkey 
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                """)
                
                # Update user_profile_access table
                await conn.execute("""
                    ALTER TABLE user_profile_access 
                    DROP CONSTRAINT IF EXISTS user_profile_access_profile_id_fkey
                """)
                await conn.execute("""
                    ALTER TABLE user_profile_access 
                    ADD CONSTRAINT user_profile_access_profile_id_fkey 
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                """)
                
                # Step 5: Migrate existing data from backup to new enhanced table
                print("Step 5: Migrating existing profile data to enhanced schema...")
                
                migrated_count = 0
                for old_profile in existing_profiles:
                    try:
                        # Extract data from old format
                        username = old_profile['username']
                        raw_data = old_profile['raw_data']
                        last_refreshed = old_profile['last_refreshed']
                        
                        # Parse raw_data to extract enhanced fields
                        enhanced_data = extract_enhanced_fields(raw_data, username)
                        enhanced_data['last_refreshed'] = last_refreshed
                        
                        # Insert into new enhanced table
                        columns = list(enhanced_data.keys())
                        placeholders = [f"${i+1}" for i in range(len(columns))]
                        values = list(enhanced_data.values())
                        
                        query = f"""
                            INSERT INTO profiles ({', '.join(columns)}) 
                            VALUES ({', '.join(placeholders)})
                            ON CONFLICT (username) DO UPDATE SET
                            last_refreshed = EXCLUDED.last_refreshed
                        """
                        
                        await conn.execute(query, *values)
                        migrated_count += 1
                        print(f"   Migrated profile: {username}")
                        
                    except Exception as e:
                        print(f"   Failed to migrate profile {username}: {e}")
                        continue
                
                print(f"Step 5 Complete: Migrated {migrated_count}/{len(existing_profiles)} profiles")
                
                # Step 6: Rename posts_enhanced to posts (if needed)
                print("Step 6: Updating posts table...")
                
                # Check if posts_enhanced has data that posts doesn't
                posts_enhanced_count = await conn.fetchval("SELECT COUNT(*) FROM posts_enhanced")
                posts_old_count = await conn.fetchval("SELECT COUNT(*) FROM posts")
                
                if posts_enhanced_count > posts_old_count:
                    await conn.execute("DROP TABLE IF EXISTS posts_backup_old")
                    await conn.execute("ALTER TABLE posts RENAME TO posts_backup_old")
                    await conn.execute("ALTER TABLE posts_enhanced RENAME TO posts")
                    print(f"   Promoted posts_enhanced ({posts_enhanced_count} posts) to main posts table")
                
                print("Migration completed successfully!")
                
        await pool.close()
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

def extract_enhanced_fields(raw_data: dict, username: str) -> dict:
    """
    Extract enhanced fields from raw Decodo data
    """
    def safe_get(data, path, default=None):
        try:
            result = data
            for key in path.split('.'):
                result = result[key]
            return result if result is not None else default
        except (KeyError, TypeError):
            return default
    
    # Extract user data from Decodo response
    try:
        results = raw_data.get('results', [])
        if results:
            content = results[0].get('content', {})
            data = content.get('data', {})
            user_data = data.get('user', {})
        else:
            user_data = {}
    except:
        user_data = {}
    
    # Map to enhanced schema
    enhanced_data = {
        'username': username,
        'instagram_user_id': safe_get(user_data, 'id', ''),
        'full_name': safe_get(user_data, 'full_name', ''),
        'biography': safe_get(user_data, 'biography', ''),
        'external_url': safe_get(user_data, 'external_url', ''),
        'external_url_shimmed': safe_get(user_data, 'external_url_linkshimmed', ''),
        'profile_pic_url': safe_get(user_data, 'profile_pic_url', ''),
        'profile_pic_url_hd': safe_get(user_data, 'profile_pic_url_hd', ''),
        
        # Statistics
        'followers_count': safe_get(user_data, 'edge_followed_by.count', 0),
        'following_count': safe_get(user_data, 'edge_follow.count', 0),
        'posts_count': safe_get(user_data, 'edge_owner_to_timeline_media.count', 0),
        'mutual_followers_count': safe_get(user_data, 'edge_mutual_followed_by.count', 0),
        'highlight_reel_count': safe_get(user_data, 'highlight_reel_count', 0),
        
        # Account Status
        'is_verified': safe_get(user_data, 'is_verified', False),
        'is_private': safe_get(user_data, 'is_private', False),
        'is_business_account': safe_get(user_data, 'is_business_account', False),
        'is_professional_account': safe_get(user_data, 'is_professional_account', False),
        'is_joined_recently': safe_get(user_data, 'is_joined_recently', False),
        
        # Business Information
        'business_category_name': safe_get(user_data, 'business_category_name', ''),
        'overall_category_name': safe_get(user_data, 'overall_category_name', ''),
        'category_enum': safe_get(user_data, 'category_enum', ''),
        'business_address_json': safe_get(user_data, 'business_address_json', ''),
        'business_contact_method': safe_get(user_data, 'business_contact_method', ''),
        'business_email': safe_get(user_data, 'business_email', ''),
        'business_phone_number': safe_get(user_data, 'business_phone_number', ''),
        
        # Features
        'has_ar_effects': safe_get(user_data, 'has_ar_effects', False),
        'has_clips': safe_get(user_data, 'has_clips', False),
        'has_guides': safe_get(user_data, 'has_guides', False),
        'has_channel': safe_get(user_data, 'has_channel', False),
        'has_onboarded_to_text_post_app': safe_get(user_data, 'has_onboarded_to_text_post_app', False),
        'show_text_post_app_badge': safe_get(user_data, 'show_text_post_app_badge', False),
        
        # Privacy
        'country_block': safe_get(user_data, 'country_block', False),
        'is_embeds_disabled': safe_get(user_data, 'is_embeds_disabled', False),
        'hide_like_and_view_counts': safe_get(user_data, 'hide_like_and_view_counts', False),
        
        # Settings
        'should_show_category': safe_get(user_data, 'should_show_category', True),
        'should_show_public_contacts': safe_get(user_data, 'should_show_public_contacts', True),
        'show_account_transparency_details': safe_get(user_data, 'show_account_transparency_details', True),
        'remove_message_entrypoint': safe_get(user_data, 'remove_message_entrypoint', False),
        
        # Viewer Relationships
        'blocked_by_viewer': safe_get(user_data, 'blocked_by_viewer'),
        'has_blocked_viewer': safe_get(user_data, 'has_blocked_viewer'),
        'restricted_by_viewer': safe_get(user_data, 'restricted_by_viewer'),
        'followed_by_viewer': safe_get(user_data, 'followed_by_viewer'),
        'follows_viewer': safe_get(user_data, 'follows_viewer'),
        'requested_by_viewer': safe_get(user_data, 'requested_by_viewer'),
        'has_requested_viewer': safe_get(user_data, 'has_requested_viewer'),
        
        # AI & Special Features
        'ai_agent_type': safe_get(user_data, 'ai_agent_type', ''),
        'ai_agent_owner_username': safe_get(user_data, 'ai_agent_owner_username', ''),
        'transparency_label': safe_get(user_data, 'transparency_label', ''),
        'transparency_product': safe_get(user_data, 'transparency_product', ''),
        
        # Supervision
        'is_supervision_enabled': safe_get(user_data, 'is_supervision_enabled', False),
        'is_guardian_of_viewer': safe_get(user_data, 'is_guardian_of_viewer', False),
        'is_supervised_by_viewer': safe_get(user_data, 'is_supervised_by_viewer', False),
        'is_supervised_user': safe_get(user_data, 'is_supervised_user', False),
        'guardian_id': safe_get(user_data, 'guardian_id', ''),
        'is_regulated_c18': safe_get(user_data, 'is_regulated_c18', False),
        'is_verified_by_mv4b': safe_get(user_data, 'is_verified_by_mv4b', False),
        
        # Advanced
        'fbid': safe_get(user_data, 'fbid', ''),
        'eimu_id': safe_get(user_data, 'eimu_id', ''),
        'pinned_channels_list_count': safe_get(user_data, 'pinned_channels_list_count', 0),
        
        # Structured Data
        'biography_with_entities': json.dumps(safe_get(user_data, 'biography_with_entities', {})),
        'bio_links': json.dumps(safe_get(user_data, 'bio_links', [])),
        'pronouns': json.dumps(safe_get(user_data, 'pronouns', [])),
        
        # Calculate data quality
        'data_quality_score': 85,  # Default score, will be recalculated
        
        # Raw data backup
        'raw_data': json.dumps(raw_data)
    }
    
    return enhanced_data

if __name__ == "__main__":
    asyncio.run(migrate_database())