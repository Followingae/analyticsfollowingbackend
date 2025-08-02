"""
Direct Supabase client for database operations without SQLAlchemy pooling issues
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional
from supabase import create_client, Client
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class SupabaseDirectClient:
    """Direct Supabase client for database operations"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        
    async def init(self):
        """Initialize Supabase client"""
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                logger.warning("Supabase credentials not configured")
                return False
                
            self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("SUCCESS: Direct Supabase client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            return False
    
    async def store_profile(self, username: str, raw_data: Dict[str, Any]) -> bool:
        """Store profile data directly in Supabase"""
        if not self.client:
            logger.warning("Supabase client not initialized")
            return False
            
        try:
            # Extract user data from Decodo response
            user_data = self._extract_user_data(raw_data)
            if not user_data:
                logger.error("Invalid Decodo response structure")
                return False
            
            # Map Decodo data to profile structure
            profile_data = self._map_decodo_to_profile_data(user_data, raw_data)
            profile_data['username'] = username
            profile_data['last_refreshed'] = datetime.now().isoformat()
            
            # Check if profile exists
            existing = self.client.table('profiles').select('id').eq('username', username).execute()
            
            if existing.data:
                # Update existing profile
                result = self.client.table('profiles').update(profile_data).eq('username', username).execute()
                logger.info(f"Updated profile for {username} in Supabase")
            else:
                # Insert new profile
                result = self.client.table('profiles').insert(profile_data).execute()
                logger.info(f"Created profile for {username} in Supabase")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing profile {username}: {str(e)}")
            return False
    
    async def get_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Get profile data from Supabase"""
        if not self.client:
            return None
            
        try:
            result = self.client.table('profiles').select('*').eq('username', username).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting profile {username}: {str(e)}")
            return None
    
    async def is_profile_fresh(self, username: str, max_age_hours: int = 24) -> bool:
        """Check if profile data is fresh"""
        profile = await self.get_profile(username)
        if not profile:
            return False
            
        try:
            last_refreshed = datetime.fromisoformat(profile['last_refreshed'].replace('Z', ''))
            age_hours = (datetime.now() - last_refreshed).total_seconds() / 3600
            return age_hours < max_age_hours
        except Exception as e:
            logger.error(f"Error checking profile freshness: {e}")
            return False
    
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
        """Map Decodo data to profile table structure"""
        def safe_get(data, path, default=None):
            try:
                result = data
                for key in path.split('.'):
                    result = result[key]
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        # Core profile data mapping
        profile_data = {
            'full_name': safe_get(user_data, 'full_name', ''),
            'biography': safe_get(user_data, 'biography', ''),
            'instagram_user_id': safe_get(user_data, 'id', ''),
            'fb_id': safe_get(user_data, 'fbid', ''),
            
            # Follow statistics
            'followers_count': safe_get(user_data, 'edge_followed_by.count', 0),
            'following_count': safe_get(user_data, 'edge_follow.count', 0),
            'posts_count': safe_get(user_data, 'edge_owner_to_timeline_media.count', 0),
            
            # Account status
            'is_verified': safe_get(user_data, 'is_verified', False),
            'is_private': safe_get(user_data, 'is_private', False),
            'is_business_account': safe_get(user_data, 'is_business_account', False),
            
            # Profile media
            'profile_pic_url': safe_get(user_data, 'profile_pic_url', ''),
            'profile_pic_url_hd': safe_get(user_data, 'profile_pic_url_hd', ''),
            'external_url': safe_get(user_data, 'external_url', ''),
            
            # Business info
            'business_category_name': safe_get(user_data, 'business_category_name', ''),
            'business_email': safe_get(user_data, 'business_email', ''),
            
            # Features
            'has_clips': safe_get(user_data, 'has_clips', False),
            'highlight_reel_count': safe_get(user_data, 'highlight_reel_count', 0),
            
            # Raw data backup
            'raw_data': raw_data
        }
        
        return profile_data

# Global instance
supabase_direct = SupabaseDirectClient()