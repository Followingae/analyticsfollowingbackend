"""
Post Analytics Database Models - Campaign Instagram Post Analysis System
Using existing campaign_post_analytics table for individual post URL analysis
"""

import uuid as uuid_lib
from sqlalchemy import Column, String, Text, Integer, BigInteger, Float, Boolean, DateTime, DECIMAL, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.unified_models import Base

class CampaignPostAnalytics(Base):
    """
    Campaign Post Analytics - Instagram Post Analysis for Campaigns

    Using the existing campaign_post_analytics table structure
    """
    __tablename__ = "campaign_post_analytics"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)

    # Post identification
    instagram_post_url = Column(Text, nullable=False)
    instagram_shortcode = Column(String(20), nullable=False)
    post_type = Column(String(20), nullable=False, default='post')  # 'post', 'reel', 'carousel'

    # Apify raw data (complete response)
    apify_raw_data = Column(JSONB, nullable=False, default={})

    # Key metrics (extracted for easy querying)
    likes_count = Column(BigInteger, default=0)
    comments_count = Column(BigInteger, default=0)
    views_count = Column(BigInteger, default=0)  # for videos/reels

    # Post content
    caption = Column(Text, nullable=True)
    hashtags = Column(ARRAY(String), default=[])  # extracted hashtags
    mentions = Column(ARRAY(String), default=[])  # extracted mentions

    # Media information
    media_urls = Column(ARRAY(String), default=[])  # images/videos URLs
    media_count = Column(Integer, default=1)

    # User/creator info
    creator_username = Column(String(100), nullable=True)
    creator_full_name = Column(Text, nullable=True)
    creator_followers_count = Column(BigInteger, default=0)

    # Engagement metrics
    engagement_rate = Column(DECIMAL(8,4), default=0)  # calculated from likes+comments/followers

    # Post metadata
    posted_at = Column(DateTime(timezone=True), nullable=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    # Analysis metadata
    added_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_analysis_complete = Column(Boolean, default=False)
    analysis_error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)  # User notes for this post in campaign

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    # campaign = relationship("Campaign", back_populates="post_analytics")
    # added_by_user = relationship("User", back_populates="campaign_posts")

