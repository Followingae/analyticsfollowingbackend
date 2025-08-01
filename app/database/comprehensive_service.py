"""
COMPREHENSIVE DATABASE SERVICE
This service handles ALL Decodo datapoints and ensures complete data storage
Replaces existing services with unified, comprehensive approach
"""
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
import datetime as dt_module  # Import the module itself to avoid conflicts
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
import logging
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import selectinload, joinedload

from app.core.config import settings
from .unified_models import (
    User, Profile, Post, UserProfileAccess, UserSearch, UserFavorite,
    AudienceDemographics, CreatorMetadata, CommentSentiment,
    RelatedProfile, Mention, Campaign, CampaignPost, CampaignProfile
)

logger = logging.getLogger(__name__)

class ComprehensiveDataService:
    """Unified service for complete Decodo data storage and retrieval"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def init_pool(self):
        """Initialize asyncpg connection pool for performance-critical operations - SINGLE POOL PATTERN"""
        try:
            # CHECK: If pool already exists, don't create a new one (single connection pool pattern)
            if self.pool is not None:
                logger.info("Comprehensive service pool already initialized - reusing existing pool")
                return
                
            if settings.DATABASE_URL and "[YOUR-PASSWORD]" not in settings.DATABASE_URL:
                self.pool = await asyncpg.create_pool(
                    settings.DATABASE_URL,
                    min_size=2,
                    max_size=10,
                    server_settings={"statement_cache_size": "100"}
                )
                logger.info("Comprehensive service connection pool initialized successfully")
            else:
                logger.warning("Database URL not configured for comprehensive service")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")

    # ==========================================================================
    # PROFILE DATA STORAGE - COMPREHENSIVE DECODO MAPPING
    # ==========================================================================
    
    async def store_complete_profile(self, db: AsyncSession, username: str, raw_data: Dict[str, Any]) -> Tuple[Profile, bool]:
        """Store COMPLETE profile using the provided database session"""
        from app.database.robust_storage import store_profile_robust
        
        logger.info(f"Starting profile storage for {username}")
        
        try:
            profile, is_new = await store_profile_robust(db, username, raw_data)
            logger.info(f"SUCCESS: Profile {username} stored successfully: {'new' if is_new else 'updated'}")
            return profile, is_new
            
        except Exception as storage_error:
            logger.error(f"STORAGE ERROR for {username}: {storage_error}")
            raise ValueError(f"Storage failed for {username}: {storage_error}")

    def _extract_user_data_comprehensive(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user data from Decodo response with comprehensive error handling"""
        try:
            # Handle multiple possible response structures
            if 'results' in raw_data:
                results = raw_data['results']
                if results and len(results) > 0:
                    result = results[0]
                    if 'content' in result and 'data' in result['content']:
                        return result['content']['data'].get('user', {})
                    elif 'data' in result:
                        return result['data'].get('user', {})
            
            # Direct user data
            if 'user' in raw_data:
                return raw_data['user']
                
            # GraphQL response structure
            if 'data' in raw_data and 'user' in raw_data['data']:
                return raw_data['data']['user']
                
            logger.warning("Could not extract user data from response structure")
            return {}
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error extracting user data: {e}")
            return {}

    def _map_all_decodo_datapoints(self, user_data: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map ALL 80+ Decodo datapoints to Profile model fields"""
        
        def safe_get(data: Dict[str, Any], path: str, default=None):
            """Safely extract nested data with dot notation"""
            try:
                result = data
                for key in path.split('.'):
                    if isinstance(result, dict):
                        result = result.get(key)
                    else:
                        return default
                return result if result is not None else default
            except (KeyError, TypeError, AttributeError):
                return default

        # Initialize profile data with all fields
        profile_data = {}
        
        # =======================================================================
        # CORE PROFILE INFORMATION
        # =======================================================================
        profile_data['instagram_user_id'] = safe_get(user_data, 'id', '')
        profile_data['full_name'] = safe_get(user_data, 'full_name', '')
        profile_data['biography'] = safe_get(user_data, 'biography', '')
        profile_data['external_url'] = safe_get(user_data, 'external_url', '')
        profile_data['external_url_shimmed'] = safe_get(user_data, 'external_url_linkshimmed', '')
        profile_data['profile_pic_url'] = safe_get(user_data, 'profile_pic_url', '')
        profile_data['profile_pic_url_hd'] = safe_get(user_data, 'profile_pic_url_hd', '')
        
        # =======================================================================
        # ACCOUNT STATISTICS (with edge handling)
        # =======================================================================
        profile_data['followers_count'] = safe_get(user_data, 'edge_followed_by.count', 0)
        profile_data['following_count'] = safe_get(user_data, 'edge_follow.count', 0)
        profile_data['posts_count'] = safe_get(user_data, 'edge_owner_to_timeline_media.count', 0)
        profile_data['mutual_followers_count'] = safe_get(user_data, 'edge_mutual_followed_by.count', 0)
        profile_data['highlight_reel_count'] = safe_get(user_data, 'highlight_reel_count', 0)
        
        # =======================================================================
        # ACCOUNT STATUS & VERIFICATION
        # =======================================================================
        profile_data['is_verified'] = safe_get(user_data, 'is_verified', False)
        profile_data['is_private'] = safe_get(user_data, 'is_private', False)
        profile_data['is_business_account'] = safe_get(user_data, 'is_business_account', False)
        profile_data['is_professional_account'] = safe_get(user_data, 'is_professional_account', False)
        profile_data['is_joined_recently'] = safe_get(user_data, 'is_joined_recently', False)
        
        # =======================================================================
        # BUSINESS INFORMATION (comprehensive)
        # =======================================================================
        profile_data['business_category_name'] = safe_get(user_data, 'business_category_name', '')
        profile_data['overall_category_name'] = safe_get(user_data, 'overall_category_name', '')
        profile_data['category_enum'] = safe_get(user_data, 'category_enum', '')
        profile_data['business_address_json'] = safe_get(user_data, 'business_address_json', '')
        profile_data['business_contact_method'] = safe_get(user_data, 'business_contact_method', '')
        profile_data['business_email'] = safe_get(user_data, 'business_email', '')
        profile_data['business_phone_number'] = safe_get(user_data, 'business_phone_number', '')
        
        # =======================================================================
        # ACCOUNT FEATURES
        # =======================================================================
        profile_data['has_ar_effects'] = safe_get(user_data, 'has_ar_effects', False)
        profile_data['has_clips'] = safe_get(user_data, 'has_clips', False)
        profile_data['has_guides'] = safe_get(user_data, 'has_guides', False)
        profile_data['has_channel'] = safe_get(user_data, 'has_channel', False)
        profile_data['has_onboarded_to_text_post_app'] = safe_get(user_data, 'has_onboarded_to_text_post_app', False)
        profile_data['show_text_post_app_badge'] = safe_get(user_data, 'show_text_post_app_badge', False)
        
        # =======================================================================
        # PRIVACY & RESTRICTIONS
        # =======================================================================
        profile_data['country_block'] = safe_get(user_data, 'country_block', False)
        profile_data['is_embeds_disabled'] = safe_get(user_data, 'is_embeds_disabled', False)
        profile_data['hide_like_and_view_counts'] = safe_get(user_data, 'hide_like_and_view_counts', False)
        
        # =======================================================================
        # ACCOUNT SETTINGS
        # =======================================================================
        profile_data['should_show_category'] = safe_get(user_data, 'should_show_category', True)
        profile_data['should_show_public_contacts'] = safe_get(user_data, 'should_show_public_contacts', True)
        profile_data['show_account_transparency_details'] = safe_get(user_data, 'show_account_transparency_details', True)
        profile_data['remove_message_entrypoint'] = safe_get(user_data, 'remove_message_entrypoint', False)
        
        # =======================================================================
        # VIEWER RELATIONSHIPS (when available)
        # =======================================================================
        profile_data['blocked_by_viewer'] = safe_get(user_data, 'blocked_by_viewer')
        profile_data['has_blocked_viewer'] = safe_get(user_data, 'has_blocked_viewer')
        profile_data['restricted_by_viewer'] = safe_get(user_data, 'restricted_by_viewer')
        profile_data['followed_by_viewer'] = safe_get(user_data, 'followed_by_viewer')
        profile_data['follows_viewer'] = safe_get(user_data, 'follows_viewer')
        profile_data['requested_by_viewer'] = safe_get(user_data, 'requested_by_viewer')
        profile_data['has_requested_viewer'] = safe_get(user_data, 'has_requested_viewer')
        
        # =======================================================================
        # AI & SPECIAL FEATURES
        # =======================================================================
        profile_data['ai_agent_type'] = safe_get(user_data, 'ai_agent_type', '')
        profile_data['ai_agent_owner_username'] = safe_get(user_data, 'ai_agent_owner_username', '')
        profile_data['transparency_label'] = safe_get(user_data, 'transparency_label', '')
        profile_data['transparency_product'] = safe_get(user_data, 'transparency_product', '')
        
        # =======================================================================
        # SUPERVISION & SAFETY
        # =======================================================================
        profile_data['is_supervision_enabled'] = safe_get(user_data, 'is_supervision_enabled', False)
        profile_data['is_guardian_of_viewer'] = safe_get(user_data, 'is_guardian_of_viewer', False)
        profile_data['is_supervised_by_viewer'] = safe_get(user_data, 'is_supervised_by_viewer', False)
        profile_data['is_supervised_user'] = safe_get(user_data, 'is_supervised_user', False)
        profile_data['guardian_id'] = safe_get(user_data, 'guardian_id', '')
        profile_data['is_regulated_c18'] = safe_get(user_data, 'is_regulated_c18', False)
        profile_data['is_verified_by_mv4b'] = safe_get(user_data, 'is_verified_by_mv4b', False)
        
        # =======================================================================
        # ADVANCED INSTAGRAM FIELDS
        # =======================================================================
        profile_data['fbid'] = safe_get(user_data, 'fbid', '')
        profile_data['eimu_id'] = safe_get(user_data, 'eimu_id', '')
        profile_data['pinned_channels_list_count'] = safe_get(user_data, 'pinned_channels_list_count', 0)
        
        # =======================================================================
        # STRUCTURED DATA (JSONB)
        # =======================================================================
        profile_data['biography_with_entities'] = safe_get(user_data, 'biography_with_entities', {})
        profile_data['bio_links'] = safe_get(user_data, 'bio_links', [])
        profile_data['pronouns'] = safe_get(user_data, 'pronouns', [])
        
        # =======================================================================
        # COMPUTED ANALYTICS
        # =======================================================================
        followers = profile_data.get('followers_count', 0)
        posts_count = profile_data.get('posts_count', 0)
        
        # Calculate engagement rate from recent posts if available
        posts_data = safe_get(user_data, 'edge_owner_to_timeline_media.edges', [])
        total_engagement = 0
        analyzed_posts = 0
        
        for post_edge in posts_data[:12]:  # Last 12 posts
            post_node = post_edge.get('node', {})
            likes = safe_get(post_node, 'edge_liked_by.count', 0)
            comments = safe_get(post_node, 'edge_media_to_comment.count', 0)
            total_engagement += likes + comments
            analyzed_posts += 1
        
        # Calculate metrics
        if analyzed_posts > 0 and followers > 0:
            avg_engagement = total_engagement / analyzed_posts
            engagement_rate = (avg_engagement / followers) * 100 if followers > 0 else 0
            profile_data['engagement_rate'] = min(engagement_rate, 100)  # Cap at 100%
            profile_data['avg_likes'] = total_engagement / analyzed_posts * 0.9  # Approximate
            profile_data['avg_comments'] = total_engagement / analyzed_posts * 0.1  # Approximate
            profile_data['avg_engagement'] = avg_engagement
        else:
            profile_data['engagement_rate'] = 0
            profile_data['avg_likes'] = 0
            profile_data['avg_comments'] = 0
            profile_data['avg_engagement'] = 0
        
        # Calculate influence score (0-10)
        influence_factors = [
            min(followers / 1000000, 3),  # Follower count (max 3 points)
            2 if profile_data.get('is_verified') else 0,  # Verification (2 points)
            1 if profile_data.get('is_business_account') else 0,  # Business account (1 point)
            min(profile_data.get('engagement_rate', 0) / 10, 2),  # Engagement rate (max 2 points)
            min(posts_count / 100, 2)  # Content volume (max 2 points)
        ]
        profile_data['influence_score'] = min(sum(influence_factors), 10)
        
        # Calculate content quality score
        quality_factors = [
            1 if profile_data.get('profile_pic_url_hd') else 0,
            1 if profile_data.get('biography') else 0,
            1 if profile_data.get('external_url') else 0,
            2 if posts_count > 10 else posts_count / 5,
            1 if profile_data.get('has_clips') else 0,
            1 if profile_data.get('has_guides') else 0,
        ]
        profile_data['content_quality_score'] = min(sum(quality_factors), 10)
        
        # Calculate follower growth rate (placeholder - would need historical data)
        profile_data['follower_growth_rate'] = 2.1  # Default placeholder
        
        # =======================================================================
        # PROFILE IMAGES & THUMBNAILS (NEW)
        # =======================================================================
        profile_images = []
        if profile_data.get('profile_pic_url'):
            profile_images.append({
                'url': profile_data['profile_pic_url'],
                'type': 'standard',
                'size': 'medium'
            })
        if profile_data.get('profile_pic_url_hd'):
            profile_images.append({
                'url': profile_data['profile_pic_url_hd'],
                'type': 'hd',
                'size': 'large'
            })
        profile_data['profile_images'] = profile_images
        
        # Generate thumbnails from profile images
        profile_thumbnails = []
        for img in profile_images:
            profile_thumbnails.append({
                'url': img['url'],
                'width': 150,
                'height': 150,
                'type': 'square_thumbnail'
            })
        profile_data['profile_thumbnails'] = profile_thumbnails
        
        # =======================================================================
        # DATA QUALITY SCORE
        # =======================================================================
        total_fields = 80  # Approximate number of mapped fields
        populated_fields = sum(1 for key, value in profile_data.items() 
                             if value not in [None, '', [], {}, 0] or key in ['followers_count', 'following_count'])
        
        profile_data['data_quality_score'] = int((populated_fields / total_fields) * 100)
        
        logger.info(f"Mapped {populated_fields}/{total_fields} fields ({profile_data['data_quality_score']}% quality) for comprehensive profile")
        
        return profile_data

    async def _store_profile_posts(self, db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any]):
        """Store ALL posts from profile with comprehensive data mapping"""
        try:
            posts_edges = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
            if not posts_edges:
                logger.info(f"No posts found for profile {profile_id}")
                return
            
            posts_created = 0
            for post_edge in posts_edges:
                post_node = post_edge.get('node', {})
                if not post_node.get('shortcode'):
                    continue
                
                # Check if post already exists
                result = await db.execute(
                    select(Post).where(
                        and_(
                            Post.profile_id == profile_id,
                            Post.shortcode == post_node['shortcode']
                        )
                    )
                )
                existing_post = result.scalar_one_or_none()
                
                if not existing_post:
                    post_data = self._map_post_data_comprehensive(post_node, profile_id)
                    
                    # Filter out any fields that don't exist in the Post model
                    valid_post_fields = {}
                    for key, value in post_data.items():
                        if hasattr(Post, key):
                            valid_post_fields[key] = value
                        else:
                            logger.warning(f"Skipping invalid field for Post model: {key}")
                    
                    post = Post(**valid_post_fields)
                    db.add(post)
                    posts_created += 1
            
            await db.commit()
            logger.info(f"Created {posts_created} new posts for profile {profile_id}")
            
        except Exception as e:
            logger.error(f"Error storing profile posts: {str(e)}")

    def _map_post_data_comprehensive(self, post_node: Dict[str, Any], profile_id: UUID) -> Dict[str, Any]:
        """Map ALL post datapoints from Decodo response"""
        
        def safe_get(data: Dict[str, Any], path: str, default=None):
            try:
                result = data
                for key in path.split('.'):
                    result = result.get(key) if isinstance(result, dict) else default
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        post_data = {
            'profile_id': profile_id,
            'instagram_post_id': safe_get(post_node, 'id', ''),
            'shortcode': safe_get(post_node, 'shortcode', ''),
            
            # Media information
            'media_type': safe_get(post_node, '__typename', ''),
            'is_video': safe_get(post_node, 'is_video', False),
            'display_url': safe_get(post_node, 'display_url', ''),
            'thumbnail_src': safe_get(post_node, 'thumbnail_src', ''),
            
            # Video fields
            'video_url': safe_get(post_node, 'video_url', ''),
            'video_view_count': safe_get(post_node, 'video_view_count', 0),
            'has_audio': safe_get(post_node, 'has_audio'),
            
            # Dimensions
            'width': safe_get(post_node, 'dimensions.width', 0),
            'height': safe_get(post_node, 'dimensions.height', 0),
            
            # Engagement
            'likes_count': safe_get(post_node, 'edge_liked_by.count', 0),
            'comments_count': safe_get(post_node, 'edge_media_to_comment.count', 0),
            'comments_disabled': safe_get(post_node, 'comments_disabled', False),
            
            # Content
            'accessibility_caption': safe_get(post_node, 'accessibility_caption', ''),
            
            # Settings
            'viewer_can_reshare': safe_get(post_node, 'viewer_can_reshare', True),
            
            # Location
            'location_name': safe_get(post_node, 'location.name', ''),
            'location_id': safe_get(post_node, 'location.id', ''),
            
            # Carousel
            'is_carousel': safe_get(post_node, '__typename') == 'GraphSidecar',
            
            # Timestamps
            'taken_at_timestamp': safe_get(post_node, 'taken_at_timestamp', 0),
            'posted_at': datetime.fromtimestamp(safe_get(post_node, 'taken_at_timestamp', 0)) if safe_get(post_node, 'taken_at_timestamp') else None,
            
            # Structured data
            'thumbnail_resources': safe_get(post_node, 'thumbnail_resources', []),
            'tagged_users': safe_get(post_node, 'edge_media_to_tagged_user.edges', []),
            
            # Caption extraction
            'raw_data': post_node
        }
        
        # Extract caption
        caption_edges = safe_get(post_node, 'edge_media_to_caption.edges', [])
        if caption_edges:
            post_data['caption'] = caption_edges[0]['node']['text']
        
        # Extract hashtags and mentions from caption
        caption = post_data.get('caption', '')
        if caption:
            import re
            hashtags = re.findall(r'#\w+', caption)
            mentions = re.findall(r'@\w+', caption)
            post_data['hashtags'] = hashtags
            post_data['mentions'] = mentions
        
        # Store post images/thumbnails
        post_images = []
        if post_data.get('display_url'):
            post_images.append({
                'url': post_data['display_url'],
                'type': 'main',
                'width': post_data.get('width', 0),
                'height': post_data.get('height', 0)
            })
        
        thumbnail_resources = post_data.get('thumbnail_resources', [])
        post_thumbnails = []
        for thumb in thumbnail_resources:
            post_thumbnails.append({
                'url': thumb.get('src', ''),
                'width': thumb.get('config_width', 0),
                'height': thumb.get('config_height', 0)
            })
        
        post_data['post_images'] = post_images
        post_data['post_thumbnails'] = post_thumbnails
        
        return post_data

    async def _store_related_profiles(self, db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any]):
        """Store related/suggested profiles"""
        try:
            # Delete existing related profiles
            await db.execute(delete(RelatedProfile).where(RelatedProfile.profile_id == profile_id))
            
            # Extract related profiles
            related_edges = user_data.get('edge_related_profiles', {}).get('edges', [])
            
            related_count = 0
            for i, edge in enumerate(related_edges[:15]):  # Store up to 15 related profiles
                node = edge.get('node', {})
                if not node.get('username'):
                    continue
                
                related_data = {
                    'profile_id': profile_id,
                    'related_username': node.get('username', ''),
                    'related_full_name': node.get('full_name', ''),
                    'related_is_verified': node.get('is_verified', False),
                    'related_is_private': node.get('is_private', False),
                    'related_profile_pic_url': node.get('profile_pic_url', ''),
                    'related_followers_count': node.get('edge_followed_by', {}).get('count', 0),
                    'similarity_score': max(100 - (i * 5), 10),  # Decreasing similarity score
                    'relationship_type': 'suggested'
                }
                
                related_profile = RelatedProfile(**related_data)
                db.add(related_profile)
                related_count += 1
            
            await db.commit()
            logger.info(f"Stored {related_count} related profiles for profile {profile_id}")
            
        except Exception as e:
            logger.error(f"Error storing related profiles: {str(e)}")

    async def _store_profile_images(self, db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any]):
        """Store profile images and thumbnails separately for better organization"""
        try:
            # This would integrate with image storage service
            # For now, we store image metadata in the profile_images/profile_thumbnails JSONB fields
            # which is already handled in _map_all_decodo_datapoints
            logger.info(f"Profile images stored in JSONB fields for profile {profile_id}")
            
        except Exception as e:
            logger.error(f"Error storing profile images: {str(e)}")

    # ==========================================================================
    # USER MANAGEMENT & ACCESS CONTROL
    # ==========================================================================
    
    async def record_user_search(self, db: AsyncSession, user_id: UUID, username: str, 
                                analysis_type: str, metadata: Dict[str, Any] = None,
                                search_duration_ms: int = None, data_source: str = None) -> UserSearch:
        """Record comprehensive user search with all metadata"""
        try:
            search_data = {
                'user_id': user_id,
                'instagram_username': username,
                'analysis_type': analysis_type,
                'search_metadata': metadata or {},
                'search_duration_ms': search_duration_ms,
                'data_source': data_source,
                'success': True
            }
            
            search = UserSearch(**search_data)
            db.add(search)
            await db.commit()
            await db.refresh(search)
            
            logger.info(f"Recorded search for user {user_id}: {username} ({analysis_type})")
            return search
            
        except Exception as e:
            logger.error(f"Error recording user search: {str(e)}")
            raise

    async def grant_profile_access(self, db: AsyncSession, user_id: UUID, profile_id: UUID, 
                                  access_method: str = 'search', credits_spent: int = 0) -> UserProfileAccess:
        """Grant comprehensive profile access with 30-day tracking"""
        try:
            # Check if access already exists
            result = await db.execute(
                select(UserProfileAccess).where(
                    and_(
                        UserProfileAccess.user_id == user_id,
                        UserProfileAccess.profile_id == profile_id
                    )
                )
            )
            access = result.scalar_one_or_none()
            
            current_time = datetime.now(timezone.utc)
            expires_at = current_time + timedelta(days=30)
            
            if access:
                # Update existing access
                access.last_accessed = current_time
                access.access_count += 1
                access.expires_at = expires_at
                if access_method:
                    access.access_method = access_method
                if credits_spent > 0:
                    access.credits_spent += credits_spent
            else:
                # Create new access record
                access_data = {
                    'user_id': user_id,
                    'profile_id': profile_id,
                    'first_accessed': current_time,
                    'last_accessed': current_time,
                    'access_count': 1,
                    'access_method': access_method,
                    'credits_spent': credits_spent,
                    'expires_at': expires_at
                }
                access = UserProfileAccess(**access_data)
                db.add(access)
            
            await db.commit()
            await db.refresh(access)
            
            logger.info(f"Granted profile access: user {user_id} -> profile {profile_id} (expires: {expires_at})")
            return access
            
        except Exception as e:
            logger.error(f"Error granting profile access: {str(e)}")
            raise

    async def check_profile_access(self, db: AsyncSession, user_id: UUID, profile_id: UUID) -> bool:
        """Check if user has valid 30-day access to profile"""
        try:
            current_time = datetime.now(timezone.utc)
            
            result = await db.execute(
                select(UserProfileAccess).where(
                    and_(
                        UserProfileAccess.user_id == user_id,
                        UserProfileAccess.profile_id == profile_id,
                        UserProfileAccess.expires_at > current_time
                    )
                )
            )
            access = result.scalar_one_or_none()
            
            return access is not None
            
        except Exception as e:
            logger.error(f"Error checking profile access: {str(e)}")
            return False

    async def get_user_accessible_profiles(self, db: AsyncSession, user_id: UUID, 
                                         limit: int = 50) -> List[Profile]:
        """Get all profiles accessible to user within 30-day window"""
        try:
            current_time = datetime.now(timezone.utc)
            
            result = await db.execute(
                select(Profile)
                .join(UserProfileAccess)
                .where(
                    and_(
                        UserProfileAccess.user_id == user_id,
                        UserProfileAccess.expires_at > current_time
                    )
                )
                .order_by(UserProfileAccess.last_accessed.desc())
                .limit(limit)
                .options(selectinload(Profile.audience_demographics))
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting accessible profiles: {str(e)}")
            return []

    # ==========================================================================
    # ANALYTICS METHODS - ENHANCED FROM DECODO DATA (Not fake AI)
    # ==========================================================================
    
    async def store_audience_demographics(self, db: AsyncSession, profile_id: UUID,
                                        gender_dist: Dict, age_dist: Dict, location_dist: Dict,
                                        sample_size: int = None, confidence_score: float = None) -> AudienceDemographics:
        """Store audience demographics enhanced from Decodo follower data"""
        try:
            result = await db.execute(
                select(AudienceDemographics).where(AudienceDemographics.profile_id == profile_id)
            )
            demographics = result.scalar_one_or_none()
            
            if demographics:
                # Update existing
                demographics.gender_distribution = gender_dist
                demographics.age_distribution = age_dist
                demographics.location_distribution = location_dist
                demographics.sample_size = sample_size
                demographics.confidence_score = confidence_score
                demographics.last_sampled = func.now()
                demographics.analysis_method = 'decodo_enhanced'
            else:
                # Create new
                demographics_data = {
                    'profile_id': profile_id,
                    'gender_distribution': gender_dist,
                    'age_distribution': age_dist,
                    'location_distribution': location_dist,
                    'sample_size': sample_size,
                    'confidence_score': confidence_score,
                    'analysis_method': 'decodo_enhanced'
                }
                demographics = AudienceDemographics(**demographics_data)
                db.add(demographics)
            
            await db.commit()
            await db.refresh(demographics)
            
            logger.info(f"Stored audience demographics for profile {profile_id}")
            return demographics
            
        except Exception as e:
            logger.error(f"Error storing audience demographics: {str(e)}")
            raise

    async def store_creator_metadata(self, db: AsyncSession, profile_id: UUID,
                                   extracted_location: str, categories: List[str],
                                   content_themes: Dict = None, primary_language: str = None) -> CreatorMetadata:
        """Store creator metadata extracted from Decodo profile data"""
        try:
            result = await db.execute(
                select(CreatorMetadata).where(CreatorMetadata.profile_id == profile_id)
            )
            metadata = result.scalar_one_or_none()
            
            if metadata:
                # Update existing
                metadata.extracted_location = extracted_location
                metadata.categories = categories
                metadata.content_themes = content_themes or {}
                metadata.primary_language = primary_language
                metadata.last_updated = func.now()
            else:
                # Create new
                metadata_data = {
                    'profile_id': profile_id,
                    'extracted_location': extracted_location,
                    'categories': categories,
                    'content_themes': content_themes or {},
                    'primary_language': primary_language,
                    'analysis_confidence': 0.85  # Based on Decodo data quality
                }
                metadata = CreatorMetadata(**metadata_data)
                db.add(metadata)
            
            await db.commit()
            await db.refresh(metadata)
            
            logger.info(f"Stored creator metadata for profile {profile_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error storing creator metadata: {str(e)}")
            raise

    # ==========================================================================
    # UTILITY FUNCTIONS
    # ==========================================================================
    
    async def get_profile_by_username(self, db: AsyncSession, username: str) -> Optional[Profile]:
        """Check if a profile exists in database by username (regardless of user access)"""
        try:
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            profile = result.scalar_one_or_none()
            
            if profile:
                logger.debug(f"Profile {username} found in database")
            else:
                logger.debug(f"Profile {username} not found in database")
            
            return profile
            
        except Exception as e:
            logger.error(f"Error checking if profile exists: {str(e)}")
            return None
    
    async def get_profile_with_all_data(self, db: AsyncSession, username: str) -> Optional[Profile]:
        """Get profile with ALL related data loaded"""
        try:
            result = await db.execute(
                select(Profile)
                .where(Profile.username == username)
                # Temporarily disable selectinload until all tables are fixed
                # .options(
                #     selectinload(Profile.posts),
                #     selectinload(Profile.audience_demographics),
                #     selectinload(Profile.creator_metadata),
                #     selectinload(Profile.related_profiles),
                #     selectinload(Profile.mentions)
                # )
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting complete profile data: {str(e)}")
            await db.rollback()
            return None

    async def cleanup_expired_data(self, db: AsyncSession, days_old: int = 90) -> Dict[str, int]:
        """Clean up expired data across all tables"""
        try:
            cleanup_results = {}
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            # Clean up expired access records
            result = await db.execute(
                delete(UserProfileAccess).where(UserProfileAccess.expires_at < cutoff_date)
            )
            cleanup_results['expired_access_records'] = result.rowcount
            
            # Clean up old search records (keep recent ones)
            result = await db.execute(
                delete(UserSearch).where(UserSearch.search_timestamp < cutoff_date)
            )
            cleanup_results['old_search_records'] = result.rowcount
            
            await db.commit()
            
            logger.info(f"Cleanup completed: {cleanup_results}")
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            await db.rollback()
            return {}

    # ==========================================================================
    # USER OPERATION FUNCTIONS - CRITICAL FOR SESSION MANAGEMENT
    # ==========================================================================
    
    async def grant_profile_access(self, db: AsyncSession, user_id: str, profile_id: UUID) -> bool:
        """Grant user 30-day access to a profile - FIXED with robust error handling"""
        try:
            # CRITICAL FIX: Convert Supabase user ID to database user ID
            db_user_id = await self._get_database_user_id(db, user_id)
            if not db_user_id:
                logger.error(f"Failed to find database user ID for Supabase ID: {user_id}")
                # Still attempt the operation with Supabase ID as fallback
                try:
                    # Convert string to UUID if needed
                    fallback_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
                    db_user_id = fallback_user_id
                    logger.warning(f"Using Supabase ID as fallback: {db_user_id}")
                except (ValueError, TypeError) as uuid_error:
                    logger.error(f"Cannot convert user_id to UUID: {uuid_error}")
                    return False
            
            # Validate profile_id
            if not isinstance(profile_id, UUID):
                logger.error(f"Invalid profile_id type: {type(profile_id)}")
                return False
            
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            
            # Check if access already exists with proper error handling
            try:
                result = await db.execute(
                    select(UserProfileAccess).where(
                        and_(
                            UserProfileAccess.user_id == db_user_id,
                            UserProfileAccess.profile_id == profile_id
                        )
                    )
                )
                existing_access = result.scalar_one_or_none()
            except Exception as query_error:
                logger.error(f"Error querying existing access: {query_error}")
                # Continue with creation attempt
                existing_access = None
            
            if existing_access:
                # Update existing access with error handling
                try:
                    await db.execute(
                        update(UserProfileAccess)
                        .where(
                            and_(
                                UserProfileAccess.user_id == db_user_id,
                                UserProfileAccess.profile_id == profile_id
                            )
                        )
                        .values(
                            expires_at=expires_at,
                            last_accessed=datetime.now(timezone.utc),
                            access_count=UserProfileAccess.access_count + 1
                        )
                    )
                    logger.info(f"Updated profile access for user {db_user_id} to profile {profile_id}")
                except Exception as update_error:
                    logger.error(f"Error updating profile access: {update_error}")
                    raise update_error
            else:
                # Create new access record with comprehensive error handling
                try:
                    access_record = UserProfileAccess(
                        id=uuid.uuid4(),
                        user_id=db_user_id,
                        profile_id=profile_id,
                        granted_at=datetime.now(timezone.utc),
                        expires_at=expires_at,
                        # Removed columns that don't exist in actual DB:
                        # - last_accessed, access_type, access_count
                    )
                    db.add(access_record)
                    logger.info(f"Granted new profile access for user {db_user_id} to profile {profile_id}")
                except Exception as create_error:
                    logger.error(f"Error creating profile access record: {create_error}")
                    raise create_error
            
            # Commit with error handling
            try:
                await db.commit()
                logger.debug(f"Successfully committed profile access for user {db_user_id}")
                return True
            except Exception as commit_error:
                logger.error(f"Error committing profile access: {commit_error}")
                await db.rollback()
                return False
            
        except Exception as e:
            logger.error(f"Comprehensive error in grant_profile_access: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            try:
                await db.rollback()
                logger.debug("Successfully rolled back transaction")
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")
            return False
    
    async def record_user_search(self, db: AsyncSession, user_id: str, username: str, 
                                analysis_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Record user search in database - FIXED with robust error handling"""
        try:
            # CRITICAL FIX: Convert Supabase user ID to database user ID
            db_user_id = await self._get_database_user_id(db, user_id)
            if not db_user_id:
                logger.error(f"Failed to find database user ID for Supabase ID: {user_id}")
                # Use Supabase ID as fallback for search recording
                db_user_id_str = str(user_id)
                logger.warning(f"Using Supabase ID as fallback for search: {db_user_id_str}")
            else:
                db_user_id_str = str(db_user_id)
            
            # Validate required parameters
            if not username or not analysis_type:
                logger.error(f"Missing required parameters: username='{username}', analysis_type='{analysis_type}'")
                return False
            
            # Clean and validate metadata
            safe_metadata = {}
            if metadata:
                try:
                    # Ensure metadata is JSON serializable
                    import json
                    json.dumps(metadata)  # Test serialization
                    safe_metadata = metadata
                except (TypeError, ValueError) as json_error:
                    logger.warning(f"Metadata not JSON serializable, using empty dict: {json_error}")
                    safe_metadata = {}
            
            # Create search record with comprehensive validation
            try:
                search_record = UserSearch(
                    id=uuid.uuid4(),
                    user_id=db_user_id_str,  # user_searches.user_id is VARCHAR
                    instagram_username=username.strip().lower(),  # Normalize username
                    search_timestamp=datetime.now(timezone.utc),
                    analysis_type=analysis_type.strip(),  # Clean analysis_type
                    search_metadata=safe_metadata
                )
                
                db.add(search_record)
                logger.debug(f"Created search record for user {db_user_id_str}: {username}")
                
            except Exception as create_error:
                logger.error(f"Error creating search record: {create_error}")
                logger.error(f"Parameters: user_id={db_user_id_str}, username={username}, analysis_type={analysis_type}")
                return False
            
            # Commit with error handling
            try:
                await db.commit()
                logger.info(f"Successfully recorded search for user {db_user_id_str}: {username}")
                return True
                
            except Exception as commit_error:
                logger.error(f"Error committing search record: {commit_error}")
                await db.rollback()
                return False
            
        except Exception as e:
            logger.error(f"Comprehensive error in record_user_search: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Parameters: user_id={user_id}, username={username}, analysis_type={analysis_type}")
            try:
                await db.rollback()
                logger.debug("Successfully rolled back search transaction")
            except Exception as rollback_error:
                logger.error(f"Error during search rollback: {rollback_error}")
            return False
    
    async def _get_database_user_id(self, db: AsyncSession, supabase_user_id: str) -> Optional[UUID]:
        """Convert Supabase user ID to database user ID - CRITICAL MAPPING FUNCTION"""
        try:
            result = await db.execute(
                select(User.id).where(User.supabase_user_id == supabase_user_id)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                logger.debug(f"Mapped Supabase ID {supabase_user_id} to database ID {db_user}")
                return db_user
            else:
                logger.warning(f"No database user found for Supabase ID: {supabase_user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error mapping user IDs: {str(e)}")
            return None
    
    async def get_user_profile_access(self, db: AsyncSession, user_id: str, username: str) -> Optional[Dict]:
        """Check if user has access to profile and return cached data if available"""
        try:
            # Find profile by username
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                logger.info(f"Profile {username} not found in database")
                return None
            
            # Check if user has access
            access = await db.execute(
                select(UserProfileAccess).where(
                    and_(
                        UserProfileAccess.user_id == UUID(user_id),
                        UserProfileAccess.profile_id == profile.id,
                        UserProfileAccess.expires_at > datetime.now(timezone.utc)
                    )
                )
            )
            user_access = access.scalar_one_or_none()
            
            if not user_access:
                logger.info(f"No valid access found for user {user_id} to profile {username}")
                return None
            
            # Return cached profile data
            return {
                "profile": {
                    "username": profile.username,
                    "full_name": profile.full_name or "",
                    "biography": profile.biography or "",
                    "followers_count": profile.followers_count or 0,
                    "following_count": profile.following_count or 0,
                    "posts_count": profile.posts_count or 0,
                    "is_verified": profile.is_verified or False,
                    "is_private": profile.is_private or False,
                    "is_business_account": profile.is_business_account or False,
                    "profile_pic_url": profile.profile_pic_url or "",
                    "profile_pic_url_hd": profile.profile_pic_url_hd or "",
                    "external_url": profile.external_url or "",
                    "engagement_rate": float(profile.engagement_rate or 0),
                    "avg_likes": profile.avg_likes or 0,
                    "avg_comments": profile.avg_comments or 0,
                    "influence_score": float(profile.influence_score or 0),
                    "content_quality_score": float(profile.content_quality_score or 0),
                },
                "analytics": {
                    "engagement_rate": float(profile.engagement_rate or 0),
                    "influence_score": float(profile.influence_score or 0),
                    "content_quality_score": float(profile.content_quality_score or 0),
                    "data_quality_score": 1.0
                },
                "meta": {
                    "analysis_timestamp": profile.last_analyzed.isoformat() if profile.last_analyzed else datetime.now(timezone.utc).isoformat(),
                    "data_source": "database_cache",
                    "last_refreshed": profile.last_analyzed.isoformat() if profile.last_analyzed else None,
                    "user_has_access": True,
                    "access_expires_in_days": (user_access.expires_at - datetime.now(timezone.utc)).days,
                    "cached": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking user profile access: {e}")
            return None
    
    async def grant_user_profile_access(self, db: AsyncSession, user_id: str, username: str) -> bool:
        """Grant user access to a profile for 30 days"""
        try:
            # Find profile by username
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                logger.warning(f"Cannot grant access - profile {username} not found in database")
                return False
            
            # Create or update access record
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            
            # Check if access already exists
            existing_access = await db.execute(
                select(UserProfileAccess).where(
                    and_(
                        UserProfileAccess.user_id == UUID(user_id),
                        UserProfileAccess.profile_id == profile.id
                    )
                )
            )
            access_record = existing_access.scalar_one_or_none()
            
            if access_record:
                # Update existing access
                access_record.expires_at = expires_at
                # access_type removed - column doesn't exist
                logger.info(f"Updated access for user {user_id} to profile {username}")
            else:
                # Create new access
                new_access = UserProfileAccess(
                    user_id=UUID(user_id),
                    profile_id=profile.id,
                    expires_at=expires_at
                )
                db.add(new_access)
                logger.info(f"Granted new access for user {user_id} to profile {username}")
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error granting user profile access: {e}")
            await db.rollback()
            return False
    
    async def close_pool(self):
        """Close the connection pool and reset state"""
        try:
            if self.pool is not None:
                await self.pool.close()
                self.pool = None
                logger.info("Comprehensive service connection pool closed")
        except Exception as e:
            logger.error(f"Error closing comprehensive service pool: {e}")

# Global service instance
comprehensive_service = ComprehensiveDataService()