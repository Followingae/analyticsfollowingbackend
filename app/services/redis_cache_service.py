"""
Redis Caching Service for Performance Optimization
Provides high-performance caching for frequently accessed data to achieve <500ms response times
"""
import json
import logging
import asyncio
from typing import Any, Dict, Optional, Union, List
from datetime import datetime, timezone, timedelta
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import pickle
import hashlib

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisCacheService:
    """High-performance Redis caching service for frequently accessed data"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self.is_connected = False
        
        # Cache TTL configurations (in seconds)
        self.ttl_configs = {
            # User session data - 24 hours
            'user_session': 86400,
            'jwt_validation': 3600,  # 1 hour for JWT validation
            
            # Dashboard data - 5 minutes (frequently updated)
            'dashboard_data': 300,
            'user_profile_data': 300,
            'team_overview': 300,
            
            # Analytics data - 10 minutes
            'system_stats': 600,
            'unlocked_profiles': 600,
            'credit_balance': 300,  # 5 minutes for credits (more dynamic)
            
            # Campaign data - 15 minutes
            'campaigns_list': 900,
            'campaign_current': 900,
            
            # Lists data - 30 minutes (less frequently changed)
            'user_lists': 1800,
            
            # Authentication data - 1 hour
            'auth_permissions': 3600,
            'team_permissions': 3600,
            
            # Static data - 24 hours
            'pricing_rules': 86400,
            'system_config': 86400
        }
    
    async def init_redis(self) -> bool:
        """Initialize Redis connection with connection pooling"""
        try:
            if self.is_connected:
                return True
                
            # Create connection pool for better performance
            self.connection_pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,  # We'll handle encoding ourselves for flexibility
                max_connections=20,     # Allow multiple concurrent connections
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await self.redis_client.ping()
            self.is_connected = True
            
            logger.info("Redis cache service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache service: {e}")
            self.is_connected = False
            return False
    
    async def close(self):
        """Close Redis connection"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            self.is_connected = False
            logger.info("Redis cache service closed")
        except Exception as e:
            logger.error(f"Error closing Redis cache service: {e}")
    
    def _get_cache_key(self, key_type: str, identifier: str, **kwargs) -> str:
        """Generate consistent cache key"""
        if kwargs:
            # Sort kwargs for consistent key generation
            kwargs_str = "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            return f"analytics:{key_type}:{identifier}:{kwargs_str}"
        return f"analytics:{key_type}:{identifier}"
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for Redis storage"""
        try:
            if isinstance(data, (dict, list, tuple)):
                return json.dumps(data, default=str).encode('utf-8')
            elif isinstance(data, (str, int, float, bool)):
                return json.dumps(data).encode('utf-8')
            else:
                # Use pickle for complex objects
                return pickle.dumps(data)
        except Exception as e:
            logger.error(f"Failed to serialize data: {e}")
            return json.dumps(str(data)).encode('utf-8')
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data from Redis"""
        try:
            # Try JSON first (most common)
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                # Fallback to pickle
                return pickle.loads(data)
            except Exception as e:
                logger.error(f"Failed to deserialize data: {e}")
                return None
    
    async def set(self, key_type: str, identifier: str, data: Any, ttl: Optional[int] = None, **kwargs) -> bool:
        """Set cached data with automatic TTL"""
        if not self.is_connected:
            if not await self.init_redis():
                return False
        
        try:
            cache_key = self._get_cache_key(key_type, identifier, **kwargs)
            serialized_data = self._serialize_data(data)
            
            # Use configured TTL or provided TTL
            cache_ttl = ttl or self.ttl_configs.get(key_type, 300)  # Default 5 minutes
            
            await self.redis_client.setex(cache_key, cache_ttl, serialized_data)
            
            logger.debug(f"Cached data: {cache_key} (TTL: {cache_ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set cache {key_type}:{identifier}: {e}")
            return False
    
    async def get(self, key_type: str, identifier: str, **kwargs) -> Optional[Any]:
        """Get cached data"""
        if not self.is_connected:
            if not await self.init_redis():
                return None
        
        try:
            cache_key = self._get_cache_key(key_type, identifier, **kwargs)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data is None:
                logger.debug(f"Cache MISS: {cache_key}")
                return None
            
            data = self._deserialize_data(cached_data)
            logger.debug(f"Cache HIT: {cache_key}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get cache {key_type}:{identifier}: {e}")
            return None
    
    async def delete(self, key_type: str, identifier: str, **kwargs) -> bool:
        """Delete cached data"""
        if not self.is_connected:
            return False
        
        try:
            cache_key = self._get_cache_key(key_type, identifier, **kwargs)
            deleted = await self.redis_client.delete(cache_key)
            
            if deleted:
                logger.debug(f"Cache DELETED: {cache_key}")
            return bool(deleted)
            
        except Exception as e:
            logger.error(f"Failed to delete cache {key_type}:{identifier}: {e}")
            return False
    
    async def exists(self, key_type: str, identifier: str, **kwargs) -> bool:
        """Check if cached data exists"""
        if not self.is_connected:
            return False
        
        try:
            cache_key = self._get_cache_key(key_type, identifier, **kwargs)
            exists = await self.redis_client.exists(cache_key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Failed to check cache existence {key_type}:{identifier}: {e}")
            return False
    
    async def get_ttl(self, key_type: str, identifier: str, **kwargs) -> int:
        """Get remaining TTL for cached data"""
        if not self.is_connected:
            return -1
        
        try:
            cache_key = self._get_cache_key(key_type, identifier, **kwargs)
            ttl = await self.redis_client.ttl(cache_key)
            return ttl
        except Exception as e:
            logger.error(f"Failed to get TTL {key_type}:{identifier}: {e}")
            return -1
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern"""
        if not self.is_connected:
            return 0
        
        try:
            keys = await self.redis_client.keys(f"analytics:{pattern}*")
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries matching pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Failed to invalidate pattern {pattern}: {e}")
            return 0
    
    # Specialized cache methods for common use cases
    
    async def cache_user_session(self, user_id: str, session_data: Dict[str, Any]) -> bool:
        """Cache user session data for fast authentication"""
        return await self.set('user_session', user_id, session_data)
    
    async def get_user_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user session data"""
        return await self.get('user_session', user_id)
    
    async def cache_jwt_validation(self, jwt_hash: str, validation_result: Dict[str, Any]) -> bool:
        """Cache JWT validation result"""
        return await self.set('jwt_validation', jwt_hash, validation_result)
    
    async def get_jwt_validation(self, jwt_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached JWT validation result"""
        return await self.get('jwt_validation', jwt_hash)
    
    async def cache_dashboard_data(self, user_id: str, dashboard_data: Dict[str, Any]) -> bool:
        """Cache dashboard data for fast loading"""
        return await self.set('dashboard_data', user_id, dashboard_data)
    
    async def get_dashboard_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached dashboard data"""
        return await self.get('dashboard_data', user_id)
    
    async def cache_unlocked_profiles(self, user_id: str, page: int, page_size: int, profiles_data: Dict[str, Any]) -> bool:
        """Cache unlocked profiles data"""
        return await self.set('unlocked_profiles', user_id, profiles_data, page=page, page_size=page_size)
    
    async def get_unlocked_profiles(self, user_id: str, page: int, page_size: int) -> Optional[Dict[str, Any]]:
        """Get cached unlocked profiles data"""
        return await self.get('unlocked_profiles', user_id, page=page, page_size=page_size)
    
    async def invalidate_user_data(self, user_id: str) -> int:
        """Invalidate all cached data for a user"""
        patterns_to_invalidate = [
            f"user_session:{user_id}",
            f"dashboard_data:{user_id}",
            f"unlocked_profiles:{user_id}",
            f"credit_balance:{user_id}",
            f"user_profile_data:{user_id}"
        ]
        
        total_deleted = 0
        for pattern in patterns_to_invalidate:
            deleted = await self.invalidate_pattern(pattern.replace(':', ':'))
            total_deleted += deleted
        
        return total_deleted
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        if not self.is_connected:
            return {"connected": False}
        
        try:
            info = await self.redis_client.info()
            return {
                "connected": True,
                "used_memory_human": info.get('used_memory_human', 'Unknown'),
                "connected_clients": info.get('connected_clients', 0),
                "total_commands_processed": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "hit_rate": round((info.get('keyspace_hits', 0) / max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1)) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"connected": False, "error": str(e)}

# Global cache service instance
redis_cache = RedisCacheService()

# Cache decorator for automatic caching
def cache_result(key_type: str, ttl: Optional[int] = None):
    """Decorator to automatically cache function results"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            if args and hasattr(args[0], '__dict__') and hasattr(args[0], 'id'):
                # Method call with user/entity ID
                identifier = getattr(args[0], 'id', str(args[0]))
            elif args:
                identifier = str(args[0])
            else:
                identifier = 'default'
            
            # Try to get from cache first
            cached_result = await redis_cache.get(key_type, str(identifier), **kwargs)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await redis_cache.set(key_type, str(identifier), result, ttl, **kwargs)
            
            return result
        return wrapper
    return decorator