"""
FINAL UNIFIED DATABASE MODELS - Complete Instagram Analytics Platform
Contains ALL tables required for the platform with real Apify integration
Includes campaigns, all Apify datapoints, and proper relationships
"""
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Text, Float, ARRAY, ForeignKey, Date, Index, CheckConstraint, UniqueConstraint, text, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.sql import func
import uuid as uuid_lib

Base = declarative_base()

# =============================================================================
# USER MANAGEMENT TABLES
# =============================================================================

class AuthUser(Base):
    """Supabase auth.users table model - READ ONLY, managed by Supabase"""
    __tablename__ = "auth_users"
    __table_args__ = {
        'schema': 'auth', 
        'extend_existing': True,
        'info': {'skip_create': True}  # Skip during table creation
    }
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String(255))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    raw_user_meta_data = Column(JSONB)
    raw_app_meta_data = Column(JSONB)


class UserProfile(Base):
    """Bridge table linking auth_users to user data"""
    __tablename__ = "user_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)  # References auth.users.id
    
    # Profile information
    full_name = Column(Text)
    first_name = Column(Text)
    last_name = Column(Text)
    company = Column(Text)
    job_title = Column(Text)
    phone_number = Column(Text)
    bio = Column(Text)
    profile_picture_url = Column(Text)
    
    # Settings and preferences
    preferences = Column(JSONB, nullable=False, default=lambda: {})
    timezone = Column(Text, default='UTC')
    language = Column(Text, default='en')
    
    # Privacy settings
    profile_visibility = Column(Boolean, default=True)
    data_analytics_enabled = Column(Boolean, default=True)
    
    # Notification settings
    notification_preferences = Column(JSONB, nullable=False, default=lambda: {
        "email_notifications": True,
        "push_notifications": True,
        "marketing_emails": False,
        "security_alerts": True,
        "weekly_reports": True
    })
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships (with explicit primaryjoin since no FK constraint)
    auth_user = relationship("AuthUser", primaryjoin="UserProfile.user_id == foreign(AuthUser.id)", viewonly=True)


