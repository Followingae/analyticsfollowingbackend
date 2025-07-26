from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class InstagramProfile(BaseModel):
    username: str = Field(..., description="Instagram username")
    full_name: Optional[str] = Field(None, description="Full display name")
    biography: Optional[str] = Field(None, description="Profile biography")
    followers: int = Field(0, description="Number of followers")
    following: int = Field(0, description="Number of following")
    posts_count: int = Field(0, description="Number of posts")
    is_verified: bool = Field(False, description="Verification status")
    is_private: bool = Field(False, description="Privacy status")
    profile_pic_url: Optional[str] = Field(None, description="Profile picture URL")
    external_url: Optional[str] = Field(None, description="External website URL")
    
    # Analytics fields
    engagement_rate: float = Field(0.0, description="Engagement rate percentage")
    avg_likes: float = Field(0.0, description="Average likes per post")
    avg_comments: float = Field(0.0, description="Average comments per post")
    avg_engagement: float = Field(0.0, description="Average engagement per post")
    
    # Derived metrics
    follower_growth_rate: Optional[float] = Field(None, description="Monthly follower growth rate")
    content_quality_score: Optional[float] = Field(None, description="Content quality score (1-10)")
    influence_score: Optional[float] = Field(None, description="Overall influence score (1-10)")


class InstagramPost(BaseModel):
    post_id: str = Field(..., description="Unique post identifier")
    shortcode: str = Field(..., description="Instagram shortcode")
    caption: Optional[str] = Field(None, description="Post caption")
    likes: int = Field(0, description="Number of likes")
    comments: int = Field(0, description="Number of comments")
    timestamp: datetime = Field(..., description="Post creation timestamp")
    media_type: str = Field("photo", description="Type of media (photo, video, carousel)")
    media_urls: List[str] = Field(default_factory=list, description="Media URLs")
    hashtags: List[str] = Field(default_factory=list, description="Hashtags used")
    mentions: List[str] = Field(default_factory=list, description="User mentions")
    location: Optional[str] = Field(None, description="Location tag")
    
    # Analytics
    engagement_rate: float = Field(0.0, description="Post engagement rate")
    performance_score: Optional[float] = Field(None, description="Post performance score")


class HashtagAnalytics(BaseModel):
    name: str = Field(..., description="Hashtag name (without #)")
    post_count: int = Field(0, description="Total posts using this hashtag")
    avg_likes: float = Field(0.0, description="Average likes for posts with this hashtag")
    avg_comments: float = Field(0.0, description="Average comments for posts with this hashtag")
    difficulty_score: float = Field(0.0, description="Hashtag difficulty score (1-10)")
    trending_score: float = Field(0.0, description="Trending score (1-10)")
    related_hashtags: List[str] = Field(default_factory=list, description="Related hashtags")


class ProfileAnalysisResponse(BaseModel):
    profile: InstagramProfile = Field(..., description="Profile information")
    recent_posts: List[InstagramPost] = Field(default_factory=list, description="Recent posts analysis")
    hashtag_analysis: List[HashtagAnalytics] = Field(default_factory=list, description="Hashtag performance")
    
    # Comprehensive analysis
    content_strategy: Dict[str, Any] = Field(default_factory=dict, description="Content strategy insights")
    best_posting_times: List[str] = Field(default_factory=list, description="Optimal posting times")
    audience_insights: Dict[str, Any] = Field(default_factory=dict, description="Audience demographics")
    growth_recommendations: List[str] = Field(default_factory=list, description="Growth recommendations")
    
    # Meta information
    analysis_timestamp: datetime = Field(default_factory=datetime.now, description="When analysis was performed")
    data_quality_score: float = Field(1.0, description="Quality of scraped data (0-1)")


class SmartProxyRequest(BaseModel):
    url: str = Field(..., description="Instagram URL to scrape")
    target: str = Field("instagram", description="Target platform")
    parse: bool = Field(True, description="Parse the response")
    headless: Optional[str] = Field("html", description="Headless mode")
    
    
class SmartProxyResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Scraping results")
    status: str = Field("success", description="Request status")
    message: Optional[str] = Field(None, description="Response message")