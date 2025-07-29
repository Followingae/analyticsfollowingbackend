"""
Enhanced database service with robust connection handling and sophisticated data mapping
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import asyncpg
from asyncpg.pool import Pool
import logging
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

class EnhancedDatabaseService:
    """
    Professional-grade database service with robust connection handling
    """
    
    def __init__(self):
        self.pool: Optional[Pool] = None
        self._connection_retry_count = 0
        self._max_retries = 3
        self._pool_settings = {
            "min_size": 5,
            "max_size": 20,
            "command_timeout": 60,
            "server_settings": {
                "statement_timeout": "300000",
                "idle_in_transaction_session_timeout": "300000"
            }
        }
    
    async def initialize(self) -> bool:
        """
        Initialize database connection pool with robust error handling
        """
        try:
            if not settings.DATABASE_URL or "[YOUR-PASSWORD]" in settings.DATABASE_URL:
                logger.error("Database URL not configured properly")
                return False
            
            # Create connection pool with retry logic
            for attempt in range(self._max_retries):
                try:
                    self.pool = await asyncpg.create_pool(
                        settings.DATABASE_URL,
                        **self._pool_settings
                    )
                    
                    # Test connection
                    async with self.pool.acquire() as conn:
                        await conn.execute("SELECT 1")
                    
                    logger.info(f"✅ Enhanced database pool initialized (attempt {attempt + 1})")
                    await self._ensure_schema_exists()
                    return True
                    
                except Exception as e:
                    logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.error(f"Failed to initialize database after {self._max_retries} attempts")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Critical database initialization error: {e}")
            return False
    
    async def _ensure_schema_exists(self):
        """
        Ensure all required tables exist with proper schema
        """
        try:
            async with self.pool.acquire() as conn:
                # Create enhanced profiles table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS profiles_enhanced (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        username VARCHAR(255) UNIQUE NOT NULL,
                        instagram_user_id VARCHAR(50) UNIQUE,
                        
                        -- Profile Basic Information
                        full_name TEXT,
                        biography TEXT,
                        external_url TEXT,
                        external_url_shimmed TEXT,
                        profile_pic_url TEXT,
                        profile_pic_url_hd TEXT,
                        
                        -- Account Statistics
                        followers_count BIGINT DEFAULT 0,
                        following_count BIGINT DEFAULT 0,
                        posts_count BIGINT DEFAULT 0,
                        mutual_followers_count BIGINT DEFAULT 0,
                        highlight_reel_count INTEGER DEFAULT 0,
                        
                        -- Account Status & Verification
                        is_verified BOOLEAN DEFAULT FALSE,
                        is_private BOOLEAN DEFAULT FALSE,
                        is_business_account BOOLEAN DEFAULT FALSE,
                        is_professional_account BOOLEAN DEFAULT FALSE,
                        is_joined_recently BOOLEAN DEFAULT FALSE,
                        
                        -- Business Information
                        business_category_name VARCHAR(255),
                        overall_category_name VARCHAR(255),
                        category_enum VARCHAR(100),
                        business_address_json TEXT,
                        business_contact_method VARCHAR(50),
                        business_email VARCHAR(255),
                        business_phone_number VARCHAR(50),
                        
                        -- Account Features
                        has_ar_effects BOOLEAN DEFAULT FALSE,
                        has_clips BOOLEAN DEFAULT FALSE,
                        has_guides BOOLEAN DEFAULT FALSE,
                        has_channel BOOLEAN DEFAULT FALSE,
                        has_onboarded_to_text_post_app BOOLEAN DEFAULT FALSE,
                        show_text_post_app_badge BOOLEAN DEFAULT FALSE,
                        
                        -- Privacy & Restrictions
                        country_block BOOLEAN DEFAULT FALSE,
                        is_embeds_disabled BOOLEAN DEFAULT FALSE,
                        hide_like_and_view_counts BOOLEAN DEFAULT FALSE,
                        
                        -- Account Settings
                        should_show_category BOOLEAN DEFAULT TRUE,
                        should_show_public_contacts BOOLEAN DEFAULT TRUE,
                        show_account_transparency_details BOOLEAN DEFAULT TRUE,
                        remove_message_entrypoint BOOLEAN DEFAULT FALSE,
                        
                        -- Viewer Relationships
                        blocked_by_viewer BOOLEAN,
                        has_blocked_viewer BOOLEAN,
                        restricted_by_viewer BOOLEAN,
                        followed_by_viewer BOOLEAN,
                        follows_viewer BOOLEAN,
                        requested_by_viewer BOOLEAN,
                        has_requested_viewer BOOLEAN,
                        
                        -- AI & Special Features
                        ai_agent_type VARCHAR(100),
                        ai_agent_owner_username VARCHAR(255),
                        transparency_label VARCHAR(255),
                        transparency_product VARCHAR(255),
                        
                        -- Supervision & Safety
                        is_supervision_enabled BOOLEAN DEFAULT FALSE,
                        is_guardian_of_viewer BOOLEAN DEFAULT FALSE,
                        is_supervised_by_viewer BOOLEAN DEFAULT FALSE,
                        is_supervised_user BOOLEAN DEFAULT FALSE,
                        guardian_id VARCHAR(50),
                        is_regulated_c18 BOOLEAN DEFAULT FALSE,
                        is_verified_by_mv4b BOOLEAN DEFAULT FALSE,
                        
                        -- Advanced Fields
                        fbid VARCHAR(50),
                        eimu_id VARCHAR(50),
                        pinned_channels_list_count INTEGER DEFAULT 0,
                        
                        -- Structured Data
                        biography_with_entities JSONB,
                        bio_links JSONB,
                        pronouns JSONB,
                        
                        -- Analytics & Metrics
                        engagement_rate FLOAT,
                        avg_likes FLOAT,
                        avg_comments FLOAT,
                        avg_engagement FLOAT,
                        content_quality_score FLOAT,
                        influence_score FLOAT,
                        data_quality_score INTEGER DEFAULT 0,
                        
                        -- Timestamps
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        
                        -- Raw data backup
                        raw_data JSONB
                    );
                """)
                
                # Create posts table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS posts_enhanced (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        profile_id UUID NOT NULL REFERENCES profiles_enhanced(id) ON DELETE CASCADE,
                        shortcode VARCHAR(50) UNIQUE NOT NULL,
                        instagram_post_id VARCHAR(50) UNIQUE,
                        
                        -- Media Information
                        media_type VARCHAR(50),
                        is_video BOOLEAN DEFAULT FALSE,
                        display_url TEXT,
                        thumbnail_src TEXT,
                        thumbnail_tall_src TEXT,
                        
                        -- Dimensions
                        width INTEGER,
                        height INTEGER,
                        
                        -- Content
                        caption TEXT,
                        accessibility_caption TEXT,
                        
                        -- Engagement Metrics
                        likes_count BIGINT DEFAULT 0,
                        comments_count BIGINT DEFAULT 0,
                        comments_disabled BOOLEAN DEFAULT FALSE,
                        
                        -- Post Settings
                        like_and_view_counts_disabled BOOLEAN DEFAULT FALSE,
                        viewer_can_reshare BOOLEAN DEFAULT TRUE,
                        has_upcoming_event BOOLEAN DEFAULT FALSE,
                        
                        -- Location
                        location_name VARCHAR(255),
                        location_id VARCHAR(50),
                        
                        -- Timestamps
                        taken_at_timestamp BIGINT,
                        posted_at TIMESTAMP WITH TIME ZONE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        
                        -- Structured Data
                        thumbnail_resources JSONB,
                        sidecar_children JSONB,
                        tagged_users JSONB,
                        coauthor_producers JSONB,
                        hashtags JSONB,
                        mentions JSONB,
                        
                        -- Raw data backup
                        raw_data JSONB
                    );
                """)
                
                # Create indexes for optimal performance
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles_enhanced(username);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_followers ON profiles_enhanced(followers_count);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_verified ON profiles_enhanced(is_verified);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_last_refreshed ON profiles_enhanced(last_refreshed);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_profile_id ON posts_enhanced(profile_id);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_shortcode ON posts_enhanced(shortcode);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts_enhanced(taken_at_timestamp);")
                
                logger.info("✅ Enhanced database schema verified/created")
                
        except Exception as e:
            logger.error(f"Failed to ensure schema exists: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Context manager for getting database connections with proper error handling
        """
        if not self.pool:
            raise Exception("Database pool not initialized")
        
        conn = None
        try:
            conn = await self.pool.acquire()
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                await self.pool.release(conn)
    
    async def store_profile_enhanced(self, username: str, raw_data: Dict[str, Any]) -> bool:
        """
        Store profile with sophisticated column allocation
        """
        try:
            # Extract and map all data points
            user_data = self._extract_user_data(raw_data)
            if not user_data:
                logger.error("Invalid Decodo response structure")
                return False
            
            # Map all 69+ datapoints to specific columns
            profile_data = self._map_decodo_to_enhanced_schema(user_data, raw_data)
            profile_data['username'] = username
            profile_data['raw_data'] = json.dumps(raw_data)
            
            async with self.get_connection() as conn:
                # Check if profile exists
                existing = await conn.fetchrow(
                    "SELECT id FROM profiles_enhanced WHERE username = $1", username
                )
                
                if existing:
                    # Update existing profile
                    set_clauses = []
                    values = []
                    param_count = 1
                    
                    for key, value in profile_data.items():
                        if key != 'username':  # Don't update username
                            set_clauses.append(f"{key} = ${param_count + 1}")
                            values.append(value)
                            param_count += 1
                    
                    set_clauses.append(f"last_refreshed = NOW()")
                    
                    query = f"""
                        UPDATE profiles_enhanced SET 
                        {', '.join(set_clauses)}
                        WHERE username = $1
                    """
                    
                    await conn.execute(query, username, *values)
                    logger.info(f"✅ Updated enhanced profile for {username}")
                    
                else:
                    # Insert new profile
                    columns = list(profile_data.keys())
                    placeholders = [f"${i+1}" for i in range(len(columns))]
                    values = list(profile_data.values())
                    
                    query = f"""
                        INSERT INTO profiles_enhanced ({', '.join(columns)}) 
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    await conn.execute(query, *values)
                    logger.info(f"✅ Created enhanced profile for {username}")
                
                # Store posts data
                await self._store_posts_enhanced(conn, username, user_data)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to store enhanced profile {username}: {e}")
            return False
    
    async def _store_posts_enhanced(self, conn, username: str, user_data: Dict[str, Any]):
        """
        Store posts with detailed media and engagement data
        """
        try:
            # Get profile ID
            profile_id = await conn.fetchval(
                "SELECT id FROM profiles_enhanced WHERE username = $1", username
            )
            
            if not profile_id:
                return
            
            # Extract posts from timeline media
            timeline_media = user_data.get('edge_owner_to_timeline_media', {})
            posts = timeline_media.get('edges', [])
            
            stored_count = 0
            for post_edge in posts:
                post_node = post_edge.get('node', {})
                shortcode = post_node.get('shortcode')
                
                if not shortcode:
                    continue
                
                # Check if post already exists
                existing_post = await conn.fetchval(
                    "SELECT id FROM posts_enhanced WHERE shortcode = $1", shortcode
                )
                
                if existing_post:
                    continue  # Skip existing posts
                
                # Map post data
                post_data = self._map_post_to_enhanced_schema(post_node, profile_id)
                
                # Insert post
                columns = list(post_data.keys())
                placeholders = [f"${i+1}" for i in range(len(columns))]
                values = list(post_data.values())
                
                query = f"""
                    INSERT INTO posts_enhanced ({', '.join(columns)}) 
                    VALUES ({', '.join(placeholders)})
                """
                
                await conn.execute(query, *values)
                stored_count += 1
            
            logger.info(f"✅ Stored {stored_count} posts for {username}")
            
        except Exception as e:
            logger.error(f"Failed to store posts for {username}: {e}")
    
    def _extract_user_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user data from Decodo response structure"""
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
    
    def _map_decodo_to_enhanced_schema(self, user_data: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map all 69+ Decodo datapoints to enhanced schema columns
        """
        def safe_get(data, path, default=None):
            try:
                result = data
                for key in path.split('.'):
                    result = result[key]
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        # Count populated fields for data quality
        profile_data = {}
        
        # Core Profile Information
        profile_data['instagram_user_id'] = safe_get(user_data, 'id', '')
        profile_data['full_name'] = safe_get(user_data, 'full_name', '')
        profile_data['biography'] = safe_get(user_data, 'biography', '')
        profile_data['external_url'] = safe_get(user_data, 'external_url', '')
        profile_data['external_url_shimmed'] = safe_get(user_data, 'external_url_linkshimmed', '')
        profile_data['profile_pic_url'] = safe_get(user_data, 'profile_pic_url', '')
        profile_data['profile_pic_url_hd'] = safe_get(user_data, 'profile_pic_url_hd', '')
        
        # Account Statistics
        profile_data['followers_count'] = safe_get(user_data, 'edge_followed_by.count', 0)
        profile_data['following_count'] = safe_get(user_data, 'edge_follow.count', 0)
        profile_data['posts_count'] = safe_get(user_data, 'edge_owner_to_timeline_media.count', 0)
        profile_data['mutual_followers_count'] = safe_get(user_data, 'edge_mutual_followed_by.count', 0)
        profile_data['highlight_reel_count'] = safe_get(user_data, 'highlight_reel_count', 0)
        
        # Account Status & Verification
        profile_data['is_verified'] = safe_get(user_data, 'is_verified', False)
        profile_data['is_private'] = safe_get(user_data, 'is_private', False)
        profile_data['is_business_account'] = safe_get(user_data, 'is_business_account', False)
        profile_data['is_professional_account'] = safe_get(user_data, 'is_professional_account', False)
        profile_data['is_joined_recently'] = safe_get(user_data, 'is_joined_recently', False)
        
        # Business Information
        profile_data['business_category_name'] = safe_get(user_data, 'business_category_name', '')
        profile_data['overall_category_name'] = safe_get(user_data, 'overall_category_name', '')
        profile_data['category_enum'] = safe_get(user_data, 'category_enum', '')
        profile_data['business_address_json'] = safe_get(user_data, 'business_address_json', '')
        profile_data['business_contact_method'] = safe_get(user_data, 'business_contact_method', '')
        profile_data['business_email'] = safe_get(user_data, 'business_email', '')
        profile_data['business_phone_number'] = safe_get(user_data, 'business_phone_number', '')
        
        # Account Features
        profile_data['has_ar_effects'] = safe_get(user_data, 'has_ar_effects', False)
        profile_data['has_clips'] = safe_get(user_data, 'has_clips', False)
        profile_data['has_guides'] = safe_get(user_data, 'has_guides', False)
        profile_data['has_channel'] = safe_get(user_data, 'has_channel', False)
        profile_data['has_onboarded_to_text_post_app'] = safe_get(user_data, 'has_onboarded_to_text_post_app', False)
        profile_data['show_text_post_app_badge'] = safe_get(user_data, 'show_text_post_app_badge', False)
        
        # Privacy & Restrictions
        profile_data['country_block'] = safe_get(user_data, 'country_block', False)
        profile_data['is_embeds_disabled'] = safe_get(user_data, 'is_embeds_disabled', False)
        profile_data['hide_like_and_view_counts'] = safe_get(user_data, 'hide_like_and_view_counts', False)
        
        # Account Settings
        profile_data['should_show_category'] = safe_get(user_data, 'should_show_category', True)
        profile_data['should_show_public_contacts'] = safe_get(user_data, 'should_show_public_contacts', True)
        profile_data['show_account_transparency_details'] = safe_get(user_data, 'show_account_transparency_details', True)
        profile_data['remove_message_entrypoint'] = safe_get(user_data, 'remove_message_entrypoint', False)
        
        # Viewer Relationships
        profile_data['blocked_by_viewer'] = safe_get(user_data, 'blocked_by_viewer')
        profile_data['has_blocked_viewer'] = safe_get(user_data, 'has_blocked_viewer')
        profile_data['restricted_by_viewer'] = safe_get(user_data, 'restricted_by_viewer')
        profile_data['followed_by_viewer'] = safe_get(user_data, 'followed_by_viewer')
        profile_data['follows_viewer'] = safe_get(user_data, 'follows_viewer')
        profile_data['requested_by_viewer'] = safe_get(user_data, 'requested_by_viewer')
        profile_data['has_requested_viewer'] = safe_get(user_data, 'has_requested_viewer')
        
        # AI & Special Features
        profile_data['ai_agent_type'] = safe_get(user_data, 'ai_agent_type', '')
        profile_data['ai_agent_owner_username'] = safe_get(user_data, 'ai_agent_owner_username', '')
        profile_data['transparency_label'] = safe_get(user_data, 'transparency_label', '')
        profile_data['transparency_product'] = safe_get(user_data, 'transparency_product', '')
        
        # Supervision & Safety
        profile_data['is_supervision_enabled'] = safe_get(user_data, 'is_supervision_enabled', False)
        profile_data['is_guardian_of_viewer'] = safe_get(user_data, 'is_guardian_of_viewer', False)
        profile_data['is_supervised_by_viewer'] = safe_get(user_data, 'is_supervised_by_viewer', False)
        profile_data['is_supervised_user'] = safe_get(user_data, 'is_supervised_user', False)
        profile_data['guardian_id'] = safe_get(user_data, 'guardian_id', '')
        profile_data['is_regulated_c18'] = safe_get(user_data, 'is_regulated_c18', False)
        profile_data['is_verified_by_mv4b'] = safe_get(user_data, 'is_verified_by_mv4b', False)
        
        # Advanced Fields
        profile_data['fbid'] = safe_get(user_data, 'fbid', '')
        profile_data['eimu_id'] = safe_get(user_data, 'eimu_id', '')
        profile_data['pinned_channels_list_count'] = safe_get(user_data, 'pinned_channels_list_count', 0)
        
        # Structured Data (keep as JSONB)
        profile_data['biography_with_entities'] = json.dumps(safe_get(user_data, 'biography_with_entities', {}))
        profile_data['bio_links'] = json.dumps(safe_get(user_data, 'bio_links', []))
        profile_data['pronouns'] = json.dumps(safe_get(user_data, 'pronouns', []))
        
        # Calculate data quality score
        total_fields = len(profile_data)
        populated_fields = sum(1 for value in profile_data.values() if value not in [None, '', [], {}, '[]', '{}'])
        profile_data['data_quality_score'] = int((populated_fields / total_fields) * 100)
        
        logger.info(f"📊 Mapped {populated_fields}/{total_fields} fields ({profile_data['data_quality_score']}% quality)")
        
        return profile_data
    
    def _map_post_to_enhanced_schema(self, post_node: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
        """
        Map post data to enhanced schema
        """
        def safe_get(data, path, default=None):
            try:
                result = data
                for key in path.split('.'):
                    result = result[key]
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        post_data = {
            'profile_id': profile_id,
            'shortcode': safe_get(post_node, 'shortcode', ''),
            'instagram_post_id': safe_get(post_node, 'id', ''),
            'media_type': safe_get(post_node, '__typename', ''),
            'is_video': safe_get(post_node, 'is_video', False),
            'display_url': safe_get(post_node, 'display_url', ''),
            'thumbnail_src': safe_get(post_node, 'thumbnail_src', ''),
            'thumbnail_tall_src': safe_get(post_node, 'thumbnail_tall_src', ''),
            'width': safe_get(post_node, 'dimensions.width'),
            'height': safe_get(post_node, 'dimensions.height'),
            'accessibility_caption': safe_get(post_node, 'accessibility_caption', ''),
            'likes_count': safe_get(post_node, 'edge_liked_by.count', 0),
            'comments_count': safe_get(post_node, 'edge_media_to_comment.count', 0),
            'comments_disabled': safe_get(post_node, 'comments_disabled', False),
            'like_and_view_counts_disabled': safe_get(post_node, 'like_and_view_counts_disabled', False),
            'viewer_can_reshare': safe_get(post_node, 'viewer_can_reshare', True),
            'has_upcoming_event': safe_get(post_node, 'has_upcoming_event', False),
            'taken_at_timestamp': safe_get(post_node, 'taken_at_timestamp'),
            'thumbnail_resources': json.dumps(safe_get(post_node, 'thumbnail_resources', [])),
            'sidecar_children': json.dumps(safe_get(post_node, 'edge_sidecar_to_children.edges', [])),
            'tagged_users': json.dumps(safe_get(post_node, 'edge_media_to_tagged_user.edges', [])),
            'coauthor_producers': json.dumps(safe_get(post_node, 'coauthor_producers', [])),
            'raw_data': json.dumps(post_node)
        }
        
        # Extract caption
        caption_edges = safe_get(post_node, 'edge_media_to_caption.edges', [])
        if caption_edges:
            post_data['caption'] = safe_get(caption_edges[0], 'node.text', '')
        
        # Extract location
        location = safe_get(post_node, 'location')
        if location:
            post_data['location_name'] = safe_get(location, 'name', '')
            post_data['location_id'] = safe_get(location, 'id', '')
        
        # Convert timestamp to datetime
        if post_data['taken_at_timestamp']:
            post_data['posted_at'] = datetime.fromtimestamp(
                post_data['taken_at_timestamp'], tz=timezone.utc
            ).isoformat()
        
        return post_data
    
    async def get_profile_enhanced(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get profile with all enhanced data
        """
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM profiles_enhanced WHERE username = $1", username
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get enhanced profile {username}: {e}")
            return None
    
    async def is_profile_fresh_enhanced(self, username: str, max_age_hours: int = 24) -> bool:
        """
        Check if profile data is fresh with robust error handling
        """
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT last_refreshed FROM profiles_enhanced 
                    WHERE username = $1 
                    AND last_refreshed > NOW() - INTERVAL '%s hours'
                """ % max_age_hours, username)
                return row is not None
        except Exception as e:
            logger.error(f"Failed to check profile freshness: {e}")
            return False
    
    async def get_recent_profiles_enhanced(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent profiles for debugging
        """
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT username, full_name, followers_count, is_verified, last_refreshed 
                    FROM profiles_enhanced 
                    ORDER BY last_refreshed DESC 
                    LIMIT $1
                """, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get recent profiles: {e}")
            return []
    
    async def get_profile_posts(self, username: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Get posts for a profile
        """
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT p.* FROM posts_enhanced p
                    JOIN profiles_enhanced pr ON p.profile_id = pr.id
                    WHERE pr.username = $1
                    ORDER BY p.taken_at_timestamp DESC
                    LIMIT $2
                """, username, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get posts for {username}: {e}")
            return []
    
    async def close(self):
        """
        Close database connection pool
        """
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

# Global instance
enhanced_db_service = EnhancedDatabaseService()