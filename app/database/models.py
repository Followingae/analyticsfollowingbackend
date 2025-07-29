from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Date, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid as uuid_lib

Base = declarative_base()

class User(Base):
    """Tracks brand-customers and their credits/subscriptions"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    email = Column(Text, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default='user')
    credits = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")
    user_profile_access = relationship("UserProfileAccess", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    """Stores each influencer's complete Instagram data from Decodo"""
    __tablename__ = "profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    username = Column(Text, unique=True, nullable=False)  # Always available
    
    # Core Profile Information
    full_name = Column(Text)
    biography = Column(Text)
    instagram_user_id = Column(Text)  # Instagram's internal ID
    fb_id = Column(Text)  # Facebook ID
    eimu_id = Column(Text)  # Extended Instagram ID
    
    # Follow Statistics (always available)
    followers_count = Column(Integer, nullable=False, default=0)
    following_count = Column(Integer, nullable=False, default=0)
    posts_count = Column(Integer, nullable=False, default=0)
    mutual_followers_count = Column(Integer, default=0)
    
    # Account Settings & Status (high reliability)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_private = Column(Boolean, nullable=False, default=False)
    is_business_account = Column(Boolean, default=False)
    is_professional_account = Column(Boolean, default=False)
    country_block = Column(Boolean, default=False)
    is_embeds_disabled = Column(Boolean, default=False)
    is_joined_recently = Column(Boolean, default=False)
    
    # Profile Media & Links (high reliability)
    profile_pic_url = Column(Text)
    profile_pic_url_hd = Column(Text)
    external_url = Column(Text)
    external_url_shimmed = Column(Text)  # Instagram wrapped URL
    
    # Business Information
    business_category_name = Column(Text)
    overall_category_name = Column(Text)
    category_enum = Column(Text)
    business_address_json = Column(Text)  # JSON string
    business_contact_method = Column(Text)
    business_email = Column(Text)
    business_phone_number = Column(Text)
    
    # Content & Features
    has_ar_effects = Column(Boolean, default=False)
    has_clips = Column(Boolean, default=False)  # Instagram Reels
    has_guides = Column(Boolean, default=False)
    has_channel = Column(Boolean, default=False)  # Broadcast channel
    highlight_reel_count = Column(Integer, default=0)
    pinned_channels_list_count = Column(Integer, default=0)
    
    # Privacy & Restrictions (viewer-specific, may be null)
    blocked_by_viewer = Column(Boolean)
    has_blocked_viewer = Column(Boolean)
    restricted_by_viewer = Column(Boolean)
    followed_by_viewer = Column(Boolean)
    follows_viewer = Column(Boolean)
    requested_by_viewer = Column(Boolean)
    has_requested_viewer = Column(Boolean)
    
    # Account Features & Settings
    hide_like_and_view_counts = Column(Boolean, default=False)
    should_show_category = Column(Boolean, default=True)
    should_show_public_contacts = Column(Boolean, default=True)
    show_account_transparency_details = Column(Boolean, default=True)
    show_text_post_app_badge = Column(Boolean, default=False)  # Threads badge
    has_onboarded_to_text_post_app = Column(Boolean, default=False)  # Threads integration
    remove_message_entrypoint = Column(Boolean, default=False)
    
    # AI & Special Features (low reliability)
    ai_agent_type = Column(Text)
    ai_agent_owner_username = Column(Text)
    transparency_label = Column(Text)
    transparency_product = Column(Text)
    
    # Supervision & Safety
    is_supervision_enabled = Column(Boolean, default=False)
    is_guardian_of_viewer = Column(Boolean, default=False)
    is_supervised_by_viewer = Column(Boolean, default=False)
    is_supervised_user = Column(Boolean, default=False)
    guardian_id = Column(Text)
    is_regulated_c18 = Column(Boolean, default=False)
    is_verified_by_mv4b = Column(Boolean, default=False)  # Meta verification
    
    # Structured Data (JSONB for complex nested data)
    biography_with_entities = Column(JSONB)  # Structured bio with hashtags/mentions
    bio_links = Column(JSONB)  # Array of clickable bio links
    pronouns = Column(JSONB)  # Array of user pronouns
    
    # Raw data backup (for any fields we missed or future additions)
    raw_data = Column(JSONB, nullable=False)
    
    # Meta information
    last_refreshed = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    data_quality_score = Column(Integer, default=100)  # Percentage of fields populated
    
    # Relationships
    posts = relationship("Post", back_populates="profile", cascade="all, delete-orphan")
    user_profile_access = relationship("UserProfileAccess", back_populates="profile", cascade="all, delete-orphan")
    audience_demographics = relationship("AudienceDemographics", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    creator_metadata = relationship("CreatorMetadata", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="profile", cascade="all, delete-orphan")
    related_profiles = relationship("RelatedProfile", back_populates="profile", cascade="all, delete-orphan")
    
    # Indexes for better performance
    __table_args__ = (
        Index('ix_profiles_username', 'username'),
        Index('ix_profiles_followers', 'followers_count'),
        Index('ix_profiles_verified', 'is_verified'),
        Index('ix_profiles_business', 'is_business_account'),
        Index('ix_profiles_last_refreshed', 'last_refreshed'),
    )


class Post(Base):
    """Stores each individual post/reel's complete data from Decodo"""
    __tablename__ = "posts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    
    # Core Post Identification
    instagram_post_id = Column(Text, nullable=False)  # Instagram's internal post ID
    shortcode = Column(Text, nullable=False, unique=True)  # URL shortcode (e.g., "CXw8yJlnQxB")
    
    # Media Information
    display_url = Column(Text)  # Main image/video URL
    is_video = Column(Boolean, default=False)
    dimensions_width = Column(Integer)  # Image/video width
    dimensions_height = Column(Integer)  # Image/video height
    
    # Video-specific fields
    video_url = Column(Text)  # Direct video URL (if is_video=True)
    video_view_count = Column(Integer, default=0)
    video_duration = Column(Integer)  # Duration in seconds
    has_audio = Column(Boolean)
    
    # Engagement Data (core metrics)
    likes_count = Column(Integer, nullable=False, default=0)
    comments_count = Column(Integer, nullable=False, default=0)
    
    # Content
    caption = Column(Text)  # Full post caption
    taken_at_timestamp = Column(Integer)  # Unix timestamp
    
    # Post Classification
    typename = Column(Text)  # "GraphImage", "GraphVideo", "GraphSidecar"
    media_type = Column(Text)  # Derived: "photo", "video", "carousel"
    
    # Carousel-specific (for multi-image posts)
    is_carousel = Column(Boolean, default=False)
    carousel_media_count = Column(Integer, default=1)
    
    # Advanced Features
    has_tagged_users = Column(Boolean, default=False)
    tagged_users = Column(JSONB)  # Array of tagged user data
    location_name = Column(Text)  # Location tag name
    location_id = Column(Text)  # Location ID
    
    # Content Analysis (extracted from caption)
    hashtags = Column(JSONB)  # Array of hashtags used
    mentions = Column(JSONB)  # Array of mentioned users
    
    # Accessibility
    accessibility_caption = Column(Text)  # Alt text for images
    
    # Performance Metrics (calculated)
    engagement_rate = Column(Integer, default=0)  # (likes + comments) / followers * 100
    performance_score = Column(Integer, default=0)  # Relative performance vs account average
    
    # Raw data backup (for any fields we missed)
    raw_data = Column(JSONB, nullable=False)
    
    # Meta information
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    profile = relationship("Profile", back_populates="posts")
    comment_sentiment = relationship("CommentSentiment", back_populates="post", cascade="all, delete-orphan")
    campaign_posts = relationship("CampaignPost", back_populates="post")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('ix_posts_profile_id', 'profile_id'),
        Index('ix_posts_shortcode', 'shortcode'),
        Index('ix_posts_timestamp', 'taken_at_timestamp'),
        Index('ix_posts_likes', 'likes_count'),
        Index('ix_posts_engagement', 'engagement_rate'),
    )


