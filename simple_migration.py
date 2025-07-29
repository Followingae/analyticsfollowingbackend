"""
Simple migration: Add enhanced columns to existing profiles table
"""
import asyncio
import asyncpg
from app.core.config import settings

async def add_enhanced_columns():
    """
    Add all enhanced columns to the existing profiles table
    """
    print("Adding enhanced columns to existing profiles table...")
    
    try:
        pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
        
        async with pool.acquire() as conn:
            
            print("Step 1: Adding enhanced columns...")
            
            # Add all the enhanced columns to the existing profiles table
            enhanced_columns = [
                # Core Profile Information
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS instagram_user_id VARCHAR(50)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS full_name TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS biography TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS external_url TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS external_url_shimmed TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_pic_url TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_pic_url_hd TEXT",
                
                # Account Statistics
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS followers_count BIGINT DEFAULT 0",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS following_count BIGINT DEFAULT 0",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS posts_count BIGINT DEFAULT 0",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS mutual_followers_count BIGINT DEFAULT 0",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS highlight_reel_count INTEGER DEFAULT 0",
                
                # Account Status & Verification
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_business_account BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_professional_account BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_joined_recently BOOLEAN DEFAULT FALSE",
                
                # Business Information
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS business_category_name VARCHAR(255)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS overall_category_name VARCHAR(255)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS category_enum VARCHAR(100)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS business_address_json TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS business_contact_method VARCHAR(50)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS business_email VARCHAR(255)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS business_phone_number VARCHAR(50)",
                
                # Account Features
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_ar_effects BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_clips BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_guides BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_channel BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_onboarded_to_text_post_app BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS show_text_post_app_badge BOOLEAN DEFAULT FALSE",
                
                # Privacy & Restrictions
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS country_block BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_embeds_disabled BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS hide_like_and_view_counts BOOLEAN DEFAULT FALSE",
                
                # Account Settings
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS should_show_category BOOLEAN DEFAULT TRUE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS should_show_public_contacts BOOLEAN DEFAULT TRUE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS show_account_transparency_details BOOLEAN DEFAULT TRUE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS remove_message_entrypoint BOOLEAN DEFAULT FALSE",
                
                # Viewer Relationships
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS blocked_by_viewer BOOLEAN",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_blocked_viewer BOOLEAN",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS restricted_by_viewer BOOLEAN",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS followed_by_viewer BOOLEAN",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS follows_viewer BOOLEAN",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS requested_by_viewer BOOLEAN",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS has_requested_viewer BOOLEAN",
                
                # AI & Special Features
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_agent_type VARCHAR(100)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_agent_owner_username VARCHAR(255)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS transparency_label VARCHAR(255)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS transparency_product VARCHAR(255)",
                
                # Supervision & Safety
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_supervision_enabled BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_guardian_of_viewer BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_supervised_by_viewer BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_supervised_user BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS guardian_id VARCHAR(50)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_regulated_c18 BOOLEAN DEFAULT FALSE",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_verified_by_mv4b BOOLEAN DEFAULT FALSE",
                
                # Advanced Fields
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS fbid VARCHAR(50)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS eimu_id VARCHAR(50)",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS pinned_channels_list_count INTEGER DEFAULT 0",
                
                # Structured Data
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS biography_with_entities JSONB",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bio_links JSONB",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS pronouns JSONB",
                
                # Analytics & Metrics
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS engagement_rate FLOAT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avg_likes FLOAT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avg_comments FLOAT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avg_engagement FLOAT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS content_quality_score FLOAT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS influence_score FLOAT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS data_quality_score INTEGER DEFAULT 0",
                
                # Timestamps (created_at already exists as last_refreshed)
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ]
            
            # Execute all column additions
            for i, sql in enumerate(enhanced_columns, 1):
                try:
                    await conn.execute(sql)
                    if i % 10 == 0:
                        print(f"   Added {i}/{len(enhanced_columns)} columns...")
                except Exception as e:
                    print(f"   Warning: {sql[:50]}... failed: {e}")
            
            print(f"Step 1 Complete: Added {len(enhanced_columns)} enhanced columns")
            
            print("Step 2: Creating indexes for performance...")
            
            # Create important indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username)",
                "CREATE INDEX IF NOT EXISTS idx_profiles_instagram_id ON profiles(instagram_user_id)",
                "CREATE INDEX IF NOT EXISTS idx_profiles_followers ON profiles(followers_count)",
                "CREATE INDEX IF NOT EXISTS idx_profiles_verified ON profiles(is_verified)",
                "CREATE INDEX IF NOT EXISTS idx_profiles_last_refreshed ON profiles(last_refreshed)"
            ]
            
            for sql in indexes:
                try:
                    await conn.execute(sql)
                except Exception as e:
                    print(f"   Warning: Index creation failed: {e}")
            
            print("Step 2 Complete: Created performance indexes")
            
            # Check final column count
            columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'profiles' 
                ORDER BY ordinal_position
            """)
            
            print(f"Migration Complete: profiles table now has {len(columns)} columns")
            print("Enhanced schema ready for sophisticated data storage!")
            
        await pool.close()
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(add_enhanced_columns())