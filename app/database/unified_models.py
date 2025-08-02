"""
FINAL UNIFIED DATABASE MODELS - Complete Instagram Analytics Platform
Contains ALL tables required for the platform with real Decodo integration
Includes campaigns, all Decodo datapoints, and proper relationships
"""
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Text, Float, ARRAY, ForeignKey, Date, Index, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid as uuid_lib

Base = declarative_base()

# =============================================================================
# USER MANAGEMENT TABLES
# =============================================================================

class User(Base):
    """Complete user management with credits, subscriptions, and preferences"""
    __tablename__ = "users"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    supabase_user_id = Column(Text, unique=True, nullable=True, index=True)  # Link to Supabase auth.users
    email = Column(Text, unique=True, nullable=False, index=True)
    hashed_password = Column(Text)  # For non-Supabase auth fallback
    
    # User profile
    full_name = Column(Text)
    first_name = Column(Text)  # NEW: For settings form
    last_name = Column(Text)   # NEW: For settings form
    company = Column(Text)     # NEW: For settings form
    job_title = Column(Text)   # NEW: For settings form
    phone_number = Column(Text)  # NEW: For settings form
    bio = Column(Text)         # NEW: For settings form
    role = Column(Text, nullable=False, default='free', index=True)  # free, premium, admin, super_admin
    status = Column(Text, nullable=False, default='active', index=True)  # active, inactive, suspended, pending
    
    # Credits and billing
    credits = Column(Integer, nullable=False, default=10)
    credits_used_this_month = Column(Integer, nullable=False, default=0)
    subscription_tier = Column(Text, default='free')  # free, basic, premium, enterprise
    subscription_expires_at = Column(DateTime(timezone=True))
    
    # Profile customization
    profile_picture_url = Column(Text)
    preferences = Column(JSONB, nullable=False, default=lambda: {})  # UI preferences, notifications, etc.
    timezone = Column(Text, default='UTC')
    language = Column(Text, default='en')
    
    # Activity tracking
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    last_activity = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
    
    # Security
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    two_factor_enabled = Column(Boolean, default=False)
    
    # Privacy Settings (from Security tab)
    profile_visibility = Column(Boolean, default=True)  # NEW: Make profile visible to others
    data_analytics_enabled = Column(Boolean, default=True)  # NEW: Allow usage analytics
    
    # Notification Settings
    notification_preferences = Column(JSONB, nullable=False, default=lambda: {
        "email_notifications": True,
        "push_notifications": True,
        "marketing_emails": False,
        "security_alerts": True,
        "weekly_reports": True
    })
    
    # Relationships
    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")
    user_profile_access = relationship("UserProfileAccess", back_populates="user", cascade="all, delete-orphan")
    user_searches = relationship("UserSearch", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("UserFavorite", back_populates="user", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name='check_email_format'),
        CheckConstraint("role IN ('free', 'premium', 'admin', 'super_admin')", name='check_role_valid'),
        CheckConstraint("status IN ('active', 'inactive', 'suspended', 'pending')", name='check_status_valid'),
        CheckConstraint("credits >= 0", name='check_credits_non_negative'),
        Index('idx_users_email_unique', 'email'),
        Index('idx_users_supabase_id', 'supabase_user_id'),
        Index('idx_users_role_status', 'role', 'status'),
        Index('idx_users_created_at', 'created_at'),
        Index('idx_users_last_login', 'last_login'),
    )


class UserSearch(Base):
    """Comprehensive search history with metadata"""
    __tablename__ = "user_searches"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid_lib.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Search details
    instagram_username = Column(String(255), nullable=False, index=True)
    search_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    analysis_type = Column(String(50), nullable=False, index=True)  # basic, comprehensive, detailed, quick, full
    
    # Search metadata and results
    search_metadata = Column(JSONB, nullable=False, default=lambda: {})
    search_duration_ms = Column(Integer)  # How long the search took
    data_source = Column(Text)  # 'fresh_fetch', 'database_cache', 'api_fallback'
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Profile snapshot at time of search (for historical tracking)
    profile_snapshot = Column(JSONB)  # Key metrics when searched
    
    # Relationships
    user = relationship("User", back_populates="user_searches")
    
    __table_args__ = (
        Index('idx_user_searches_user_timestamp', 'user_id', 'search_timestamp'),
        Index('idx_user_searches_username', 'instagram_username'),
        Index('idx_user_searches_success', 'success'),
    )


