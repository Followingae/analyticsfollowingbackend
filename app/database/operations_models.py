"""
Campaign Operations OS Database Models
SQLAlchemy models for campaign management system
"""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, JSON,
    ForeignKey, DateTime, Date, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from app.database.connection import Base


# Enums
class CampaignStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class WorkstreamStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DeliverableStatusEnum(str, enum.Enum):
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


class ApprovalStatusEnum(str, enum.Enum):
    NOT_SENT = "NOT_SENT"
    SENT_TO_CLIENT = "SENT_TO_CLIENT"
    CLIENT_COMMENTED = "CLIENT_COMMENTED"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


# Campaign Operations Tables
class Campaign(Base):
    """Main campaign table"""
    __tablename__ = 'ops_campaigns'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    brand_name = Column(String(255), nullable=False)
    campaign_name = Column(String(255), nullable=False)
    description = Column(Text)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.PLANNING, nullable=False)

    # Settings (SUPERADMIN ONLY)
    settings = Column(JSON, default={})

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id'), nullable=False, index=True)

    # Relationships
    workstreams = relationship("Workstream", back_populates="campaign", cascade="all, delete-orphan")
    deliverables = relationship("Deliverable", back_populates="campaign", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="campaign", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="campaign", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="campaign", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_ops_campaigns_brand_status', 'brand_id', 'status'),
        Index('idx_ops_campaigns_dates', 'start_date', 'end_date'),
        Index('idx_ops_campaigns_team', 'team_id'),
    )


class Workstream(Base):
    """Workstream/content stream table"""
    __tablename__ = 'ops_workstreams'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(50), nullable=False)  # ugc, influencer_paid, etc.
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(WorkstreamStatus), default=WorkstreamStatus.DRAFT, nullable=False)

    # Financial (SUPERADMIN ONLY)
    budget_allocated = Column(Float)
    budget_spent = Column(Float, default=0)

    # Internal notes (SUPERADMIN ONLY)
    internal_notes = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Relationships
    campaign = relationship("Campaign", back_populates="workstreams")
    deliverables = relationship("Deliverable", back_populates="workstream", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="workstream", cascade="all, delete-orphan")
    production_batches = relationship("ProductionBatch", back_populates="workstream", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_ops_workstreams_campaign', 'campaign_id'),
        Index('idx_ops_workstreams_status', 'status'),
        Index('idx_ops_workstreams_type', 'type'),
    )


class Deliverable(Base):
    """Individual deliverable/content piece"""
    __tablename__ = 'ops_deliverables'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workstream_id = Column(UUID(as_uuid=True), ForeignKey('ops_workstreams.id', ondelete='CASCADE'), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id', ondelete='CASCADE'), nullable=False)

    # Basic info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(String(50), nullable=False)  # video, reel, story_set, etc.
    status = Column(SQLEnum(DeliverableStatusEnum), default=DeliverableStatusEnum.IDEA, nullable=False)

    # Dates
    due_date = Column(Date)
    posting_date = Column(Date)

    # Associations
    concept_id = Column(UUID(as_uuid=True), ForeignKey('ops_concepts.id', ondelete='SET NULL'))
    assignment_id = Column(UUID(as_uuid=True), ForeignKey('ops_assignments.id', ondelete='SET NULL'))
    production_batch_id = Column(UUID(as_uuid=True), ForeignKey('ops_production_batches.id', ondelete='SET NULL'))

    # Assets (JSON structure)
    assets = Column(JSON, default={})

    # Posting proof
    posting_proof = Column(JSON, default={})

    # Dependencies
    dependencies = Column(JSON, default=[])

    # Notes
    internal_notes = Column(Text)  # SUPERADMIN ONLY
    client_notes = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    # Relationships
    workstream = relationship("Workstream", back_populates="deliverables")
    campaign = relationship("Campaign", back_populates="deliverables")
    concept = relationship("Concept", back_populates="deliverables")
    assignment = relationship("Assignment", back_populates="deliverables")
    production_batch = relationship("ProductionBatch", back_populates="deliverables")

    # Indexes
    __table_args__ = (
        Index('idx_ops_deliverables_workstream', 'workstream_id'),
        Index('idx_ops_deliverables_campaign', 'campaign_id'),
        Index('idx_ops_deliverables_status', 'status'),
        Index('idx_ops_deliverables_dates', 'due_date', 'posting_date'),
        Index('idx_ops_deliverables_concept', 'concept_id'),
    )


class Concept(Base):
    """Creative concepts for deliverables"""
    __tablename__ = 'ops_concepts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workstream_id = Column(UUID(as_uuid=True), ForeignKey('ops_workstreams.id', ondelete='CASCADE'), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id', ondelete='CASCADE'), nullable=False)

    # Content
    title = Column(String(255), nullable=False)
    hook = Column(Text)
    script = Column(Text)
    on_screen_text = Column(Text)
    reference_links = Column(JSON, default=[])
    key_messages = Column(JSON, default=[])
    purpose = Column(String(255))
    pillar = Column(String(255))

    # Versions
    internal_version = Column(Text)  # SUPERADMIN ONLY
    client_facing_version = Column(Text)

    # Approval
    approval_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.NOT_SENT, nullable=False)
    approval_history = Column(JSON, default=[])

    # Comments
    comments = Column(JSON, default=[])

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Relationships
    workstream = relationship("Workstream", back_populates="concepts")
    campaign = relationship("Campaign", back_populates="concepts")
    deliverables = relationship("Deliverable", back_populates="concept")

    # Indexes
    __table_args__ = (
        Index('idx_ops_concepts_workstream', 'workstream_id'),
        Index('idx_ops_concepts_campaign', 'campaign_id'),
        Index('idx_ops_concepts_approval', 'approval_status'),
    )