class SearchHistory(Base):
    """Additional search tracking table"""
    __tablename__ = "search_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Search details
    search_query = Column(Text, nullable=False)
    search_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_agent = Column(Text)
    ip_address = Column(Text)
    
    # Search metadata
    search_type = Column(String(50), index=True)  # 'profile', 'hashtag', 'location'
    results_count = Column(Integer, default=0)
    search_duration_ms = Column(Integer)
    
    # Relationships
    profile = relationship("Profile")
    
    __table_args__ = (
        Index('idx_search_history_timestamp', 'search_timestamp'),
        Index('idx_search_history_profile', 'profile_id'),
    )

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
    first_name = Column("user.first_name", Text)  # NEW: For settings form
    last_name = Column("user.last_name", Text)   # NEW: For settings form
    company = Column(Text)     # NEW: For settings form
    job_title = Column(Text)   # NEW: For settings form
    phone_number = Column(Text)  # NEW: For settings form
    bio = Column(Text)         # NEW: For settings form
    profile_picture_url = Column(Text)  # Profile picture URL
    role = Column(Text, nullable=False, default='free', index=True)  # free, premium, admin, super_admin
    status = Column(Text, nullable=False, default='active', index=True)  # active, inactive, suspended, pending
    
    # Credits and billing
    credits = Column(Integer, nullable=False, default=10)
    credits_used_this_month = Column(Integer, nullable=False, default=0)
    subscription_tier = Column(Text, default='free')  # free, basic, premium, enterprise
    subscription_expires_at = Column(DateTime(timezone=True))
    stripe_customer_id = Column(Text, unique=True, nullable=True, index=True)  # Stripe customer ID
    
    # Profile customization
    avatar_config = Column(JSONB)  # BoringAvatars configuration (variant, colorScheme, colors, seed)
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
    email_verified = Column("user.email_verified", Boolean, default=False)
    phone_verified = Column("user.phone_verified", Boolean, default=False)
    two_factor_enabled = Column("user.two_factor_enabled", Boolean, default=False)
    
    # Privacy Settings (from Security tab)
    profile_visibility = Column("user.profile_visibility", Boolean, default=True)  # NEW: Make profile visible to others
    data_analytics_enabled = Column("user.data_analytics_enabled", Boolean, default=True)  # NEW: Allow usage analytics
    
    # Notification Settings
    notification_preferences = Column(JSONB, nullable=False, default=lambda: {
        "email_notifications": True,
        "push_notifications": True,
        "marketing_emails": False,
        "security_alerts": True,
        "weekly_reports": True
    })
    
    # Relationships
    user_profile_access = relationship("UserProfileAccess", back_populates="user", cascade="all, delete-orphan")
    user_searches = relationship("UserSearch", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("UserFavorite", back_populates="user", cascade="all, delete-orphan")
    user_lists = relationship("UserList", back_populates="user", cascade="all, delete-orphan")
    user_list_items = relationship("UserListItem", back_populates="user", cascade="all, delete-orphan")
    ai_analysis_jobs = relationship("AIAnalysisJob", back_populates="user", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")
    campaign_proposals = relationship("CampaignProposal", foreign_keys="[CampaignProposal.user_id]", back_populates="user", cascade="all, delete-orphan")
    
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
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
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
    
    # Access details - matching actual database schema
    granted_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True, server_default=text("now() + interval '30 days'"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    
    # Removed columns that don't exist in actual DB:
    # - access_type
    # - first_accessed 
    # - last_accessed
    # - access_count
    
    # Relationships
    user = relationship("User", back_populates="user_profile_access")
    profile = relationship("Profile", back_populates="user_access")
    
    # Constraints and indexes matching actual database
    __table_args__ = (
        Index('idx_user_profile_access_user_id', 'user_id'),
        Index('idx_user_profile_access_profile_id', 'profile_id'),  
        Index('idx_user_profile_access_expires_at', 'expires_at'),
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
# INSTAGRAM DATA TABLES (From Apify API)
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
    profile_pic_url_hd = Column(Text, nullable=True)  # High definition profile picture
    cdn_avatar_url = Column(Text, nullable=True)  # CDN processed profile picture URL
    
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
    
    # Category (Instagram business category)
    category = Column(String(255), nullable=True)
    instagram_business_category = Column(String(100), nullable=True)  # Renamed for clarity

    # Location detection
    detected_country = Column(String(2), nullable=True)  # ISO 2-letter country code (e.g., "AE", "US")
    
    # AI-Enhanced Content Intelligence (added by AI migration)
    ai_primary_content_type = Column(String(50), nullable=True)  # AI-determined main category (DEPRECATED - use ai_top_3_categories)
    ai_content_distribution = Column(JSONB, nullable=True)  # {"Fashion": 0.4, "Travel": 0.3, etc}
    ai_avg_sentiment_score = Column(Float, nullable=True, default=0.0)  # Average sentiment across posts
    ai_language_distribution = Column(JSONB, nullable=True)  # {"en": 0.8, "ar": 0.2, etc}
    ai_content_quality_score = Column(Float, nullable=True, default=0.0)  # Overall content quality
    ai_profile_analyzed_at = Column(DateTime(timezone=True), nullable=True)  # When AI analysis was done
    
    # NEW: Top Categories System for Frontend Display
    ai_top_3_categories = Column(JSONB, nullable=True)  # [{"category": "Fashion & Beauty", "percentage": 45.2, "confidence": 0.87}, ...]
    ai_top_10_categories = Column(JSONB, nullable=True)  # [{"category": "Fashion & Beauty", "percentage": 45.2, "confidence": 0.87}, ...]

    # COMPREHENSIVE AI ANALYSIS (All 10 Models)
    ai_audience_quality = Column(JSONB, nullable=True)  # Audience authenticity, engagement quality, bot detection
    ai_visual_content = Column(JSONB, nullable=True)  # Visual aesthetics, composition, consistency analysis
    ai_audience_insights = Column(JSONB, nullable=True)  # Demographics, interests, behavioral patterns
    ai_trend_detection = Column(JSONB, nullable=True)  # Content trends, viral potential, momentum analysis
    ai_advanced_nlp = Column(JSONB, nullable=True)  # Writing style, vocabulary, emotional patterns
    ai_fraud_detection = Column(JSONB, nullable=True)  # Fraud risk, suspicious patterns, authenticity
    ai_behavioral_patterns = Column(JSONB, nullable=True)  # Posting patterns, lifecycle, consistency

    # Comprehensive AI Metadata
    ai_comprehensive_analysis_version = Column(String(20), nullable=True)  # Track comprehensive AI version
    ai_comprehensive_analyzed_at = Column(DateTime(timezone=True), nullable=True)  # When comprehensive analysis completed
    ai_models_success_rate = Column(Float, nullable=True)  # Success rate of all 10 models (0.0-1.0)
    ai_models_status = Column(JSONB, nullable=True)  # Status of each individual model
    
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
    search_history = relationship("SearchHistory", back_populates="profile", cascade="all, delete-orphan")
    ai_analysis_jobs = relationship("AIAnalysisJob", back_populates="profile", cascade="all, delete-orphan")
    campaign_creators = relationship("CampaignCreator", back_populates="profile", cascade="all, delete-orphan")
    
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
    """COMPREHENSIVE Instagram post with ALL Apify post datapoints"""
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
    
    # AI Content Intelligence (added by AI migration)
    ai_content_category = Column(String(50), nullable=True, index=True)  # Fashion, Tech, Travel, etc.
    ai_category_confidence = Column(Float, nullable=True, default=0.0)  # 0.0-1.0 confidence
    ai_sentiment = Column(String(20), nullable=True, index=True)  # positive, negative, neutral
    ai_sentiment_score = Column(Float, nullable=True, default=0.0)  # -1.0 to +1.0
    ai_sentiment_confidence = Column(Float, nullable=True, default=0.0)  # 0.0-1.0
    ai_language_code = Column(String(10), nullable=True, index=True)  # ISO language code
    ai_language_confidence = Column(Float, nullable=True, default=0.0)  # 0.0-1.0
    ai_analysis_raw = Column(JSONB, nullable=True)  # Full AI analysis results
    ai_analyzed_at = Column(DateTime(timezone=True), nullable=True, index=True)  # When analyzed
    ai_analysis_version = Column(String(20), nullable=True, default='1.0.0')  # Track model versions
    
    # Media storage
    post_images = Column(JSONB)  # Array of image versions/sizes stored
    post_thumbnails = Column(JSONB)  # Array of thumbnail versions
    
    # Raw data backup
    raw_data = Column(JSONB, nullable=False)

    # CDN URLs (Cloudflare R2)
    cdn_thumbnail_url = Column(Text, nullable=True)  # Optimized thumbnail URL from Cloudflare

    # Analysis source tracking
    analysis_source = Column(String(50), nullable=False, default='creator_analytics', index=True)  # 'creator_analytics', 'post_analytics', 'campaign'

    # Relationships
    profile = relationship("Profile", back_populates="posts")
    comment_sentiment = relationship("CommentSentiment", back_populates="post", cascade="all, delete-orphan")
    campaign_posts = relationship("CampaignPost", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_posts_profile_timestamp', 'profile_id', 'taken_at_timestamp'),
        Index('idx_posts_engagement', 'likes_count', 'comments_count'),
        Index('idx_posts_media_type', 'media_type'),
        Index('idx_posts_carousel', 'is_carousel'),
    )


# =============================================================================
# ANALYTICS & INSIGHTS TABLES (Enhanced from Apify data)
# =============================================================================

class AudienceDemographics(Base):
    """Enhanced audience demographics (computed from Apify follower data)"""
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
    analysis_method = Column(Text)  # 'apify_enhanced', 'manual', 'estimated'
    
    # Relationship
    profile = relationship("Profile", back_populates="audience_demographics")
    
    __table_args__ = (
        Index('idx_audience_demographics_sampled', 'last_sampled'),
    )


class CreatorMetadata(Base):
    """Enhanced creator metadata (extracted from Apify profile data)"""
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
    """Related/similar profiles (from Apify suggestions)"""
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
    source_type = Column(String(50), default='user_search', index=True)  # 'user_search' or 'background_discovery'
    source = Column(String(50))  # 'apify', 'manual', 'algorithm'
    
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
# CAMPAIGN MODULE - Brand Campaign Management
# =============================================================================

class Campaign(Base):
    """Brand campaigns for managing Instagram influencer collaborations"""
    __tablename__ = "campaigns"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Campaign details
    name = Column(String(255), nullable=False)
    description = Column(Text)  # Campaign description
    brand_name = Column(String(255), nullable=False)
    brand_logo_url = Column(Text)  # CDN URL for brand logo
    status = Column(String(20), nullable=False, default='draft')  # draft, active, paused, in_review, completed, archived

    # Budget tracking
    budget = Column(Numeric(12, 2))  # Total campaign budget
    spent = Column(Numeric(12, 2), default=0)  # Amount spent so far

    # Campaign dates
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))

    # Metadata
    tags = Column(ARRAY(String), default=list)  # Campaign tags for organization
    created_by = Column(String(20), default='user')  # user | superadmin
    proposal_id = Column(UUID(as_uuid=True), ForeignKey('campaign_proposals.id', ondelete='SET NULL'), nullable=True)  # Link to proposal if created from one

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True))  # When campaign was archived

    # Relationships
    user = relationship("User", back_populates="campaigns")
    campaign_posts = relationship("CampaignPost", back_populates="campaign", cascade="all, delete-orphan")
    campaign_creators = relationship("CampaignCreator", back_populates="campaign", cascade="all, delete-orphan")
    proposal = relationship("CampaignProposal", back_populates="campaigns", foreign_keys=[proposal_id])

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'paused', 'in_review', 'completed', 'archived')", name='campaigns_status_check'),
        Index('idx_campaigns_user_id', 'user_id'),
        Index('idx_campaigns_status', 'status'),
        Index('idx_campaigns_created_at', 'created_at'),
        Index('idx_campaigns_proposal_id', 'proposal_id'),
        Index('idx_campaigns_archived_at', 'archived_at'),
    )


