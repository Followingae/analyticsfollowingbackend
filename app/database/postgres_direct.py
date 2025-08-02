"""
Direct PostgreSQL connection for Supabase database operations
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import asyncpg
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class PostgresDirectClient:
    """Direct PostgreSQL client for database operations"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def init(self):
        """Initialize PostgreSQL connection pool"""
        try:
            if not settings.DATABASE_URL or "[YOUR-PASSWORD]" in settings.DATABASE_URL:
                logger.warning("Database URL not configured")
                return False
            
            # Parse the DATABASE_URL for asyncpg
            db_url = settings.DATABASE_URL.replace("postgresql://", "")
            
            self.pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=1,
                max_size=5,
                server_settings={"statement_cache_size": "0"}
            )
            logger.info("SUCCESS: Direct PostgreSQL pool initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            return False
    
    async def store_profile(self, username: str, raw_data: Dict[str, Any]) -> bool:
        """Store profile data directly in PostgreSQL"""
        if not self.pool:
            logger.warning("PostgreSQL pool not initialized")
            return False
            
        try:
            # Extract user data from Decodo response
            user_data = self._extract_user_data(raw_data)
            if not user_data:
                logger.error("Invalid Decodo response structure")
                return False
            
            # Map Decodo data to profile structure
            profile_data = self._map_decodo_to_profile_data(user_data, raw_data)
            
            async with self.pool.acquire() as conn:
                # Check if profile exists
                existing = await conn.fetchrow(
                    "SELECT id FROM profiles WHERE username = $1", username
                )
                
                if existing:
                    # Simple update with key fields only
                    await conn.execute("""
                        UPDATE profiles SET 
                            raw_data = $2,
                            full_name = $3,
                            biography = $4,
                            followers_count = $5,
                            following_count = $6,
                            posts_count = $7,
                            is_verified = $8,
                            is_private = $9,
                            profile_pic_url = $10,
                            profile_pic_url_hd = $11,
                            external_url = $12,
                            instagram_user_id = $13,
                            business_category_name = $14,
                            has_clips = $15,
                            last_refreshed = NOW()
                        WHERE username = $1
                    """, 
                    username,
                    json.dumps(raw_data),
                    profile_data.get('full_name', ''),
                    profile_data.get('biography', ''),
                    profile_data.get('followers_count', 0),
                    profile_data.get('following_count', 0),
                    profile_data.get('posts_count', 0),
                    profile_data.get('is_verified', False),
                    profile_data.get('is_private', False),
                    profile_data.get('profile_pic_url', ''),
                    profile_data.get('profile_pic_url_hd', ''),
                    profile_data.get('external_url', ''),
                    profile_data.get('instagram_user_id', ''),
                    profile_data.get('business_category_name', ''),
                    profile_data.get('has_clips', False)
                    )
                    logger.info(f"Updated enhanced profile for {username} in PostgreSQL")
                else:
                    # Simple insert with key fields only
                    profile_id = str(uuid.uuid4())
                    await conn.execute("""
                        INSERT INTO profiles (
                            id, username, raw_data, full_name, biography, 
                            followers_count, following_count, posts_count,
                            is_verified, is_private, profile_pic_url, profile_pic_url_hd,
                            external_url, instagram_user_id, business_category_name, 
                            has_clips, last_refreshed
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW()
                        )
                    """,
                    profile_id,
                    username,
                    json.dumps(raw_data),
                    profile_data.get('full_name', ''),
                    profile_data.get('biography', ''),
                    profile_data.get('followers_count', 0),
                    profile_data.get('following_count', 0),
                    profile_data.get('posts_count', 0),
                    profile_data.get('is_verified', False),
                    profile_data.get('is_private', False),
                    profile_data.get('profile_pic_url', ''),
                    profile_data.get('profile_pic_url_hd', ''),
                    profile_data.get('external_url', ''),
                    profile_data.get('instagram_user_id', ''),
                    profile_data.get('business_category_name', ''),
                    profile_data.get('has_clips', False)
                    )
                    logger.info(f"Created enhanced profile for {username} in PostgreSQL with ID {profile_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing profile {username}: {str(e)}")
            return False
    
    async def get_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Get profile data from PostgreSQL"""
        if not self.pool:
            return None
            
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM profiles WHERE username = $1", username
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting profile {username}: {str(e)}")
            return None
    
    async def is_profile_fresh(self, username: str, max_age_hours: int = 24) -> bool:
        """Check if profile data is fresh"""
        if not self.pool:
            return False
            
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT last_refreshed FROM profiles 
                    WHERE username = $1 
                    AND last_refreshed > NOW() - INTERVAL '%s hours'
                """ % max_age_hours, username)
                return row is not None
        except Exception as e:
            logger.error(f"Error checking profile freshness: {e}")
            return False
    
    async def get_recent_profiles(self, limit: int = 10) -> list:
        """Get recent profiles for debugging"""
        if not self.pool:
            return []
            
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT username, last_refreshed 
                    FROM profiles 
                    ORDER BY last_refreshed DESC 
                    LIMIT $1
                """, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent profiles: {e}")
            return []
    
    def _extract_user_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user data from Decodo response"""
        try:
            results = raw_data.get('results', [])
            if not results:
                return {}
            
            content = results[0].get('content', {})
            data = content.get('data', {})
            user_data = data.get('user', {})
            
            return user_data
        except (KeyError, IndexError, TypeError):
            return {}
    
    def _map_decodo_to_profile_data(self, user_data: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Decodo data to enhanced profile table structure"""
        def safe_get(data, path, default=None):
            try:
                result = data
                for key in path.split('.'):
                    result = result[key]
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        # Enhanced profile data mapping - all 69+ fields
        profile_data = {
            # Core Profile Information
            'instagram_user_id': safe_get(user_data, 'id', ''),
            'full_name': safe_get(user_data, 'full_name', ''),
            'biography': safe_get(user_data, 'biography', ''),
            'external_url': safe_get(user_data, 'external_url', ''),
            'external_url_shimmed': safe_get(user_data, 'external_url_linkshimmed', ''),
            'profile_pic_url': safe_get(user_data, 'profile_pic_url', ''),
            'profile_pic_url_hd': safe_get(user_data, 'profile_pic_url_hd', ''),
            
            # Account Statistics
            'followers_count': safe_get(user_data, 'edge_followed_by.count', 0),
            'following_count': safe_get(user_data, 'edge_follow.count', 0),
            'posts_count': safe_get(user_data, 'edge_owner_to_timeline_media.count', 0),
            'mutual_followers_count': safe_get(user_data, 'edge_mutual_followed_by.count', 0),
            'highlight_reel_count': safe_get(user_data, 'highlight_reel_count', 0),
            
            # Account Status & Verification
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
            
            # Account Features
            'has_ar_effects': safe_get(user_data, 'has_ar_effects', False),
            'has_clips': safe_get(user_data, 'has_clips', False),
            'has_guides': safe_get(user_data, 'has_guides', False),
            'has_channel': safe_get(user_data, 'has_channel', False),
            'has_onboarded_to_text_post_app': safe_get(user_data, 'has_onboarded_to_text_post_app', False),
            'show_text_post_app_badge': safe_get(user_data, 'show_text_post_app_badge', False),
            
            # Privacy & Restrictions
            'country_block': safe_get(user_data, 'country_block', False),
            'is_embeds_disabled': safe_get(user_data, 'is_embeds_disabled', False),
            'hide_like_and_view_counts': safe_get(user_data, 'hide_like_and_view_counts', False),
            
            # Account Settings
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
            
            # Supervision & Safety
            'is_supervision_enabled': safe_get(user_data, 'is_supervision_enabled', False),
            'is_guardian_of_viewer': safe_get(user_data, 'is_guardian_of_viewer', False),
            'is_supervised_by_viewer': safe_get(user_data, 'is_supervised_by_viewer', False),
            'is_supervised_user': safe_get(user_data, 'is_supervised_user', False),
            'guardian_id': safe_get(user_data, 'guardian_id', ''),
            'is_regulated_c18': safe_get(user_data, 'is_regulated_c18', False),
            'is_verified_by_mv4b': safe_get(user_data, 'is_verified_by_mv4b', False),
            
            # Advanced Fields
            'fbid': safe_get(user_data, 'fbid', ''),
            'eimu_id': safe_get(user_data, 'eimu_id', ''),
            'pinned_channels_list_count': safe_get(user_data, 'pinned_channels_list_count', 0),
            
            # Structured Data (JSONB)
            'biography_with_entities': safe_get(user_data, 'biography_with_entities', {}),
            'bio_links': safe_get(user_data, 'bio_links', []),
            'pronouns': safe_get(user_data, 'pronouns', []),
            
            # Calculate data quality score
            'data_quality_score': 90  # Will be calculated based on populated fields
        }
        
        return profile_data

# Global instance
postgres_direct = PostgresDirectClient()