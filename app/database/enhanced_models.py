"""
Enhanced database models with sophisticated column allocation for all Decodo datapoints
"""
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Text, DateTime, Float, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Profile(Base):
    """
    Sophisticated profile model with all 69+ Decodo datapoints allocated to specific columns
    """
    __tablename__ = "profiles"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    instagram_user_id = Column(String(50), unique=True, index=True)
    
    # Profile Basic Information
    full_name = Column(Text)
    biography = Column(Text)
    external_url = Column(Text)
    external_url_shimmed = Column(Text)
    profile_pic_url = Column(Text)
    profile_pic_url_hd = Column(Text)
    
    # Account Statistics
    followers_count = Column(BigInteger, default=0, index=True)
    following_count = Column(BigInteger, default=0)
    posts_count = Column(BigInteger, default=0)
    mutual_followers_count = Column(BigInteger, default=0)
    highlight_reel_count = Column(Integer, default=0)
    
    # Account Status & Verification
    is_verified = Column(Boolean, default=False, index=True)
    is_private = Column(Boolean, default=False, index=True)
    is_business_account = Column(Boolean, default=False)
    is_professional_account = Column(Boolean, default=False)
    is_joined_recently = Column(Boolean, default=False)
    
    # Business Information
    business_category_name = Column(String(255))
    overall_category_name = Column(String(255))
    category_enum = Column(String(100))
    business_address_json = Column(Text)
    business_contact_method = Column(String(50))
    business_email = Column(String(255))
    business_phone_number = Column(String(50))
    
    # Account Features
    has_ar_effects = Column(Boolean, default=False)
    has_clips = Column(Boolean, default=False)
    has_guides = Column(Boolean, default=False)
    has_channel = Column(Boolean, default=False)
    has_onboarded_to_text_post_app = Column(Boolean, default=False)
    show_text_post_app_badge = Column(Boolean, default=False)
    
    # Privacy & Restrictions
    country_block = Column(Boolean, default=False)
    is_embeds_disabled = Column(Boolean, default=False)
    hide_like_and_view_counts = Column(Boolean, default=False)
    
    # Account Settings
    should_show_category = Column(Boolean, default=True)
    should_show_public_contacts = Column(Boolean, default=True)
    show_account_transparency_details = Column(Boolean, default=True)
    remove_message_entrypoint = Column(Boolean, default=False)
    
    # Viewer Relationships (for authenticated requests)
    blocked_by_viewer = Column(Boolean)
    has_blocked_viewer = Column(Boolean)
    restricted_by_viewer = Column(Boolean)
    followed_by_viewer = Column(Boolean)
    follows_viewer = Column(Boolean)
    requested_by_viewer = Column(Boolean)
    has_requested_viewer = Column(Boolean)
    
    # AI & Special Features
    ai_agent_type = Column(String(100))
    ai_agent_owner_username = Column(String(255))
    transparency_label = Column(String(255))
    transparency_product = Column(String(255))
    
    # Supervision & Safety
    is_supervision_enabled = Column(Boolean, default=False)
    is_guardian_of_viewer = Column(Boolean, default=False)
    is_supervised_by_viewer = Column(Boolean, default=False)
    is_supervised_user = Column(Boolean, default=False)
    guardian_id = Column(String(50))
    is_regulated_c18 = Column(Boolean, default=False)
    is_verified_by_mv4b = Column(Boolean, default=False)
    
    # Advanced Fields
    fbid = Column(String(50))
    eimu_id = Column(String(50))
    pinned_channels_list_count = Column(Integer, default=0)
    
    # Structured Data (JSONB for complex nested data)
    biography_with_entities = Column(JSONB)
    bio_links = Column(JSONB)
    pronouns = Column(JSONB)
    
    # Analytics & Metrics (computed fields)
    engagement_rate = Column(Float)
    avg_likes = Column(Float)
    avg_comments = Column(Float)
    avg_engagement = Column(Float)
    content_quality_score = Column(Float)
    influence_score = Column(Float)
    data_quality_score = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_refreshed = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Raw data backup (for debugging and future features)
    raw_data = Column(JSONB)
    
    # Relationships
    posts = relationship("Post", back_populates="profile", cascade="all, delete-orphan")
    related_profiles = relationship("RelatedProfile", back_populates="profile", cascade="all, delete-orphan")

class Post(Base):
    """
    Sophisticated post model with detailed media and engagement data
    """
    __tablename__ = "posts"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)
    shortcode = Column(String(50), unique=True, nullable=False, index=True)
    instagram_post_id = Column(String(50), unique=True, index=True)
    
    # Media Information
    media_type = Column(String(50))  # GraphImage, GraphVideo, GraphSidecar
    is_video = Column(Boolean, default=False)
    display_url = Column(Text)
    thumbnail_src = Column(Text)
    thumbnail_tall_src = Column(Text)
    
    # Dimensions
    width = Column(Integer)
    height = Column(Integer)
    
    # Content
    caption = Column(Text)
    accessibility_caption = Column(Text)
    
    # Engagement Metrics
    likes_count = Column(BigInteger, default=0, index=True)
    comments_count = Column(BigInteger, default=0)
    comments_disabled = Column(Boolean, default=False)
    
    # Post Settings
    like_and_view_counts_disabled = Column(Boolean, default=False)
    viewer_can_reshare = Column(Boolean, default=True)
    has_upcoming_event = Column(Boolean, default=False)
    
    # Location
    location_name = Column(String(255))
    location_id = Column(String(50))
    
    # Timestamps
    taken_at_timestamp = Column(BigInteger, index=True)
    posted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Structured Data
    thumbnail_resources = Column(JSONB)
    sidecar_children = Column(JSONB)  # For carousel posts
    tagged_users = Column(JSONB)
    coauthor_producers = Column(JSONB)
    
    # Content Analysis (for AI/ML)
    hashtags = Column(JSONB)
    mentions = Column(JSONB)
    
    # Raw data backup
    raw_data = Column(JSONB)
    
    # Relationships
    profile = relationship("Profile", back_populates="posts")

class RelatedProfile(Base):
    """
    Store Instagram's suggested related profiles
    """
    __tablename__ = "related_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    
    # Related profile data
    related_username = Column(String(255), nullable=False)
    related_full_name = Column(String(255))
    related_is_verified = Column(Boolean, default=False)
    related_is_private = Column(Boolean, default=False)
    related_profile_pic_url = Column(Text)
    similarity_score = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    profile = relationship("Profile", back_populates="related_profiles")

class ProfileAnalyticsHistory(Base):
    """
    Track analytics changes over time for trend analysis
    """
    __tablename__ = "profile_analytics_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)
    
    # Snapshot data
    followers_count = Column(BigInteger)
    following_count = Column(BigInteger)
    posts_count = Column(BigInteger)
    engagement_rate = Column(Float)
    avg_likes = Column(Float)
    avg_comments = Column(Float)
    
    # Calculated metrics
    follower_growth = Column(Integer)  # Change from previous snapshot
    engagement_change = Column(Float)
    
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class User(Base):
    """
    Users who access the analytics platform
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user")
    credits = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))

class UserProfileAccess(Base):
    """
    Track which profiles users have accessed (30-day unlock system)
    """
    __tablename__ = "user_profile_access"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())
    
    # Composite index for efficient lookups
    __table_args__ = (
        {"schema": None},
    )