class CampaignPost(Base):
    """Instagram posts associated with campaigns"""
    __tablename__ = "campaign_posts"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True)

    # Post metadata
    instagram_post_url = Column(Text, nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_posts")
    post = relationship("Post", back_populates="campaign_posts")

    __table_args__ = (
        UniqueConstraint('campaign_id', 'post_id', name='unique_campaign_post'),
        Index('idx_campaign_posts_campaign_id', 'campaign_id'),
        Index('idx_campaign_posts_post_id', 'post_id'),
        Index('idx_campaign_posts_added_at', 'added_at'),
    )


class CampaignCreator(Base):
    """Unique creators/influencers in campaigns (auto-populated from posts)"""
    __tablename__ = "campaign_creators"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)

    # Creator metadata
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_creators")
    profile = relationship("Profile", back_populates="campaign_creators")

    __table_args__ = (
        UniqueConstraint('campaign_id', 'profile_id', name='unique_campaign_creator'),
        Index('idx_campaign_creators_campaign_id', 'campaign_id'),
        Index('idx_campaign_creators_profile_id', 'profile_id'),
    )


# =============================================================================
# CAMPAIGN WORKFLOW TABLES (SUPERADMIN FLOW)
# =============================================================================

class CampaignInfluencerSelection(Base):
    """Influencer selections for superadmin-managed campaigns"""
    __tablename__ = "campaign_influencer_selections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)

    # Selection details
    selected_by = Column(UUID(as_uuid=True), nullable=False)
    selection_status = Column(String(20), nullable=False, default='pending')

    # Locking details
    locked_at = Column(DateTime(timezone=True))
    locked_by = Column(UUID(as_uuid=True))
    lock_expires_at = Column(DateTime(timezone=True))

    # Metadata
    selection_notes = Column(Text)
    estimated_cost = Column(Numeric(12, 2))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    campaign = relationship("Campaign")
    profile = relationship("Profile")

    __table_args__ = (
        CheckConstraint("selection_status IN ('pending', 'locked', 'rejected', 'removed')", name='campaign_influencer_selections_status_check'),
        UniqueConstraint('campaign_id', 'profile_id', name='unique_campaign_profile'),
        Index('idx_campaign_influencer_selections_campaign', 'campaign_id'),
        Index('idx_campaign_influencer_selections_profile', 'profile_id'),
        Index('idx_campaign_influencer_selections_status', 'selection_status'),
    )


class CampaignContentApproval(Base):
    """Content approval workflow for superadmin-managed campaigns"""
    __tablename__ = "campaign_content_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey('posts.id', ondelete='CASCADE'))

    # Content details
    content_type = Column(String(20), nullable=False)
    content_url = Column(Text)
    content_caption = Column(Text)
    content_media_urls = Column(JSONB, default=list)

    # Approval workflow
    approval_status = Column(String(20), nullable=False, default='pending')
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(UUID(as_uuid=True))

    # Feedback
    reviewer_notes = Column(Text)
    revision_notes = Column(Text)
    revision_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    campaign = relationship("Campaign")
    profile = relationship("Profile")
    post = relationship("Post")

    __table_args__ = (
        CheckConstraint("content_type IN ('draft', 'final', 'published')", name='campaign_content_approvals_type_check'),
        CheckConstraint("approval_status IN ('pending', 'approved', 'rejected', 'revision_requested')", name='campaign_content_approvals_status_check'),
        Index('idx_campaign_content_approvals_campaign', 'campaign_id'),
        Index('idx_campaign_content_approvals_profile', 'profile_id'),
        Index('idx_campaign_content_approvals_status', 'approval_status'),
    )


class CampaignWorkflowNotification(Base):
    """Notifications for campaign workflow events"""
    __tablename__ = "campaign_workflow_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)

    # Notification details
    notification_type = Column(String(50), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)

    # Content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(Text)
    notification_metadata = Column('metadata', JSONB, default=dict)

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    campaign = relationship("Campaign")

    __table_args__ = (
        CheckConstraint("notification_type IN ('influencer_selected', 'influencer_locked', 'influencer_rejected', 'content_submitted', 'content_approved', 'content_rejected', 'revision_requested', 'campaign_completed')", name='campaign_workflow_notifications_type_check'),
        Index('idx_campaign_workflow_notifications_recipient', 'recipient_id', 'is_read'),
        Index('idx_campaign_workflow_notifications_campaign', 'campaign_id'),
        Index('idx_campaign_workflow_notifications_type', 'notification_type'),
    )


class CampaignWorkflowState(Base):
    """Track campaign workflow state for superadmin-managed campaigns"""
    __tablename__ = "campaign_workflow_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # Workflow stages
    current_stage = Column(String(50), nullable=False, default='draft')

    # Stage timestamps
    draft_started_at = Column(DateTime(timezone=True), server_default=func.now())
    selection_started_at = Column(DateTime(timezone=True))
    lock_confirmed_at = Column(DateTime(timezone=True))
    content_submission_started_at = Column(DateTime(timezone=True))
    active_started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Counters
    influencers_selected = Column(Integer, default=0)
    influencers_locked = Column(Integer, default=0)
    content_pending = Column(Integer, default=0)
    content_approved = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    campaign = relationship("Campaign")

    __table_args__ = (
        CheckConstraint("current_stage IN ('draft', 'influencer_selection', 'awaiting_lock', 'locked', 'content_submission', 'content_review', 'active', 'completed', 'cancelled')", name='campaign_workflow_state_stage_check'),
        Index('idx_campaign_workflow_state_stage', 'current_stage'),
    )


