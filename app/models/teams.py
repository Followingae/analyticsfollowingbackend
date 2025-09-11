"""
Team Management Models - B2B SaaS Team Collaboration
Pydantic models for team-based features and authentication
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date
from enum import Enum

class TeamRole(str, Enum):
    """Team member roles"""
    OWNER = "owner"    # Initial subscriber, full control
    MEMBER = "member"  # Invited users, usage access only

class SubscriptionTier(str, Enum):
    """Subscription tier options"""
    FREE = "free"
    STANDARD = "standard"  # $199/month
    PREMIUM = "premium"    # $499/month

class TeamStatus(str, Enum):
    """Team subscription status"""
    ACTIVE = "active"
    TRIAL = "trial" 
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"

# =============================================================================
# TEAM MODELS
# =============================================================================

class TeamCreate(BaseModel):
    """Create new team"""
    name: str = Field(..., min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    settings: Optional[Dict[str, Any]] = None

class TeamUpdate(BaseModel):
    """Update team information"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    settings: Optional[Dict[str, Any]] = None

class TeamResponse(BaseModel):
    """Team information response"""
    id: UUID
    name: str
    company_name: Optional[str]
    subscription_tier: SubscriptionTier
    subscription_status: TeamStatus
    subscription_expires_at: Optional[datetime]
    
    # Limits and usage
    max_team_members: int
    monthly_profile_limit: int
    monthly_email_limit: int
    monthly_posts_limit: int
    
    profiles_used_this_month: int
    emails_used_this_month: int
    posts_used_this_month: int
    
    # Calculated fields
    member_count: int
    remaining_capacity: Dict[str, int] = Field(default_factory=dict)
    
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# =============================================================================
# TEAM MEMBER MODELS  
# =============================================================================

class TeamMemberCreate(BaseModel):
    """Add member to team (internal use)"""
    user_id: UUID
    role: TeamRole = TeamRole.MEMBER
    permissions: Optional[Dict[str, bool]] = None

class TeamMemberUpdate(BaseModel):
    """Update team member"""
    role: Optional[TeamRole] = None
    permissions: Optional[Dict[str, bool]] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|suspended)$")

class TeamMemberResponse(BaseModel):
    """Team member information"""
    id: UUID
    team_id: UUID
    user_id: UUID
    role: TeamRole
    permissions: Dict[str, bool]
    status: str
    
    # User details (would be joined from user table)
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    
    joined_at: datetime
    last_active_at: Optional[datetime]
    
    created_at: datetime
    
    class Config:
        from_attributes = True

# =============================================================================
# TEAM INVITATION MODELS
# =============================================================================

class TeamInvitationCreate(BaseModel):
    """Send team invitation"""
    email: EmailStr
    role: TeamRole = TeamRole.MEMBER
    personal_message: Optional[str] = Field(None, max_length=500)

class TeamInvitationResponse(BaseModel):
    """Team invitation details"""
    id: UUID
    team_id: UUID
    email: str
    role: TeamRole
    status: str
    expires_at: datetime
    personal_message: Optional[str]
    
    invited_by_email: Optional[str] = None
    
    created_at: datetime
    
    class Config:
        from_attributes = True

# =============================================================================
# USAGE TRACKING MODELS
# =============================================================================

class UsageTrackingResponse(BaseModel):
    """Monthly usage tracking"""
    team_id: UUID
    user_id: UUID
    billing_month: date
    
    profiles_analyzed: int
    emails_unlocked: int
    posts_analyzed: int
    
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TeamUsageSummary(BaseModel):
    """Team usage summary"""
    team_id: UUID
    team_name: str
    subscription_tier: SubscriptionTier
    billing_month: date
    
    # Limits
    monthly_limits: Dict[str, int]
    
    # Current usage
    current_usage: Dict[str, int]
    
    # Remaining capacity
    remaining_capacity: Dict[str, int]
    
    # Usage by member
    member_usage: List[Dict[str, Any]]
    
    # Usage percentage
    usage_percentage: Dict[str, float]

# =============================================================================
# TOPUP MODELS
# =============================================================================

class TopupOrderCreate(BaseModel):
    """Create topup order"""
    topup_type: str = Field(..., pattern="^(profiles|emails|posts)$")
    quantity: int = Field(..., gt=0)
    