class Assignment(Base):
    """Creator/talent assignments"""
    __tablename__ = 'ops_assignments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workstream_id = Column(UUID(as_uuid=True), ForeignKey('ops_workstreams.id', ondelete='CASCADE'), nullable=False)
    creator_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    creator_username = Column(String(255), nullable=False)
    creator_name = Column(String(255))

    # Creator info (SUPERADMIN ONLY fields)
    contact_info = Column(JSON, default={})
    payment_info = Column(JSON, default={})
    reliability_score = Column(Float)

    # Assignment details
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Relationships
    deliverables = relationship("Deliverable", back_populates="assignment")

    # Indexes
    __table_args__ = (
        Index('idx_ops_assignments_workstream', 'workstream_id'),
        Index('idx_ops_assignments_creator', 'creator_id'),
    )


class ProductionBatch(Base):
    """Production batches/shoots"""
    __tablename__ = 'ops_production_batches'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workstream_id = Column(UUID(as_uuid=True), ForeignKey('ops_workstreams.id', ondelete='CASCADE'), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id'), nullable=False)

    # Basic info
    name = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    location = Column(String(255))

    # Schedule (SUPERADMIN ONLY)
    call_time = Column(String(10))  # HH:MM format
    wrap_time = Column(String(10))  # HH:MM format

    # Roster (SUPERADMIN ONLY)
    roster = Column(JSON, default=[])

    # Checklist (SUPERADMIN ONLY)
    checklist_items = Column(JSON, default=[])

    # Summary for clients
    status_summary = Column(JSON, default={})

    # Notes
    internal_notes = Column(Text)  # SUPERADMIN ONLY

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workstream = relationship("Workstream", back_populates="production_batches")
    deliverables = relationship("Deliverable", back_populates="production_batch")

    # Indexes
    __table_args__ = (
        Index('idx_ops_production_workstream', 'workstream_id'),
        Index('idx_ops_production_date', 'date'),
    )


class Event(Base):
    """Events and activations"""
    __tablename__ = 'ops_events'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id', ondelete='CASCADE'), nullable=False)
    workstream_id = Column(UUID(as_uuid=True), ForeignKey('ops_workstreams.id', ondelete='SET NULL'))

    # Basic info
    name = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    venue = Column(String(255))
    type = Column(String(50), nullable=False)  # activation, shoot, experience, other
    status = Column(String(50), default='planning', nullable=False)

    # Barter management (SUPERADMIN ONLY)
    barter_type = Column(String(50))  # tickets, products, both
    barter_inventory = Column(Integer)
    barter_allocated = Column(Integer, default=0)

    # Shortlist (SUPERADMIN ONLY)
    shortlist = Column(JSON, default=[])

    # Enrollments
    enrollments = Column(JSON, default=[])

    # Summary for clients
    summary = Column(JSON, default={})

    # Notes
    internal_notes = Column(Text)  # SUPERADMIN ONLY

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="events")

    # Indexes
    __table_args__ = (
        Index('idx_ops_events_campaign', 'campaign_id'),
        Index('idx_ops_events_date', 'date'),
        Index('idx_ops_events_status', 'status'),
    )


class Payout(Base):
    """Creator payouts (SUPERADMIN ONLY)"""
    __tablename__ = 'ops_payouts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id', ondelete='CASCADE'), nullable=False)
    creator_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    creator_name = Column(String(255), nullable=False)

    # Payment details
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='USD', nullable=False)
    status = Column(String(50), default='pending', nullable=False)
    payment_method = Column(String(50), nullable=False)

    # Banking details (encrypted/masked)
    banking_details = Column(JSON, default={})

    # Documentation
    invoice_number = Column(String(100))
    paid_at = Column(DateTime(timezone=True))
    notes = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    # Indexes
    __table_args__ = (
        Index('idx_ops_payouts_campaign', 'campaign_id'),
        Index('idx_ops_payouts_creator', 'creator_id'),
        Index('idx_ops_payouts_status', 'status'),
    )


class ActivityLog(Base):
    """Activity log for all operations"""
    __tablename__ = 'ops_activity_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('ops_campaigns.id', ondelete='CASCADE'), nullable=False)
    workstream_id = Column(UUID(as_uuid=True), ForeignKey('ops_workstreams.id', ondelete='SET NULL'))
    deliverable_id = Column(UUID(as_uuid=True), ForeignKey('ops_deliverables.id', ondelete='SET NULL'))

    # Activity details
    type = Column(String(50), nullable=False)  # status_change, approval, comment, etc.
    actor_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    actor_name = Column(String(255), nullable=False)
    actor_role = Column(String(50), nullable=False)
    action = Column(String(255), nullable=False)
    details = Column(JSON, default={})

    # Visibility
    is_client_visible = Column(Boolean, default=True, nullable=False)

    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="activities")

    # Indexes
    __table_args__ = (
        Index('idx_ops_activity_campaign', 'campaign_id'),
        Index('idx_ops_activity_timestamp', 'timestamp'),
        Index('idx_ops_activity_type', 'type'),
        Index('idx_ops_activity_visibility', 'is_client_visible'),
    )