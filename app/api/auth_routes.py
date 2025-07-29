"""
Authentication API routes
Comprehensive user authentication, registration, and management endpoints
"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from typing import Optional, List
from datetime import datetime
import logging

from app.models.auth import (
    UserCreate, UserResponse, LoginRequest, LoginResponse,
    TokenRefreshRequest, PasswordResetRequest, PasswordResetConfirm,
    UserInDB, UserDashboardStats, UserSearchHistoryResponse
)
from app.services.supabase_auth_service import supabase_auth_service as auth_service
from app.middleware.auth_middleware import (
    get_current_user, get_current_active_user, get_optional_user,
    require_premium, require_admin, check_user_rate_limit,
    security
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/health")
async def auth_health_check():
    """Dedicated auth service health check"""
    return await auth_service.health_check()


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, background_tasks: BackgroundTasks):
    """
    Register a new user account
    
    - **email**: Valid email address
    - **password**: Minimum 8 characters
    - **full_name**: Optional full name
    - **role**: Default is 'free'
    
    Returns user profile (email verification required for activation)
    """
    try:
        # Initialize auth service if not already done
        if not auth_service.initialized:
            await auth_service.initialize()
        
        user = await auth_service.register_user(user_data)
        
        # TODO: Send welcome email in background
        # background_tasks.add_task(send_welcome_email, user.email)
        
        logger.info(f"New user registered: {user.email}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=LoginResponse)
async def login_user(login_data: LoginRequest):
    """
    Authenticate user and return access tokens
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token and refresh token
    """
    try:
        # Initialize auth service if not already done
        if not auth_service.initialized:
            await auth_service.initialize()
        
        response = await auth_service.login_user(login_data)
        
        logger.info(f"User logged in: {login_data.email}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        import traceback
        logger.error(f"Login exception traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/refresh")
async def refresh_token(refresh_data: TokenRefreshRequest):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token
    
    Returns new access token
    """
    # TODO: Implement token refresh logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not yet implemented"
    )


@router.post("/logout")
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout user and invalidate tokens
    """
    try:
        token = credentials.credentials
        success = await auth_service.logout_user(token)
        
        if success:
            return {"message": "Successfully logged out"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Logout failed"
            )
            
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: UserInDB = Depends(get_current_active_user)):
    """
    Get current user's profile information
    
    Requires valid authentication token
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        status=current_user.status,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        profile_picture_url=current_user.profile_picture_url
    )


@router.get("/dashboard", response_model=UserDashboardStats)
async def get_user_dashboard(current_user: UserInDB = Depends(get_current_active_user)):
    """
    Get comprehensive dashboard statistics for authenticated user
    
    Returns:
    - Total searches performed
    - Searches this month
    - Recent search history
    - Account statistics
    """
    try:
        stats = await auth_service.get_user_dashboard_stats(current_user.id)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get dashboard stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard data"
        )


@router.get("/search-history", response_model=UserSearchHistoryResponse)
async def get_search_history(
    page: int = 1,
    page_size: int = 20,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get user's search history with pagination
    
    - **page**: Page number (starts at 1)
    - **page_size**: Number of results per page (max 100)
    """
    try:
        if page_size > 100:
            page_size = 100
        
        searches = await auth_service.get_user_search_history(
            current_user.id, page, page_size
        )
        
        # Get total count for pagination info
        # TODO: Implement efficient count query
        total_count = len(searches)  # Simplified for now
        
        return UserSearchHistoryResponse(
            searches=searches,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to get search history for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load search history"
        )


@router.post("/forgot-password")
async def request_password_reset(reset_data: PasswordResetRequest, background_tasks: BackgroundTasks):
    """
    Request password reset email
    
    - **email**: User's email address
    
    Sends password reset email if account exists
    """
    # TODO: Implement password reset logic
    # background_tasks.add_task(send_password_reset_email, reset_data.email)
    
    # Always return success for security (don't reveal if email exists)
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def confirm_password_reset(reset_data: PasswordResetConfirm):
    """
    Confirm password reset with token
    
    - **token**: Password reset token from email
    - **new_password**: New password (minimum 8 characters)
    """
    # TODO: Implement password reset confirmation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset not yet implemented"
    )


@router.get("/verify-email/{token}")
async def verify_email(token: str):
    """
    Verify user's email address
    
    - **token**: Email verification token from registration email
    """
    # TODO: Implement email verification
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email verification not yet implemented"
    )


# ADMIN ENDPOINTS

@router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_all_users(
    page: int = 1,
    page_size: int = 50,
    current_user: UserInDB = Depends(require_admin())
):
    """
    Admin endpoint: List all users
    
    Requires admin role
    """
    # TODO: Implement admin user listing
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Admin user listing not yet implemented"
    )


@router.put("/admin/users/{user_id}/status", dependencies=[Depends(require_admin)])
async def update_user_status(
    user_id: str,
    new_status: str,
    current_user: UserInDB = Depends(require_admin())
):
    """
    Admin endpoint: Update user account status
    
    - **user_id**: Target user ID
    - **new_status**: New status (active, inactive, suspended)
    
    Requires admin role
    """
    # TODO: Implement user status updates
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User status updates not yet implemented"
    )


# PREMIUM FEATURES

@router.get("/premium/analytics", dependencies=[Depends(require_premium)])
async def get_premium_analytics(current_user: UserInDB = Depends(require_premium())):
    """
    Premium endpoint: Advanced analytics and insights
    
    Requires premium or admin role
    """
    return {
        "message": "Premium analytics feature",
        "user_role": current_user.role,
        "advanced_features": [
            "Unlimited searches",
            "Historical data tracking",
            "Advanced export options",
            "Priority support"
        ]
    }


# RATE LIMITED ENDPOINTS

@router.get("/rate-limited-test", dependencies=[Depends(check_user_rate_limit)])
async def rate_limited_endpoint(current_user: UserInDB = Depends(check_user_rate_limit)):
    """
    Test endpoint with rate limiting
    
    Rate limits based on user role:
    - Free: 100 requests/hour
    - Premium: 1000 requests/hour  
    - Admin: 10000 requests/hour
    """
    return {
        "message": "Rate limited endpoint accessed successfully",
        "user_role": current_user.role,
        "timestamp": datetime.utcnow().isoformat()
    }