class UserProfileAccess(Base):
    """Implements the 30-day unlock window per user/profile"""
    __tablename__ = "user_profile_access"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    last_accessed = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="user_profile_access")
    profile = relationship("Profile", back_populates="user_profile_access")
    
    # Unique constraint
    __table_args__ = (Index('ix_user_profile_access_unique', 'user_id', 'profile_id', unique=True),)


# Analytics & ML Enhancement Tables

class AudienceDemographics(Base):
    """Caches DeepFace + spaCy demographics for up to 30 days"""
    __tablename__ = "audience_demographics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, unique=True)
    last_sampled = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    gender_dist = Column(JSONB, nullable=False)  # e.g. {"male":0.6,"female":0.4}
    age_dist = Column(JSONB, nullable=False)     # e.g. {"18-24":0.5,...}
    location_dist = Column(JSONB, nullable=False) # e.g. {"Dubai":0.3,...}
    
    # Relationships
    profile = relationship("Profile", back_populates="audience_demographics")


class CreatorMetadata(Base):
    """Stores inferred location & content categories via zero-shot"""
    __tablename__ = "creator_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, unique=True)
    extracted_location = Column(Text)
    categories = Column(ARRAY(Text), nullable=False, default=list)  # e.g. ["fashion","tech"]
    last_updated = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    profile = relationship("Profile", back_populates="creator_metadata")


