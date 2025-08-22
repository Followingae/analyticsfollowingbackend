"""
Role-Based Authentication & Authorization System
Analytics Following Backend - Simplified Implementation
"""
from functools import wraps
from typing import Optional, List, Dict, Any, Union
import logging
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from uuid import UUID
import json
from datetime import datetime, timedelta

from app.models.auth import UserInDB
from app.database.connection import get_db
from app.database.unified_models import User, UserProfile
from app.core.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Redis connection for caching permissions and session management
try:
    redis_client = redis.from_url(settings.REDIS_URL) if hasattr(settings, 'REDIS_URL') else None
except:
    redis_client = None

class RoleLevel:
    """Role hierarchy levels for access control"""
    SUPER_ADMIN = 5
    ADMIN = 4
    BRAND_ENTERPRISE = 3
    BRAND_PREMIUM = 2
    BRAND_STANDARD = 1
    BRAND_FREE = 0

class PermissionCategories:
    """Permission categories for organized access control"""
    USER_MANAGEMENT = "user_management"
    FINANCIAL = "financial"
    CONTENT = "content"
    PROPOSALS = "proposals"
    SYSTEM = "system"

class AuthenticationError(HTTPException):
    """Custom authentication error"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class AuthorizationError(HTTPException):
    """Custom authorization error"""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

class FeatureAccessError(HTTPException):
    """Feature access denied error"""
    def __init__(self, detail: str = "Feature access denied", upgrade_required: str = None):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
            headers={"X-Upgrade-Required": upgrade_required} if upgrade_required else None
        )

class RoleBasedAuthService:
    """Comprehensive role-based authentication and authorization service"""
    
    def __init__(self):
        self.permission_cache_ttl = 300  # 5 minutes
        self.user_cache_ttl = 600  # 10 minutes
        
    async def get_user_with_permissions(
        self, 
        user_id: UUID, 
        db: AsyncSession,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Get user with full permission data, cached for performance"""
        cache_key = f"user_permissions:{user_id}"
        
        # Try cache first
        if use_cache and redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")
        
        # Query user information (simplified for current database structure)
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise AuthenticationError("User not found")
        
        # Simple role-based permissions (no complex role tables yet)
        role_level_map = {
            'free': 0,
            'standard': 1,
            'premium': 2,
            'enterprise': 3,
            'admin': 4,
            'super_admin': 5
        }
        
        role_level = role_level_map.get(user.role, 0)
        
        # Basic permissions based on role
        permissions = []
        if role_level >= 4:  # Admin and above
            permissions = [
                "can_view_all_users",
                "can_edit_users", 
                "can_delete_users",
                "can_view_system_logs",
                "can_adjust_credits",
                "can_view_proposal_analytics"
            ]
        elif role_level >= 2:  # Premium and above
            permissions = [
                "can_view_profiles",
                "can_export_data",
                "can_use_advanced_features"
            ]
        else:  # Free/Standard
            permissions = [
                "can_view_profiles"
            ]
        
        user_data_dict = {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "role_level": role_level,
            "is_admin": role_level >= 4,
            "account_status": user.status,
            "subscription_tier": user.subscription_tier,
            "permissions": permissions,
            "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
        
        # Cache the result
        if redis_client:
            try:
                redis_client.setex(
                    cache_key, 
                    self.user_cache_ttl, 
                    json.dumps(user_data_dict, default=str)
                )
            except Exception as e:
                logger.warning(f"Failed to cache user data: {e}")
        
        return user_data_dict
    
    async def check_permission(
        self, 
        user_data: Dict[str, Any], 
        required_permission: str
    ) -> bool:
        """Check if user has specific permission"""
        return required_permission in user_data.get("permissions", [])
    
    async def check_role_level(
        self, 
        user_data: Dict[str, Any], 
        minimum_level: int
    ) -> bool:
        """Check if user meets minimum role level requirement"""
        return user_data.get("role_level", 0) >= minimum_level
    
    async def check_subscription_feature(
        self,
        user_id: UUID,
        feature_name: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Check if user has access to specific subscription feature (simplified)"""
        # Get user subscription tier
        user_query = select(User.subscription_tier, User.role).where(User.id == user_id)
        result = await db.execute(user_query)
        user_data = result.first()
        
        if not user_data:
            return {"allowed": False, "reason": "User not found"}
        
        subscription_tier, role = user_data
        
        # Simple feature access rules based on tier/role
        feature_access = {
            "unlimited": ["all"],  # Admin access
            "professional": ["advanced_analytics", "bulk_export", "api_access"],
            "standard": ["basic_analytics", "limited_export"],
            "free": ["basic_view"]
        }
        
        allowed_features = feature_access.get(subscription_tier, [])
        
        if "all" in allowed_features or feature_name in allowed_features:
            return {"allowed": True, "tier": subscription_tier}
        else:
            return {
                "allowed": False, 
                "reason": f"Feature not available for {subscription_tier} tier",
                "upgrade_required": self._get_next_tier(subscription_tier)
            }
    
    def _get_next_tier(self, current_tier: str) -> str:
        """Get the next subscription tier for upgrade suggestions"""
        tier_hierarchy = {
            "brand_free": "brand_standard",
            "brand_standard": "brand_premium", 
            "brand_premium": "brand_enterprise",
            "brand_enterprise": "brand_enterprise"
        }
        return tier_hierarchy.get(current_tier, "brand_premium")
    
    async def log_user_activity(
        self,
        user_id: UUID,
        action_type: str,
        resource_type: str = None,
        resource_id: UUID = None,
        action_details: Dict[str, Any] = None,
        request: Request = None,
        db: AsyncSession = None,
        success: bool = True,
        error_message: str = None,
        credits_spent: int = 0
    ):
        """Log user activity for audit and analytics (simplified)"""
        if not db:
            return
        
        try:
            # Simple logging using raw SQL for now
            await db.execute(text("""
                INSERT INTO user_activity_logs (
                    user_id, action_type, resource_type, resource_id, 
                    action_details, ip_address, success, error_message, 
                    credits_spent, created_at
                ) VALUES (
                    :user_id, :action_type, :resource_type, :resource_id,
                    :action_details, :ip_address, :success, :error_message,
                    :credits_spent, NOW()
                )
            """), {
                "user_id": str(user_id),
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "action_details": json.dumps(action_details or {}),
                "ip_address": request.client.host if request else None,
                "success": success,
                "error_message": error_message,
                "credits_spent": credits_spent
            })
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log user activity: {e}")
            await db.rollback()
    
    async def log_admin_action(
        self,
        admin_user_id: UUID,
        action_type: str,
        target_user_id: UUID = None,
        old_values: Dict[str, Any] = None,
        new_values: Dict[str, Any] = None,
        reason: str = None,
        severity: str = "info",
        db: AsyncSession = None
    ):
        """Log admin actions for audit trail (simplified)"""
        if not db:
            return
        
        try:
            # Simple admin action logging using raw SQL
            await db.execute(text("""
                INSERT INTO admin_actions_log (
                    admin_user_id, target_user_id, action_type, 
                    old_values, new_values, reason, severity, created_at
                ) VALUES (
                    :admin_user_id, :target_user_id, :action_type,
                    :old_values, :new_values, :reason, :severity, NOW()
                )
            """), {
                "admin_user_id": str(admin_user_id),
                "target_user_id": str(target_user_id) if target_user_id else None,
                "action_type": action_type,
                "old_values": json.dumps(old_values or {}),
                "new_values": json.dumps(new_values or {}),
                "reason": reason,
                "severity": severity
            })
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
            await db.rollback()
    
    async def invalidate_user_cache(self, user_id: UUID):
        """Invalidate user cache when permissions change"""
        if redis_client:
            try:
                cache_key = f"user_permissions:{user_id}"
                redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Failed to invalidate user cache: {e}")

# Global service instance
auth_service = RoleBasedAuthService()

async def get_current_user_with_permissions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Dependency to get current user with full permission data"""
    from app.middleware.auth_middleware import get_current_active_user
    
    # Get basic user from existing auth middleware
    current_user = await get_current_active_user(credentials, db)
    
    # Get enhanced user data with permissions
    user_data = await auth_service.get_user_with_permissions(
        current_user.id, db
    )
    
    # Check account status
    if user_data.get("account_status") != "active":
        raise AuthenticationError("Account is not active")
    
    return user_data

def requires_role(required_role: str):
    """Decorator to require specific role"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                # Try to get from args (for route functions)
                for arg in args:
                    if isinstance(arg, dict) and "role" in arg:
                        current_user = arg
                        break
            
            if not current_user or current_user.get("role") != required_role:
                raise AuthorizationError(f"Role '{required_role}' required")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def requires_role_level(minimum_level: int):
    """Decorator to require minimum role level"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                # Try to get from args
                for arg in args:
                    if isinstance(arg, dict) and "role_level" in arg:
                        current_user = arg
                        break
            
            if not current_user or current_user.get("role_level", 0) < minimum_level:
                raise AuthorizationError(f"Role level {minimum_level} or higher required")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def requires_permission(permission_name: str):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                # Try to get from args
                for arg in args:
                    if isinstance(arg, dict) and "permissions" in arg:
                        current_user = arg
                        break
            
            if not current_user:
                raise AuthenticationError("User authentication required")
            
            permissions = current_user.get("permissions", [])
            if permission_name not in permissions:
                raise AuthorizationError(f"Permission '{permission_name}' required")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def requires_subscription_feature(feature_name: str):
    """Decorator to require subscription feature access"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not current_user or not db:
                raise AuthenticationError("Authentication and database required")
            
            user_id = UUID(current_user["id"])
            feature_access = await auth_service.check_subscription_feature(
                user_id, feature_name, db
            )
            
            if not feature_access["allowed"]:
                upgrade_required = feature_access.get("upgrade_required")
                raise FeatureAccessError(
                    detail=feature_access["reason"],
                    upgrade_required=upgrade_required
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def audit_action(action_type: str, resource_type: str = None):
    """Decorator to automatically log user actions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")
            request = kwargs.get("request")
            
            start_time = datetime.utcnow()
            success = True
            error_message = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                if current_user and db:
                    response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    
                    await auth_service.log_user_activity(
                        user_id=UUID(current_user["id"]),
                        action_type=action_type,
                        resource_type=resource_type,
                        request=request,
                        db=db,
                        success=success,
                        error_message=error_message
                    )
        return wrapper
    return decorator

# Combined decorators for common patterns
def admin_only(permission_name: str = None):
    """Decorator for admin-only endpoints"""
    def decorator(func):
        @requires_role_level(RoleLevel.ADMIN)
        @requires_permission(permission_name) if permission_name else lambda f: f
        @audit_action("admin_action")
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def super_admin_only():
    """Decorator for super admin only endpoints"""
    def decorator(func):
        @requires_role("super_admin")
        @audit_action("super_admin_action")
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator