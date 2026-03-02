"""
Influencer Master Database (IMD) - Pydantic Request/Response Models
Superadmin-managed influencer CRM with pricing, shares, and export support.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class InfluencerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"
    PENDING = "pending"


class TagAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"


class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


class ExportScope(str, Enum):
    ALL = "all"
    SELECTED = "selected"
    FILTERED = "filtered"


class ShareAccessLevel(str, Enum):
    VIEW = "view"
    FULL = "full"


# =============================================================================
# PRICING NESTED MODELS
# =============================================================================

class CostPricingUpdate(BaseModel):
    """Cost pricing fields (what we pay the influencer) in USD cents"""
    cost_post_usd_cents: Optional[int] = None
    cost_story_usd_cents: Optional[int] = None
    cost_reel_usd_cents: Optional[int] = None
    cost_carousel_usd_cents: Optional[int] = None
    cost_video_usd_cents: Optional[int] = None
    cost_bundle_usd_cents: Optional[int] = None
    cost_monthly_usd_cents: Optional[int] = None


class SellPricingUpdate(BaseModel):
    """Sell pricing fields (what we charge the client) in USD cents"""
    sell_post_usd_cents: Optional[int] = None
    sell_story_usd_cents: Optional[int] = None
    sell_reel_usd_cents: Optional[int] = None
    sell_carousel_usd_cents: Optional[int] = None
    sell_video_usd_cents: Optional[int] = None
    sell_bundle_usd_cents: Optional[int] = None
    sell_monthly_usd_cents: Optional[int] = None


# =============================================================================
# INFLUENCER REQUEST MODELS
# =============================================================================

class AddInfluencerRequest(BaseModel):
    """Add a single influencer by username"""
    username: str = Field(..., min_length=1, max_length=255)
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[InfluencerStatus] = InfluencerStatus.ACTIVE
    tier: Optional[str] = None
    cost_pricing: Optional[CostPricingUpdate] = None
    sell_pricing: Optional[SellPricingUpdate] = None


class BulkImportRequest(BaseModel):
    """Bulk import influencers by username list"""
    usernames: List[str] = Field(..., min_items=1, max_items=100)


class InfluencerUpdateRequest(BaseModel):
    """Partial update for an influencer record"""
    full_name: Optional[str] = None
    status: Optional[InfluencerStatus] = None
    tier: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    internal_notes: Optional[str] = None
    cost_pricing: Optional[CostPricingUpdate] = None
    sell_pricing: Optional[SellPricingUpdate] = None
    auto_calculate_sell: Optional[bool] = None
    default_markup_percentage: Optional[float] = None
    package_pricing: Optional[Dict[str, Any]] = None
    volume_discounts: Optional[List[Dict[str, Any]]] = None


class BulkTagRequest(BaseModel):
    """Bulk add/remove tags on multiple influencers"""
    influencer_ids: List[UUID] = Field(..., min_items=1)
    tags: List[str] = Field(..., min_items=1)
    action: TagAction = TagAction.ADD


class BulkPricingUpdate(BaseModel):
    """Per-influencer pricing update within a bulk operation"""
    influencer_id: UUID
    cost_pricing: Optional[CostPricingUpdate] = None
    sell_pricing: Optional[SellPricingUpdate] = None


class BulkPricingRequest(BaseModel):
    """Bulk pricing update for multiple influencers"""
    updates: List[BulkPricingUpdate] = Field(..., min_items=1)


class ExportRequest(BaseModel):
    """Export influencers to CSV or JSON"""
    format: ExportFormat = ExportFormat.CSV
    fields: Optional[Dict[str, bool]] = None
    scope: ExportScope = ExportScope.ALL
    selected_ids: Optional[List[UUID]] = None
    filters: Optional[Dict[str, Any]] = None


# =============================================================================
# SHARE REQUEST MODELS
# =============================================================================

class VisibleFieldsConfig(BaseModel):
    """Configuration for which fields are visible in a share"""
    show_analytics: bool = True
    show_sell_pricing: bool = False
    show_engagement: bool = True
    show_audience: bool = True
    show_content_analysis: bool = True
    show_contact_info: bool = False


class ShareCreateRequest(BaseModel):
    """Create a new influencer access share"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    influencer_ids: List[UUID] = Field(..., min_items=1)
    user_emails: List[str] = Field(..., min_items=1)
    visible_fields: Optional[VisibleFieldsConfig] = None
    duration: Optional[str] = Field("30d", description="Duration string like 7d, 30d, 90d")


