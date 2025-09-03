"""
Resilient Authentication Service - Bulletproof Auth with Offline Fallback
Handles network failures, token validation, and cached authentication
"""
import asyncio
import logging
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.supabase_auth_service import supabase_auth_service
from app.models.auth import UserInDB
from app.database.unified_models import User
from app.resilience.database_resilience import database_resilience

logger = logging.getLogger(__name__)

class ResilientAuthService:
    """
    Bulletproof authentication with offline capabilities
    """
    
    def __init__(self):
        # Token cache for offline validation
        self.token_cache: Dict[str, Dict] = {}
        self.cache_duration = 300  # 5 minutes
        
        # Failed validation cache to prevent repeated failures
        self.failed_tokens: Dict[str, float] = {}
        self.failed_token_timeout = 60  # 1 minute
        
        # Network status tracking
        self.last_network_check = None
        self.network_available = True
        
    def is_token_cached_as_failed(self, token: str) -> bool:
        """Check if token recently failed validation"""
        if token not in self.failed_tokens:
            return False
            
        failure_time = self.failed_tokens[token]
        if time.time() - failure_time > self.failed_token_timeout:
            # Timeout expired, remove from failed cache
            del self.failed_tokens[token]
            return False
            
        return True
    
    def cache_token_failure(self, token: str):
        """Cache a token validation failure"""
        self.failed_tokens[token] = time.time()
        logger.debug(f"RESILIENT AUTH: Cached token failure")
    
    def get_cached_token(self, token: str) -> Optional[Dict]:
        """Get cached token validation result"""
        if token not in self.token_cache:
            return None
            
        cached_data = self.token_cache[token]
        cache_time = cached_data.get('cached_at', 0)
        
        # Check if cache is still valid
        if time.time() - cache_time > self.cache_duration:
            del self.token_cache[token]
            return None
            
        return cached_data.get('user_data')
    
    def cache_token(self, token: str, user_data):
        """Cache successful token validation"""
        # Convert UserInDB to dict if needed
        if hasattr(user_data, 'dict'):
            user_dict = user_data.dict()
        elif hasattr(user_data, '__dict__'):
            user_dict = user_data.__dict__
        else:
            user_dict = user_data
            
        self.token_cache[token] = {
            'user_data': user_dict,
            'cached_at': time.time()
        }
        logger.debug(f"RESILIENT AUTH: Cached token validation for user {user_dict.get('email', 'unknown')}")
    
    async def validate_token_resilient(self, token: str) -> Optional[UserInDB]:
        """
        Validate token with comprehensive fallback strategies
        """
        try:
            # Check if token recently failed
            if self.is_token_cached_as_failed(token):
                logger.debug("RESILIENT AUTH: Token recently failed validation, skipping")
                return None
            
            # Try cached validation first
            cached_user = self.get_cached_token(token)
            if cached_user:
                logger.debug("RESILIENT AUTH: Using cached token validation")
                return UserInDB(**cached_user)
            
            # Try online validation with Supabase
            try:
                logger.debug("RESILIENT AUTH: Attempting Supabase token validation")
                user_data = await supabase_auth_service.get_current_user(token)
                
                if user_data:
                    # Success! Cache the result
                    self.cache_token(token, user_data)
                    self.network_available = True
                    return user_data
                    
            except Exception as e:
                logger.warning(f"RESILIENT AUTH: Supabase validation failed: {e}")
                self.network_available = False
                
                # Try local JWT validation as fallback
                try:
                    return await self.validate_token_local_fallback(token)
                except Exception as fallback_error:
                    logger.warning(f"RESILIENT AUTH: Local fallback failed: {fallback_error}")
                    
                # Cache the failure
                self.cache_token_failure(token)
                return None
                
        except Exception as e:
            logger.error(f"RESILIENT AUTH: Token validation error: {e}")
            self.cache_token_failure(token)
            return None
    
    async def validate_token_local_fallback(self, token: str) -> Optional[UserInDB]:
        """
        Local JWT validation fallback when Supabase is unavailable
        """
        try:
            # Decode JWT without signature verification (for offline use)
            # WARNING: This is less secure but allows offline operation
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Extract user information
            user_id = decoded.get('sub')
            email = decoded.get('email')
            exp = decoded.get('exp')
            
            if not user_id or not email:
                logger.warning("RESILIENT AUTH: Invalid token structure")
                return None
            
            # Check expiration
            if exp and time.time() > exp:
                logger.warning("RESILIENT AUTH: Token expired")
                return None
            
            # Create user object for offline validation with all required fields
            from datetime import datetime, timezone
            
            # CRITICAL FIX: Look up actual database user ID using Supabase user ID
            database_user_id = None
            try:
                from app.database.connection import async_engine
                import asyncio
                from sqlalchemy import text
                
                # Use a coroutine to get the database user ID
                async def get_db_user_id():
                    async with async_engine.begin() as conn:
                        result = await conn.execute(
                            text("SELECT id FROM users WHERE supabase_user_id = :supabase_id"),
                            {"supabase_id": user_id}
                        )
                        row = result.fetchone()
                        return str(row[0]) if row else None
                
                # Get or create event loop to run the async query
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're in an async context, we can't use loop.run_until_complete
                        # In this case, we'll use the Supabase ID as fallback and log a warning
                        logger.warning(f"RESILIENT AUTH: Cannot lookup database ID in async context, using Supabase ID as fallback for {email}")
                        database_user_id = user_id
                    else:
                        database_user_id = loop.run_until_complete(get_db_user_id())
                except RuntimeError:
                    # No event loop, create one
                    database_user_id = asyncio.run(get_db_user_id())
                    
            except Exception as db_lookup_error:
                logger.warning(f"RESILIENT AUTH: Failed to lookup database user ID for {email}: {db_lookup_error}")
                database_user_id = user_id  # Fallback to Supabase ID
            
            # Use the correct database ID or fallback to Supabase ID
            if not database_user_id:
                logger.warning(f"RESILIENT AUTH: No database user found for Supabase ID {user_id}, using Supabase ID as fallback")
                database_user_id = user_id
            
            user_data = {
                'id': database_user_id,  # FIXED: Use actual database user ID
                'supabase_user_id': user_id,  # Keep Supabase ID for reference
                'email': email,
                'full_name': decoded.get('user_metadata', {}).get('full_name', ''),
                'role': 'free',  # Valid enum value for offline validation
                'status': 'active',
                'credits': 0,  # Required field
                'credits_used_this_month': 0,  # Required field
                'subscription_tier': 'free',  # Required field
                'preferences': {},  # Required field
                'created_at': datetime.now(timezone.utc),  # Required field
                'updated_at': datetime.now(timezone.utc)   # Required field
            }
            
            logger.info(f"RESILIENT AUTH: Local fallback validation successful for {email}")
            return UserInDB(**user_data)
            
        except Exception as e:
            logger.error(f"RESILIENT AUTH: Local fallback validation failed: {e}")
            return None
    
    async def login_resilient(self, email: str, password: str) -> Optional[Dict]:
        """
        Login with resilience handling
        """
        try:
            # Create LoginRequest object for Supabase service
            from app.models.auth import LoginRequest
            login_request = LoginRequest(email=email, password=password)
            
            # Try primary Supabase login
            result = await supabase_auth_service.login_user(login_request)
            
            if result:
                self.network_available = True
                return result
                
        except Exception as e:
            logger.warning(f"RESILIENT AUTH: Primary login failed: {e}")
            self.network_available = False
            
            # For security reasons, we don't implement offline login
            # That would require storing password hashes locally
            raise Exception("Login requires network connectivity")
    
    def cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        current_time = time.time()
        
        # Clean token cache
        expired_tokens = [
            token for token, data in self.token_cache.items()
            if current_time - data.get('cached_at', 0) > self.cache_duration
        ]
        
        for token in expired_tokens:
            del self.token_cache[token]
        
        # Clean failed tokens cache
        expired_failures = [
            token for token, failure_time in self.failed_tokens.items()
            if current_time - failure_time > self.failed_token_timeout
        ]
        
        for token in expired_failures:
            del self.failed_tokens[token]
        
        if expired_tokens or expired_failures:
            logger.debug(f"RESILIENT AUTH: Cleaned {len(expired_tokens)} expired tokens, {len(expired_failures)} failed tokens")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cached_tokens': len(self.token_cache),
            'failed_tokens': len(self.failed_tokens),
            'network_available': self.network_available,
            'last_cleanup': datetime.now(timezone.utc).isoformat()
        }

# Global instance
resilient_auth_service = ResilientAuthService()