class CampaignProposal(Base):
    """Campaign proposals from superadmin to users"""
    __tablename__ = "campaign_proposals"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_admin_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Proposal details
    title = Column(String(255), nullable=False)
    campaign_name = Column(String(255), nullable=False)
    description = Column(Text)
    proposal_notes = Column(Text)  # Superadmin notes for the user
    proposal_type = Column(String(50), default='influencer_list')  # influencer_list | campaign_package

    # Status tracking
    status = Column(String(20), nullable=False, default='draft')  # draft, sent, in_review, approved, rejected

    # Budget & metrics
    total_budget = Column(Numeric(12, 2))
    expected_reach = Column(BigInteger)
    avg_engagement_rate = Column(Numeric(5, 2))
    estimated_impressions = Column(BigInteger)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    sent_at = Column(DateTime(timezone=True))  # When sent to user
    responded_at = Column(DateTime(timezone=True))  # When user responded

    # User response
    rejection_reason = Column(Text)  # If rejected, why

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="campaign_proposals")
    created_by_admin = relationship("User", foreign_keys=[created_by_admin_id])
    proposal_influencers = relationship("ProposalInfluencer", back_populates="proposal", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="proposal")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'sent', 'in_review', 'approved', 'rejected')", name='proposal_status_check'),
        CheckConstraint("proposal_type IN ('influencer_list', 'campaign_package')", name='proposal_type_check'),
        Index('idx_proposals_user_id', 'user_id'),
        Index('idx_proposals_status', 'status'),
        Index('idx_proposals_created_at', 'created_at'),
    )


class ProposalInfluencer(Base):
    """Influencers suggested in proposals with user selection tracking"""
    __tablename__ = "proposal_influencers"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey('campaign_proposals.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)

    # Superadmin's suggestion
    estimated_cost = Column(Numeric(12, 2))  # Estimated cost for this influencer
    suggested_by_admin = Column(Boolean, default=True)

    # User's selection
    selected_by_user = Column(Boolean, default=False)  # User selected this influencer
    selection_notes = Column(Text)  # User notes about selection/deselection

    # Timestamps
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    selected_at = Column(DateTime(timezone=True))  # When user selected

    # Relationships
    proposal = relationship("CampaignProposal", back_populates="proposal_influencers")
    profile = relationship("Profile")

    __table_args__ = (
        UniqueConstraint('proposal_id', 'profile_id', name='unique_proposal_influencer'),
        Index('idx_proposal_influencers_proposal_id', 'proposal_id'),
        Index('idx_proposal_influencers_profile_id', 'profile_id'),
        Index('idx_proposal_influencers_selected', 'selected_by_user'),
    )


# =============================================================================
# MY LISTS MODULE - User List Management
# =============================================================================

class UserList(Base):
    """User-created lists for organizing Instagram profiles"""
    __tablename__ = "user_lists"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # List metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default='#3B82F6')  # Hex color for UI customization
    icon = Column(String(50), default='list')  # Icon identifier for UI
    
    # List settings
    is_public = Column(Boolean, nullable=False, default=False)  # Future: allow public list sharing
    is_favorite = Column(Boolean, nullable=False, default=False)  # Mark important lists
    sort_order = Column(Integer, default=0)  # User-defined list ordering
    
    # List statistics (computed)
    items_count = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="user_lists")
    list_items = relationship("UserListItem", back_populates="user_list", cascade="all, delete-orphan", order_by="UserListItem.position")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(name)) > 0", name='user_lists_name_not_empty'),
        CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name='user_lists_color_valid'),
        Index('idx_user_lists_user_id', 'user_id'),
        Index('idx_user_lists_created_at', 'created_at'),
        Index('idx_user_lists_updated', 'last_updated'),
        Index('idx_user_lists_public', 'is_public'),
    )


class UserListItem(Base):
    """Junction table linking lists to Instagram profiles with customization"""
    __tablename__ = "user_list_items"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey('user_lists.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # Denormalized for RLS
    
    # Item metadata
    position = Column(Integer, nullable=False, default=0)  # Order within the list
    notes = Column(Text)  # User notes for this profile in this list
    tags = Column(ARRAY(Text))  # User-defined tags for this item
    
    # Item settings
    is_pinned = Column(Boolean, nullable=False, default=False)  # Pin to top of list
    color_label = Column(String(7))  # Optional color label for this item
    
    # Timestamps
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_list = relationship("UserList", back_populates="list_items")
    profile = relationship("Profile")
    user = relationship("User", back_populates="user_list_items")
    
    # Constraints
    __table_args__ = (
        Index('idx_user_list_items_list_profile', 'list_id', 'profile_id', unique=True),  # Prevent duplicates
        CheckConstraint("position >= 0", name='user_list_items_position_non_negative'),
        Index('idx_user_list_items_list_id', 'list_id'),
        Index('idx_user_list_items_profile_id', 'profile_id'),
        Index('idx_user_list_items_user_id', 'user_id'),
        Index('idx_user_list_items_position', 'list_id', 'position'),
        Index('idx_user_list_items_added_at', 'added_at'),
    )


# =============================================================================
# ENHANCED LISTS SYSTEM MODELS  
# Advanced list management with collaboration, templates, and analytics
# =============================================================================

class ListTemplate(Base):
    """Pre-defined list templates for common use cases"""
    __tablename__ = "list_templates"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Template metadata
    template_name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100), nullable=False)  # campaign, discovery, analysis, outreach
    
    # Template configuration
    default_settings = Column(JSONB, nullable=False, default='{}')
    required_fields = Column(JSONB, default='[]')
    optional_fields = Column(JSONB, default='[]')
    auto_rules = Column(JSONB, default='{}')
    
    # Template properties
    is_public = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    usage_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_list_templates_category', 'category', 'is_public'),
        Index('idx_list_templates_usage', 'usage_count'),
        Index('idx_list_templates_creator', 'created_by', 'created_at'),
    )


class ListCollaboration(Base):
    """Share lists and collaborate with team members"""
    __tablename__ = "list_collaborations"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey('user_lists.id', ondelete='CASCADE'), nullable=False)
    
    # Collaboration participants
    shared_with_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    shared_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Permissions
    permission_level = Column(String(50), nullable=False, default='view')  # view, comment, edit, admin
    can_add_items = Column(Boolean, default=False)
    can_remove_items = Column(Boolean, default=False)
    can_edit_items = Column(Boolean, default=False)
    can_invite_others = Column(Boolean, default=False)
    
    # Collaboration metadata
    invitation_message = Column(Text)
    accepted_at = Column(DateTime(timezone=True))
    last_accessed = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(50), default='pending')  # pending, accepted, declined, revoked
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_list = relationship("UserList")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by_user = relationship("User", foreign_keys=[shared_by_user_id])
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_list_collaborations_list', 'list_id', 'status'),
        Index('idx_list_collaborations_user', 'shared_with_user_id', 'status'),
        Index('idx_list_collaborations_shared_by', 'shared_by_user_id', 'created_at'),
        Index('idx_list_collaborations_unique', 'list_id', 'shared_with_user_id', unique=True),
    )


