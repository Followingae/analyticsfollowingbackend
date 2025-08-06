"""
Authentication models for user management and auth
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User roles for role-based access control"""
    FREE = "free"
    PREMIUM = "premium"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.FREE
    status: UserStatus = UserStatus.ACTIVE


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update model"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class UserInDB(UserBase):
    """User model as stored in database"""
    id: str
    supabase_user_id: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    profile_picture_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = {}
    
    class Config:
        from_attributes = True


class UserResponse(UserBase):
    """User response model (excludes sensitive data)"""
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None
    avatar_config: Optional[Dict[str, Any]] = None
    
    # Profile information fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    
    # Preferences
    timezone: Optional[str] = "UTC"
    language: Optional[str] = "en"


class LoginRequest(BaseModel):
    """Login request model"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation"""
    token: str
    new_password: str = Field(..., min_length=8)


class UserSearchHistory(BaseModel):
    """User search history model"""
    id: str
    user_id: str
    instagram_username: str
    search_timestamp: datetime
    analysis_type: str  # 'basic', 'comprehensive', 'summary'
    search_metadata: Optional[Dict[str, Any]] = {}


class UserSearchHistoryResponse(BaseModel):
    """User search history response"""
    searches: List[UserSearchHistory]
    total_count: int
    page: int
    page_size: int


class UserDashboardStats(BaseModel):
    """User dashboard statistics"""
    total_searches: int
    searches_this_month: int
    favorite_profiles: List[str]
    recent_searches: List[UserSearchHistory]
    account_created: datetime
    last_active: datetime