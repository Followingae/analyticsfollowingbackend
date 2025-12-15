"""
Standardized Subscription and Role Models
Defines the exact tiers and permissions for the platform
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel

class SubscriptionTier(str, Enum):
    """Standardized subscription tiers"""
    FREE = "free"           # Free tier - 5 profiles/month
    STANDARD = "standard"   # $199/month - 500 profiles, 250 emails, 125 posts
    PREMIUM = "premium"     # $499/month - 2000 profiles, 800 emails, 300 posts

class UserRole(str, Enum):
    """User roles - separate from subscription"""
    USER = "user"           # Regular user (any subscription tier)
    SUPER_ADMIN = "super_admin"  # SuperAdmin with full control

class BillingType(str, Enum):
    """Billing type for users"""
    STRIPE = "stripe"       # Self-service via Stripe (can manage own subscription)
    OFFLINE = "offline"     # Manual billing by SuperAdmin (no Stripe access)

class FeaturePermission(str, Enum):
    """ACTUAL platform modules that can be toggled - NOT internal processes like AI"""
    CREATOR_SEARCH = "creator_search"  # Search and analyze Instagram profiles (AI built-in)
    POST_ANALYTICS = "post_analytics"  # Individual post analysis (AI built-in)
    BULK_EXPORT = "bulk_export"  # Export unlocked profiles/posts to CSV/Excel
    CAMPAIGN_MANAGEMENT = "campaign_management"  # Create and manage campaigns
    TEAM_MANAGEMENT = "team_management"  # Add team members
    DISCOVERY = "discovery"  # Browse and unlock profiles from database
    API_ACCESS = "api_access"  # Programmatic API access
    EMAIL_UNLOCK = "email_unlock"  # Unlock creator email addresses
    LISTS_MANAGEMENT = "lists_management"  # Create and manage creator lists

class SubscriptionLimits(BaseModel):
    """Monthly limits for each tier"""
    profiles_per_month: int
    emails_per_month: int
    posts_per_month: int
    team_members: int
    api_calls_per_month: Optional[int] = None
    bulk_export_enabled: bool = True
    campaign_management_enabled: bool = True
    lists_enabled: bool = True

# Define limits for each tier
TIER_LIMITS: Dict[SubscriptionTier, SubscriptionLimits] = {
    SubscriptionTier.FREE: SubscriptionLimits(
        profiles_per_month=5,
        emails_per_month=0,
        posts_per_month=0,
        team_members=1,
        api_calls_per_month=None,
        bulk_export_enabled=False,
        campaign_management_enabled=False,
        lists_enabled=False
    ),
    SubscriptionTier.STANDARD: SubscriptionLimits(
        profiles_per_month=500,
        emails_per_month=250,
        posts_per_month=125,
        team_members=2,
        api_calls_per_month=10000,
        bulk_export_enabled=True,
        campaign_management_enabled=True,
        lists_enabled=True
    ),
    SubscriptionTier.PREMIUM: SubscriptionLimits(
        profiles_per_month=2000,
        emails_per_month=800,
        posts_per_month=300,
        team_members=5,
        api_calls_per_month=50000,
        bulk_export_enabled=True,
        campaign_management_enabled=True,
        lists_enabled=True
    )
}

class CreditTopupPackage(BaseModel):
    """Predefined credit topup packages for SuperAdmin"""
    name: str
    credits: int
    description: str
    expires_in_days: Optional[int] = None  # None means no expiry

# Predefined topup packages
TOPUP_PACKAGES = {
    "starter_100": CreditTopupPackage(
        name="Starter Pack",
        credits=100,
        description="Small credit boost",
        expires_in_days=30
    ),
    "standard_500": CreditTopupPackage(
        name="Standard Pack",
        credits=500,
        description="Standard credit package",
        expires_in_days=60
    ),
    "premium_1000": CreditTopupPackage(
        name="Premium Pack",
        credits=1000,
        description="Large credit package",
        expires_in_days=90
    ),
    "enterprise_5000": CreditTopupPackage(
        name="Enterprise Pack",
        credits=5000,
        description="Enterprise credit package",
        expires_in_days=180
    ),
    "bonus": CreditTopupPackage(
        name="Bonus Credits",
        credits=0,  # Custom amount
        description="Special bonus or compensation",
        expires_in_days=None
    )
}