# class ListActivityLog(Base):
#     """Activity log for list changes and collaboration - TEMPORARILY DISABLED"""
#     __tablename__ = "list_activity_logs"
#
#     # Primary identification
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
#     list_id = Column(UUID(as_uuid=True), ForeignKey('user_lists.id', ondelete='CASCADE'), nullable=False, index=True)
#     user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
#
#     # Activity details
#     activity_type = Column(String(50), nullable=False, index=True)  # created, updated, item_added, item_removed, shared, etc.
#     description = Column(Text, nullable=False)
#
#     # Context data
#     affected_item_id = Column(UUID(as_uuid=True))  # Profile ID if activity affects an item
#     activity_metadata = Column(JSONB, default='{}')
#
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
#
#     # Relationships
#     user_list = relationship("UserList")
#     user = relationship("User", foreign_keys=[user_id])
#
#     # Database constraints and indexes
#     __table_args__ = (
#         Index('idx_list_activity_list_created', 'list_id', 'created_at'),
#         Index('idx_list_activity_user_created', 'user_id', 'created_at'),
#         Index('idx_list_activity_type_created', 'activity_type', 'created_at'),
#     )


class ListPerformanceMetrics(Base):
    """Performance metrics and analytics for lists"""
    __tablename__ = "list_performance_metrics"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey('user_lists.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    
    # Performance metrics
    total_views = Column(Integer, default=0)
    unique_viewers = Column(Integer, default=0)
    export_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    collaboration_count = Column(Integer, default=0)
    
    # Engagement metrics
    avg_session_duration = Column(Float, default=0.0)  # in minutes
    bounce_rate = Column(Float, default=0.0)  # percentage
    most_viewed_items = Column(JSONB, default='[]')
    
    # Usage patterns
    peak_usage_hours = Column(JSONB, default='[]')
    usage_by_day = Column(JSONB, default='{}')
    device_breakdown = Column(JSONB, default='{}')
    
    # Performance scores
    engagement_score = Column(Float, default=0.0)  # 0-100
    utility_score = Column(Float, default=0.0)  # 0-100
    collaboration_score = Column(Float, default=0.0)  # 0-100
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_calculated_at = Column(DateTime(timezone=True))
    
    # Relationships
    user_list = relationship("UserList")
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_list_performance_engagement', 'engagement_score'),
        Index('idx_list_performance_utility', 'utility_score'),
        Index('idx_list_performance_updated', 'updated_at'),
    )


class ListExportJob(Base):
    """Track export jobs for lists"""
    __tablename__ = "list_export_jobs"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey('user_lists.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Export configuration
    export_format = Column(String(20), nullable=False)  # csv, xlsx, json, pdf
    include_fields = Column(JSONB, default='[]')
    export_filters = Column(JSONB, default='{}')
    
    # Job status
    status = Column(String(50), default='pending')  # pending, processing, completed, failed, expired
    progress_percentage = Column(Integer, default=0)
    
    # File information
    file_path = Column(String(500))
    file_size_bytes = Column(BigInteger)
    download_count = Column(Integer, default=0)
    
    # Processing details
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP + INTERVAL '7 days'"))
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_list = relationship("UserList")
    user = relationship("User", foreign_keys=[user_id])
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_list_export_user_created', 'user_id', 'created_at'),
        Index('idx_list_export_list_created', 'list_id', 'created_at'),
        Index('idx_list_export_status', 'status', 'created_at'),
        Index('idx_list_export_expires', 'expires_at'),
    )


# =============================================================================
# USER AVATAR MANAGEMENT
# =============================================================================

class UserAvatar(Base):
    """Model for user uploaded avatars"""
    
    __tablename__ = "user_avatars"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    original_filename = Column(String)
    processed_size = Column(String)  # e.g., "400x400"
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<UserAvatar(id={self.id}, user_id={self.user_id}, file_path={self.file_path}, is_active={self.is_active})>"
    
    @property
    def public_url(self):
        """Generate public URL for the avatar"""
        from app.core.config import settings
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/avatars/{self.file_path}"
    
    __table_args__ = (
        Index('idx_user_avatars_user_id', 'user_id'),
        Index('idx_user_avatars_active', 'user_id', 'is_active'),
        CheckConstraint('is_active IN (true, false)', name='check_is_active_boolean'),
    )


# =============================================================================
# AI ANALYSIS JOB TRACKING SYSTEM
# =============================================================================

class AIAnalysisJob(Base):
    """AI Analysis Job Tracking - Mission Critical for Background Task Management"""
    __tablename__ = "ai_analysis_jobs"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    job_id = Column(String(255), unique=True, nullable=False, index=True)  # Human-readable job ID
    
    # Job scope and target
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    job_type = Column(String(50), nullable=False, index=True)  # 'profile_analysis', 'bulk_analysis', 'repair_analysis'
    
    # Job status tracking
    status = Column(String(20), nullable=False, default='pending', index=True)  
    # pending, running, completed, failed, cancelled, repair_needed
    
    # Progress tracking
    total_posts = Column(Integer, default=0)
    posts_processed = Column(Integer, default=0)
    posts_successful = Column(Integer, default=0)
    posts_failed = Column(Integer, default=0)
    
    # Timing
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)  # For detecting hung jobs
    
    # Error handling and diagnostics
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)  # Detailed error info for debugging
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Results and validation
    profile_analysis_completed = Column(Boolean, default=False)  # Critical: Profile-level aggregation done
    data_consistency_validated = Column(Boolean, default=False)  # Critical: Data integrity checked
    analysis_metadata = Column(JSONB, nullable=True)  # Analysis results summary
    
    # Performance metrics
    processing_duration_seconds = Column(Integer, nullable=True)
    posts_per_second = Column(Float, nullable=True)
    
    # Relationships
    profile = relationship("Profile", back_populates="ai_analysis_jobs")
    user = relationship("User", back_populates="ai_analysis_jobs")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'repair_needed')", 
                       name='check_job_status_valid'),
        CheckConstraint("job_type IN ('profile_analysis', 'bulk_analysis', 'repair_analysis')", 
                       name='check_job_type_valid'),
        CheckConstraint("posts_processed >= 0", name='check_posts_processed_non_negative'),
        CheckConstraint("posts_successful >= 0", name='check_posts_successful_non_negative'),
        CheckConstraint("posts_failed >= 0", name='check_posts_failed_non_negative'),
        CheckConstraint("retry_count >= 0", name='check_retry_count_non_negative'),
        CheckConstraint("max_retries >= 0", name='check_max_retries_non_negative'),
        Index('idx_ai_jobs_status_created', 'status', 'created_at'),
        Index('idx_ai_jobs_profile_status', 'profile_id', 'status'),
        Index('idx_ai_jobs_user_created', 'user_id', 'created_at'),
        Index('idx_ai_jobs_heartbeat', 'last_heartbeat'),
        Index('idx_ai_jobs_job_type', 'job_type'),
        Index('idx_ai_jobs_completion_status', 'profile_analysis_completed', 'data_consistency_validated'),
    )


