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
    BRAND_PREMIUM = "brand_premium"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    SUPER_ADMIN = "super_admin"  # Match Supabase role naming


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class BillingType(str, Enum):
    """Billing type for user accounts"""
    ADMIN_MANAGED = "admin_managed"  # Admin creates and manages billing
    ONLINE_PAYMENT = "online_payment"  # User pays directly through Stripe


class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.FREE
    status: UserStatus = UserStatus.ACTIVE
    billing_type: BillingType = BillingType.ONLINE_PAYMENT


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8)
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class UserUpdate(BaseModel):
    """User update model"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    billing_type: Optional[BillingType] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


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
    updated_at: Optional[datetime] = None

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

    # Billing and subscription info
    stripe_customer_id: Optional[str] = None


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


class TeamInfo(BaseModel):
    """Team information for dashboard"""
    id: str
    name: str
    subscription_tier: str
    subscription_status: str
    monthly_limits: Dict[str, int]
    monthly_usage: Dict[str, int]


class SubscriptionInfo(BaseModel):
    """Combined subscription information"""
    tier: str  # Resolved tier (user.role or team.subscription_tier)
    limits: Dict[str, int]
    usage: Dict[str, int]
    is_team_subscription: bool


class UserDashboardStats(BaseModel):
    """User dashboard statistics - DEPRECATED, use UserDashboardResponse"""
    total_searches: int
    searches_this_month: int
    favorite_profiles: List[str]
    recent_searches: List[UserSearchHistory]
    account_created: datetime
    last_active: datetime


class UserDashboardResponse(BaseModel):
    """Complete dashboard response with user context"""
    user: UserResponse
    team: Optional[TeamInfo] = None
    subscription: SubscriptionInfo
    stats: Dict[str, Any]  # Dashboard statistics