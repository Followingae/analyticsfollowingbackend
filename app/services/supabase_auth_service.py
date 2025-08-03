"""
Industry-Standard Supabase Authentication Service
Bulletproof, production-ready authentication using only Supabase Auth
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.models.auth import (
    UserCreate, UserInDB, UserResponse, LoginRequest, LoginResponse,
    UserRole, UserStatus
)

logger = logging.getLogger(__name__)
security = HTTPBearer()

# JWT settings for token creation
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


class ProductionSupabaseAuthService:
    """Production-ready Supabase authentication service"""
    
    def __init__(self):
        self.supabase = None
        self.initialized = False
        self.initialization_error = None
    
    async def initialize(self) -> bool:
        """Initialize Supabase client with comprehensive error handling"""
        if self.initialized and self.supabase:
            return True
            
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
                self.supabase: Client = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_KEY
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
            
            # Create UserResponse
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
                logger.warning(f"Failed to parse created_at: {e}, using current time")
                created_at = datetime.now(timezone.utc)
            
            user_response = UserResponse(
                id=user.id,
                email=user.email or login_data.email,
                full_name=user_metadata.get("full_name", ""),
                role=user_role,
                status=UserStatus.ACTIVE,
                created_at=created_at,
                last_login=datetime.now(),
                profile_picture_url=user_metadata.get("avatar_url")
            )
            
            # Use Supabase session tokens
            access_token = session.access_token if session else user.id
            refresh_token = session.refresh_token if session else ""
            expires_in = session.expires_in if session else ACCESS_TOKEN_EXPIRE_MINUTES * 60
            
            # Ensure user exists in our database (non-blocking)
            try:
                await self._ensure_user_in_database(user, user_metadata)
            except Exception as db_error:
                logger.warning(f"Database sync failed (non-blocking): {db_error}")
                # Don't fail authentication if database sync fails - continue with login
            
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
            
            async with SessionLocal() as db:
                try:
                    # Check if user exists by Supabase ID first (more reliable)
                    logger.info(f"SYNC: Looking for user with Supabase ID: {supabase_user.id}")
                    result = await db.execute(select(User).where(User.supabase_user_id == supabase_user.id))
                    existing_user = result.scalar_one_or_none()
                    
                    if not existing_user:
                        # Check by email as fallback
                        logger.info(f"SYNC: User not found by Supabase ID, checking by email: {supabase_user.email}")
                        result = await db.execute(select(User).where(User.email == supabase_user.email))
                        existing_user = result.scalar_one_or_none()
                    
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
                    
                except Exception as db_error:
                    await db.rollback()
                    logger.error(f"SYNC: Database sync failed for {supabase_user.email}: {db_error}")
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
            
            # Sync to database
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
        """Get current user from Supabase session token with enhanced validation"""
        await self.ensure_initialized()
        
        try:
            logger.info(f"TOKEN: Validating token for current user (length: {len(token)})")
            
            # Method 1: Try direct token validation
            try:
                user_response = self.supabase.auth.get_user(token)
                logger.info(f"TOKEN: Direct validation response received")
                
                if user_response and user_response.user:
                    logger.info(f"TOKEN: Direct validation successful for user: {user_response.user.email}")
                    return self._create_user_in_db_from_supabase(user_response.user)
                else:
                    logger.warning(f"TOKEN: Direct validation returned no user")
            except Exception as direct_error:
                logger.warning(f"TOKEN: Direct validation failed: {direct_error}")
            
            # Method 2: Try setting session and then getting user
            try:
                logger.info(f"TOKEN: Attempting session-based validation")
                
                # Set the session with the token
                session_response = self.supabase.auth.set_session(token, token)
                logger.info(f"TOKEN: Session set, attempting to get user")
                
                # Now try to get the current user from the session
                user_response = self.supabase.auth.get_user()
                
                if user_response and user_response.user:
                    logger.info(f"TOKEN: Session validation successful for user: {user_response.user.email}")
                    return self._create_user_in_db_from_supabase(user_response.user)
                else:
                    logger.warning(f"TOKEN: Session validation returned no user")
            except Exception as session_error:
                logger.warning(f"TOKEN: Session validation failed: {session_error}")
            
            # Method 3: Try using the token as a JWT and verify manually
            try:
                logger.info(f"TOKEN: Attempting JWT manual verification")
                
                # Create a new temporary client with this specific token
                from supabase import create_client
                temp_client = create_client(self.supabase_url, self.supabase_key)
                
                # Set auth header manually
                temp_client.auth._client.headers.update({
                    "Authorization": f"Bearer {token}"
                })
                
                user_response = temp_client.auth.get_user(token)
                
                if user_response and user_response.user:
                    logger.info(f"TOKEN: JWT verification successful for user: {user_response.user.email}")
                    return self._create_user_in_db_from_supabase(user_response.user)
                else:
                    logger.warning(f"TOKEN: JWT verification returned no user")
            except Exception as jwt_error:
                logger.warning(f"TOKEN: JWT verification failed: {jwt_error}")
            
            # If all methods fail, raise authentication error
            logger.error(f"TOKEN: All validation methods failed for token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token - all validation methods failed"
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
        
        logger.info(f"TOKEN: Successfully created UserInDB for: {user.email}")
        return user_in_db
    
    async def logout_user(self, token: str) -> bool:
        """Logout user by invalidating Supabase session"""
        await self.ensure_initialized()
        
        try:
            self.supabase.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"ERROR: Logout failed: {e}")
            return False
    
    async def get_user_dashboard_stats(self, user_id: str):
        """Get comprehensive dashboard statistics for user"""
        await self.ensure_initialized()
        
        try:
            from app.models.auth import UserDashboardStats, UserSearchHistory
            from app.database.connection import async_engine
            from sqlalchemy import text
            
            # Use connection pool instead of creating new connections
            async with async_engine.begin() as conn:
                
                # Optimized query: Get user ID and basic info in one query
                user_result = await conn.execute(text("""
                    SELECT id, created_at FROM users WHERE supabase_user_id = :user_id
                """), {"user_id": str(user_id)})
                
                user_row = user_result.fetchone()
                
                if not user_row:
                    logger.warning(f"No database user found for Supabase ID: {user_id}")
                    return UserDashboardStats(
                        total_searches=0,
                        searches_this_month=0,
                        favorite_profiles=[],
                        recent_searches=[],
                        account_created=datetime.now(),
                        last_active=datetime.now()
                    )
                
                db_user_id = user_row.id
                user_created = user_row.created_at
                
                # Optimized query: Get search statistics in one query
                search_stats_result = await conn.execute(text("""
                    SELECT 
                        COUNT(*) as total_searches,
                        COUNT(*) FILTER (WHERE search_timestamp >= date_trunc('month', CURRENT_DATE)) as searches_this_month
                    FROM user_searches 
                    WHERE user_id = :user_id
                """), {"user_id": str(db_user_id)})
                
                stats_row = search_stats_result.fetchone()
                total_searches = stats_row.total_searches or 0
                searches_this_month = stats_row.searches_this_month or 0
                
                # Get recent searches
                recent_search_result = await conn.execute(text("""
                    SELECT id, user_id, instagram_username, search_timestamp, 
                           analysis_type, search_metadata
                    FROM user_searches 
                    WHERE user_id = :user_id
                    ORDER BY search_timestamp DESC 
                    LIMIT 10
                """), {"user_id": str(db_user_id)})
                
                recent_searches = [
                    UserSearchHistory(
                        id=str(row.id),
                        user_id=str(row.user_id),
                        instagram_username=row.instagram_username,
                        search_timestamp=row.search_timestamp,
                        analysis_type=row.analysis_type,
                        search_metadata=row.search_metadata or {}
                    )
                    for row in recent_search_result.fetchall()
                ]
                
                # Get favorite profiles (unlocked profiles) - user_profile_access.user_id is UUID
                favorite_profiles_result = await conn.execute(text("""
                    SELECT p.username FROM user_profile_access upa
                    JOIN profiles p ON p.id = upa.profile_id
                    WHERE upa.user_id = :user_id
                    ORDER BY upa.granted_at DESC
                    LIMIT 10
                """), {"user_id": str(db_user_id)})
                
                favorite_profile_list = [row.username for row in favorite_profiles_result.fetchall()]
                
                return UserDashboardStats(
                    total_searches=total_searches,
                    searches_this_month=searches_this_month,
                    favorite_profiles=favorite_profile_list,
                    recent_searches=recent_searches,
                    account_created=user_created,
                    last_active=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"ERROR: Failed to get dashboard stats for user {user_id}: {e}")
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