class CommentSentiment(Base):
    """Aggregates sentiment of post comments"""
    __tablename__ = "comment_sentiment"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    sentiment = Column(JSONB, nullable=False)  # e.g. {"positive":0.6,"neutral":0.3,"negative":0.1}
    calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    post = relationship("Post", back_populates="comment_sentiment")
    
    # Index for better query performance
    __table_args__ = (Index('ix_comment_sentiment_post_id', 'post_id'),)


# Campaigns & Mentions Tables

class Mention(Base):
    """Lists external posts that mention this influencer"""
    __tablename__ = "mentions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    mention_data = Column(JSONB, nullable=False)  # raw Decodo or scraped payload
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    profile = relationship("Profile", back_populates="mentions")
    
    # Index for better query performance
    __table_args__ = (Index('ix_mentions_profile_id', 'profile_id'),)


class Campaign(Base):
    """Defines user campaigns"""
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(Text, nullable=False)
    logo_url = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="campaigns")
    campaign_posts = relationship("CampaignPost", back_populates="campaign", cascade="all, delete-orphan")


class CampaignPost(Base):
    """Joins campaigns to posts"""
    __tablename__ = "campaign_posts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    post_id = Column(UUID(as_uuid=True), ForeignKey('posts.id'), nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_posts")
    post = relationship("Post", back_populates="campaign_posts")
    
    # Unique constraint and index
    __table_args__ = (
        Index('ix_campaign_posts_unique', 'campaign_id', 'post_id', unique=True),
        Index('ix_campaign_posts_campaign_id', 'campaign_id')
    )


class RelatedProfile(Base):
    """Stores related/similar profiles suggested by Instagram"""
    __tablename__ = "related_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    
    # Related profile information
    related_username = Column(Text, nullable=False)
    related_full_name = Column(Text)
    related_is_verified = Column(Boolean, default=False)
    related_is_private = Column(Boolean, default=False)
    related_profile_pic_url = Column(Text)
    
    # Relationship metadata
    similarity_score = Column(Integer, default=0)  # 0-100 based on position in recommendations
    discovered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    profile = relationship("Profile", back_populates="related_profiles")
    
    # Indexes
    __table_args__ = (
        Index('ix_related_profiles_profile_id', 'profile_id'),
        Index('ix_related_profiles_username', 'related_username'),
    )