class UserProfileAccess(Base):
    """30-day profile access tracking system"""
    __tablename__ = "user_profile_access"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Access details
    granted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    access_type = Column(String(50), nullable=False)  # 'search', 'refresh', 'premium', 'campaign'
    
    # Usage tracking
    first_accessed = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    access_count = Column(Integer, default=1)
    
    # Relationships
    user = relationship("User", back_populates="user_profile_access")
    profile = relationship("Profile", back_populates="user_access")
    
    __table_args__ = (
        Index('idx_user_profile_access_expires', 'expires_at'),
        Index('idx_user_profile_access_user_profile', 'user_id', 'profile_id'),
        Index('idx_user_profile_access_active', 'expires_at', 'user_id'),
    )


class UserFavorite(Base):
    """User favorite profiles for quick access"""
    __tablename__ = "user_favorites"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Favorite details
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes = Column(Text)
    tags = Column(ARRAY(Text))  # User-defined tags for organization
    
    # Relationships
    user = relationship("User", back_populates="favorites")
    profile = relationship("Profile")
    
    __table_args__ = (
        Index('idx_user_favorites_user_profile', 'user_id', 'profile_id', unique=True),
        Index('idx_user_favorites_added', 'added_at'),
    )


# =============================================================================
# INSTAGRAM DATA TABLES (From Decodo API)
# =============================================================================