class AIAnalysisJobLog(Base):
    """Detailed logging for AI Analysis Jobs - Critical for Debugging and Monitoring"""
    __tablename__ = "ai_analysis_job_logs"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('ai_analysis_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Log entry details
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    log_level = Column(String(10), nullable=False, index=True)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    
    # Contextual information
    post_id = Column(UUID(as_uuid=True), nullable=True)  # If log relates to specific post
    processing_step = Column(String(50), nullable=True)  # 'post_analysis', 'profile_aggregation', 'validation'
    execution_time_ms = Column(Integer, nullable=True)  # Time taken for this step
    
    # Additional context
    log_metadata = Column(JSONB, nullable=True)  # Additional structured data
    
    # Relationships
    job = relationship("AIAnalysisJob", backref="logs")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", 
                       name='check_log_level_valid'),
        Index('idx_ai_job_logs_job_timestamp', 'job_id', 'timestamp'),
        Index('idx_ai_job_logs_level_timestamp', 'log_level', 'timestamp'),
        Index('idx_ai_job_logs_step', 'processing_step'),
    )


# =============================================================================
# DISCOVERY SYSTEM MODELS
# Credit-gated influencer discovery with advanced filtering and profile unlocking
# =============================================================================

class DiscoverySession(Base):
    """Track paginated discovery searches and credit consumption"""
    __tablename__ = "discovery_sessions"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Search metadata
    search_criteria = Column(JSONB, nullable=False, default='{}')
    total_results = Column(Integer, default=0)
    pages_viewed = Column(Integer, default=1)
    results_per_page = Column(Integer, default=20)
    
    # Credit tracking
    credits_consumed = Column(Integer, default=0)
    free_pages_used = Column(Integer, default=0)
    
    # Session timing
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP + INTERVAL '2 hours'"))
    
    # Search performance
    search_duration_ms = Column(Integer)
    data_source = Column(String(50), default='database')
    
    # Relationships
    user = relationship("User")
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_discovery_sessions_user', 'user_id', 'created_at'),
        Index('idx_discovery_sessions_expires', 'expires_at'),
        Index('idx_discovery_sessions_active', 'user_id', 'expires_at'),
    )


class DiscoveryFilter(Base):
    """Allow users to save and reuse complex filter combinations"""
    __tablename__ = "discovery_filters"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Filter metadata
    filter_name = Column(String(200), nullable=False)
    description = Column(Text)
    filter_criteria = Column(JSONB, nullable=False, default='{}')
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True))
    
    # Metadata
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_discovery_filters_user', 'user_id', 'created_at'),
        Index('idx_discovery_filters_name', 'user_id', 'filter_name'),
    )


class UnlockedProfile(Base):
    """Track which profiles each user has unlocked with credits"""
    __tablename__ = "unlocked_profiles"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    
    # Unlock details
    unlocked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    credits_spent = Column(Integer, nullable=False)
    unlock_type = Column(String(50), default='profile_analysis')
    
    # Unlock metadata
    unlock_reason = Column(Text)
    transaction_id = Column(BigInteger, ForeignKey('credit_transactions.id'))
    
    # Relationships
    user = relationship("User")
    profile = relationship("Profile")
    transaction = relationship("CreditTransaction")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint('credits_spent >= 0', name='unlocked_profiles_credits_positive'),
        Index('idx_unlocked_profiles_user', 'user_id', 'unlocked_at'),
        Index('idx_unlocked_profiles_profile', 'profile_id'),
        Index('idx_unlocked_profiles_user_profile', 'user_id', 'profile_id', unique=True),
    )


# =============================================================================
# CREDITS SYSTEM MODELS
# Comprehensive credits-based monetization layer for the analytics platform
# =============================================================================

class CreditPackage(Base):
    """Subscription packages with credit allowances"""
    __tablename__ = "credit_packages"
    
    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(150), nullable=False)
    
    # Credit allocation
    monthly_credits = Column(Integer, nullable=False, default=0)
    description = Column(Text)
    
    # Package settings
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    wallets = relationship("CreditWallet", back_populates="package")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("monthly_credits >= 0", name='credit_packages_credits_positive'),
        Index('idx_credit_packages_active', 'is_active', 'sort_order'),
    )


class CreditPricingRule(Base):
    """Pricing rules for different credit actions"""
    __tablename__ = "credit_pricing_rules"
    
    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    
    # Pricing configuration
    cost_per_action = Column(Integer, nullable=False, default=0)
    free_allowance_per_month = Column(Integer, default=0, nullable=False)
    description = Column(Text)
    
    # Rule status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("cost_per_action >= 0", name='credit_pricing_cost_positive'),
        CheckConstraint("free_allowance_per_month >= 0", name='credit_pricing_allowance_positive'),
        Index('idx_credit_pricing_active', 'action_type', postgresql_where=text('is_active = true')),
    )


