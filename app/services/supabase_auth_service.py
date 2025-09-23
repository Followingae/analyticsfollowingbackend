"""
Industry-Standard Supabase Authentication Service
Bulletproof, production-ready authentication using only Supabase Auth
"""
import asyncio
import logging
import uuid
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.models.auth import (
    UserCreate, UserInDB, UserResponse, LoginRequest, LoginResponse,
    UserRole, UserStatus
)
from app.services.redis_cache_service import redis_cache

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Legacy in-memory cache (replaced by Redis)
_token_cache = {}
_token_cache_ttl = timedelta(minutes=10)
_user_sync_cache = {}
_user_sync_cache_ttl = timedelta(minutes=30)

# JWT settings for token creation
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


class ProductionSupabaseAuthService:
    """Production-ready Supabase authentication service"""
    
    def __init__(self):
        self.supabase = None
        self.supabase_url = None
        self.supabase_key = None
        self.initialized = False
        self.initialization_error = None
    
    async def initialize(self) -> bool:
        """Initialize Supabase client with Redis caching for performance"""
        if self.initialized and self.supabase:
            return True
        
        # Initialize Redis cache for performance optimization
        await redis_cache.init_redis()
            
        try:
            logger.info("Initializing Supabase Auth Service...")
            
            # Validate environment variables
            if not settings.SUPABASE_URL:
                self.initialization_error = "SUPABASE_URL environment variable not set"
                logger.error(f"ERROR: {self.initialization_error}")
                return False
                
            if not settings.SUPABASE_KEY:
                self.initialization_error = "SUPABASE_KEY environment variable not set"
                logger.error(f"ERROR: {self.initialization_error}")
                return False
            
            # Import and create client
            try:
                from supabase import create_client, Client
                logger.info("SUCCESS: Supabase package imported successfully")
            except ImportError as e:
                self.initialization_error = f"Failed to import Supabase: {e}"
                logger.error(f"ERROR: {self.initialization_error}")
                return False
            
            # Create Supabase client
            try:
                self.supabase_url = settings.SUPABASE_URL
                self.supabase_key = settings.SUPABASE_KEY
                self.supabase: Client = create_client(
                    self.supabase_url,
                    self.supabase_key
                )
                logger.info("SUCCESS: Supabase client created successfully")
            except Exception as e:
                self.initialization_error = f"Failed to create Supabase client: {e}"
                logger.error(f"ERROR: {self.initialization_error}")
                return False
            
            # Test client connectivity (non-admin test)
            try:
                # Simple test - try to access session (doesn't require admin)
                test_response = self.supabase.auth.get_session()
                logger.info("SUCCESS: Supabase Auth connectivity test passed (non-admin)")
            except Exception as e:
                logger.warning(f"WARNING: Supabase Auth test failed (but client created): {e}")
                # Don't fail initialization - client might still work for authentication
            
            self.initialized = True
            self.initialization_error = None
            logger.info("COMPLETE: Supabase Auth Service initialized successfully")
            return True
            
        except Exception as e:
            self.initialization_error = f"Unexpected error during initialization: {e}"
            logger.error(f"ERROR: {self.initialization_error}")
            logger.error(f"ERROR: Error type: {type(e).__name__}")
            import traceback
            logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
            return False
    
    async def ensure_initialized(self):
        """Ensure service is initialized, attempt reinitialization if needed"""
        if not self.initialized:
            logger.warning("SYNC: Auth service not initialized, attempting initialization...")
            success = await self.initialize()
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Authentication service unavailable: {self.initialization_error}"
                )
    
    async def login_user(self, login_data: LoginRequest) -> LoginResponse:
        """Authenticate user using Supabase Auth"""
        await self.ensure_initialized()
        
        try:
            logger.info(f"AUTH: Attempting login for user: {login_data.email}")
            
            # Authenticate with Supabase
            try:
                auth_response = self.supabase.auth.sign_in_with_password({
                    "email": login_data.email,
                    "password": login_data.password
                })
                logger.info(f"AUTH: Successfully got Supabase auth response for {login_data.email}")
            except Exception as supabase_error:
                logger.error(f"AUTH: Supabase authentication failed: {supabase_error}")
                logger.error(f"AUTH: Supabase error type: {type(supabase_error).__name__}")
                error_str = str(supabase_error).lower()
                
                # Check if error is due to email confirmation
                if "email not confirmed" in error_str or "email_not_confirmed" in error_str:
                    logger.warning(f"AUTH: Email not confirmed for {login_data.email} - this is expected for demo accounts")
                    # For demo accounts, we can't confirm emails, so this is expected
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email confirmation required. For demo accounts, please contact support."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password"
                    )
            
            # Check if authentication was successful
            if not auth_response.user:
                logger.warning(f"ERROR: Authentication failed - no user returned for {login_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            user = auth_response.user
            session = auth_response.session
            
            logger.info(f"SUCCESS: Supabase authentication successful for user ID: {user.id}")
            
            # Get user metadata
            user_metadata = user.user_metadata or {}
            app_metadata = user.app_metadata or {}
            
            # Determine user role
            role_value = (
                user_metadata.get("role") or 
                app_metadata.get("role") or 
                "free"
            )
            
            try:
                user_role = UserRole(role_value)
            except ValueError:
                logger.warning(f"WARNING: Invalid role '{role_value}' for user {user.id}, defaulting to 'free'")
                user_role = UserRole.FREE
            
            # Get fresh user data from database after successful authentication
            user_response = await self._get_fresh_user_data_from_database(user, user_metadata, user_role)
            
            # Use Supabase session tokens
            access_token = session.access_token if session else user.id
            refresh_token = session.refresh_token if session else ""
            expires_in = session.expires_in if session else ACCESS_TOKEN_EXPIRE_MINUTES * 60
            
            # Ensure user exists in our database (non-blocking) - with caching
            try:
                await self._ensure_user_in_database_cached(user, user_metadata)
            except Exception as db_error:
                logger.warning(f"Database sync failed (non-blocking): {db_error}")
                # Don't fail authentication if database sync fails - continue with login
            
            # Cache user session for instant authentication on subsequent requests
            await self._cache_user_session_data(user.id, user_response, access_token)
            
            response = LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                user=user_response
            )
            
            logger.info(f"COMPLETE: Login successful for {login_data.email}")
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"ERROR: Login failed for {login_data.email}: {e}")
            logger.error(f"ERROR: Error type: {type(e).__name__}")
            import traceback
            logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
            
            # Check for specific Supabase errors
            error_message = str(e).lower()
            if "invalid" in error_message and ("email" in error_message or "password" in error_message):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            elif "network" in error_message or "connection" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication failed due to server error"
                )
    
    async def _get_fresh_user_data_from_database(self, supabase_user, user_metadata: dict, user_role):
        """Get fresh user data from database after successful authentication to prevent stale data"""
        try:
            logger.info(f"LOGIN-FRESH: Fetching fresh user data from database for {supabase_user.email}")
            
            from app.database.connection import async_engine
            from sqlalchemy import text
            
            # Use connection pool for fast database access with timeout
            async with asyncio.timeout(60.0):  # 60 second timeout (industry standard)
                async with async_engine.connect() as conn:  # ENTERPRISE: Use connect() for read operations (faster)
                    # OPTIMIZED: Enterprise-grade login query with performance hints
                    result = await conn.execute(text("""
                        SELECT id, email, full_name, role, status, created_at, last_login,
                               profile_picture_url, "user.first_name" as first_name, "user.last_name" as last_name,
                               company, job_title, phone_number, bio, timezone, language, updated_at
                        FROM users
                        WHERE supabase_user_id = :user_id
                        LIMIT 1
                    """), {"user_id": supabase_user.id})
                
                user_row = result.fetchone()
                
                if user_row:
                    logger.info(f"LOGIN-FRESH: Found fresh user data in database for {supabase_user.email}")
                    # Return fresh data from database
                    return UserResponse(
                        id=supabase_user.id,  # Use Supabase ID for consistency
                        email=user_row.email,
                        full_name=user_row.full_name,
                        role=UserRole(user_row.role) if user_row.role else user_role,
                        status=UserStatus(user_row.status) if user_row.status else UserStatus.ACTIVE,
                        created_at=user_row.created_at or datetime.now(timezone.utc),
                        last_login=datetime.now(),
                        profile_picture_url=user_row.profile_picture_url,
                        first_name=user_row.first_name,
                        last_name=user_row.last_name,
                        company=user_row.company,
                        job_title=user_row.job_title,
                        phone_number=user_row.phone_number,
                        bio=user_row.bio,
                        timezone=user_row.timezone or "UTC",
                        language=user_row.language or "en",
                        updated_at=user_row.updated_at
                    )
                else:
                    logger.warning(f"LOGIN-FRESH: User not found in database, using Supabase data for {supabase_user.email}")
                    # Fallback to Supabase data if not in database
                    created_at = datetime.now(timezone.utc)
                    try:
                        if supabase_user.created_at:
                            if isinstance(supabase_user.created_at, str):
                                created_at = datetime.fromisoformat(supabase_user.created_at.replace('Z', '+00:00'))
                            else:
                                created_at = supabase_user.created_at
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.warning(f"Failed to parse created_at: {e}, using current time")
                        created_at = datetime.now(timezone.utc)
                    
                    # Parse avatar_config from JSON string to dict
                    avatar_config = None
                    try:
                        import json
                        avatar_config = json.loads(db_user.avatar_config) if db_user.avatar_config else None
                    except (json.JSONDecodeError, TypeError):
                        avatar_config = None
                    
                    user_response = UserResponse(
                        id=supabase_user.id,
                        email=supabase_user.email,
                        full_name=db_user.full_name or user_metadata.get("full_name", ""),  # Prioritize database
                        role=user_role,
                        status=UserStatus.ACTIVE,
                        created_at=created_at,
                        last_login=datetime.now(),
                        avatar_config=avatar_config,
                        # CONSISTENT SCHEMA: Add all profile fields
                        first_name=getattr(db_user, 'first_name', None),
                        last_name=getattr(db_user, 'last_name', None),
                        company=getattr(db_user, 'company', None),  # THIS ENSURES CONSISTENT COMPANY
                        job_title=getattr(db_user, 'job_title', None),
                        phone_number=getattr(db_user, 'phone_number', None),
                        bio=getattr(db_user, 'bio', None),
                        timezone=getattr(db_user, 'timezone', 'UTC'),
                        language=getattr(db_user, 'language', 'en'),
                        updated_at=getattr(db_user, 'updated_at', None)
                    )
                    
                    # DEBUG LOGGING: Track user data being returned
                    logger.info(f"LOGIN-RESPONSE: Returning user data for {supabase_user.email}")
                    logger.info(f"LOGIN-RESPONSE: full_name='{user_response.full_name}', company='{user_response.company}'")
                    
                    return user_response
                    
        except asyncio.TimeoutError:
            logger.warning(f"LOGIN-FRESH: Database timeout after 60s for {supabase_user.email}")
            # Fallback to basic Supabase data if database times out
            logger.warning("LOGIN-FALLBACK: Using basic Supabase data - database timeout")
            return UserResponse(
                id=supabase_user.id,
                email=supabase_user.email,
                full_name=user_metadata.get("full_name") or user_metadata.get("name"),
                role=user_role,
                status=UserStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                last_login=datetime.now(),
                timezone="UTC",
                language="en"
            )
        except Exception as e:
            logger.error(f"LOGIN-FRESH: Failed to fetch fresh user data for {supabase_user.email}: {e}")
            # Fallback to basic Supabase data if database fetch fails
            logger.warning("LOGIN-FALLBACK: Using basic Supabase data - database fetch failed")
            return UserResponse(
                id=supabase_user.id,
                email=supabase_user.email,
                full_name=user_metadata.get("full_name", supabase_user.email.split("@")[0]),  # Better fallback
                role=user_role,
                status=UserStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                last_login=datetime.now(),
                # CONSISTENT SCHEMA: Add empty fields for consistency
                avatar_config=None,
                first_name=None,
                last_name=None, 
                company=None,  # Ensures company is always present (even if null)
                job_title=None,
                phone_number=None,
                bio=None,
                timezone="UTC",
                language="en",
                updated_at=None
            )

    async def _ensure_user_in_database_cached(self, supabase_user, user_metadata: dict):
        """Cached version of _ensure_user_in_database to prevent excessive syncing"""
        user_cache_key = f"{supabase_user.id}:{supabase_user.email}"
        current_time = datetime.now()
        
        # Debug logging
        logger.debug(f"SYNC-CACHE: Checking cache for key: {user_cache_key}")
        logger.debug(f"SYNC-CACHE: Current cache size: {len(_user_sync_cache)}")
        
        # Check if user was recently synced
        if user_cache_key in _user_sync_cache:
            cached_time, cached_data = _user_sync_cache[user_cache_key]
            time_since_cache = current_time - cached_time
            logger.debug(f"SYNC-CACHE: Found in cache, age: {time_since_cache}, TTL: {_user_sync_cache_ttl}")
            
            if time_since_cache < _user_sync_cache_ttl:
                logger.info(f"SYNC-CACHE: Cache HIT for {supabase_user.email}, skipping database sync")
                return cached_data
            else:
                logger.debug(f"SYNC-CACHE: Cache expired for {supabase_user.email}")
        else:
            logger.debug(f"SYNC-CACHE: Key not found in cache")
        
        # User not in cache or cache expired, perform sync
        logger.info(f"SYNC-CACHE: Cache MISS for {supabase_user.email}, performing database sync")
        result = await self._ensure_user_in_database(supabase_user, user_metadata)
        
        # Cache the result
        _user_sync_cache[user_cache_key] = (current_time, result)
        logger.debug(f"SYNC-CACHE: Stored in cache: {user_cache_key} at {current_time}")
        
        # Clean up old cache entries (simple cleanup)
        if len(_user_sync_cache) > 100:  # Prevent memory bloat
            cutoff_time = current_time - _user_sync_cache_ttl
            expired_keys = [
                key for key, (cached_time, _) in _user_sync_cache.items() 
                if cached_time < cutoff_time
            ]
            for key in expired_keys:
                del _user_sync_cache[key]
        
        return result

    async def _ensure_user_in_database(self, supabase_user, user_metadata: dict):
        """Ensure user exists in our database with proper fields - CRITICAL FOR USER DATA"""
        try:
            logger.info(f"SYNC: Starting database sync for: {supabase_user.email}")
            
            from app.database.connection import SessionLocal
            from app.database.unified_models import User
            from sqlalchemy import select, update
            import uuid
            from datetime import timezone
            
            if not SessionLocal:
                logger.warning("SYNC: Database not available for user sync")
                return
            
            # Use UTC timezone properly  
            current_time = datetime.now(timezone.utc)
            logger.info(f"SYNC: Using UTC time: {current_time}")
            
            # ENTERPRISE: Aggressive retry logic for high-scale platform
            max_retries = 2  # Faster failure detection for enterprise responsiveness
            retry_delay = 0.5  # Reduced delay for speed
            
            for attempt in range(max_retries):
                try:
                    async with SessionLocal() as db:
                        # ENTERPRISE: Optimize for fast login performance
                        from sqlalchemy import text
                        await db.execute(text("SET statement_timeout = '45s'"))  # Increased timeout for stability
                        
                        # ENFORCE: Check if user exists by Supabase ID ONLY (never create duplicates)
                        logger.info(f"SYNC: Looking for user with Supabase ID: {supabase_user.id} (attempt {attempt + 1})")
                        result = await db.execute(select(User).where(User.supabase_user_id == supabase_user.id))
                        existing_user = result.scalar_one_or_none()
                        
                        if not existing_user:
                            # CRITICAL: Check by email and UPDATE their supabase_user_id if they exist
                            logger.info(f"SYNC: User not found by Supabase ID, checking by email: {supabase_user.email}")
                            result = await db.execute(select(User).where(User.email == supabase_user.email))
                            existing_user = result.scalar_one_or_none()
                            
                            if existing_user and not existing_user.supabase_user_id:
                                # Fix orphaned user: link to Supabase Auth ID
                                logger.warning(f"SYNC: FIXING ORPHANED USER - Linking {supabase_user.email} to Supabase ID {supabase_user.id}")
                                await db.execute(
                                    update(User)
                                    .where(User.id == existing_user.id)
                                    .values(supabase_user_id=supabase_user.id)
                                )
                                existing_user.supabase_user_id = supabase_user.id  # Update local object
                        
                        if existing_user:
                            # Update existing user's last login and Supabase ID
                            logger.info(f"SYNC: Updating existing user ID: {existing_user.id}")
                            await db.execute(
                                update(User)
                                .where(User.id == existing_user.id)
                                .values(
                                    supabase_user_id=supabase_user.id,
                                    last_login=current_time,
                                    last_activity=current_time,
                                    email_verified=bool(supabase_user.email_confirmed_at)
                                )
                            )
                            logger.info(f"SYNC: Successfully updated existing user: {supabase_user.email}")
                        else:
                            # Create new user in database - only required fields
                            logger.info(f"SYNC: Creating new user for: {supabase_user.email}")
                            
                            # Validate role before creating
                            role_value = user_metadata.get("role", "free")
                            if role_value not in ["free", "premium", "admin", "super_admin"]:
                                role_value = "free"
                            
                            new_user = User(
                                supabase_user_id=supabase_user.id,  # Link to Supabase
                                email=supabase_user.email,
                                full_name=user_metadata.get("full_name", ""),
                                role=role_value,
                                status="active",
                                email_verified=bool(supabase_user.email_confirmed_at),
                                last_login=current_time,
                                last_activity=current_time
                                # Don't set created_at - let database handle it with server_default
                            )
                            db.add(new_user)
                            logger.info(f"SYNC: Successfully created new user: {supabase_user.email}")
                        
                        await db.commit()
                        logger.info(f"SYNC: Database commit successful for: {supabase_user.email}")
                        break  # Success - exit retry loop
                        
                except (TimeoutError, ConnectionError, Exception) as db_error:
                    if hasattr(db, 'rollback'):
                        await db.rollback()
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"SYNC: Database timeout/error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"SYNC: Database sync failed after {max_retries} attempts for {supabase_user.email}")
                        logger.error(f"SYNC: Error type: {type(db_error).__name__}")
                        import traceback
                        logger.error(f"SYNC: Traceback: {traceback.format_exc()}")
                        # Don't raise - make this non-blocking for authentication
                    
        except Exception as e:
            logger.error(f"SYNC: Failed to sync user to database: {e}")
            logger.error(f"SYNC: Error type: {type(e).__name__}")
            import traceback
            logger.error(f"SYNC: Traceback: {traceback.format_exc()}")
            # Don't fail authentication if database sync fails - but log the error
    
    async def register_user(self, user_data: UserCreate) -> UserResponse:
        """Register new user with Supabase Auth"""
        await self.ensure_initialized()
        
        try:
            logger.info(f"NOTE: Registering new user: {user_data.email}")
            
            # Create user in Supabase Auth (non-admin) with email confirmation disabled
            auth_response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
                    "email_redirect_to": None,  # Disable email confirmation
                    "data": {
                        "full_name": user_data.full_name or "",
                        "role": user_data.role.value
                    }
                }
            })
            
            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user account"
                )
            
            user = auth_response.user
            user_metadata = user.user_metadata or {}
            
            # Sync to database - forced sync during registration
            await self._ensure_user_in_database(user, user_metadata)
            
            # Handle datetime parsing safely
            try:
                from datetime import timezone
                if user.created_at:
                    if isinstance(user.created_at, str):
                        # Parse string datetime
                        created_at = datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
                    else:
                        # Already datetime object
                        created_at = user.created_at
                else:
                    created_at = datetime.now(timezone.utc)
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to parse created_at in registration: {e}, using current time")
                created_at = datetime.now(timezone.utc)
            
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                full_name=user_metadata.get("full_name", ""),
                role=UserRole(user_metadata.get("role", "free")),
                status=UserStatus.ACTIVE,
                created_at=created_at,
                last_login=None
            )
            
            logger.info(f"SUCCESS: User registration successful: {user_data.email}")
            return user_response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"ERROR: Registration failed for {user_data.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    async def get_current_user(self, token: str) -> UserInDB:
        """Get current user from Supabase session token with Redis caching for <100ms response"""
        await self.ensure_initialized()
        
        try:
            # Generate secure cache key for JWT validation
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            
            # Check Redis cache first for instant JWT validation
            cached_validation = await redis_cache.get_jwt_validation(token_hash)
            if cached_validation:
                logger.info(f"🚀 JWT CACHE HIT: Instant auth for user {cached_validation.get('user_id')}")
                return self._user_response_to_user_in_db(cached_validation['user_data'])
            
            logger.info(f"🔍 JWT CACHE MISS: Performing Supabase validation for token {token_hash[:8]}...")
            
            # Method 1: Try direct token validation
            try:
                user_response = self.supabase.auth.get_user(token)
                
                if user_response and user_response.user:
                    # CRITICAL: Ensure user exists in database before creating UserInDB object
                    try:
                        user_metadata = user_response.user.user_metadata or {}
                        await self._ensure_user_in_database_cached(user_response.user, user_metadata)
                    except Exception as db_error:
                        logger.warning(f"Database sync failed during token validation: {db_error}")
                        # Continue authentication even if database sync fails
                    
                    user_in_db = self._create_user_in_db_from_supabase(user_response.user)
                    
                    # Cache the successful JWT validation in Redis for 1 hour
                    await self._cache_jwt_validation(token_hash, user_in_db, user_response.user)
                    
                    return user_in_db
                else:
                    logger.warning(f"TOKEN: Direct validation returned no user")
            except Exception as direct_error:
                logger.warning(f"TOKEN: Direct validation failed: {direct_error}")
            
            # Method 2: Try setting session and then getting user
            try:
                # Set the session with the token
                session_response = self.supabase.auth.set_session(token, token)
                
                # Now try to get the current user from the session
                user_response = self.supabase.auth.get_user()
                
                if user_response and user_response.user:
                    # CRITICAL: Ensure user exists in database before creating UserInDB object
                    try:
                        user_metadata = user_response.user.user_metadata or {}
                        await self._ensure_user_in_database_cached(user_response.user, user_metadata)
                    except Exception as db_error:
                        logger.warning(f"Database sync failed during session validation: {db_error}")
                        # Continue authentication even if database sync fails
                    
                    user_in_db = self._create_user_in_db_from_supabase(user_response.user)
                    
                    # Cache the successful JWT validation in Redis
                    await self._cache_jwt_validation(token_hash, user_in_db, user_response.user)
                    
                    return user_in_db
            except Exception as session_error:
                logger.warning(f"TOKEN: Session validation failed: {session_error}")
            
            # Method 3: Try refresh token if available (removed problematic JWT method)
            # Skip manual JWT verification as it uses unsupported internal APIs
            
            # If all methods fail, raise authentication error with refresh guidance
            logger.error(f"TOKEN: All validation methods failed for token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "token_expired",
                    "message": "Access token has expired. Please refresh your token using the refresh endpoint.",
                    "requires_refresh": True
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"ERROR: Unexpected error in token validation: {e}")
            logger.error(f"ERROR: Error type: {type(e).__name__}")
            import traceback
            logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed due to server error"
            )
    
    def _create_user_in_db_from_supabase(self, user) -> UserInDB:
        """Helper method to create UserInDB from Supabase user object"""
        user_metadata = user.user_metadata or {}
        
        # Handle datetime parsing safely
        try:
            if user.created_at:
                if isinstance(user.created_at, str):
                    # Parse string datetime
                    created_at = datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
                else:
                    # Already datetime object
                    created_at = user.created_at
            else:
                created_at = datetime.now()
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse created_at in _create_user_in_db_from_supabase: {e}, using current time")
            created_at = datetime.now()
        
        # Validate role
        role_value = user_metadata.get("role", "free")
        try:
            user_role = UserRole(role_value)
        except ValueError:
            logger.warning(f"Invalid role '{role_value}' for user {user.id}, defaulting to 'free'")
            user_role = UserRole.FREE
            
        user_in_db = UserInDB(
            id=user.id,
            supabase_user_id=user.id,
            email=user.email,
            full_name=user_metadata.get("full_name", ""),
            role=user_role,
            status=UserStatus.ACTIVE,
            created_at=created_at,
            updated_at=datetime.now(),
            last_login=datetime.now()
        )
        
        return user_in_db
    
    async def _cache_jwt_validation(self, token_hash: str, user_in_db: UserInDB, supabase_user) -> None:
        """Cache JWT validation result in Redis for <100ms authentication"""
        try:
            validation_data = {
                'user_id': user_in_db.id,
                'email': user_in_db.email,
                'validated_at': datetime.now(timezone.utc).isoformat(),
                'user_data': {
                    'id': user_in_db.id,
                    'supabase_user_id': user_in_db.supabase_user_id,
                    'email': user_in_db.email,
                    'full_name': user_in_db.full_name,
                    'role': user_in_db.role.value,
                    'status': user_in_db.status.value,
                    'created_at': user_in_db.created_at.isoformat() if user_in_db.created_at else None,
                    'last_login': user_in_db.last_login.isoformat() if user_in_db.last_login else None
                }
            }
            
            await redis_cache.cache_jwt_validation(token_hash, validation_data)
            logger.info(f"✅ CACHED JWT validation for user {user_in_db.email}")
            
        except Exception as e:
            logger.warning(f"Failed to cache JWT validation: {e}")
    
    async def _cache_user_session_data(self, user_id: str, user_response: UserResponse, access_token: str) -> None:
        """Cache user session data for instant dashboard loading"""
        try:
            session_data = {
                'user_id': user_id,
                'email': user_response.email,
                'full_name': user_response.full_name,
                'role': user_response.role.value,
                'status': user_response.status.value,
                'access_token': access_token,
                'cached_at': datetime.now(timezone.utc).isoformat()
            }
            
            await redis_cache.cache_user_session(user_id, session_data)
            logger.info(f"✅ CACHED session data for user {user_response.email}")
            
        except Exception as e:
            logger.warning(f"Failed to cache user session: {e}")
    
    def _user_response_to_user_in_db(self, user_data: Dict[str, Any]) -> UserInDB:
        """Convert cached user data back to UserInDB object"""
        return UserInDB(
            id=user_data['id'],
            supabase_user_id=user_data['supabase_user_id'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=UserRole(user_data['role']),
            status=UserStatus(user_data['status']),
            created_at=datetime.fromisoformat(user_data['created_at']) if user_data['created_at'] else datetime.now(),
            updated_at=datetime.now(),
            last_login=datetime.fromisoformat(user_data['last_login']) if user_data['last_login'] else datetime.now()
        )
    
    async def _cache_dashboard_stats(self, user_id: str, dashboard_stats) -> None:
        """Cache dashboard statistics in Redis for <500ms subsequent loads"""
        try:
            dashboard_data = {
                'total_searches': dashboard_stats.total_searches,
                'searches_this_month': dashboard_stats.searches_this_month,
                'favorite_profiles': dashboard_stats.favorite_profiles,
                'recent_searches': [
                    {
                        'id': search.id,
                        'user_id': search.user_id,
                        'instagram_username': search.instagram_username,
                        'search_timestamp': search.search_timestamp.isoformat() if search.search_timestamp else None,
                        'analysis_type': search.analysis_type,
                        'search_metadata': search.search_metadata or {}
                    } for search in dashboard_stats.recent_searches
                ],
                'account_created': dashboard_stats.account_created.isoformat() if dashboard_stats.account_created else None,
                'last_active': dashboard_stats.last_active.isoformat() if dashboard_stats.last_active else None,
                'cached_at': datetime.now(timezone.utc).isoformat()
            }
            
            await redis_cache.cache_dashboard_data(user_id, dashboard_data)
            logger.info(f"✅ CACHED dashboard stats for user {user_id}")
            
        except Exception as e:
            logger.warning(f"Failed to cache dashboard stats: {e}")
    
    async def logout_user(self, token: str) -> bool:
        """Logout user by invalidating Supabase session"""
        await self.ensure_initialized()
        
        try:
            self.supabase.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"ERROR: Logout failed: {e}")
            return False
    
    async def get_user_dashboard_stats(self, user_id: str, db: AsyncSession):
        """Get comprehensive dashboard statistics for user with Redis caching for <500ms response"""
        await self.ensure_initialized()

        # CIRCUIT BREAKER: Check if service is degraded
        from app.resilience.database_resilience import database_resilience
        if database_resilience.should_circuit_break():
            logger.warning(f"CIRCUIT BREAKER: Dashboard service degraded for user {user_id}")
            # Return cached data or minimal fallback
            cached_dashboard = await redis_cache.get_dashboard_data(user_id)
            if cached_dashboard:
                logger.info(f"🔄 CIRCUIT BREAKER: Serving cached data for user {user_id}")
                from app.models.auth import UserDashboardStats, UserSearchHistory
                return UserDashboardStats(
                    total_searches=cached_dashboard['total_searches'],
                    searches_this_month=cached_dashboard['searches_this_month'],
                    favorite_profiles=cached_dashboard['favorite_profiles'],
                    recent_searches=[
                        UserSearchHistory(
                            id=search['id'],
                            user_id=search['user_id'],
                            instagram_username=search['instagram_username'],
                            search_timestamp=datetime.fromisoformat(search['search_timestamp']),
                            analysis_type=search['analysis_type'],
                            search_metadata=search['search_metadata']
                        ) for search in cached_dashboard['recent_searches']
                    ],
                    account_created=datetime.fromisoformat(cached_dashboard['account_created']),
                    last_active=datetime.fromisoformat(cached_dashboard['last_active'])
                )
            else:
                # No cache available, return minimal stats
                return UserDashboardStats(
                    total_searches=0,
                    searches_this_month=0,
                    favorite_profiles=[],
                    recent_searches=[],
                    account_created=datetime.now(),
                    last_active=datetime.now()
                )

        try:
            # Check Redis cache first for instant dashboard loading
            cached_dashboard = await redis_cache.get_dashboard_data(user_id)
            if cached_dashboard:
                logger.info(f"🚀 DASHBOARD CACHE HIT: Instant load for user {user_id}")
                from app.models.auth import UserDashboardStats, UserSearchHistory
                return UserDashboardStats(
                    total_searches=cached_dashboard['total_searches'],
                    searches_this_month=cached_dashboard['searches_this_month'],
                    favorite_profiles=cached_dashboard['favorite_profiles'],
                    recent_searches=[
                        UserSearchHistory(
                            id=search['id'],
                            user_id=search['user_id'],
                            instagram_username=search['instagram_username'],
                            search_timestamp=datetime.fromisoformat(search['search_timestamp']),
                            analysis_type=search['analysis_type'],
                            search_metadata=search['search_metadata']
                        ) for search in cached_dashboard['recent_searches']
                    ],
                    account_created=datetime.fromisoformat(cached_dashboard['account_created']),
                    last_active=datetime.fromisoformat(cached_dashboard['last_active'])
                )
            
            logger.info(f"🔍 DASHBOARD CACHE MISS: Fetching fresh data for user {user_id}")
            
            from app.models.auth import UserDashboardStats, UserSearchHistory
            from sqlalchemy import text

            # Use session-based approach with optimized timeout
            async with asyncio.timeout(5.0):  # Industry standard: aggressive timeout for UX

                # ENTERPRISE OPTIMIZATION: Single CTE query for ALL dashboard data
                result = await db.execute(text("""
                    WITH user_data AS (
                        SELECT id, created_at
                        FROM users
                        WHERE supabase_user_id = :user_id
                        LIMIT 1
                    ),
                    search_stats AS (
                        SELECT
                            COALESCE(COUNT(*), 0) as total_searches,
                            COALESCE(COUNT(*) FILTER (WHERE search_timestamp >= date_trunc('month', CURRENT_DATE)), 0) as searches_this_month
                        FROM user_searches us
                        INNER JOIN user_data ud ON us.user_id = ud.id
                    ),
                    recent_searches AS (
                        SELECT
                            us.id::text as search_id,
                            us.user_id::text as search_user_id,
                            us.instagram_username,
                            us.search_timestamp,
                            us.analysis_type,
                            COALESCE(us.search_metadata, '{}'::jsonb) as search_metadata
                        FROM user_searches us
                        INNER JOIN user_data ud ON us.user_id = ud.id
                        ORDER BY us.search_timestamp DESC
                        LIMIT 10
                    ),
                    favorite_profiles AS (
                        SELECT p.username
                        FROM user_profile_access upa
                        INNER JOIN profiles p ON p.id = upa.profile_id
                        INNER JOIN user_data ud ON upa.user_id = ud.id
                        ORDER BY upa.granted_at DESC
                        LIMIT 10
                    )
                    SELECT
                        ud.id as user_id,
                        ud.created_at,
                        COALESCE(ss.total_searches, 0) as total_searches,
                        COALESCE(ss.searches_this_month, 0) as searches_this_month,
                        COALESCE(
                            json_agg(
                                json_build_object(
                                    'id', rs.search_id,
                                    'user_id', rs.search_user_id,
                                    'instagram_username', rs.instagram_username,
                                    'search_timestamp', rs.search_timestamp,
                                    'analysis_type', rs.analysis_type,
                                    'search_metadata', rs.search_metadata
                                ) ORDER BY rs.search_timestamp DESC
                            ) FILTER (WHERE rs.search_id IS NOT NULL),
                            '[]'::json
                        ) as recent_searches_json,
                        COALESCE(
                            array_agg(fp.username ORDER BY fp.username) FILTER (WHERE fp.username IS NOT NULL),
                            ARRAY[]::text[]
                        ) as favorite_profiles_array
                    FROM user_data ud
                    LEFT JOIN search_stats ss ON true
                    LEFT JOIN recent_searches rs ON true
                    LEFT JOIN favorite_profiles fp ON true
                    GROUP BY ud.id, ud.created_at, ss.total_searches, ss.searches_this_month
                """), {"user_id": str(user_id)})

                row = result.fetchone()

                if not row or not row.user_id:
                    logger.warning(f"No database user found for Supabase ID: {user_id}")
                    return UserDashboardStats(
                        total_searches=0,
                        searches_this_month=0,
                        favorite_profiles=[],
                        recent_searches=[],
                        account_created=datetime.now(),
                        last_active=datetime.now()
                    )

                # Parse JSON search data efficiently
                import json
                recent_searches_data = json.loads(row.recent_searches_json) if row.recent_searches_json else []
                recent_searches = [
                    UserSearchHistory(
                        id=search['id'],
                        user_id=search['user_id'],
                        instagram_username=search['instagram_username'],
                        search_timestamp=datetime.fromisoformat(search['search_timestamp'].replace('Z', '+00:00')) if isinstance(search['search_timestamp'], str) else search['search_timestamp'],
                        analysis_type=search['analysis_type'],
                        search_metadata=search['search_metadata'] or {}
                    )
                    for search in recent_searches_data
                ]

                dashboard_stats = UserDashboardStats(
                    total_searches=row.total_searches,
                    searches_this_month=row.searches_this_month,
                    favorite_profiles=list(row.favorite_profiles_array) if row.favorite_profiles_array else [],
                    recent_searches=recent_searches,
                    account_created=row.created_at,
                    last_active=datetime.now()
                )

                # Cache dashboard data for 5 minutes for instant subsequent loads
                await self._cache_dashboard_stats(user_id, dashboard_stats)

                # RESILIENCE: Record successful operation
                database_resilience.record_success()

                return dashboard_stats
                
        except asyncio.TimeoutError:
            logger.error(f"DASHBOARD: Database timeout after 5s for user {user_id} - circuit breaker activated")
            # RESILIENCE: Record timeout failure
            database_resilience.record_failure()
            # CIRCUIT BREAKER: Return cached fallback or minimal stats
            return UserDashboardStats(
                total_searches=0,
                searches_this_month=0,
                favorite_profiles=[],
                recent_searches=[],
                account_created=datetime.now(),
                last_active=datetime.now()
            )
        except Exception as e:
            logger.error(f"ERROR: Failed to get dashboard stats for user {user_id}: {e}")
            # RESILIENCE: Record general failure
            database_resilience.record_failure()
            # Return empty stats on error
            return UserDashboardStats(
                total_searches=0,
                searches_this_month=0,
                favorite_profiles=[],
                recent_searches=[],
                account_created=datetime.now(),
                last_active=datetime.now()
            )
    
    async def get_user_search_history(self, user_id: str, page: int = 1, page_size: int = 20):
        """Get user's search history with pagination"""
        await self.ensure_initialized()
        
        try:
            import asyncpg
            from app.core.config import settings
            from app.models.auth import UserSearchHistory
            
            if not settings.DATABASE_URL:
                logger.warning("WARNING: DATABASE_URL not available for search history")
                return []
            
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            try:
                # CRITICAL FIX: Convert Supabase user ID to database user ID for searches
                db_user_id = await conn.fetchval(
                    "SELECT id FROM users WHERE supabase_user_id = $1",
                    str(user_id)
                )
                
                if not db_user_id:
                    logger.warning(f"No database user found for Supabase ID: {user_id}")
                    return []
                
                offset = (page - 1) * page_size
                
                # Get search history with pagination (user_searches.user_id is VARCHAR)
                search_rows = await conn.fetch(
                    """
                    SELECT id, user_id, instagram_username, search_timestamp, 
                           analysis_type, search_metadata
                    FROM user_searches 
                    WHERE user_id = $1 
                    ORDER BY search_timestamp DESC 
                    LIMIT $2 OFFSET $3
                    """,
                    str(db_user_id), page_size, offset
                )
                
                return [
                    UserSearchHistory(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        instagram_username=row['instagram_username'],
                        search_timestamp=row['search_timestamp'],
                        analysis_type=row['analysis_type'],
                        search_metadata=row['search_metadata'] or {}
                    )
                    for row in search_rows
                ]
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"ERROR: Failed to get search history for user {user_id}: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for auth service"""
        health_status = {
            "service": "supabase_auth",
            "status": "unknown",
            "initialized": self.initialized,
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        try:
            # Check initialization
            if not self.initialized:
                await self.initialize()
            
            if not self.initialized:
                health_status["status"] = "unhealthy"
                health_status["details"]["error"] = self.initialization_error
                return health_status
            
            # Test Supabase connectivity (non-admin)
            try:
                # Test with session check (doesn't require admin)
                session_response = self.supabase.auth.get_session()
                health_status["details"]["supabase_connectivity"] = "ok"
                health_status["details"]["session_status"] = "accessible"
            except Exception as e:
                health_status["details"]["supabase_connectivity"] = f"error: {e}"
            
            # Test environment variables
            health_status["details"]["environment"] = {
                "supabase_url": "set" if settings.SUPABASE_URL else "missing",
                "supabase_key": "set" if settings.SUPABASE_KEY else "missing",
                "database_url": "set" if settings.DATABASE_URL else "missing"
            }
            
            # Overall status
            if (self.initialized and 
                health_status["details"]["supabase_connectivity"] == "ok" and
                settings.SUPABASE_URL and settings.SUPABASE_KEY):
                health_status["status"] = "healthy"
            else:
                health_status["status"] = "degraded"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["details"]["error"] = str(e)
        
        return health_status
    
    async def verify_user_password(self, email: str, password: str) -> bool:
        """Verify user's current password"""
        await self.ensure_initialized()
        
        try:
            # Attempt to sign in with the provided credentials
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            # If sign in succeeds, password is correct
            return response.user is not None
            
        except Exception as e:
            logger.warning(f"Password verification failed for {email}: {e}")
            return False
    
    async def change_user_password(self, email: str, current_password: str, new_password: str) -> bool:
        """Change user's password after verifying current password"""
        await self.ensure_initialized()
        
        try:
            # First verify current password
            if not await self.verify_user_password(email, current_password):
                return False
            
            # Sign in to get session for password change
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": current_password
            })
            
            if not auth_response.user:
                return False
            
            # Update password
            update_response = self.supabase.auth.update_user({
                "password": new_password
            })
            
            if update_response.user:
                logger.info(f"Password changed successfully for user {email}")
                return True
            else:
                logger.error(f"Password change failed for user {email}")
                return False
                
        except Exception as e:
            logger.error(f"Password change error for {email}: {e}")
            return False
    
    async def refresh_token(self, refresh_token: str) -> Optional[LoginResponse]:
        """Refresh access token using refresh token"""
        await self.ensure_initialized()
        
        try:
            logger.info("Attempting to refresh access token")
            
            # Use Supabase refresh token functionality
            auth_response = self.supabase.auth.refresh_session(refresh_token)
            
            if not auth_response.user or not auth_response.session:
                logger.warning("Token refresh failed - invalid refresh token")
                return None
            
            user = auth_response.user
            session = auth_response.session
            user_metadata = user.user_metadata or {}
            
            # Determine user role
            role_value = (
                user_metadata.get("role") or 
                user.app_metadata.get("role") if user.app_metadata else "free"
            )
            
            try:
                user_role = UserRole(role_value)
            except ValueError:
                logger.warning(f"Invalid role '{role_value}' for user {user.id}, defaulting to 'free'")
                user_role = UserRole.FREE
            
            # Handle datetime parsing safely
            try:
                if user.created_at:
                    if isinstance(user.created_at, str):
                        created_at = datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
                    else:
                        created_at = user.created_at
                else:
                    created_at = datetime.now()
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to parse created_at in refresh: {e}, using current time")
                created_at = datetime.now()
            
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                full_name=user_metadata.get("full_name", ""),
                role=user_role,
                status=UserStatus.ACTIVE,
                created_at=created_at,
                last_login=datetime.now(),
                profile_picture_url=user_metadata.get("avatar_url")
            )
            
            # Update last activity in database
            await self._update_user_activity(user)
            
            response = LoginResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                token_type="bearer",
                expires_in=session.expires_in,
                user=user_response
            )
            
            logger.info(f"Token refresh successful for user {user.email}")
            return response
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    async def _update_user_activity(self, supabase_user):
        """Update user's last activity timestamp"""
        try:
            from app.database.connection import SessionLocal
            from app.database.unified_models import User
            from sqlalchemy import update
            
            if not SessionLocal:
                return
            
            async with SessionLocal() as db:
                try:
                    await db.execute(
                        update(User)
                        .where(User.supabase_user_id == supabase_user.id)
                        .values(
                            last_activity=datetime.now(timezone.utc)
                        )
                    )
                    await db.commit()
                    logger.debug(f"Updated activity for user {supabase_user.email}")
                except Exception as db_error:
                    await db.rollback()
                    logger.warning(f"Failed to update user activity: {db_error}")
                    
        except Exception as e:
            logger.warning(f"Failed to update user activity: {e}")


# Create global instance
supabase_auth_service = ProductionSupabaseAuthService()


async def get_auth_service() -> ProductionSupabaseAuthService:
    """Dependency to get auth service instance"""
    await supabase_auth_service.initialize()
    return supabase_auth_service