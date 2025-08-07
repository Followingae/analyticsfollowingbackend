"""
Pydantic models for My Lists API
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

# =============================================================================
# BASE MODELS
# =============================================================================

class ProfileSummary(BaseModel):
    """Simplified profile data for list items"""
    id: UUID
    username: str
    full_name: Optional[str] = None
    followers_count: Optional[int] = None
    is_verified: Optional[bool] = False
    profile_pic_url: Optional[str] = None
    engagement_rate: Optional[float] = None
    category: Optional[str] = None

# =============================================================================
# LIST MODELS
# =============================================================================

class UserListCreate(BaseModel):
    """Request model for creating a new list"""
    name: str = Field(..., min_length=1, max_length=255, description="List name")
    description: Optional[str] = Field(None, max_length=1000, description="List description")
    color: Optional[str] = Field("#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    icon: Optional[str] = Field("list", max_length=50, description="Icon identifier")
    is_favorite: Optional[bool] = Field(False, description="Mark as favorite list")

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

class UserListUpdate(BaseModel):
    """Request model for updating a list"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)
    is_favorite: Optional[bool] = None

    @validator('name')
    def validate_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Name cannot be empty')
        return v.strip() if v else v

class UserListItemResponse(BaseModel):
    """Response model for list items"""
    id: UUID
    position: int
    notes: Optional[str] = None
    tags: List[str] = []
    is_pinned: bool = False
    color_label: Optional[str] = None
    added_at: datetime
    updated_at: datetime
    profile: ProfileSummary

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    """Response model for lists"""
    id: UUID
    name: str
    description: Optional[str] = None
    color: str
    icon: str
    is_public: bool = False
    is_favorite: bool = False
    sort_order: int = 0
    items_count: int = 0
    last_updated: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[UserListItemResponse] = []

    class Config:
        from_attributes = True

class UserListSummary(BaseModel):
    """Simplified list data for list overviews"""
    id: UUID
    name: str
    description: Optional[str] = None
    color: str
    icon: str
    is_public: bool = False
    is_favorite: bool = False
    sort_order: int = 0
    items_count: int = 0
    last_updated: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# =============================================================================
# LIST ITEM MODELS
# =============================================================================

class UserListItemCreate(BaseModel):
    """Request model for adding item to list"""
    profile_id: Optional[UUID] = Field(None, description="Profile UUID to add")
    profile_username: Optional[str] = Field(None, min_length=1, max_length=255, description="Profile username to add")
    position: Optional[int] = Field(0, ge=0, description="Position in list")
    notes: Optional[str] = Field(None, max_length=1000, description="User notes")
    tags: Optional[List[str]] = Field([], description="User tags")
    is_pinned: Optional[bool] = Field(False, description="Pin to top")
    color_label: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Color label")

    @validator('profile_username')
    def validate_profile_identifier(cls, v, values):
        profile_id = values.get('profile_id')
        if not profile_id and not v:
            raise ValueError('Either profile_id or profile_username must be provided')
        if profile_id and v:
            raise ValueError('Provide either profile_id or profile_username, not both')
        return v

class UserListItemUpdate(BaseModel):
    """Request model for updating list item"""
    position: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None
    color_label: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

class UserListItemBulkCreate(BaseModel):
    """Request model for bulk adding profiles to list"""
    profile_ids: Optional[List[UUID]] = Field(None, min_items=1, max_items=50, description="Profile UUIDs to add")
    profile_usernames: Optional[List[str]] = Field(None, min_items=1, max_items=50, description="Profile usernames to add")
    notes: Optional[str] = Field(None, max_length=1000, description="Default notes for all items")
    tags: Optional[List[str]] = Field([], description="Default tags for all items")

    @validator('profile_usernames')
    def validate_bulk_identifiers(cls, v, values):
        profile_ids = values.get('profile_ids')
        if not profile_ids and not v:
            raise ValueError('Either profile_ids or profile_usernames must be provided')
        if profile_ids and v:
            raise ValueError('Provide either profile_ids or profile_usernames, not both')
        return v

# =============================================================================
# OPERATION MODELS
# =============================================================================

class ListReorderItem(BaseModel):
    """Item position for reordering"""
    item_id: UUID
    position: int = Field(..., ge=0)

class ListReorderRequest(BaseModel):
    """Request model for reordering list items"""
    item_positions: List[ListReorderItem] = Field(..., min_items=1, max_items=1000)

class ListDuplicateRequest(BaseModel):
    """Request model for duplicating a list"""
    name: str = Field(..., min_length=1, max_length=255, description="Name for the new list")
    include_items: Optional[bool] = Field(True, description="Include all items in duplicate")

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

class BulkOperationRequest(BaseModel):
    """Request model for bulk list operations"""
    operation: str = Field(..., pattern="^(delete|favorite|unfavorite)$", description="Operation to perform")
    list_ids: List[UUID] = Field(..., min_items=1, max_items=50, description="List IDs to operate on")

# =============================================================================
# RESPONSE WRAPPER MODELS
# =============================================================================

class PaginationInfo(BaseModel):
    """Pagination metadata"""
    current_page: int
    total_pages: int
    total_items: int
    items_per_page: int
    has_next: bool = False
    has_prev: bool = False

class UserListsResponse(BaseModel):
    """Response wrapper for lists with pagination"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "lists": [],
                    "pagination": {
                        "current_page": 1,
                        "total_pages": 2,
                        "total_items": 25,
                        "items_per_page": 20,
                        "has_next": True,
                        "has_prev": False
                    }
                }
            }
        }

class SingleListResponse(BaseModel):
    """Response wrapper for single list"""
    success: bool = True
    data: UserListResponse
    message: Optional[str] = None

class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    success: bool = True
    data: Dict[str, int] = Field(default_factory=dict)
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "added_count": 3,
                    "skipped_count": 1,
                    "processed_count": 4
                },
                "message": "Bulk operation completed"
            }
        }

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "validation_error",
                "message": "Invalid request data",
                "details": {
                    "name": ["Name is required"]
                }
            }
        }

# =============================================================================
# ANALYTICS MODELS
# =============================================================================

class ListAnalyticsSummary(BaseModel):
    """List analytics summary"""
    total_profiles: int
    total_followers: int
    average_engagement_rate: float
    verified_count: int
    categories: Dict[str, int] = Field(default_factory=dict)

class ListAnalyticsResponse(BaseModel):
    """Response for list analytics"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "list_summary": {
                        "total_profiles": 12,
                        "total_followers": 1250000,
                        "average_engagement_rate": 4.2,
                        "verified_count": 8
                    },
                    "top_performers": [],
                    "categories": {"fitness": 5, "lifestyle": 7}
                }
            }
        }

class AvailableProfilesResponse(BaseModel):
    """Response for available profiles that can be added to lists"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "profiles": [],
                    "pagination": {
                        "current_page": 1,
                        "total_pages": 5,
                        "total_items": 89,
                        "items_per_page": 20
                    }
                }
            }
        }