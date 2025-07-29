"""
Industry-Standard Supabase Authentication Service
Bulletproof, production-ready authentication using only Supabase Auth
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
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
            logger.info("🔄 Initializing Supabase Auth Service...")
            
            # Validate environment variables
            if not settings.SUPABASE_URL:
                self.initialization_error = "SUPABASE_URL environment variable not set"
                logger.error(f"❌ {self.initialization_error}")
                return False
                
            if not settings.SUPABASE_KEY:
                self.initialization_error = "SUPABASE_KEY environment variable not set"
                logger.error(f"❌ {self.initialization_error}")
                return False
            
            # Import and create client
            try:
                from supabase import create_client, Client
                logger.info("✅ Supabase package imported successfully")
            except ImportError as e:
                self.initialization_error = f"Failed to import Supabase: {e}"
                logger.error(f"❌ {self.initialization_error}")
                return False
            
            # Create Supabase client
            try:
                self.supabase: Client = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_KEY
                )
                logger.info("✅ Supabase client created successfully")
            except Exception as e:
                self.initialization_error = f"Failed to create Supabase client: {e}"
                logger.error(f"❌ {self.initialization_error}")
                return False
            
            # Test client connectivity (non-admin test)
            try:
                # Simple test - try to access session (doesn't require admin)
                test_response = self.supabase.auth.get_session()
                logger.info("✅ Supabase Auth connectivity test passed (non-admin)")
            except Exception as e:
                logger.warning(f"⚠️ Supabase Auth test failed (but client created): {e}")
                # Don't fail initialization - client might still work for authentication
            
            self.initialized = True
            self.initialization_error = None
            logger.info("🎉 Supabase Auth Service initialized successfully")
            return True
            
        except Exception as e:
            self.initialization_error = f"Unexpected error during initialization: {e}"
            logger.error(f"❌ {self.initialization_error}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    async def ensure_initialized(self):
        """Ensure service is initialized, attempt reinitialization if needed"""
        if not self.initialized:
            logger.warning("🔄 Auth service not initialized, attempting initialization...")
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
            logger.info(f"🔐 Attempting login for user: {login_data.email}")
            
            # Authenticate with Supabase
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })
            
            logger.info(f"📨 Received auth response for {login_data.email}")
            
            # Check if authentication was successful
            if not auth_response.user:
                logger.warning(f"❌ Authentication failed - no user returned for {login_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            user = auth_response.user
            session = auth_response.session
            
            logger.info(f"✅ Supabase authentication successful for user ID: {user.id}")
            
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
                logger.warning(f"⚠️ Invalid role '{role_value}' for user {user.id}, defaulting to 'free'")
                user_role = UserRole.FREE
            
            # Create UserResponse
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
                logger.warning(f"Failed to parse created_at: {e}, using current time")
                created_at = datetime.now()
            
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
            
            # Ensure user exists in our database
            await self._ensure_user_in_database(user, user_metadata)
            
            response = LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                user=user_response
            )
            
            logger.info(f"🎉 Login successful for {login_data.email}")
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"❌ Login failed for {login_data.email}: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
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
        """Ensure user exists in our database with proper fields"""
        try:
            import asyncpg
            from app.core.config import settings
            
            if not settings.DATABASE_URL:
                logger.warning("⚠️ DATABASE_URL not available, skipping database user creation")
                return
            
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            # Insert or update user in database
            await conn.execute("""
                INSERT INTO users (
                    id, 
                    email, 
                    hashed_password, 
                    role, 
                    credits, 
                    full_name, 
                    status, 
                    supabase_user_id, 
                    last_login, 
                    created_at,
                    profile_picture_url
                ) VALUES (
                    $1::uuid, $2, 'supabase_managed', $3, $4, $5, 'active', $6, NOW(), NOW(), $7
                )
                ON CONFLICT (email) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    status = 'active',
                    supabase_user_id = EXCLUDED.supabase_user_id,
                    last_login = NOW(),
                    profile_picture_url = EXCLUDED.profile_picture_url
            """, 
                supabase_user.id,  # id
                supabase_user.email,  # email
                user_metadata.get("role", "free"),  # role
                1000 if user_metadata.get("role") == "premium" else 100,  # credits
                user_metadata.get("full_name", ""),  # full_name
                supabase_user.id,  # supabase_user_id
                user_metadata.get("avatar_url")  # profile_picture_url
            )
            
            await conn.close()
            logger.info(f"✅ User {supabase_user.email} synchronized to database")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to sync user to database: {e}")
            # Don't fail authentication if database sync fails
    
    async def register_user(self, user_data: UserCreate) -> UserResponse:
        """Register new user with Supabase Auth"""
        await self.ensure_initialized()
        
        try:
            logger.info(f"📝 Registering new user: {user_data.email}")
            
            # Create user in Supabase Auth (non-admin)
            auth_response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
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
                logger.warning(f"Failed to parse created_at in registration: {e}, using current time")
                created_at = datetime.now()
            
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                full_name=user_metadata.get("full_name", ""),
                role=UserRole(user_metadata.get("role", "free")),
                status=UserStatus.ACTIVE,
                created_at=created_at,
                last_login=None
            )
            
            logger.info(f"✅ User registration successful: {user_data.email}")
            return user_response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Registration failed for {user_data.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    async def get_current_user(self, token: str) -> UserInDB:
        """Get current user from Supabase session token"""
        await self.ensure_initialized()
        
        try:
            # Verify token with Supabase
            user_response = self.supabase.auth.get_user(token)
            
            if not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            user = user_response.user
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
                logger.warning(f"Failed to parse created_at in get_current_user: {e}, using current time")
                created_at = datetime.now()
                
            user_in_db = UserInDB(
                id=user.id,
                supabase_user_id=user.id,
                email=user.email,
                full_name=user_metadata.get("full_name", ""),
                role=UserRole(user_metadata.get("role", "free")),
                status=UserStatus.ACTIVE,
                created_at=created_at,
                updated_at=datetime.now(),
                last_login=datetime.now()
            )
            
            return user_in_db
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    async def logout_user(self, token: str) -> bool:
        """Logout user by invalidating Supabase session"""
        await self.ensure_initialized()
        
        try:
            self.supabase.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"❌ Logout failed: {e}")
            return False
    
    async def get_user_dashboard_stats(self, user_id: str):
        """Get comprehensive dashboard statistics for user"""
        await self.ensure_initialized()
        
        try:
            import asyncpg
            from app.core.config import settings
            from app.models.auth import UserDashboardStats, UserSearchHistory
            
            if not settings.DATABASE_URL:
                logger.warning("⚠️ DATABASE_URL not available for dashboard stats")
                # Return empty stats if no database connection
                return UserDashboardStats(
                    total_searches=0,
                    searches_this_month=0,
                    favorite_profiles=[],
                    recent_searches=[],
                    account_created=datetime.now(),
                    last_active=datetime.now()
                )
            
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            try:
                # Get total searches for user (user_searches.user_id is VARCHAR)
                total_searches = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_searches WHERE user_id = $1",
                    str(user_id)
                ) or 0
                
                # Get searches this month (user_searches.user_id is VARCHAR)
                searches_this_month = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM user_searches 
                    WHERE user_id = $1 AND search_timestamp >= date_trunc('month', CURRENT_DATE)
                    """,
                    str(user_id)
                ) or 0
                
                # Get recent searches (user_searches.user_id is VARCHAR)
                recent_search_rows = await conn.fetch(
                    """
                    SELECT id, user_id, instagram_username, search_timestamp, 
                           analysis_type, search_metadata
                    FROM user_searches 
                    WHERE user_id = $1 
                    ORDER BY search_timestamp DESC 
                    LIMIT 10
                    """,
                    str(user_id)
                )
                
                recent_searches = [
                    UserSearchHistory(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        instagram_username=row['instagram_username'],
                        search_timestamp=row['search_timestamp'],
                        analysis_type=row['analysis_type'],
                        search_metadata=row['search_metadata'] or {}
                    )
                    for row in recent_search_rows
                ]
                
                # Get user creation date (users.id is UUID)
                user_created = await conn.fetchval(
                    "SELECT created_at FROM users WHERE id = $1::uuid",
                    str(user_id)
                ) or datetime.now()
                
                # Get favorite profiles (unlocked profiles) - user_profile_access.user_id is UUID
                favorite_profiles = await conn.fetch(
                    """
                    SELECT p.username FROM user_profile_access upa
                    JOIN profiles p ON p.id = upa.profile_id
                    WHERE upa.user_id = $1::uuid
                    ORDER BY upa.last_accessed DESC
                    LIMIT 10
                    """,
                    str(user_id)
                )
                
                favorite_profile_list = [row['username'] for row in favorite_profiles]
                
                return UserDashboardStats(
                    total_searches=total_searches,
                    searches_this_month=searches_this_month,
                    favorite_profiles=favorite_profile_list,
                    recent_searches=recent_searches,
                    account_created=user_created,
                    last_active=datetime.now()
                )
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Failed to get dashboard stats for user {user_id}: {e}")
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
                logger.warning("⚠️ DATABASE_URL not available for search history")
                return []
            
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            try:
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
                    str(user_id), page_size, offset
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
            logger.error(f"❌ Failed to get search history for user {user_id}: {e}")
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


# Create global instance
supabase_auth_service = ProductionSupabaseAuthService()


async def get_auth_service() -> ProductionSupabaseAuthService:
    """Dependency to get auth service instance"""
    await supabase_auth_service.initialize()
    return supabase_auth_service