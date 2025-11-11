"""
Redis Cache Manager - Compatibility Wrapper
This module provides backward compatibility by wrapping the redis_cache_service
"""
from app.services.redis_cache_service import redis_cache

# Create cache_manager alias with initialized property
class CacheManagerWrapper:
    """Wrapper to provide compatibility with existing code"""

    def __init__(self, redis_service):
        self._redis_service = redis_service

    @property
    def initialized(self) -> bool:
        """Check if Redis is initialized and connected"""
        return self._redis_service.is_connected

    @property
    def redis_client(self):
        """Access to Redis client"""
        return self._redis_service.redis_client

    async def init_redis(self):
        """Initialize Redis connection"""
        return await self._redis_service.init_redis()

    async def close(self):
        """Close Redis connection"""
        await self._redis_service.close()

# Create singleton cache_manager instance
cache_manager = CacheManagerWrapper(redis_cache)