class Profile(Base):
    """Instagram profile matching actual database schema"""
    __tablename__ = "profiles"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    instagram_user_id = Column(Text, nullable=True)
    
    # Basic profile information
    full_name = Column(String(500), nullable=True)
    biography = Column(Text, nullable=True)
    external_url = Column(Text, nullable=True)
    profile_pic_url = Column(Text, nullable=True)
    
    # Statistics
    followers_count = Column(BigInteger, nullable=True)
    following_count = Column(BigInteger, nullable=True)
    posts_count = Column(BigInteger, nullable=True)
    
    # Account status
    is_verified = Column(Boolean, nullable=True, default=False)
    is_private = Column(Boolean, nullable=True, default=False)
    is_business_account = Column(Boolean, nullable=True, default=False)
    
    # Analytics
    engagement_rate = Column(Float, nullable=True)
    influence_score = Column(Float, nullable=True)
    data_quality_score = Column(Float, nullable=True, default=0.0)
    
    # Category
    category = Column(String(255), nullable=True)
    
    # Data management
    refresh_count = Column(Integer, nullable=True, default=0)
    last_refreshed = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    
    # Raw data backup
    raw_data = Column(JSONB, nullable=False, default=lambda: {})
    
    # Relationships
    posts = relationship("Post", back_populates="profile", cascade="all, delete-orphan", order_by="Post.taken_at_timestamp.desc()")
    user_access = relationship("UserProfileAccess", back_populates="profile", cascade="all, delete-orphan")
    audience_demographics = relationship("AudienceDemographics", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    creator_metadata = relationship("CreatorMetadata", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    related_profiles = relationship("RelatedProfile", back_populates="profile", cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="profile", cascade="all, delete-orphan")
    campaign_profiles = relationship("CampaignProfile", back_populates="profile")
    
    __table_args__ = (
        Index('idx_profiles_username_lower', func.lower(username)),
        Index('idx_profiles_text_search', func.to_tsvector('english', func.concat(username, ' ', func.coalesce(full_name, '')))),
        Index('idx_profiles_followers_desc', 'followers_count'),
        Index('idx_profiles_verified_followers', 'is_verified', 'followers_count'),
        Index('idx_profiles_business_verified', 'is_business_account', 'is_verified'),
        Index('idx_profiles_engagement_desc', 'engagement_rate'),
        Index('idx_profiles_influence_desc', 'influence_score'),
        Index('idx_profiles_last_refreshed', 'last_refreshed'),
    )


class Post(Base):
    """COMPREHENSIVE Instagram post with ALL Decodo post datapoints"""
    __tablename__ = "posts"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Instagram post identification
    instagram_post_id = Column(Text, nullable=False, unique=True, index=True)
    shortcode = Column(Text, nullable=False, unique=True, index=True)  # URL shortcode
    
    # Media Information
    media_type = Column(String(50), index=True)  # GraphImage, GraphVideo, GraphSidecar
    is_video = Column(Boolean, default=False, index=True)
    display_url = Column(Text)
    thumbnail_src = Column(Text)
    thumbnail_tall_src = Column(Text)
    
    # Video-specific fields
    video_url = Column(Text)
    video_view_count = Column(BigInteger, default=0)
    video_duration = Column(Integer)  # Duration in seconds
    has_audio = Column(Boolean)
    
    # Image dimensions
    width = Column(Integer)
    height = Column(Integer)
    
    # Content
    caption = Column(Text)
    accessibility_caption = Column(Text)  # Alt text
    
    # Engagement metrics (indexed for performance)
    likes_count = Column(BigInteger, default=0, index=True)
    comments_count = Column(BigInteger, default=0, index=True)
    comments_disabled = Column(Boolean, default=False)
    
    # Post settings
    like_and_view_counts_disabled = Column(Boolean, default=False)
    viewer_can_reshare = Column(Boolean, default=True)
    has_upcoming_event = Column(Boolean, default=False)
    
    # Location
    location_name = Column(String(255))
    location_id = Column(String(50))
    
    # Carousel/multiple media
    is_carousel = Column(Boolean, default=False)
    carousel_media_count = Column(Integer, default=1)
    
    # Timestamps
    taken_at_timestamp = Column(BigInteger, index=True)  # Unix timestamp
    posted_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Structured data
    thumbnail_resources = Column(JSONB)  # Array of thumbnail sizes
    sidecar_children = Column(JSONB)  # For carousel posts
    tagged_users = Column(JSONB)  # Array of tagged users
    coauthor_producers = Column(JSONB)  # Collaboration data
    
    # Content analysis (extracted from caption and media)
    hashtags = Column(JSONB)  # Extracted hashtags
    mentions = Column(JSONB)  # Extracted mentions
    
    # Performance metrics (computed)
    engagement_rate = Column(Float)  # (likes + comments) / profile_followers * 100
    performance_score = Column(Float)  # Relative to account average
    
    # Media storage
    post_images = Column(JSONB)  # Array of image versions/sizes stored
    post_thumbnails = Column(JSONB)  # Array of thumbnail versions
    
    # Raw data backup
    raw_data = Column(JSONB, nullable=False)
    
    # Relationships
    profile = relationship("Profile", back_populates="posts")
    comment_sentiment = relationship("CommentSentiment", back_populates="post", cascade="all, delete-orphan")
    campaign_posts = relationship("CampaignPost", back_populates="post")
    
    __table_args__ = (
        Index('idx_posts_profile_timestamp', 'profile_id', 'taken_at_timestamp'),
        Index('idx_posts_engagement', 'likes_count', 'comments_count'),
        Index('idx_posts_media_type', 'media_type'),
        Index('idx_posts_carousel', 'is_carousel'),
    )


# =============================================================================
# ANALYTICS & INSIGHTS TABLES (Enhanced from Decodo data)
# =============================================================================

class AudienceDemographics(Base):
    """Enhanced audience demographics (computed from Decodo follower data)"""
    __tablename__ = "audience_demographics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # Demographic distributions (JSONB for flexibility)
    gender_distribution = Column(JSONB, nullable=False)  # {"male": 0.6, "female": 0.4}
    age_distribution = Column(JSONB, nullable=False)     # {"18-24": 0.5, "25-34": 0.3, ...}
    location_distribution = Column(JSONB, nullable=False) # {"Dubai": 0.3, "USA": 0.2, ...}
    
    # Analysis metadata
    sample_size = Column(Integer)  # Number of followers analyzed
    confidence_score = Column(Float)  # Analysis confidence
    last_sampled = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    analysis_method = Column(Text)  # 'decodo_enhanced', 'manual', 'estimated'
    
    # Relationship
    profile = relationship("Profile", back_populates="audience_demographics")
    
    __table_args__ = (
        Index('idx_audience_demographics_sampled', 'last_sampled'),
    )


class CreatorMetadata(Base):
    """Enhanced creator metadata (extracted from Decodo profile data)"""
    __tablename__ = "creator_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # Extracted information
    extracted_location = Column(Text, index=True)  # Extracted from bio/business data
    categories = Column(ARRAY(Text), nullable=False, default=list, index=True)  # ["fashion", "tech", "travel"]
    content_themes = Column(JSONB)  # Detected content themes with confidence scores
    
    # Language and content analysis
    primary_language = Column(String(10))  # ISO language code
    secondary_languages = Column(ARRAY(String(10)))
    content_sentiment = Column(String(20))  # 'positive', 'neutral', 'negative'
    brand_mentions = Column(JSONB)  # Frequently mentioned brands
    
    # Analysis metadata
    last_updated = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    analysis_confidence = Column(Float, default=0.0)
    posts_analyzed = Column(Integer, default=0)
    
    # Relationship
    profile = relationship("Profile", back_populates="creator_metadata")
    
    __table_args__ = (
        Index('idx_creator_metadata_location', 'extracted_location'),
        Index('idx_creator_metadata_updated', 'last_updated'),
    )


class CommentSentiment(Base):
    """Comment sentiment analysis for posts"""
    __tablename__ = "comment_sentiment"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Sentiment analysis results
    positive_score = Column(Float, default=0.0)
    negative_score = Column(Float, default=0.0)
    neutral_score = Column(Float, default=0.0)
    overall_sentiment = Column(String(20), index=True)  # 'positive', 'negative', 'neutral'
    
    # Analysis details
    comments_analyzed = Column(Integer, default=0)
    analysis_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationship
    post = relationship("Post", back_populates="comment_sentiment")
    
    __table_args__ = (
        Index('idx_comment_sentiment_post', 'post_id'),
        Index('idx_comment_sentiment_overall', 'overall_sentiment'),
    )


class RelatedProfile(Base):
    """Related/similar profiles (from Decodo suggestions)"""
    __tablename__ = "related_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Related profile information
    related_username = Column(String(255), nullable=False, index=True)
    related_full_name = Column(Text)
    related_is_verified = Column(Boolean, default=False)
    related_is_private = Column(Boolean, default=False)
    related_profile_pic_url = Column(Text)
    related_followers_count = Column(BigInteger, default=0)
    
    # Relationship metrics
    similarity_score = Column(Float, default=0.0)  # 0-1 similarity score
    relationship_type = Column(String(50))  # 'similar', 'competitor', 'collaboration'
    
    # Discovery details
    discovered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source = Column(String(50))  # 'decodo', 'manual', 'algorithm'
    
    # Relationship
    profile = relationship("Profile", back_populates="related_profiles")
    
    __table_args__ = (
        Index('idx_related_profiles_username', 'related_username'),
        Index('idx_related_profiles_similarity', 'similarity_score'),
    )


class Mention(Base):
    """Profile mentions tracking"""
    __tablename__ = "mentions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Mention details
    mentioned_username = Column(String(255), nullable=False, index=True)
    mention_type = Column(String(50), nullable=False)  # 'tag', 'caption', 'comment'
    mention_context = Column(Text)  # Where the mention occurred
    
    # Timing
    mentioned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationship
    profile = relationship("Profile", back_populates="mentions")
    
    __table_args__ = (
        Index('idx_mentions_username', 'mentioned_username'),
        Index('idx_mentions_type', 'mention_type'),
    )


# =============================================================================
# CAMPAIGN MANAGEMENT TABLES (Real Platform Feature)
# =============================================================================

class Campaign(Base):
    """User campaigns for influencer tracking"""
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Campaign details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    logo_url = Column(Text)
    
    # Campaign timing
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Campaign status
    status = Column(String(50), nullable=False, default='active')  # active, paused, completed, archived
    
    # Campaign settings
    budget = Column(Float)
    target_audience = Column(JSONB)  # Target demographics
    campaign_goals = Column(JSONB)  # Goals and KPIs
    
    # Relationships
    user = relationship("User", back_populates="campaigns")
    campaign_posts = relationship("CampaignPost", back_populates="campaign", cascade="all, delete-orphan")
    campaign_profiles = relationship("CampaignProfile", back_populates="campaign", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_campaigns_user_status', 'user_id', 'status'),
        Index('idx_campaigns_dates', 'start_date', 'end_date'),
    )


class CampaignPost(Base):
    """Posts associated with campaigns"""
    __tablename__ = "campaign_posts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Association metadata
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    role = Column(String(50))  # 'sponsored', 'organic', 'collaboration', 'mention'
    performance_tier = Column(String(20))  # 'high', 'medium', 'low'
    notes = Column(Text)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_posts")
    post = relationship("Post", back_populates="campaign_posts")
    
    __table_args__ = (
        Index('ix_campaign_posts_unique', 'campaign_id', 'post_id', unique=True),
        Index('idx_campaign_posts_added', 'added_at'),
    )


class CampaignProfile(Base):
    """Profiles tracked in campaigns (competitors, influencers, etc.)"""
    __tablename__ = "campaign_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Association metadata
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    role = Column(String(50))  # 'competitor', 'inspiration', 'target_influencer', 'collaboration'
    priority = Column(Integer, default=1)  # 1=high, 2=medium, 3=low
    notes = Column(Text)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_profiles")
    profile = relationship("Profile", back_populates="campaign_profiles")
    
    __table_args__ = (
        Index('ix_campaign_profiles_unique', 'campaign_id', 'profile_id', unique=True),
        Index('idx_campaign_profiles_role', 'role'),
        Index('idx_campaign_profiles_priority', 'priority'),
    )