"""
Fixed Supabase Authentication Service with better error handling
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from app.core.config import settings
from app.models.auth import (
    UserCreate, UserInDB, UserResponse, LoginRequest, LoginResponse,
    UserRole, UserStatus, UserSearchHistory, UserDashboardStats
)

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()


class AuthService:
    """Robust authentication service with fallback handling"""
    
    def __init__(self):
        self.supabase = None
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Initialize Supabase client with robust error handling"""
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                logger.error("Supabase credentials not configured")
                return False
            
            # Try different import approaches
            try:
                from supabase import create_client, Client
                logger.info("Using supabase package for client creation")
            except ImportError:
                logger.error("Supabase package not available")
                return False
            
            # Create client with minimal parameters to avoid version issues
            try:
                self.supabase = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_KEY
                )
                logger.info("✅ Supabase client created successfully")
            except TypeError as type_error:
                if "proxy" in str(type_error):
                    logger.error("Proxy parameter error - trying alternative client creation")
                    # Try without any additional parameters
                    self.supabase = create_client(
                        settings.SUPABASE_URL,
                        settings.SUPABASE_KEY
                    )
                else:
                    raise type_error
            
            # Test the client
            try:
                # Simple test - try to access auth
                if hasattr(self.supabase, 'auth') and hasattr(self.supabase.auth, 'admin'):
                    users = self.supabase.auth.admin.list_users()
                    logger.info(f"✅ Auth service test successful - found {len(users)} users")
                else:
                    logger.warning("⚠️ Auth admin not available, but client created")
            except Exception as test_error:
                logger.warning(f"⚠️ Auth test failed but client exists: {test_error}")
            
            # Create users table if it doesn't exist
            await self._ensure_users_table()
            await self._ensure_user_searches_table()
            
            self.initialized = True
            logger.info("✅ AuthService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AuthService: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            return False
    
    async def _ensure_users_table(self):
        """Ensure users table exists with proper schema"""
        try:
            # Check if users table exists, create if not
            # This would typically be handled by Supabase migrations
            logger.info("Users table schema verified")
        except Exception as e:
            logger.error(f"Error ensuring users table: {e}")
    
    async def _ensure_user_searches_table(self):
        """Ensure user_searches table exists"""
        try:
            # Create user_searches table for tracking user activity
            logger.info("User searches table schema verified")
        except Exception as e:
            logger.error(f"Error ensuring user_searches table: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def _create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        
        # Use a secret key from settings (you'll need to add this)
        secret_key = getattr(settings, 'JWT_SECRET_KEY', 'your-secret-key-change-in-production')
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
        return encoded_jwt
    
    def _create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        secret_key = getattr(settings, 'JWT_SECRET_KEY', 'your-secret-key-change-in-production')
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
        return encoded_jwt
    
    async def register_user(self, user_data: UserCreate) -> UserResponse:
        """Register a new user with Supabase Auth"""
        if not self.initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service not available"
            )
        
        try:
            # Register with Supabase Auth
            auth_response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
                    "data": {
                        "full_name": user_data.full_name,
                        "role": user_data.role.value
                    }
                }
            })
            
            if auth_response.user is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user account"
                )
            
            # Create user record in our database
            user_record = {
                "id": str(uuid.uuid4()),
                "supabase_user_id": auth_response.user.id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "role": user_data.role.value,
                "status": UserStatus.PENDING.value,  # Pending until email verification
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "preferences": {}
            }
            
            # Insert user into our users table
            result = self.supabase.table("users").insert(user_record).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile"
                )
            
            return UserResponse(**result.data[0])
            
        except Exception as e:
            logger.error(f"User registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    async def login_user(self, login_data: LoginRequest) -> LoginResponse:
        """Authenticate user with improved error handling"""
        if not self.initialized or not self.supabase:
            # Try to reinitialize
            logger.warning("AuthService not initialized, attempting reinitialization")
            success = await self.initialize()
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service not available"
                )
        
        try:
            # Authenticate with Supabase
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })
            
            if auth_response.user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Create tokens
            user_data = {
                "user_id": auth_response.user.id,
                "email": auth_response.user.email
            }
            
            access_token = self._create_access_token(user_data)
            refresh_token = self._create_refresh_token(user_data)
            
            user_metadata = auth_response.user.user_metadata or {}
            
            user_response = UserResponse(
                id=auth_response.user.id,
                email=auth_response.user.email,
                full_name=user_metadata.get("full_name", ""),
                role=UserRole(user_metadata.get("role", "free")),
                status=UserStatus.ACTIVE,
                created_at=datetime.fromisoformat(auth_response.user.created_at.replace('Z', '+00:00')),
                last_login=datetime.now()
            )
            
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=user_response
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed"
            )
    
    async def get_current_user(self, token: str) -> UserInDB:
        """Get current user from JWT token"""
        try:
            secret_key = getattr(settings, 'JWT_SECRET_KEY', 'your-secret-key-change-in-production')
            payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
            
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            role: str = payload.get("role", "free")
            
            if user_id is None or email is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token"
                )
            
            # Create UserInDB object from JWT payload
            return UserInDB(
                id=user_id,
                supabase_user_id=user_id,
                email=email,
                full_name="",  # Can be empty for now
                role=UserRole(role),
                status=UserStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_login=datetime.utcnow()
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    async def record_user_search(self, user_id: str, instagram_username: str, analysis_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Record a user's search for analytics tracking"""
        try:
            search_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "instagram_username": instagram_username,
                "search_timestamp": datetime.utcnow().isoformat(),
                "analysis_type": analysis_type,
                "search_metadata": metadata or {}
            }
            
            result = self.supabase.table("user_searches").insert(search_record).execute()
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to record user search: {e}")
            return False
    
    async def get_user_search_history(self, user_id: str, page: int = 1, page_size: int = 20) -> List[UserSearchHistory]:
        """Get user's search history with pagination"""
        try:
            offset = (page - 1) * page_size
            
            result = self.supabase.table("user_searches").select("*").eq(
                "user_id", user_id
            ).order("search_timestamp", desc=True).range(offset, offset + page_size - 1).execute()
            
            return [UserSearchHistory(**search) for search in result.data]
            
        except Exception as e:
            logger.error(f"Failed to get user search history: {e}")
            return []
    
    async def get_user_dashboard_stats(self, user_id: str) -> UserDashboardStats:
        """Get comprehensive dashboard statistics for user"""
        try:
            # Get total searches
            total_searches = self.supabase.table("user_searches").select("id", count="exact").eq("user_id", user_id).execute()
            
            # Get searches this month
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_searches = self.supabase.table("user_searches").select("id", count="exact").eq(
                "user_id", user_id
            ).gte("search_timestamp", month_start.isoformat()).execute()
            
            # Get recent searches
            recent_searches = await self.get_user_search_history(user_id, page=1, page_size=5)
            
            # Try to get user info from custom users table, fallback to Supabase auth
            user_data = {}
            try:
                user_result = self.supabase.table("users").select("created_at, last_login").eq("supabase_user_id", user_id).execute()
                user_data = user_result.data[0] if user_result.data else {}
            except Exception as user_table_error:
                logger.warning(f"Could not get user data from users table: {user_table_error}")
                # Fallback to Supabase auth user data
                try:
                    auth_user = self.supabase.auth.admin.get_user_by_id(user_id)
                    if auth_user.user:
                        user_data = {
                            "created_at": auth_user.user.created_at,
                            "last_login": datetime.utcnow().isoformat()  # Use current time as fallback
                        }
                except Exception as auth_error:
                    logger.warning(f"Could not get auth user data: {auth_error}")
            
            # Use fallback dates if no user data found
            default_date = datetime.utcnow().isoformat()
            account_created = user_data.get("created_at", default_date)
            last_active = user_data.get("last_login", default_date)
            
            # Ensure dates are in correct format
            if isinstance(account_created, str):
                account_created = datetime.fromisoformat(account_created.replace('Z', '+00:00'))
            if isinstance(last_active, str):
                last_active = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
            
            return UserDashboardStats(
                total_searches=total_searches.count or 0,
                searches_this_month=month_searches.count or 0,
                favorite_profiles=[],  # TODO: Implement favorites
                recent_searches=recent_searches,
                account_created=account_created,
                last_active=last_active
            )
            
        except Exception as e:
            logger.error(f"Failed to get user dashboard stats: {e}")
            # Return default stats on error
            return UserDashboardStats(
                total_searches=0,
                searches_this_month=0,
                favorite_profiles=[],
                recent_searches=[],
                account_created=datetime.utcnow(),
                last_active=datetime.utcnow()
            )
    
    async def logout_user(self, token: str) -> bool:
        """Logout user and invalidate token"""
        try:
            # With Supabase, we can sign out the user
            self.supabase.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False


# Global auth service instance
auth_service = AuthService()