"""
Cache Integration Service - High-level caching operations for application data
Integrates with Redis cache manager to provide smart caching for analytics data
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import hashlib
import json

from app.services.redis_cache_service import redis_cache

logger = logging.getLogger(__name__)

class CacheIntegrationService:
    """
    High-level caching service that provides smart caching strategies
    for different types of application data
    """

    def __init__(self):
        self.cache_manager = redis_cache
        
    async def initialize(self) -> bool:
        """Initialize the cache integration service"""
        return await self.cache_manager.initialize()
    
    # =============================================================================
    # PROFILE CACHING
    # =============================================================================
    
    async def cache_profile_analytics(self, username: str, analytics_data: Dict[str, Any], 
                                    user_id: Optional[str] = None) -> bool:
        """Cache comprehensive profile analytics data"""
        try:
            # Generate cache identifier that includes user context if available
            cache_id = f"{username}:{user_id}" if user_id else username
            
            # Add caching metadata
            cached_data = {
                **analytics_data,
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "profile_analytics",
                    "username": username,
                    "user_context": bool(user_id)
                }
            }
            
            return await self.cache_manager.set(
                cache_type="profile_analytics",
                identifier=cache_id,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache profile analytics for {username}: {e}")
            return False
    
    async def get_cached_profile_analytics(self, username: str, 
                                         user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached profile analytics data"""
        try:
            cache_id = f"{username}:{user_id}" if user_id else username
            
            cached_data = await self.cache_manager.get(
                cache_type="profile_analytics",
                identifier=cache_id
            )
            
            if cached_data and isinstance(cached_data, dict):
                # Remove cache metadata before returning
                cached_data.pop("_cache_metadata", None)
                return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached profile analytics for {username}: {e}")
            return None
    
    async def cache_profile_basic(self, username: str, profile_data: Dict[str, Any]) -> bool:
        """Cache basic profile information (longer TTL)"""
        try:
            cached_data = {
                **profile_data,
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "profile_basic",
                    "username": username
                }
            }
            
            return await self.cache_manager.set(
                cache_type="profile_basic",
                identifier=username,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache basic profile data for {username}: {e}")
            return False
    
    async def get_cached_profile_basic(self, username: str) -> Optional[Dict[str, Any]]:
        """Get cached basic profile data"""
        try:
            cached_data = await self.cache_manager.get(
                cache_type="profile_basic",
                identifier=username
            )
            
            if cached_data and isinstance(cached_data, dict):
                cached_data.pop("_cache_metadata", None)
                return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached basic profile data for {username}: {e}")
            return None
    
    # =============================================================================
    # POSTS CACHING
    # =============================================================================
    
    async def cache_posts_data(self, username: str, posts_data: List[Dict[str, Any]], 
                             limit: int = 20, offset: int = 0) -> bool:
        """Cache posts data with pagination parameters"""
        try:
            cache_id = f"{username}:limit_{limit}:offset_{offset}"
            
            cached_data = {
                "posts": posts_data,
                "pagination": {"limit": limit, "offset": offset, "total": len(posts_data)},
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "posts_data",
                    "username": username
                }
            }
            
            return await self.cache_manager.set(
                cache_type="posts_data",
                identifier=cache_id,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache posts data for {username}: {e}")
            return False
    
    async def get_cached_posts_data(self, username: str, limit: int = 20, 
                                   offset: int = 0) -> Optional[Dict[str, Any]]:
        """Get cached posts data with pagination"""
        try:
            cache_id = f"{username}:limit_{limit}:offset_{offset}"
            
            cached_data = await self.cache_manager.get(
                cache_type="posts_data",
                identifier=cache_id
            )
            
            if cached_data and isinstance(cached_data, dict):
                cached_data.pop("_cache_metadata", None)
                return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached posts data for {username}: {e}")
            return None
    
    # =============================================================================
    # AI ANALYSIS CACHING
    # =============================================================================
    
    async def cache_ai_analysis_results(self, profile_id: str, ai_results: Dict[str, Any]) -> bool:
        """Cache AI analysis results (long TTL as AI analysis is expensive)"""
        try:
            cached_data = {
                **ai_results,
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "ai_analysis",
                    "profile_id": profile_id
                }
            }
            
            return await self.cache_manager.set(
                cache_type="ai_analysis_results",
                identifier=profile_id,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache AI analysis results for {profile_id}: {e}")
            return False
    
    async def get_cached_ai_analysis_results(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get cached AI analysis results"""
        try:
            cached_data = await self.cache_manager.get(
                cache_type="ai_analysis_results",
                identifier=profile_id
            )
            
            if cached_data and isinstance(cached_data, dict):
                cached_data.pop("_cache_metadata", None)
                return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached AI analysis results for {profile_id}: {e}")
            return None
    
    # =============================================================================
    # USER ACCESS CACHING
    # =============================================================================
    
    async def cache_user_access_data(self, user_id: str, access_data: Dict[str, Any]) -> bool:
        """Cache user access permissions and profile list"""
        try:
            cached_data = {
                **access_data,
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "user_access",
                    "user_id": user_id
                }
            }
            
            return await self.cache_manager.set(
                cache_type="user_access_cache",
                identifier=user_id,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache user access data for {user_id}: {e}")
            return False
    
    async def get_cached_user_access_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user access data"""
        try:
            cached_data = await self.cache_manager.get(
                cache_type="user_access_cache",
                identifier=user_id
            )
            
            if cached_data and isinstance(cached_data, dict):
                cached_data.pop("_cache_metadata", None)
                return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached user access data for {user_id}: {e}")
            return None
    
    # =============================================================================
    # ENGAGEMENT CALCULATIONS CACHING
    # =============================================================================
    
    async def cache_engagement_calculation(self, username: str, engagement_data: Dict[str, Any]) -> bool:
        """Cache calculated engagement metrics"""
        try:
            cached_data = {
                **engagement_data,
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "engagement",
                    "username": username
                }
            }
            
            return await self.cache_manager.set(
                cache_type="engagement_calculations",
                identifier=username,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache engagement calculation for {username}: {e}")
            return False
    
    async def get_cached_engagement_calculation(self, username: str) -> Optional[Dict[str, Any]]:
        """Get cached engagement metrics"""
        try:
            cached_data = await self.cache_manager.get(
                cache_type="engagement_calculations",
                identifier=username
            )
            
            if cached_data and isinstance(cached_data, dict):
                cached_data.pop("_cache_metadata", None)
                return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached engagement calculation for {username}: {e}")
            return None
    
    # =============================================================================
    # SEARCH RESULTS CACHING
    # =============================================================================
    
    async def cache_search_results(self, search_query: str, search_results: Dict[str, Any], 
                                 user_id: Optional[str] = None) -> bool:
        """Cache search results with user context"""
        try:
            # Create a unique cache key for the search
            search_hash = hashlib.md5(search_query.encode()).hexdigest()[:12]
            cache_id = f"{search_hash}:{user_id}" if user_id else search_hash
            
            cached_data = {
                **search_results,
                "search_query": search_query,
                "_cache_metadata": {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_type": "search_results",
                    "search_hash": search_hash,
                    "user_context": bool(user_id)
                }
            }
            
            return await self.cache_manager.set(
                cache_type="search_results",
                identifier=cache_id,
                data=cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache search results for '{search_query}': {e}")
            return False
    
    async def get_cached_search_results(self, search_query: str, 
                                       user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached search results"""
        try:
            search_hash = hashlib.md5(search_query.encode()).hexdigest()[:12]
            cache_id = f"{search_hash}:{user_id}" if user_id else search_hash
            
            cached_data = await self.cache_manager.get(
                cache_type="search_results",
                identifier=cache_id
            )
            
            if cached_data and isinstance(cached_data, dict):
                cached_data.pop("_cache_metadata", None)
                # Verify the search query matches
                if cached_data.get("search_query") == search_query:
                    return cached_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached search results for '{search_query}': {e}")
            return None
    
    # =============================================================================
    # CACHE MANAGEMENT OPERATIONS
    # =============================================================================
    
    async def invalidate_profile_cache(self, username: str) -> int:
        """Invalidate all cache entries related to a profile"""
        try:
            return await self.cache_manager.invalidate_profile_cache(username)
        except Exception as e:
            logger.error(f"Failed to invalidate profile cache for {username}: {e}")
            return 0
    
    async def warm_profile_cache(self, username: str, profile_data: Dict[str, Any], 
                               analytics_data: Dict[str, Any], posts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Warm cache with comprehensive profile data"""
        try:
            cache_items = [
                {
                    "cache_type": "profile_basic",
                    "identifier": username,
                    "data": profile_data
                },
                {
                    "cache_type": "profile_analytics",
                    "identifier": username,
                    "data": analytics_data
                },
                {
                    "cache_type": "posts_data",
                    "identifier": f"{username}:limit_20:offset_0",
                    "data": {
                        "posts": posts_data[:20],
                        "pagination": {"limit": 20, "offset": 0, "total": len(posts_data)}
                    }
                }
            ]
            
            return await self.cache_manager.warm_cache(cache_items)
            
        except Exception as e:
            logger.error(f"Failed to warm profile cache for {username}: {e}")
            return {"success": 0, "failed": 1, "errors": [str(e)]}
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            redis_stats = await self.cache_manager.get_cache_stats()
            health_check = await self.cache_manager.health_check()
            
            return {
                "cache_system": "Redis",
                "status": health_check.get("status", "unknown"),
                "redis_stats": redis_stats,
                "health_check": health_check,
                "cache_configuration": {
                    cache_type: {
                        "ttl_minutes": config["ttl_seconds"] / 60,
                        "key_prefix": config["key_prefix"]
                    }
                    for cache_type, config in self.cache_manager.CACHE_CONFIG.items()
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_expired_cache(self) -> Dict[str, Any]:
        """Clean up expired cache entries"""
        try:
            return await self.cache_manager.cleanup_expired_keys()
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return {"error": str(e)}

# Global cache integration service
cache_integration_service = CacheIntegrationService()