class ShareUpdateRequest(BaseModel):
    """Partial update for an existing share"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    influencer_ids: Optional[List[UUID]] = None
    user_emails: Optional[List[str]] = None
    visible_fields: Optional[VisibleFieldsConfig] = None
    duration: Optional[str] = None
    is_active: Optional[bool] = None


class ShareExtendRequest(BaseModel):
    """Extend a share's expiration"""
    expires_at: datetime


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class InfluencerResponse(BaseModel):
    """Full influencer record response"""
    id: UUID
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    profile_image_url: Optional[str] = None
    is_verified: bool = False
    is_private: bool = False

    # Metrics
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    engagement_rate: Optional[float] = None
    avg_likes: int = 0
    avg_comments: int = 0
    avg_views: int = 0

    # CRM
    status: str = "active"
    tier: Optional[str] = None
    categories: List[str] = []
    tags: List[str] = []
    internal_notes: Optional[str] = None

    # Cost pricing
    cost_post_usd_cents: Optional[int] = None
    cost_story_usd_cents: Optional[int] = None
    cost_reel_usd_cents: Optional[int] = None
    cost_carousel_usd_cents: Optional[int] = None
    cost_video_usd_cents: Optional[int] = None
    cost_bundle_usd_cents: Optional[int] = None
    cost_monthly_usd_cents: Optional[int] = None

    # Sell pricing
    sell_post_usd_cents: Optional[int] = None
    sell_story_usd_cents: Optional[int] = None
    sell_reel_usd_cents: Optional[int] = None
    sell_carousel_usd_cents: Optional[int] = None
    sell_video_usd_cents: Optional[int] = None
    sell_bundle_usd_cents: Optional[int] = None
    sell_monthly_usd_cents: Optional[int] = None

    # Auto pricing
    auto_calculate_sell: bool = False
    default_markup_percentage: Optional[float] = None

    # JSON fields
    package_pricing: Optional[Dict[str, Any]] = None
    volume_discounts: Optional[List[Dict[str, Any]]] = None
    platforms: Optional[Dict[str, Any]] = None
    language_distribution: Optional[Dict[str, Any]] = None

    # AI
    ai_content_categories: List[str] = []
    ai_sentiment_score: Optional[float] = None
    ai_audience_quality_score: Optional[float] = None

    # Tracking
    last_analytics_refresh: Optional[datetime] = None
    added_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SharedInfluencerResponse(BaseModel):
    """Influencer response filtered by visible_fields - NEVER includes cost pricing or internal_notes"""
    id: UUID
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    profile_image_url: Optional[str] = None
    is_verified: bool = False
    is_private: bool = False

    # Metrics (always shown)
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0

    # Conditionally shown based on visible_fields
    engagement_rate: Optional[float] = None
    avg_likes: Optional[int] = None
    avg_comments: Optional[int] = None
    avg_views: Optional[int] = None

    # Sell pricing (only if show_sell_pricing)
    sell_post_usd_cents: Optional[int] = None
    sell_story_usd_cents: Optional[int] = None
    sell_reel_usd_cents: Optional[int] = None
    sell_carousel_usd_cents: Optional[int] = None
    sell_video_usd_cents: Optional[int] = None
    sell_bundle_usd_cents: Optional[int] = None
    sell_monthly_usd_cents: Optional[int] = None

    # CRM (safe fields only)
    status: Optional[str] = None
    tier: Optional[str] = None
    categories: List[str] = []
    tags: List[str] = []

    # AI / content (if show_content_analysis)
    ai_content_categories: Optional[List[str]] = None
    ai_sentiment_score: Optional[float] = None
    language_distribution: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ShareResponse(BaseModel):
    """Share configuration response"""
    id: UUID
    name: str
    description: Optional[str] = None
    influencer_ids: List[UUID] = []
    visible_fields: Dict[str, Any] = {}
    duration: Optional[str] = None
    is_active: bool = True
    created_by: UUID
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Populated from join
    shared_with_users: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True
