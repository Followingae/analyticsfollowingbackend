"""
Discovery System Pydantic Models
Data structures for credit-gated discovery and profile unlocking
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field, validator


# ============================================================================
# DISCOVERY SEARCH MODELS
# ============================================================================

class DiscoverySearchCriteria(BaseModel):
    """Search criteria for discovery"""
    platform: Optional[str] = None
    min_followers: Optional[int] = Field(None, ge=0)
    max_followers: Optional[int] = Field(None, ge=0)
    min_engagement: Optional[float] = Field(None, ge=0, le=100)
    max_engagement: Optional[float] = Field(None, ge=0, le=100)
    categories: Optional[List[str]] = []
    languages: Optional[List[str]] = []
    verified: Optional[bool] = None
    business_account: Optional[bool] = None
    barter_eligible: Optional[bool] = None
    search_text: Optional[str] = Field(None, min_length=1, max_length=200)
    
    @validator('max_followers')
    def max_followers_validation(cls, v, values):
        if v is not None and 'min_followers' in values and values['min_followers'] is not None:
            if v < values['min_followers']:
                raise ValueError('max_followers must be greater than or equal to min_followers')
        return v
    
    @validator('max_engagement')
    def max_engagement_validation(cls, v, values):
        if v is not None and 'min_engagement' in values and values['min_engagement'] is not None:
            if v < values['min_engagement']:
                raise ValueError('max_engagement must be greater than or equal to min_engagement')
        return v


class ProfilePreviewData(BaseModel):
    """Preview data available without unlock"""
    username: str
    platform: str
    followers_range: str
    profile_picture_url: Optional[str] = None
    verified: bool = False
    business_account: bool = False
    categories: List[str] = []
    location: Optional[str] = None


class ProfileFullData(BaseModel):
    """Full profile data available after unlock"""
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None
    engagement_rate: Optional[float] = None
    avg_likes: Optional[int] = None
    avg_comments: Optional[int] = None
    full_name: Optional[str] = None
    biography: Optional[str] = None
    external_url: Optional[str] = None
    categories: List[str] = []
    languages: List[str] = []
    sell_price_usd: Optional[int] = None
    min_collaboration_fee: Optional[int] = None
    barter_eligible: bool = False
    ai_content_insights: Optional[Dict[str, Any]] = None


class DiscoveryProfileResult(BaseModel):
    """Single profile result in discovery"""
    profile_id: UUID
    username: str
    platform: str
    is_unlocked: bool
    preview_data: ProfilePreviewData
    full_data: Optional[ProfileFullData] = None


class DiscoveryPaginationInfo(BaseModel):
    """Pagination information for discovery results"""
    current_page: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    total_results: int = Field(..., ge=0)
    results_per_page: int = Field(..., ge=1, le=100)


class DiscoveryCreditsInfo(BaseModel):
    """Credit information for discovery"""
    credits_spent: int = Field(..., ge=0)
    total_credits_consumed: int = Field(..., ge=0)
    free_pages_remaining: int = Field(..., ge=0)
    transaction_id: Optional[int] = None


# ============================================================================
# DISCOVERY SESSION MODELS
# ============================================================================

class DiscoverySessionCreate(BaseModel):
    """Request to start a discovery session"""
    search_criteria: DiscoverySearchCriteria


class DiscoverySessionResponse(BaseModel):
    """Response when starting a discovery session"""
    session_id: UUID
    total_results: int
    results_per_page: int
    first_page: List[DiscoveryProfileResult]
    credits_consumed: int
    free_pages_remaining: int
    search_criteria: DiscoverySearchCriteria


class DiscoveryPageRequest(BaseModel):
    """Request for a specific discovery page"""
    session_id: UUID
    page_number: int = Field(..., ge=1)


class DiscoveryPageResponse(BaseModel):
    """Response for discovery page"""
    results: List[DiscoveryProfileResult]
    pagination: DiscoveryPaginationInfo
    credits_info: DiscoveryCreditsInfo


class DiscoveryErrorResponse(BaseModel):
    """Error response for discovery operations"""
    error: str
    message: str
    credits_required: Optional[int] = None
    wallet_balance: Optional[int] = None


# ============================================================================
# PROFILE UNLOCK MODELS
# ============================================================================

class ProfileUnlockRequest(BaseModel):
    """Request to unlock a profile"""
    profile_id: UUID
    unlock_reason: Optional[str] = Field(None, max_length=500)


class ProfileUnlockResponse(BaseModel):
    """Response after unlocking a profile"""
    unlocked: bool
    unlock_id: Optional[UUID] = None
    credits_spent: int
    transaction_id: Optional[int] = None
    unlocked_at: Optional[datetime] = None
    full_data: Optional[ProfileFullData] = None
    already_unlocked: Optional[bool] = None


class UnlockedProfileSummary(BaseModel):
    """Summary of an unlocked profile"""
    unlock_id: UUID
    unlocked_at: datetime
    credits_spent: int
    profile: DiscoveryProfileResult


# ============================================================================
# DISCOVERY FILTER MODELS
# ============================================================================

class DiscoveryFilterCreate(BaseModel):
    """Request to create a saved discovery filter"""
    filter_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    filter_criteria: DiscoverySearchCriteria


class DiscoveryFilterUpdate(BaseModel):
    """Request to update a saved discovery filter"""
    filter_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    filter_criteria: Optional[DiscoverySearchCriteria] = None


class DiscoveryFilterResponse(BaseModel):
    """Saved discovery filter"""
    filter_id: UUID
    filter_name: str
    description: Optional[str] = None
    filter_criteria: DiscoverySearchCriteria
    usage_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime


# ============================================================================
# DISCOVERY ANALYTICS MODELS
# ============================================================================

class DiscoveryUsageStats(BaseModel):
    """Discovery usage statistics"""
    total_sessions: int
    total_pages_viewed: int
    total_credits_spent: int
    unique_profiles_discovered: int
    profiles_unlocked: int
    avg_session_duration_minutes: Optional[float] = None
    most_used_filters: List[Dict[str, Any]] = []


class DiscoveryTrendData(BaseModel):
    """Discovery trend data over time"""
    date: date
    sessions_count: int
    pages_viewed: int
    credits_consumed: int
    unique_users: int


# ============================================================================
# DISCOVERY API RESPONSE WRAPPERS
# ============================================================================

class DiscoverySearchResponse(BaseModel):
    """Complete discovery search response"""
    success: bool = True
    data: Optional[Union[DiscoverySessionResponse, DiscoveryPageResponse]] = None
    error: Optional[DiscoveryErrorResponse] = None
    message: Optional[str] = None


class ProfileUnlockApiResponse(BaseModel):
    """Complete profile unlock API response"""
    success: bool = True
    data: Optional[ProfileUnlockResponse] = None
    error: Optional[DiscoveryErrorResponse] = None
    message: Optional[str] = None


# ============================================================================
# BULK OPERATIONS MODELS
# ============================================================================

class BulkProfileUnlockRequest(BaseModel):
    """Request to unlock multiple profiles"""
    profile_ids: List[UUID] = Field(..., min_items=1, max_items=10)
    unlock_reason: Optional[str] = Field(None, max_length=500)


class BulkUnlockResult(BaseModel):
    """Result for a single profile in bulk unlock"""
    profile_id: UUID
    success: bool
    credits_spent: int = 0
    unlock_id: Optional[UUID] = None
    error_message: Optional[str] = None
    already_unlocked: bool = False


class BulkProfileUnlockResponse(BaseModel):
    """Response for bulk profile unlock"""
    total_requested: int
    successful_unlocks: int
    already_unlocked: int
    failed_unlocks: int
    total_credits_spent: int
    results: List[BulkUnlockResult]


# ============================================================================
# DISCOVERY EXPORT MODELS
# ============================================================================

class DiscoveryExportRequest(BaseModel):
    """Request to export discovery results"""
    session_id: UUID
    export_format: str = Field(..., pattern="^(csv|xlsx|json)$")
    include_full_data: bool = False  # Only for unlocked profiles
    max_results: Optional[int] = Field(None, ge=1, le=1000)


class DiscoveryExportResponse(BaseModel):
    """Response for discovery export"""
    export_id: UUID
    download_url: str
    expires_at: datetime
    file_size_bytes: int
    records_count: int
    export_format: str