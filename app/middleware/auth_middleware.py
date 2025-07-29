"""
Authentication middleware for FastAPI
Provides JWT token validation and user authentication
"""
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import logging

from app.services.supabase_auth_service import supabase_auth_service as auth_service
from app.models.auth import UserInDB, UserRole

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthMiddleware:
    """Authentication middleware class"""
    
    def __init__(self):
        self.public_endpoints = {
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
    
    def is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (doesn't require authentication)"""
        return any(path.startswith(endpoint) for endpoint in self.public_endpoints)


auth_middleware = AuthMiddleware()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInDB:
    """
    Dependency to get current authenticated user
    """
    try:
        token = credentials.credentials
        user = await auth_service.get_current_user(token)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """
    Dependency to get current active user (not suspended/inactive)
    """
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )
    return current_user


async def get_optional_user(request: Request) -> Optional[UserInDB]:
    """
    Optional authentication - returns user if authenticated, None if not
    Useful for endpoints that work with or without authentication
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        user = await auth_service.get_current_user(token)
        return user if user.status == "active" else None
    except:
        return None


def require_roles(allowed_roles: List[UserRole]):
    """
    Dependency factory to require specific user roles
    Usage: Depends(require_roles([UserRole.ADMIN, UserRole.PREMIUM]))
    """
    async def role_checker(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        if UserRole(current_user.role) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
            )
        return current_user
    
    return role_checker


def require_premium():
    """Dependency to require premium or admin access"""
    return require_roles([UserRole.PREMIUM, UserRole.ADMIN])


def require_admin():
    """Dependency to require admin access"""
    return require_roles([UserRole.ADMIN])


async def verify_api_key(request: Request) -> bool:
    """
    Alternative authentication method using API keys
    For programmatic access or integration partners
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return False
    
    # TODO: Implement API key validation
    # This would check against a database of valid API keys
    return False


class RateLimitMiddleware:
    """Rate limiting middleware for API protection"""
    
    def __init__(self):
        self.rate_limits = {
            UserRole.FREE: {"requests_per_hour": 100, "searches_per_day": 10},
            UserRole.PREMIUM: {"requests_per_hour": 1000, "searches_per_day": 1000},
            UserRole.ADMIN: {"requests_per_hour": 10000, "searches_per_day": 10000}
        }
    
    async def check_rate_limit(self, user: UserInDB, endpoint_type: str = "general") -> bool:
        """
        Check if user has exceeded rate limits
        Returns True if within limits, False if exceeded
        """
        try:
            user_role = UserRole(user.role)
            limits = self.rate_limits.get(user_role, self.rate_limits[UserRole.FREE])
            
            # TODO: Implement actual rate limiting logic with Redis or database
            # This would track user requests and enforce limits
            
            return True  # Placeholder - always allow for now
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow on error to avoid service disruption


rate_limit_middleware = RateLimitMiddleware()


async def check_user_rate_limit(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """
    Dependency to check rate limits for authenticated users
    """
    is_within_limits = await rate_limit_middleware.check_rate_limit(current_user)
    
    if not is_within_limits:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please upgrade your plan or try again later."
        )
    
    return current_user