class CreditWallet(Base):
    """User credit balance and billing cycle information"""
    __tablename__ = "credit_wallets"
    
    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    package_id = Column(Integer, ForeignKey('credit_packages.id', ondelete='SET NULL'), nullable=True)
    
    # Balance tracking
    current_balance = Column(Integer, default=0, nullable=False)
    total_earned_this_cycle = Column(Integer, default=0, nullable=False)
    total_purchased_this_cycle = Column(Integer, default=0, nullable=False)
    total_spent_this_cycle = Column(Integer, default=0, nullable=False)
    lifetime_earned = Column(Integer, default=0, nullable=False)
    lifetime_spent = Column(Integer, default=0, nullable=False)
    
    # Billing cycle management
    current_billing_cycle_start = Column(DateTime(timezone=True))
    current_billing_cycle_end = Column(DateTime(timezone=True))
    next_reset_date = Column(Date)
    next_credit_refresh_date = Column(DateTime(timezone=True))
    rollover_months_allowed = Column(Integer, default=0)
    
    # Subscription status
    subscription_status = Column(String(30), default='active', nullable=False)
    subscription_active = Column(Boolean, default=True, nullable=False)
    auto_refresh_enabled = Column(Boolean, default=True, nullable=False)
    
    # Account management
    is_locked = Column(Boolean, default=False, nullable=False)
    freeze_reason = Column(Text)
    last_activity_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    package = relationship("CreditPackage", back_populates="wallets")
    transactions = relationship("CreditTransaction", back_populates="wallet")
    unlocked_influencers = relationship("UnlockedInfluencer", primaryjoin="CreditWallet.user_id == foreign(UnlockedInfluencer.user_id)", back_populates="user_wallet")
    top_up_orders = relationship("CreditTopUpOrder", back_populates="wallet")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint('current_balance >= 0', name='check_balance_non_negative'),
        CheckConstraint('total_earned_this_cycle >= 0', name='check_earned_cycle_non_negative'),
        CheckConstraint('total_spent_this_cycle >= 0', name='check_spent_cycle_non_negative'),
        CheckConstraint('lifetime_earned >= 0', name='check_lifetime_earned_non_negative'),
        CheckConstraint('lifetime_spent >= 0', name='check_lifetime_spent_non_negative'),
        Index('idx_credit_wallets_user_id', 'user_id'),
        Index('idx_credit_wallets_package_id', 'package_id'),
        Index('idx_credit_wallets_status', 'subscription_status'),
        Index('idx_credit_wallets_refresh', 'next_credit_refresh_date'),
        Index('idx_credit_wallets_activity', 'last_activity_at'),
    )


class CreditTransaction(Base):
    """Individual credit transactions (earned, spent, refunded)"""
    __tablename__ = "credit_transactions"
    
    # Primary identification
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey('credit_wallets.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Transaction details
    transaction_type = Column(String(30), nullable=False, index=True)
    action_type = Column(String(50), nullable=True, index=True)
    amount = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    
    # Reference tracking
    reference_type = Column(String(50), nullable=True, index=True)
    reference_id = Column(String(255), nullable=True, index=True)
    
    # Balance tracking at transaction time
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    
    # Billing cycle tracking
    billing_cycle_date = Column(Date, nullable=True, index=True)
    
    # Metadata
    transaction_metadata = Column(JSONB, nullable=False, default='{}')
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    wallet = relationship("CreditWallet", back_populates="transactions")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("amount != 0", name='check_transaction_amount_non_zero'),
        CheckConstraint("balance_before >= 0", name='check_balance_before_non_negative'),
        CheckConstraint("balance_after >= 0", name='check_balance_after_non_negative'),
        CheckConstraint("transaction_type IN ('earned', 'spent', 'refunded', 'expired', 'bonus')", name='check_transaction_type_valid'),
        CheckConstraint("status IN ('pending', 'completed', 'failed', 'cancelled')", name='check_status_valid'),
        Index('idx_credit_transactions_wallet_created', 'wallet_id', 'created_at'),
        Index('idx_credit_transactions_user_created', 'user_id', 'created_at'),
        Index('idx_credit_transactions_type_created', 'transaction_type', 'created_at'),
        Index('idx_credit_transactions_billing_cycle', 'user_id', 'billing_cycle_date'),
        Index('idx_credit_transactions_reference', 'reference_type', 'reference_id'),
    )


class UnlockedInfluencer(Base):
    """Track permanently unlocked influencers for each user - MATCHES ACTUAL DATABASE SCHEMA"""
    __tablename__ = "unlocked_influencers"
    
    # ACTUAL DATABASE COLUMNS ONLY
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    username = Column(String(100), nullable=False)  # For quick lookup
    unlocked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    credits_spent = Column(Integer, nullable=False)
    transaction_id = Column(BigInteger)  # Link to credit transaction
    
    # Relationships
    user_wallet = relationship("CreditWallet", primaryjoin="foreign(UnlockedInfluencer.user_id) == CreditWallet.user_id", back_populates="unlocked_influencers")
    profile = relationship("Profile")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint('credits_spent > 0', name='check_credits_spent_positive'),
        Index('idx_unlocked_influencers_user_id', 'user_id'),
        Index('idx_unlocked_influencers_profile_id', 'profile_id'),
        Index('idx_unlocked_influencers_username', 'user_id', 'username'),
        # Unique constraint to prevent duplicate unlocks
        Index('idx_unlocked_influencers_unique', 'user_id', 'profile_id', unique=True),
    )


class CreditUsageTracking(Base):
    """Detailed tracking of credit usage for analytics and billing"""
    __tablename__ = "credit_usage_tracking"
    
    # Primary identification
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Usage details
    feature_used = Column(String(50), nullable=False, index=True)
    credits_consumed = Column(Integer, nullable=False)
    
    # Context tracking
    profile_username = Column(String(100), nullable=True, index=True)
    session_identifier = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Pricing information at time of use
    cost_per_action = Column(Integer, nullable=False)
    pricing_rule_used = Column(String(100), nullable=True)
    
    # Billing cycle tracking
    billing_cycle_date = Column(Date, nullable=False, index=True)
    
    # Success tracking
    action_successful = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    used_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint('credits_consumed > 0', name='check_credits_consumed_positive'),
        CheckConstraint('cost_per_action > 0', name='check_cost_per_action_positive'),
        Index('idx_credit_usage_user_date', 'user_id', 'used_at'),
        Index('idx_credit_usage_feature', 'feature_used', 'used_at'),
        Index('idx_credit_usage_billing', 'billing_cycle_date', 'credits_consumed'),
        Index('idx_credit_usage_success', 'action_successful', 'used_at'),
        Index('idx_credit_usage_profile', 'profile_username', 'used_at'),
    )


class CreditTopUpOrder(Base):
    """Track credit top-up orders and payment processing"""
    __tablename__ = "credit_top_up_orders"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    wallet_id = Column(Integer, ForeignKey('credit_wallets.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Order details
    credits_purchased = Column(Integer, nullable=False)
    amount_usd_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    
    # Payment processing
    payment_intent_id = Column(String(100), nullable=True, index=True)
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(30), default='pending', nullable=False)
    
    # Processing details
    processed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    refund_reason = Column(Text, nullable=True)
    
    # Order metadata
    order_metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    wallet = relationship("CreditWallet", back_populates="top_up_orders")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint('credits_purchased > 0', name='check_credits_purchased_positive'),
        CheckConstraint('amount_usd_cents > 0', name='check_amount_positive'),
        CheckConstraint("payment_status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'refunded')", name='check_payment_status_valid'),
        Index('idx_credit_top_ups_wallet_created', 'wallet_id', 'created_at'),
        Index('idx_credit_top_ups_user_created', 'user_id', 'created_at'),
        Index('idx_credit_top_ups_status', 'payment_status', 'created_at'),
        Index('idx_credit_top_ups_payment_intent', 'payment_intent_id'),
    )