class TopupOrderResponse(BaseModel):
    """Topup order details"""
    id: UUID
    team_id: UUID
    topup_type: str
    quantity: int
    unit_price: float
    discount_rate: float
    total_price: float
    
    payment_status: str
    status: str
    
    valid_from: date
    valid_until: date
    
    created_at: datetime
    
    class Config:
        from_attributes = True

# =============================================================================
# TEAM CONTEXT MODELS (for responses)
# =============================================================================

class TeamContextResponse(BaseModel):
    """Team context information for frontend"""
    team_id: UUID
    team_name: str
    user_role: TeamRole
    subscription_tier: SubscriptionTier
    subscription_status: TeamStatus
    
    # Usage information
    monthly_limits: Dict[str, int]
    current_usage: Dict[str, int] 
    remaining_capacity: Dict[str, int]
    
    # User permissions
    user_permissions: Dict[str, bool]
    
    # Subscription info
    subscription_expires_at: Optional[datetime]
    billing_cycle_start: Optional[date]
    billing_cycle_end: Optional[date]

class RolePermissions(BaseModel):
    """Role-based permissions definition"""
    role: TeamRole
    permissions: Dict[str, bool]
    description: str

# =============================================================================
# ERROR RESPONSE MODELS
# =============================================================================

class TeamErrorResponse(BaseModel):
    """Team-related error response"""
    error: str
    message: str
    team_context: Optional[Dict[str, Any]] = None
    upgrade_required: Optional[SubscriptionTier] = None
    
class UsageLimitErrorResponse(BaseModel):
    """Usage limit exceeded error"""
    error: str = "usage_limit_exceeded"
    message: str
    usage_type: str
    current_usage: int
    limit: int
    available: int
    subscription_tier: SubscriptionTier
    upgrade_options: Optional[Dict[str, Any]] = None

# =============================================================================
# SUBSCRIPTION TIER DEFINITIONS
# =============================================================================

SUBSCRIPTION_TIER_LIMITS = {
    SubscriptionTier.FREE: {
        "max_team_members": 1,
        "monthly_profile_limit": 5,
        "monthly_email_limit": 0,
        "monthly_posts_limit": 0,
        "price_per_month": 0,
        "topup_discount": 0.0,
        "features": ["basic_analytics"]
    },
    SubscriptionTier.STANDARD: {
        "max_team_members": 2,
        "monthly_profile_limit": 500,
        "monthly_email_limit": 250,
        "monthly_posts_limit": 125,
        "price_per_month": 199,
        "topup_discount": 0.0,
        "features": ["full_analytics", "campaigns", "lists", "export", "priority_support"]
    },
    SubscriptionTier.PREMIUM: {
        "max_team_members": 5,
        "monthly_profile_limit": 2000,
        "monthly_email_limit": 800,
        "monthly_posts_limit": 300,
        "price_per_month": 499,
        "topup_discount": 0.2,  # 20% discount
        "features": ["full_analytics", "campaigns", "lists", "export", "priority_support", "topup_discount"]
    },
    # CRITICAL FIX: Add professional tier for existing users
    "professional": {
        "max_team_members": 5,
        "monthly_profile_limit": 2000,
        "monthly_email_limit": 800,
        "monthly_posts_limit": 300,
        "price_per_month": 499,
        "topup_discount": 0.2,  # 20% discount
        "features": ["full_analytics", "campaigns", "lists", "export", "priority_support", "topup_discount"]
    }
}

TEAM_ROLE_PERMISSIONS = {
    TeamRole.OWNER: {
        "can_invite_members": True,
        "can_remove_members": True,
        "can_manage_team": True,
        "can_view_billing": True,
        "can_purchase_topups": True,
        "can_cancel_subscription": True,
        "can_export_data": True,
        "can_manage_campaigns": True,
        "can_manage_lists": True,
        "can_view_usage": True,
        "can_analyze_profiles": True,
        "can_unlock_emails": True,
        "can_analyze_posts": True
    },
    TeamRole.MEMBER: {
        "can_invite_members": False,
        "can_remove_members": False,
        "can_manage_team": False,
        "can_view_billing": False,
        "can_purchase_topups": False,
        "can_cancel_subscription": False,
        "can_export_data": True,
        "can_manage_campaigns": True,
        "can_manage_lists": True,
        "can_view_usage": True,
        "can_analyze_profiles": True,
        "can_unlock_emails": True,
        "can_analyze_posts": True
    }
}