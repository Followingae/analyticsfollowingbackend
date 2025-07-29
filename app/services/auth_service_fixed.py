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
            
            self.initialized = True
            logger.info("✅ AuthService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AuthService: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            return False
    
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
    
    def _create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        
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


# Create global instance
auth_service_fixed = AuthService()