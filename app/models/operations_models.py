"""
Campaign Operations OS Models
Complete data models for campaign management system
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from uuid import UUID
from enum import Enum


# Enums for Operations OS
class WorkstreamType(str, Enum):
    UGC = "ugc"
    INFLUENCER_PAID = "influencer_paid"
    INFLUENCER_BARTER = "influencer_barter"
    VIDEO_SHOOT = "video_shoot"
    PHOTO_SHOOT = "photo_shoot"
    EVENT_ACTIVATION = "event_activation"
    HYBRID = "hybrid"


class DeliverableType(str, Enum):
    VIDEO = "video"
    REEL = "reel"
    STORY_SET = "story_set"
    PHOTO_SET = "photo_set"
    EVENT_CONTENT = "event_content"
    OTHER = "other"


class DeliverableStatus(str, Enum):
    IDEA = "IDEA"
    DRAFTING = "DRAFTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    IN_PRODUCTION = "IN_PRODUCTION"
    EDITING = "EDITING"
    IN_REVIEW = "IN_REVIEW"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    READY_TO_POST = "READY_TO_POST"
    POSTED = "POSTED"
    ARCHIVED = "ARCHIVED"


class ApprovalStatus(str, Enum):
    NOT_SENT = "NOT_SENT"
    SENT_TO_CLIENT = "SENT_TO_CLIENT"
    CLIENT_COMMENTED = "CLIENT_COMMENTED"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class EventStatus(str, Enum):
    PLANNING = "planning"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PayoutStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


class EnrollmentStatus(str, Enum):
    SELECTED = "SELECTED"
    INVITED = "INVITED"
    ATTENDED = "ATTENDED"
    CONTENT_READY = "CONTENT_READY"
    POSTED = "POSTED"


# Permission Models
class OperationsPermissions(BaseModel):
    """User permissions for Operations OS"""
    view_internal_notes: bool = False
    view_finance: bool = False
    view_banking: bool = False
    create_workstreams: bool = False
    create_deliverables: bool = False
    approve_concepts: bool = False
    manage_production: bool = False
    manage_events: bool = False
    export_data: bool = False
    bulk_operations: bool = False
    access_settings: bool = False
    bypass_approvals: bool = False


class OperationsAccess(BaseModel):
    """Complete access control response"""
    user_id: str
    email: str
    role: str
    subscription_tier: str
    operations_access: OperationsPermissions
    campaign_access: List[Dict[str, str]] = []
    team_id: Optional[str] = None
    is_team_admin: bool = False


# Campaign Models
class CampaignBase(BaseModel):
    """Base campaign model"""
    brand_id: str
    brand_name: str
    campaign_name: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    status: Literal["planning", "active", "completed", "archived"] = "planning"


class CampaignCreate(CampaignBase):
    """Campaign creation request"""
    pass


class CampaignUpdate(BaseModel):
    """Campaign update request"""
    campaign_name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[Literal["planning", "active", "completed", "archived"]] = None


class CampaignResponse(CampaignBase):
    """Campaign response with metadata"""
    id: str
    total_deliverables: int = 0
    completed_deliverables: int = 0
    pending_approvals: int = 0
    overdue_posts: int = 0
    upcoming_shoots: int = 0
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    _access: Optional[Dict[str, Any]] = None


class CampaignOverview(BaseModel):
    """Campaign overview dashboard data"""
    campaign_id: str
    summary: Dict[str, int]
    this_week: Dict[str, List[Dict[str, Any]]]
    blockers: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
    quick_stats: Dict[str, Any]
    _access: Dict[str, str]


# Workstream Models
class WorkstreamBase(BaseModel):
    """Base workstream model"""
    campaign_id: str
    type: WorkstreamType
    name: str
    description: Optional[str] = None
    status: Literal["draft", "active", "completed", "archived"] = "draft"


class WorkstreamCreate(WorkstreamBase):
    """Workstream creation request (SUPERADMIN ONLY)"""
    budget_allocated: Optional[float] = None
    internal_notes: Optional[str] = None


class WorkstreamUpdate(BaseModel):
    """Workstream update request"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["draft", "active", "completed", "archived"]] = None
    budget_allocated: Optional[float] = None
    internal_notes: Optional[str] = None


class WorkstreamResponse(WorkstreamBase):
    """Workstream response with role-based fields"""
    id: str
    deliverables_count: int = 0
    completion_percentage: float = 0.0
    pending_approvals: int = 0
    next_milestone: Optional[Dict[str, Any]] = None
    # Superadmin-only fields
    budget_allocated: Optional[float] = None
    budget_spent: Optional[float] = None
    internal_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    _access: Optional[Dict[str, Any]] = None