# =============================================================================
# TEAM MANAGEMENT SYSTEM - B2B SaaS Team Collaboration
# =============================================================================

class Team(Base):
    """
    Team entity for B2B SaaS collaboration
    Each team has a subscription and pooled usage limits
    """
    __tablename__ = 'teams'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Team information
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    
    # Subscription information
    subscription_tier = Column(String(20), nullable=False, default='free')  # free, standard, premium
    subscription_status = Column(String(20), nullable=False, default='active')  # active, trial, suspended, cancelled, past_due
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Team limits based on subscription
    max_team_members = Column(Integer, nullable=False, default=1)
    monthly_profile_limit = Column(Integer, nullable=False, default=5)
    monthly_email_limit = Column(Integer, nullable=False, default=0)
    monthly_posts_limit = Column(Integer, nullable=False, default=0)
    
    # Current month usage (pooled across all team members)
    profiles_used_this_month = Column(Integer, nullable=False, default=0)
    emails_used_this_month = Column(Integer, nullable=False, default=0)
    posts_used_this_month = Column(Integer, nullable=False, default=0)
    
    # Team settings
    settings = Column(JSONB, default='{}')
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    invitations = relationship("TeamInvitation", back_populates="team", cascade="all, delete-orphan")
    profile_access = relationship("TeamProfileAccess", back_populates="team", cascade="all, delete-orphan")
    currency_settings = relationship("TeamCurrencySettings", back_populates="team", uselist=False, cascade="all, delete-orphan")
    
    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("max_team_members > 0", name='teams_max_members_positive'),
        CheckConstraint("monthly_profile_limit >= 0", name='teams_profile_limit_non_negative'),
        CheckConstraint("monthly_email_limit >= 0", name='teams_email_limit_non_negative'),
        CheckConstraint("monthly_posts_limit >= 0", name='teams_posts_limit_non_negative'),
        CheckConstraint("profiles_used_this_month >= 0", name='teams_profiles_used_non_negative'),
        CheckConstraint("emails_used_this_month >= 0", name='teams_emails_used_non_negative'),
        CheckConstraint("posts_used_this_month >= 0", name='teams_posts_used_non_negative'),
        Index('idx_teams_subscription', 'subscription_tier', 'subscription_status'),
        Index('idx_teams_usage', 'profiles_used_this_month', 'emails_used_this_month'),
    )


class TeamCurrencySettings(Base):
    """
    Currency configuration per team (Industry Standard Pattern)
    Each team operates in one currency - eliminates currency complexity
    """
    __tablename__ = 'team_currency_settings'

    # Primary key is team_id (one currency per team)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), primary_key=True)

    # Currency configuration
    currency_code = Column(String(3), nullable=False, default='USD')  # ISO 4217 codes
    currency_symbol = Column(String(10), nullable=False, default='$')
    decimal_places = Column(Integer, nullable=False, default=2)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    team = relationship("Team", back_populates="currency_settings")

    # Database constraints and indexes
    __table_args__ = (
        CheckConstraint("decimal_places >= 0 AND decimal_places <= 4", name='currency_decimal_places_range'),
        CheckConstraint("LENGTH(currency_code) = 3", name='currency_code_length'),
        Index('idx_team_currency_settings_currency_code', 'currency_code'),
    )


class TeamMember(Base):
    """
    Team membership with roles and permissions
    Links users to teams with specific roles (owner/member)
    """
    __tablename__ = 'team_members'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Foreign keys
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Role and permissions
    role = Column(String(20), nullable=False, default='member')  # owner, member
    permissions = Column(JSONB, default='{}')
    status = Column(String(20), nullable=False, default='active')  # active, inactive, suspended, removed
    
    # Activity tracking
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    
    # Invitation tracking
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    invitation_accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="members")
    
    # Database constraints and indexes
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='unique_team_user_membership'),
        Index('idx_team_members_team_role', 'team_id', 'role', 'status'),
        Index('idx_team_members_user', 'user_id', 'status'),
        Index('idx_team_members_activity', 'last_active_at', 'status'),
    )

class TeamInvitation(Base):
    """
    Team invitation system for inviting new members
    Secure token-based invitations with expiration
    """
    __tablename__ = 'team_invitations'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Foreign keys
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False)
    invited_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Invitation details
    email = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='member')  # owner, member
    invitation_token = Column(String(255), nullable=False, unique=True)
    
    # Status and expiration
    status = Column(String(20), nullable=False, default='pending')  # pending, accepted, expired, cancelled
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Optional personal message
    personal_message = Column(Text, nullable=True)
    
    # Acceptance tracking
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Cancellation tracking
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="invitations")
    
    # Database constraints and indexes
    __table_args__ = (
        Index('idx_team_invitations_token', 'invitation_token'),
        Index('idx_team_invitations_email_status', 'email', 'status'),
        Index('idx_team_invitations_team_status', 'team_id', 'status'),
        Index('idx_team_invitations_expiry', 'expires_at', 'status'),
    )

class TeamProfileAccess(Base):
    """
    Team-based profile access tracking
    Records which teams have access to which Instagram profiles
    """
    __tablename__ = 'team_profile_access'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Foreign keys
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Access tracking
    accessed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="profile_access")
    
    # Database constraints and indexes
    __table_args__ = (
        UniqueConstraint('team_id', 'profile_id', name='unique_team_profile_access'),
        Index('idx_team_profile_access_team', 'team_id', 'accessed_at'),
        Index('idx_team_profile_access_profile', 'profile_id', 'accessed_at'),
    )

class MonthlyUsageTracking(Base):
    """
    Monthly usage tracking per team member
    Tracks individual member usage within team pooled limits
    """
    __tablename__ = 'monthly_usage_tracking'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Foreign keys
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Usage tracking period
    billing_month = Column(Date, nullable=False)  # First day of the billing month
    
    # Usage counters
    profiles_analyzed = Column(Integer, nullable=False, default=0)
    emails_unlocked = Column(Integer, nullable=False, default=0)
    posts_analyzed = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Database constraints and indexes
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', 'billing_month', name='unique_team_user_month_usage'),
        CheckConstraint("profiles_analyzed >= 0", name='monthly_usage_profiles_non_negative'),
        CheckConstraint("emails_unlocked >= 0", name='monthly_usage_emails_non_negative'),
        CheckConstraint("posts_analyzed >= 0", name='monthly_usage_posts_non_negative'),
        Index('idx_monthly_usage_team_month', 'team_id', 'billing_month'),
        Index('idx_monthly_usage_user_month', 'user_id', 'billing_month'),
    )