# Deliverable Models
class DeliverableBase(BaseModel):
    """Base deliverable model"""
    workstream_id: str
    campaign_id: str
    title: str
    description: Optional[str] = None
    type: DeliverableType
    status: DeliverableStatus = DeliverableStatus.IDEA
    due_date: Optional[date] = None
    posting_date: Optional[date] = None


class DeliverableCreate(DeliverableBase):
    """Deliverable creation request (SUPERADMIN ONLY)"""
    internal_notes: Optional[str] = None


class DeliverableUpdate(BaseModel):
    """Deliverable update request"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[DeliverableStatus] = None
    due_date: Optional[date] = None
    posting_date: Optional[date] = None
    internal_notes: Optional[str] = None
    client_notes: Optional[str] = None


class AssetInfo(BaseModel):
    """Asset information for deliverables"""
    frame_io_folder: Optional[str] = None  # SUPERADMIN ONLY
    frame_io_share_link: Optional[str] = None  # Available to all
    hd_updated: bool = False
    hd_updated_at: Optional[datetime] = None
    hd_updated_by: Optional[str] = None  # SUPERADMIN ONLY
    versions: List[Dict[str, Any]] = []
    raw_files: List[str] = []  # SUPERADMIN ONLY
    edited_files: List[str] = []


class PostingProof(BaseModel):
    """Posting proof for deliverables"""
    platform: Literal["instagram", "tiktok", "youtube", "other"]
    url: str
    posted_at: Optional[datetime] = None
    metrics_snapshot: Optional[Dict[str, int]] = None


class DeliverableResponse(DeliverableBase):
    """Deliverable response with role-based fields"""
    id: str
    concept_id: Optional[str] = None
    assignment_id: Optional[str] = None
    production_batch_id: Optional[str] = None
    assets: Optional[AssetInfo] = None
    posting_proof: Optional[PostingProof] = None
    dependencies: List[Dict[str, Any]] = []
    internal_notes: Optional[str] = None  # SUPERADMIN ONLY
    client_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    last_modified_by: Optional[str] = None
    _access: Optional[Dict[str, Any]] = None


class BulkDeliverableOperation(BaseModel):
    """Bulk operation request (SUPERADMIN ONLY)"""
    type: Literal["status_change", "assign_creator", "schedule_batch", "delete"]
    target_ids: List[str]
    params: Dict[str, Any]


# Concept Models
class ConceptBase(BaseModel):
    """Base concept model"""
    workstream_id: str
    campaign_id: str
    title: str
    hook: Optional[str] = None
    script: Optional[str] = None
    on_screen_text: Optional[str] = None
    reference_links: List[str] = []
    key_messages: List[str] = []
    purpose: Optional[str] = None
    pillar: Optional[str] = None


class ConceptCreate(ConceptBase):
    """Concept creation request (SUPERADMIN ONLY)"""
    internal_version: Optional[str] = None
    client_facing_version: Optional[str] = None


class ConceptUpdate(BaseModel):
    """Concept update request"""
    title: Optional[str] = None
    hook: Optional[str] = None
    script: Optional[str] = None
    on_screen_text: Optional[str] = None
    reference_links: Optional[List[str]] = None
    key_messages: Optional[List[str]] = None
    purpose: Optional[str] = None
    pillar: Optional[str] = None
    internal_version: Optional[str] = None
    client_facing_version: Optional[str] = None


class ConceptApproval(BaseModel):
    """Concept approval/rejection request"""
    decision: Literal["approve", "request_changes"]
    comment: str
    is_internal: bool = False  # Only super_admin can set this


class ConceptComment(BaseModel):
    """Comment on concept"""
    id: str
    user_id: str
    user_name: str
    user_role: str
    comment: str
    timestamp: datetime
    is_internal: bool = False


class ConceptResponse(ConceptBase):
    """Concept response with role-based fields"""
    id: str
    internal_version: Optional[str] = None  # SUPERADMIN ONLY
    client_facing_version: Optional[str] = None
    approval_status: ApprovalStatus
    approval_history: List[Dict[str, Any]] = []
    comments: List[ConceptComment] = []
    deliverable_ids: List[str] = []
    created_at: datetime
    updated_at: datetime
    created_by: str
    _access: Optional[Dict[str, Any]] = None


# Production Models
class ProductionBatch(BaseModel):
    """Production batch for shoots"""
    id: str
    workstream_id: str
    campaign_id: str
    name: str
    date: date
    location: str
    call_time: Optional[str] = None  # SUPERADMIN ONLY
    wrap_time: Optional[str] = None  # SUPERADMIN ONLY
    roster: Optional[List[Dict[str, str]]] = None  # SUPERADMIN ONLY
    deliverable_ids: List[str] = []  # SUPERADMIN ONLY
    deliverable_count: int = 0
    checklist_items: Optional[List[Dict[str, Any]]] = None  # SUPERADMIN ONLY
    status_summary: Dict[str, int]
    internal_notes: Optional[str] = None  # SUPERADMIN ONLY
    created_at: datetime
    updated_at: datetime
    _access: Optional[Dict[str, Any]] = None


# Event Models
class EventBase(BaseModel):
    """Base event model"""
    campaign_id: str
    workstream_id: Optional[str] = None
    name: str
    date: date
    venue: str
    type: Literal["activation", "shoot", "experience", "other"]
    status: EventStatus = EventStatus.PLANNING


class EventCreate(EventBase):
    """Event creation request (SUPERADMIN ONLY)"""
    barter_type: Optional[Literal["tickets", "products", "both"]] = None
    barter_inventory: Optional[int] = None
    internal_notes: Optional[str] = None


class EventEnrollment(BaseModel):
    """Event enrollment"""
    id: str
    creator_username: str
    creator_name: Optional[str] = None  # SUPERADMIN ONLY
    status: EnrollmentStatus
    barter_given: Optional[Dict[str, Any]] = None  # SUPERADMIN ONLY
    attendance_confirmed: bool = False
    content_ready: bool = False
    posting_urls: List[str] = []
    compliance_status: Literal["pending", "compliant", "overdue", "violation"]


class EventResponse(EventBase):
    """Event response with role-based fields"""
    id: str
    barter_type: Optional[Literal["tickets", "products", "both"]] = None
    barter_inventory: Optional[int] = None  # SUPERADMIN ONLY
    barter_allocated: Optional[int] = None  # SUPERADMIN ONLY
    shortlist: Optional[List[Dict[str, Any]]] = None  # SUPERADMIN ONLY
    enrollments: List[EventEnrollment] = []
    summary: Dict[str, int]
    internal_notes: Optional[str] = None  # SUPERADMIN ONLY
    created_at: datetime
    updated_at: datetime
    _access: Optional[Dict[str, Any]] = None


# Finance Models (SUPERADMIN ONLY)
class PayoutRequest(BaseModel):
    """Payout request (SUPERADMIN ONLY)"""
    creator_id: str
    amount: float
    currency: str = "USD"
    payment_method: Literal["bank_transfer", "paypal", "other"]
    banking_details: Optional[Dict[str, str]] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None


class PayoutResponse(BaseModel):
    """Payout response (SUPERADMIN ONLY)"""
    id: str
    campaign_id: str
    creator_id: str
    creator_name: str
    amount: float
    currency: str
    status: PayoutStatus
    payment_method: str
    banking_details: Optional[Dict[str, str]] = None
    invoice_number: Optional[str] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    _access: Optional[Dict[str, Any]] = None


# Settings Models (SUPERADMIN ONLY)
class CampaignSettings(BaseModel):
    """Campaign settings (SUPERADMIN ONLY)"""
    visibility: Dict[str, bool]
    approvals: Dict[str, Any]
    templates: Dict[str, str]
    notifications: Dict[str, bool]
    client_users: List[Dict[str, Any]]
    _access: Optional[Dict[str, Any]] = None


# Activity Models
class ActivityEntry(BaseModel):
    """Activity log entry"""
    id: str
    campaign_id: str
    workstream_id: Optional[str] = None
    deliverable_id: Optional[str] = None
    type: str
    actor_id: str
    actor_name: str
    actor_role: str
    action: str
    details: Dict[str, Any]
    timestamp: datetime
    is_client_visible: bool


# List Response Models
class WorkstreamListResponse(BaseModel):
    """List of workstreams"""
    workstreams: List[WorkstreamResponse]
    _access: Dict[str, Any]


class DeliverableListResponse(BaseModel):
    """List of deliverables"""
    deliverables: List[DeliverableResponse]
    _access: Dict[str, Any]


class ConceptListResponse(BaseModel):
    """List of concepts"""
    concepts: List[ConceptResponse]
    _access: Dict[str, Any]


class EventListResponse(BaseModel):
    """List of events"""
    events: List[EventResponse]
    _access: Dict[str, Any]


class ActivityListResponse(BaseModel):
    """List of activities"""
    activities: List[ActivityEntry]
    total: int
    page: int
    has_more: bool
    _access: Dict[str, Any]