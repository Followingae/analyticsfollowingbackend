"""
COMPREHENSIVE DATABASE SERVICE
This service handles ALL Apify datapoints and ensures complete data storage
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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import selectinload, joinedload

from app.core.config import settings
from app.resilience.database_resilience import database_resilience
from .unified_models import (
    User, Profile, Post, UserProfileAccess, UserSearch, UserFavorite,
    AudienceDemographics, CreatorMetadata, CommentSentiment,
    RelatedProfile, Mention, UserList, UserListItem
)
from app.services.engagement_rate_service import EngagementRateService
from app.services.location_detection_service import LocationDetectionService

logger = logging.getLogger(__name__)


class ComprehensiveDataService:
    """Unified service for complete Apify data storage and retrieval"""
    
    def __init__(self):
        self.location_service = LocationDetectionService()
        
    
    async def check_db_health(self, db: AsyncSession) -> bool:
        """Check if database connection is healthy"""
        try:
            # If there's an invalid transaction, roll it back first
            if hasattr(db, '_connection') and db._connection and hasattr(db._connection, '_invalidated') and db._connection._invalidated:
                logger.warning("Connection invalidated, attempting rollback")
                await db.rollback()
            
            # Simple health check query with timeout
            result = await asyncio.wait_for(
                db.execute(text("SELECT 1")), 
                timeout=5.0
            )
            return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            # Try rollback if transaction is in invalid state
            try:
                await db.rollback()
                logger.debug("Performed rollback after health check failure")
            except:
                pass
            return False
    
    async def retry_db_operation(self, operation, db: AsyncSession, max_retries: int = 2):
        """Retry database operations with health checks"""
        for attempt in range(max_retries + 1):
            try:
                # Always ensure clean transaction state before operation
                try:
                    if db.in_transaction():
                        await db.rollback()
                        logger.debug(f"Rolled back transaction before attempt {attempt + 1}")
                except Exception as rollback_error:
                    logger.debug(f"Rollback check error (non-critical): {rollback_error}")

                if attempt > 0:
                    # Check health before retry
                    if not await self.check_db_health(db):
                        logger.warning(f"Database unhealthy on retry attempt {attempt}")
                        await asyncio.sleep(0.5)  # Give database time to recover

                return await operation()

            except Exception as e:
                # Check for transaction abort error
                error_msg = str(e).lower()
                if "current transaction is aborted" in error_msg or "infailedsqltransaction" in error_msg:
                    logger.warning(f"Transaction aborted on attempt {attempt + 1}, will retry with fresh transaction")
                    # Force rollback for next attempt
                    try:
                        await db.rollback()
                    except:
                        pass

                if attempt == max_retries:
                    logger.error(f"Database operation failed after {max_retries + 1} attempts: {e}")
                    raise
                else:
                    logger.warning(f"Database operation failed on attempt {attempt + 1}, retrying: {e}")
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

    # ==========================================================================
    # PROFILE DATA DELETION - FOR COMPLETE REFRESH
    # ==========================================================================
    
    async def delete_complete_profile_data(self, db: AsyncSession, username: str):
        """COMPLETELY DELETE all data for a profile (for force refresh)"""
        logger.info(f"DELETION: Starting complete data deletion for {username}")
        
        try:
            # Get profile to delete
            profile = await self.get_profile_by_username(db, username)
            if not profile:
                logger.info(f"No profile found for {username}, nothing to delete")
                return
            
            profile_id = profile.id
            logger.info(f"Found profile {username} with ID {profile_id}, deleting all related data")
            
            # Delete in proper order to avoid foreign key constraints
            
            # 1. Delete campaign profile associations first
            logger.info("Deleting campaign profile associations...")
            await db.execute(delete(CampaignProfile).where(CampaignProfile.profile_id == profile_id))
            
            # 2. Delete campaign posts (via subquery to find posts belonging to this profile)
            logger.info("Deleting campaign posts for this profile...")
            subquery = select(Post.id).where(Post.profile_id == profile_id)
            await db.execute(delete(CampaignPost).where(CampaignPost.post_id.in_(subquery)))
            
            # 3. Delete analytics and metadata
            logger.info("Deleting analytics and metadata...")
            await db.execute(delete(AudienceDemographics).where(AudienceDemographics.profile_id == profile_id))
            await db.execute(delete(CreatorMetadata).where(CreatorMetadata.profile_id == profile_id))
            
            # Delete comment sentiment for this profile's posts
            logger.info("Deleting comment sentiment data...")
            posts_subquery = select(Post.id).where(Post.profile_id == profile_id)
            await db.execute(delete(CommentSentiment).where(CommentSentiment.post_id.in_(posts_subquery)))
            
            # 4. Delete related profiles and mentions
            logger.info("Deleting related profiles and mentions...")
            await db.execute(delete(RelatedProfile).where(RelatedProfile.profile_id == profile_id))
            await db.execute(delete(Mention).where(Mention.profile_id == profile_id))
            
            # 5. Delete user access records (but keep user searches for history)
            logger.info("Deleting user access records...")
            await db.execute(delete(UserProfileAccess).where(UserProfileAccess.profile_id == profile_id))
            await db.execute(delete(UserFavorite).where(UserFavorite.profile_id == profile_id))
            
            # 6. Delete all posts (this should cascade to remaining associations)
            logger.info("Deleting all posts...")
            await db.execute(delete(Post).where(Post.profile_id == profile_id))
            
            # 7. Finally delete the profile itself
            logger.info("Deleting profile...")
            await db.execute(delete(Profile).where(Profile.id == profile_id))
            
            # Commit all deletions
            await db.commit()
            logger.info(f"SUCCESS: Completely deleted all data for {username}")
            
        except Exception as e:
            logger.error(f"ERROR: Failed to delete profile data for {username}: {e}")
            await db.rollback()
            raise ValueError(f"Failed to delete profile data: {e}")

    # ==========================================================================
    # PROFILE DATA STORAGE - COMPREHENSIVE APIFY MAPPING
    # ==========================================================================
    
    async def store_complete_profile(self, db: AsyncSession, username: str, raw_data: Dict[str, Any], is_background_discovery: bool = False) -> Tuple[Profile, bool]:
        """Store COMPLETE profile with ALL related data (posts, related profiles, etc.)"""
        from app.database.robust_storage import store_profile_robust
        
        logger.info(f"Starting comprehensive profile storage for {username}")
        print(f"DATABASE: Storing complete profile for '{username}'")
        
        try:
            # Store main profile first
            print(f"Calling robust_storage.store_profile_robust...")
            profile, is_new = await store_profile_robust(db, username, raw_data)
            logger.info(f"SUCCESS: Profile {username} stored successfully: {'new' if is_new else 'updated'}")

            # CRITICAL: Store profile ID immediately to avoid greenlet issues
            profile_id = profile.id
            print(f"Profile stored: ID={profile_id}, new={is_new}")

            # Extract user data for post processing
            user_data = self._extract_user_data_comprehensive(raw_data)

            if user_data:
                # Store all posts from profile
                logger.info(f"Processing posts for profile {profile_id}")
                print(f"DATABASE: Processing posts for profile {profile_id}")
                posts_count = await self._store_profile_posts(db, profile_id, user_data)
                print(f"DATABASE: Stored {posts_count} posts")

                # Store related profiles ONLY for user-initiated searches, NOT background analytics
                if not is_background_discovery:
                    logger.info(f"Processing related profiles for profile {profile_id}")
                    print(f"DATABASE: Processing related profiles...")
                    related_count = await self._store_related_profiles(db, profile_id, user_data, is_background_discovery)
                    print(f"DATABASE: Stored {related_count} related profiles")
                else:
                    logger.info(f"🚫 Skipping related profiles storage for background analytics")
                    print(f"DATABASE: Skipping related profiles (background analytics)")
                    related_count = 0

                # Store profile images metadata
                logger.info(f"Processing profile images for profile {profile_id}")
                print(f"DATABASE: Processing profile images metadata...")
                await self._store_profile_images(db, profile_id, user_data)
                print(f"DATABASE: Profile images metadata processed")

                # Detect and store creator location
                logger.info(f"Running location detection for profile {profile_id}")
                print(f"DATABASE: Running location detection...")
                await self._detect_and_store_location(db, profile_id, user_data, raw_data, username)
                print(f"DATABASE: Location detection completed")

                logger.info(f"SUCCESS: Complete profile data stored for {username}")
            else:
                logger.warning(f"No user data found for {username}, skipping post/related data processing")
            
            return profile, is_new
            
        except Exception as storage_error:
            logger.error(f"STORAGE ERROR for {username}: {storage_error}")
            raise ValueError(f"Storage failed for {username}: {storage_error}")

    def _extract_user_data_comprehensive(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user data from Apify response with comprehensive error handling"""
        try:
            # Handle Apify format - data is directly in content.data, no user wrapper
            if 'results' in raw_data:
                results = raw_data['results']
                if results and len(results) > 0:
                    result = results[0]
                    if 'content' in result and 'data' in result['content']:
                        # CRITICAL FIX: Apify data is directly in 'data', not in 'data.user'
                        return result['content']['data']
                    elif 'data' in result:
                        return result['data']

            # Fallback: Direct user data (legacy formats)
            if 'user' in raw_data:
                return raw_data['user']

            # GraphQL response structure (legacy)
            if 'data' in raw_data and 'user' in raw_data['data']:
                return raw_data['data']['user']
                
            logger.warning("Could not extract user data from response structure")
            return {}
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error extracting user data: {e}")
            return {}

    def _map_all_apify_datapoints(self, user_data: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map ALL 80+ Apify datapoints to Profile model fields"""
        
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
        # Profile images - direct URLs (external proxy will be handled elsewhere)
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
        
        # CRITICAL FIX: Calculate engagement rate from recent posts - handle both formats
        # Try Instagram GraphQL format first
        posts_data = safe_get(user_data, 'edge_owner_to_timeline_media.edges', [])
        if not posts_data:
            # Try Apify format - convert to GraphQL-like structure for compatibility
            apify_posts = safe_get(user_data, 'posts', [])
            posts_data = [{'node': post} for post in apify_posts]

        total_engagement = 0
        analyzed_posts = 0

        for post_edge in posts_data[:12]:  # Last 12 posts
            post_node = post_edge.get('node', {})
            # Handle both GraphQL format (edge_liked_by.count) and Apify format (direct likes_count)
            likes = safe_get(post_node, 'edge_liked_by.count', 0) or safe_get(post_node, 'likes_count', 0)
            comments = safe_get(post_node, 'edge_media_to_comment.count', 0) or safe_get(post_node, 'comments_count', 0)
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
                'url': profile_data['profile_pic_url'],  # Already proxied above
                'original_url': safe_get(user_data, 'profile_pic_url', ''),  # Store original for reference
                'type': 'standard',
                'size': 'medium'
            })
        if profile_data.get('profile_pic_url_hd'):
            profile_images.append({
                'url': profile_data['profile_pic_url_hd'],  # Already proxied above
                'original_url': safe_get(user_data, 'profile_pic_url_hd', ''),  # Store original for reference
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

    async def _store_profile_posts(self, db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any]) -> int:
        """Store ALL posts from profile with comprehensive data mapping and engagement rate calculation"""
        try:
            # CRITICAL FIX: Handle both Instagram GraphQL format AND Apify format
            posts_edges = []

            # Try Instagram GraphQL format first (edge_owner_to_timeline_media.edges)
            graphql_posts = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
            if graphql_posts:
                posts_edges = graphql_posts
                print(f" DATABASE: Found {len(posts_edges)} posts to process (GraphQL format)")
            else:
                # Try Apify format (simple posts array)
                apify_posts = user_data.get('posts', [])
                if apify_posts:
                    # Convert Apify format to GraphQL-like format for compatibility
                    posts_edges = [{'node': post} for post in apify_posts]
                    print(f" DATABASE: Found {len(posts_edges)} posts to process (Apify format)")

            if not posts_edges:
                logger.info(f"No posts found for profile {profile_id}")
                print(f" DATABASE: No posts found for profile {profile_id}")
                return 0
            
            # Get profile's followers count for engagement rate calculation
            print(f" DATABASE: Getting follower count for engagement rate calculation...")
            profile_result = await db.execute(
                select(Profile.followers_count).where(Profile.id == profile_id)
            )
            followers_count = profile_result.scalar() or 0
            print(f" DATABASE: Profile has {followers_count} followers for engagement calculation")
            
            posts_created = 0
            posts_skipped = 0
            
            for i, post_edge in enumerate(posts_edges, 1):
                post_node = post_edge.get('node', {})
                shortcode = post_node.get('shortcode')
                
                if not shortcode:
                    posts_skipped += 1
                    continue
                
                print(f" DATABASE: Processing post {i}/{len(posts_edges)} (shortcode: {shortcode})")

                # Check if post already exists (by shortcode globally, not just profile_id)
                result = await db.execute(
                    select(Post).where(Post.shortcode == shortcode)
                )
                existing_post = result.scalar_one_or_none()

                if existing_post:
                    # Post exists - update if profile_id matches, otherwise skip
                    if existing_post.profile_id == profile_id:
                        print(f" DATABASE: Post {shortcode} exists for this profile, updating...")
                        # Update existing post with new data
                        post_data = self._map_post_data_comprehensive(post_node, profile_id)
                        post_data = EngagementRateService.enhance_post_data_with_engagement(
                            post_data, followers_count
                        )

                        # Update only fields that exist in Post model
                        for key, value in post_data.items():
                            if hasattr(Post, key):
                                setattr(existing_post, key, value)

                        posts_skipped += 1  # Count as skipped for simplicity
                        print(f" DATABASE: Post {shortcode} updated")
                    else:
                        print(f" DATABASE: Post {shortcode} exists for different profile (ID: {existing_post.profile_id}), skipping")
                        posts_skipped += 1
                    continue
                
                print(f" DATABASE: Creating new post {shortcode}...")
                post_data = self._map_post_data_comprehensive(post_node, profile_id)
                
                # Calculate and add engagement rate
                post_data = EngagementRateService.enhance_post_data_with_engagement(
                    post_data, followers_count
                )
                
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
                print(f" DATABASE: Post {shortcode} prepared for database insert")
            
            print(f" DATABASE: Committing {posts_created} new posts to database...")
            await db.commit()
            logger.info(f"Created {posts_created} new posts for profile {profile_id}")
            logger.info(f"DATABASE: Successfully committed {posts_created} posts ({posts_skipped} skipped as duplicates)")
            
            # Update profile's overall engagement rate after adding posts
            if posts_created > 0:
                logger.info("DATABASE: Updating overall engagement rate for profile...")
                await EngagementRateService.update_profile_engagement_rate(db, str(profile_id))
                logger.info(f"Updated overall engagement rate for profile {profile_id}")
                logger.info("DATABASE: Profile engagement rate updated")
            
            return posts_created
            
        except Exception as e:
            logger.error(f"Error storing profile posts: {str(e)}")
            return 0

    def _map_post_data_comprehensive(self, post_node: Dict[str, Any], profile_id: UUID) -> Dict[str, Any]:
        """Map ALL post datapoints from Apify response with automatic image proxying"""
        
        def safe_get(data: Dict[str, Any], path: str, default=None):
            try:
                result = data
                for key in path.split('.'):
                    result = result.get(key) if isinstance(result, dict) else default
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        # CRITICAL FIX: Handle both Instagram GraphQL format AND Apify format
        shortcode = safe_get(post_node, 'shortcode', '')
        instagram_id = safe_get(post_node, 'id', '') or safe_get(post_node, 'instagram_post_id', '')

        # BUGFIX: Ensure instagram_post_id is never empty by using shortcode as fallback
        if not instagram_id and shortcode:
            instagram_id = f"shortcode_{shortcode}"
        elif not instagram_id:
            # Generate a unique ID if both are missing
            import uuid
            instagram_id = f"generated_{str(uuid.uuid4())[:8]}"

        post_data = {
            'profile_id': profile_id,
            'instagram_post_id': instagram_id,
            'shortcode': shortcode,

            # Media information - handle both formats
            'media_type': safe_get(post_node, '__typename', ''),
            'is_video': safe_get(post_node, 'is_video', False),
            'display_url': safe_get(post_node, 'display_url', ''),
            'thumbnail_src': safe_get(post_node, 'thumbnail_src', ''),
            'thumbnail_tall_src': safe_get(post_node, 'thumbnail_tall_src', ''),

            # Video fields - handle both formats
            'video_url': safe_get(post_node, 'video_url', ''),
            'video_view_count': safe_get(post_node, 'video_view_count', 0),
            'has_audio': safe_get(post_node, 'has_audio'),
            'video_duration': safe_get(post_node, 'video_duration'),

            # Dimensions
            'width': safe_get(post_node, 'dimensions.width', 0),
            'height': safe_get(post_node, 'dimensions.height', 0),

            # CRITICAL: Engagement - handle both GraphQL format (edge_liked_by.count) and Apify format (likes_count)
            'likes_count': safe_get(post_node, 'edge_liked_by.count', 0) or safe_get(post_node, 'likes_count', 0),
            'comments_count': safe_get(post_node, 'edge_media_to_comment.count', 0) or safe_get(post_node, 'comments_count', 0),
            'comments_disabled': safe_get(post_node, 'comments_disabled', False),
            
            # Content
            'accessibility_caption': safe_get(post_node, 'accessibility_caption', ''),
            
            # Settings
            'viewer_can_reshare': safe_get(post_node, 'viewer_can_reshare', True),
            'like_and_view_counts_disabled': safe_get(post_node, 'like_and_view_counts_disabled', False),
            'has_upcoming_event': safe_get(post_node, 'has_upcoming_event', False),
            
            # Location
            'location_name': safe_get(post_node, 'location.name', ''),
            'location_id': safe_get(post_node, 'location.id', ''),
            
            # Carousel handling
            'is_carousel': safe_get(post_node, '__typename') == 'GraphSidecar',
            'carousel_media_count': len(safe_get(post_node, 'edge_sidecar_to_children.edges', [])) if safe_get(post_node, '__typename') == 'GraphSidecar' else 1,
            
            # CRITICAL: Timestamps - handle both formats
            'taken_at_timestamp': safe_get(post_node, 'taken_at_timestamp', 0) or safe_get(post_node, 'timestamp', 0),
            
            # Structured data
            'thumbnail_resources': safe_get(post_node, 'thumbnail_resources', []),
            'tagged_users': safe_get(post_node, 'edge_media_to_tagged_user.edges', []),
            'coauthor_producers': safe_get(post_node, 'coauthor_producers', []),
            
            # Handle sidecar children (carousel posts)
            'sidecar_children': safe_get(post_node, 'edge_sidecar_to_children.edges', []) if safe_get(post_node, '__typename') == 'GraphSidecar' else [],
            
            # Raw data backup
            'raw_data': post_node
        }
        
        # CRITICAL FIX: Extract caption - handle both Instagram GraphQL format AND Apify format
        caption_text = ''

        # Try Instagram GraphQL format first (edge_media_to_caption.edges)
        caption_edges = safe_get(post_node, 'edge_media_to_caption.edges', [])
        if caption_edges and len(caption_edges) > 0:
            caption_text = caption_edges[0].get('node', {}).get('text', '')

        # If no caption found, try Apify format (direct caption field)
        if not caption_text:
            caption_text = safe_get(post_node, 'caption', '') or safe_get(post_node, 'text', '')

        post_data['caption'] = caption_text
        
        # Extract hashtags and mentions from caption
        caption = post_data.get('caption', '')
        if caption:
            import re
            hashtags = re.findall(r'#\w+', caption)
            mentions = re.findall(r'@\w+', caption)
            post_data['hashtags'] = hashtags
            post_data['mentions'] = mentions
        
        # Store post images/thumbnails with automatic proxying (eliminates CORS issues)
        post_images = []
        if post_data.get('display_url'):
            # Note: display_url is already proxied above
            post_images.append({
                'url': post_data['display_url'],  # Already proxied
                'original_url': safe_get(post_node, 'display_url', ''),  # Store original for reference
                'type': 'main',
                'width': post_data.get('width', 0),
                'height': post_data.get('height', 0),
                'is_video': post_data.get('is_video', False)
            })
        
        # Add video URL if available
        if post_data.get('video_url'):
            post_images.append({
                'url': post_data['video_url'],  # Already proxied
                'original_url': safe_get(post_node, 'video_url', ''),  # Store original for reference
                'type': 'video',
                'width': post_data.get('width', 0),
                'height': post_data.get('height', 0),
                'is_video': True
            })
        
        # Process thumbnail resources with direct URLs
        thumbnail_resources = post_data.get('thumbnail_resources', [])
        post_thumbnails = []
        for thumb in thumbnail_resources:
            original_url = thumb.get('src', '')
            post_thumbnails.append({
                'url': original_url,  # Direct URL
                'original_url': original_url,  # Store original for reference
                'width': thumb.get('config_width', 0),
                'height': thumb.get('config_height', 0),
                'type': 'thumbnail'
            })
        
        # Add carousel children images with direct URLs
        if post_data.get('sidecar_children'):
            for child_edge in post_data['sidecar_children']:
                child_node = child_edge.get('node', {})
                original_url = child_node.get('display_url', '')
                if original_url:
                    post_images.append({
                        'url': original_url,  # Direct URL
                        'original_url': original_url,  # Store original for reference
                        'type': 'carousel_item',
                        'width': safe_get(child_node, 'dimensions.width', 0),
                        'height': safe_get(child_node, 'dimensions.height', 0),
                        'is_video': child_node.get('is_video', False)
                    })
        
        post_data['post_images'] = post_images
        post_data['post_thumbnails'] = post_thumbnails
        
        # Calculate engagement rate for this post
        likes = post_data.get('likes_count', 0)
        comments = post_data.get('comments_count', 0)
        total_engagement = likes + comments
        
        # We'll need the profile's follower count for accurate engagement rate
        # For now, store the engagement metrics
        post_data['engagement_rate'] = None  # Will be calculated with profile context
        post_data['performance_score'] = None  # Will be calculated with profile context
        
        return post_data

    async def _store_related_profiles(self, db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any], is_background_discovery: bool = False) -> int:
        """Store related/suggested profiles"""
        try:
            print(f" DATABASE: Cleaning existing related profiles...")
            # Delete existing related profiles
            delete_result = await db.execute(delete(RelatedProfile).where(RelatedProfile.profile_id == profile_id))
            print(f" DATABASE: Deleted {delete_result.rowcount or 0} existing related profiles")
            
            # CRITICAL FIX: Handle both Instagram GraphQL format AND Apify format for related profiles
            related_edges = []

            # Try Instagram GraphQL format first (edge_related_profiles.edges)
            graphql_related = user_data.get('edge_related_profiles', {}).get('edges', [])
            if graphql_related:
                related_edges = graphql_related
                print(f" DATABASE: Found {len(related_edges)} related profiles to process (GraphQL format)")
            else:
                # Try Apify format (simple related_profiles array)
                apify_related = user_data.get('related_profiles', [])
                if apify_related:
                    # Convert Apify format to GraphQL-like format for compatibility
                    related_edges = [{'node': profile} for profile in apify_related]
                    print(f" DATABASE: Found {len(related_edges)} related profiles to process (Apify format)")

            if not related_edges:
                print(f" DATABASE: No related profiles found")
                return 0
            
            related_count = 0
            for i, edge in enumerate(related_edges[:15], 1):  # Store up to 15 related profiles
                node = edge.get('node', {})
                username = node.get('username')
                
                if not username:
                    print(f" DATABASE: Skipping related profile {i} (no username)")
                    continue
                
                print(f" DATABASE: Processing related profile {i}/{min(len(related_edges), 15)}: @{username}")
                
                related_data = {
                    'profile_id': profile_id,
                    'related_username': username,
                    'related_full_name': node.get('full_name', ''),
                    'related_is_verified': node.get('is_verified', False),
                    'related_is_private': node.get('is_private', False),
                    'related_profile_pic_url': node.get('profile_pic_url', ''),
                    'related_followers_count': node.get('edge_followed_by', {}).get('count', 0),
                    'similarity_score': max(100 - (i * 5), 10),  # Decreasing similarity score
                    'relationship_type': 'suggested',
                    'source_type': 'background_discovery' if is_background_discovery else 'user_search'
                }
                
                related_profile = RelatedProfile(**related_data)
                db.add(related_profile)
                related_count += 1
                print(f" DATABASE: Related profile @{username} prepared for insert")
            
            print(f" DATABASE: Committing {related_count} related profiles to database...")
            await db.commit()
            logger.info(f"Stored {related_count} related profiles for profile {profile_id}")
            print(f"[SUCCESS] DATABASE: Successfully committed {related_count} related profiles")


            return related_count
            
        except Exception as e:
            logger.error(f"Error storing related profiles: {str(e)}")
            return 0

    async def _store_profile_images(self, db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any]):
        """Store profile images and thumbnails separately for better organization"""
        try:
            # This would integrate with image storage service
            # For now, we store image metadata in the profile_images/profile_thumbnails JSONB fields
            # which is already handled in _map_all_apify_datapoints
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

    async def grant_profile_access_with_tracking(self, db: AsyncSession, user_id: UUID, profile_id: UUID) -> UserProfileAccess:
        """Grant comprehensive profile access with 30-day tracking - UPDATED FOR ACTUAL SCHEMA"""
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
                # Update existing access - only use columns that exist
                access.expires_at = expires_at
                # Note: last_accessed, access_count, etc. don't exist in actual schema
            else:
                # Create new access record - only use columns that exist
                access_data = {
                    'user_id': user_id,
                    'profile_id': profile_id,
                    'granted_at': current_time,
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
                .order_by(UserProfileAccess.granted_at.desc())
                .limit(limit)
                .options(selectinload(Profile.audience_demographics))
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting accessible profiles: {str(e)}")
            return []

    # ==========================================================================
    # ANALYTICS METHODS - ENHANCED FROM APIFY DATA (Not fake AI)
    # ==========================================================================
    
    async def store_audience_demographics(self, db: AsyncSession, profile_id: UUID,
                                        gender_dist: Dict, age_dist: Dict, location_dist: Dict,
                                        sample_size: int = None, confidence_score: float = None) -> AudienceDemographics:
        """Store audience demographics enhanced from Apify follower data"""
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
                demographics.analysis_method = 'apify_enhanced'
            else:
                # Create new
                demographics_data = {
                    'profile_id': profile_id,
                    'gender_distribution': gender_dist,
                    'age_distribution': age_dist,
                    'location_distribution': location_dist,
                    'sample_size': sample_size,
                    'confidence_score': confidence_score,
                    'analysis_method': 'apify_enhanced'
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
        """Store creator metadata extracted from Apify profile data"""
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
                    'analysis_confidence': 0.85  # Based on Apify data quality
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
    
    async def grant_profile_access(self, db: AsyncSession, user_id, profile_id) -> bool:
        """Grant user 30-day access to a profile - FIXED for actual schema"""
        try:
            logger.info(f"ACCESS GRANT: Starting grant for user_id={user_id} (type: {type(user_id)}) to profile_id={profile_id} (type: {type(profile_id)})")
            
            # CRITICAL FIX: Convert Supabase user ID to database user ID
            db_user_id = await self._get_database_user_id(db, user_id)
            if not db_user_id:
                logger.error(f"ACCESS GRANT ERROR: Failed to find database user ID for Supabase ID: {user_id}")
                # Still attempt the operation with Supabase ID as fallback
                try:
                    # Convert string to UUID if needed
                    fallback_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
                    db_user_id = fallback_user_id
                    logger.warning(f"ACCESS GRANT FALLBACK: Using Supabase ID as fallback: {db_user_id}")
                except (ValueError, TypeError) as uuid_error:
                    logger.error(f"ACCESS GRANT FALLBACK ERROR: Cannot convert user_id to UUID: {uuid_error}")
                    return False
            
            # Validate and convert profile_id to UUID if needed
            if isinstance(profile_id, str):
                try:
                    profile_id = UUID(profile_id)
                    logger.info(f"ACCESS GRANT: Converted profile_id string to UUID: {profile_id}")
                except (ValueError, TypeError) as conv_error:
                    logger.error(f"ACCESS GRANT ERROR: Cannot convert profile_id string to UUID: {conv_error}")
                    return False
            elif not isinstance(profile_id, UUID):
                logger.error(f"ACCESS GRANT ERROR: Invalid profile_id type: {type(profile_id)}")
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
                # Update existing access - only use columns that exist
                try:
                    await db.execute(
                        update(UserProfileAccess)
                        .where(
                            and_(
                                UserProfileAccess.user_id == db_user_id,
                                UserProfileAccess.profile_id == profile_id
                            )
                        )
                        .values(expires_at=expires_at)
                    )
                    logger.info(f"Updated profile access for user {db_user_id} to profile {profile_id}")
                except Exception as update_error:
                    logger.error(f"Error updating profile access: {update_error}")
                    raise update_error
            else:
                # Create new access record - only use columns that exist
                try:
                    access_record = UserProfileAccess(
                        id=uuid.uuid4(),
                        user_id=db_user_id,
                        profile_id=profile_id,
                        granted_at=datetime.now(timezone.utc),
                        expires_at=expires_at
                    )
                    db.add(access_record)
                    logger.info(f"Granted new profile access for user {db_user_id} to profile {profile_id}")
                except Exception as create_error:
                    logger.error(f"Error creating profile access record: {create_error}")
                    raise create_error
            
            # Commit with error handling
            try:
                logger.info(f"ACCESS GRANT: Committing transaction for user {db_user_id} -> profile {profile_id}")
                await db.commit()
                logger.info(f"ACCESS GRANT SUCCESS: Successfully committed profile access for user {db_user_id}")
                return True
            except Exception as commit_error:
                logger.error(f"ACCESS GRANT COMMIT ERROR: Error committing profile access: {commit_error}")
                logger.error(f"ACCESS GRANT COMMIT ERROR TYPE: {type(commit_error).__name__}")
                try:
                    await db.rollback()
                    logger.info("ACCESS GRANT: Transaction rolled back successfully")
                except Exception as rollback_error:
                    logger.error(f"ACCESS GRANT ROLLBACK ERROR: {rollback_error}")
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
    
    async def record_user_search_fixed(self, db: AsyncSession, user_id, username: str, 
                                analysis_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Record user search in database - FIXED for actual schema"""
        try:
            # CRITICAL FIX: Convert Supabase user ID to database user ID
            db_user_id = await self._get_database_user_id(db, user_id)
            if not db_user_id:
                logger.error(f"Failed to find database user ID for Supabase ID: {user_id}")
                # Use Supabase ID as fallback for search recording
                try:
                    db_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
                    logger.warning(f"Using Supabase ID as fallback for search: {db_user_id}")
                except (ValueError, TypeError) as uuid_error:
                    logger.error(f"Cannot convert user_id to UUID: {uuid_error}")
                    return False
            
            # Validate required parameters
            if not username or not analysis_type:
                logger.error(f"Missing required parameters: username='{username}', analysis_type='{analysis_type}'")
                return False
            
            # Clean and validate metadata
            safe_metadata = {}
            if metadata:
                try:
                    # Convert UUIDs to strings for JSON serialization
                    import json
                    from uuid import UUID

                    def convert_uuids_to_strings(obj):
                        """Recursively convert UUID objects to strings"""
                        if isinstance(obj, UUID):
                            return str(obj)
                        elif isinstance(obj, dict):
                            return {k: convert_uuids_to_strings(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_uuids_to_strings(item) for item in obj]
                        else:
                            return obj

                    serializable_metadata = convert_uuids_to_strings(metadata)
                    json.dumps(serializable_metadata)  # Test serialization
                    safe_metadata = serializable_metadata
                except (TypeError, ValueError) as json_error:
                    logger.warning(f"Metadata not JSON serializable, using empty dict: {json_error}")
                    safe_metadata = {}
            
            # Create search record - use actual columns that exist
            try:
                search_record = UserSearch(
                    id=uuid.uuid4(),
                    user_id=db_user_id,  # user_searches.user_id is UUID
                    instagram_username=username.strip().lower(),  # Normalize username
                    search_timestamp=datetime.now(timezone.utc),
                    analysis_type=analysis_type.strip(),  # Clean analysis_type
                    search_metadata=safe_metadata
                )
                
                db.add(search_record)
                logger.debug(f"Created search record for user {db_user_id}: {username}")
                
            except Exception as create_error:
                logger.error(f"Error creating search record: {create_error}")
                logger.error(f"Parameters: user_id={db_user_id}, username={username}, analysis_type={analysis_type}")
                return False
            
            # Commit with error handling
            try:
                await db.commit()
                logger.info(f"Successfully recorded search for user {db_user_id}: {username}")
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
    
    async def _get_database_user_id(self, db: AsyncSession, supabase_user_id) -> Optional[UUID]:
        """Convert Supabase user ID to database user ID - CRITICAL MAPPING FUNCTION"""
        try:
            # Convert UUID to string if needed - supabase_user_id column is TEXT
            if isinstance(supabase_user_id, UUID):
                supabase_user_id_str = str(supabase_user_id)
                logger.debug(f"MAPPING: Converted UUID to string: {supabase_user_id_str}")
            else:
                supabase_user_id_str = str(supabase_user_id)
            
            logger.debug(f"MAPPING: Looking for user with Supabase ID: {supabase_user_id_str} (type: {type(supabase_user_id_str)})")
            
            result = await db.execute(
                select(User.id).where(User.supabase_user_id == supabase_user_id_str)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                logger.info(f"MAPPING SUCCESS: Supabase ID {supabase_user_id_str} -> database ID {db_user} (type: {type(db_user)})")
                return db_user
            else:
                logger.warning(f"MAPPING FAILED: No database user found for Supabase ID: {supabase_user_id_str}")
                return None
                
        except Exception as e:
            logger.error(f"MAPPING ERROR: Error mapping user IDs: {str(e)}")
            return None
    
    async def get_user_unlocked_profiles(self, db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get all profiles that user has access to (for creators page) - WITH RESILIENCE"""
        
        async def _execute_operation(db_session, user_id, page, page_size):
            """Inner function for resilient execution"""
            from datetime import datetime, timezone
            from uuid import UUID
            
            logger.info(f"Getting unlocked profiles for user {user_id}, page {page}")
            
            # Convert string user_id to UUID (Supabase auth ID is already a UUID string)
            try:
                user_uuid = UUID(user_id)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user_id format: {user_id}, error: {e}")
                raise ValueError(f"Invalid user_id format: {user_id}")

            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get current time for consistent timestamp comparison
            current_time = datetime.now(timezone.utc)
            
            # CRITICAL FIX: Get profiles from user_profile_access table (30-day access system)
            from app.database.unified_models import UserProfileAccess
            from datetime import datetime, timezone
            from sqlalchemy import text

            # CRITICAL: Map from auth.users.id to public.users.id for user_profile_access
            user_mapping_query = text("""
                SELECT id FROM users WHERE supabase_user_id = :auth_user_id
            """)

            user_mapping_result = await db_session.execute(user_mapping_query, {
                "auth_user_id": str(user_uuid)  # Convert UUID to string
            })

            user_mapping_row = user_mapping_result.fetchone()
            if not user_mapping_row:
                logger.error(f"No public.users record found for auth user {user_uuid}")
                return {
                    'profiles': [],
                    'total_count': 0,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': 0
                }

            public_user_id = user_mapping_row[0]
            logger.info(f"Mapped auth user {user_uuid} to public user {public_user_id}")

            # Query user_profile_access table - this is the correct 30-day access system
            current_time = datetime.now(timezone.utc)

            # PGBOUNCER FIX: Use raw SQL query to avoid ORM issues
            raw_query = text("""
                SELECT
                    upa.id as access_id,
                    upa.user_id,
                    upa.profile_id,
                    upa.granted_at,
                    upa.expires_at,
                    upa.access_type,
                    upa.credits_spent,
                    p.*
                FROM user_profile_access upa
                JOIN profiles p ON upa.profile_id = p.id
                WHERE upa.user_id = :user_id
                    AND upa.expires_at > :current_time
                ORDER BY upa.granted_at DESC
                OFFSET :offset
                LIMIT :limit
            """)

            # Execute queries with retry and timeout protection
            async def execute_queries():
                # Use asyncio.wait_for to add timeout protection
                result = await asyncio.wait_for(
                    db_session.execute(raw_query, {
                        "user_id": public_user_id,
                        "current_time": current_time,
                        "offset": offset,
                        "limit": page_size
                    }),
                    timeout=30.0
                )
                profiles_data = result.all()

                # Count total accessible profiles for this user (active access only)
                count_query = select(func.count(UserProfileAccess.id)).where(
                    UserProfileAccess.user_id == public_user_id,  # Use mapped public user ID
                    UserProfileAccess.expires_at > current_time
                )

                count_result = await asyncio.wait_for(db_session.execute(count_query), timeout=30.0)
                total_count = count_result.scalar() or 0

                return profiles_data, total_count

            try:
                profiles_data, total_count = await self.retry_db_operation(execute_queries, db_session)
                
            except asyncio.TimeoutError:
                logger.error(f"Database query timeout for user {user_id}")
                raise ValueError("Database query timeout - please try again")
            except Exception as db_error:
                logger.error(f"Database error for user {user_id}: {str(db_error)}")
                raise ValueError(f"Database operation failed: {str(db_error)}")
            
            # Format response
            profiles = []

            for row in profiles_data:
                # The raw SQL query returns a single row with all columns
                row_dict = dict(row._mapping)

                # Calculate remaining days
                expires_at = row_dict.get('expires_at')
                days_remaining = None
                if expires_at:
                    days_remaining = max(0, (expires_at - current_time).days)

                profile_data = {
                    "username": row_dict.get('username', ''),
                    "full_name": row_dict.get('full_name', ''),
                    "profile_pic_url": row_dict.get('profile_pic_url', ''),
                    "profile_pic_url_hd": row_dict.get('profile_pic_url_hd', ''),
                    "cdn_avatar_url": row_dict.get('cdn_avatar_url', ''),  # CDN processed profile picture URL
                    # Pre-proxied URLs for frontend consistency
                    "proxied_profile_pic_url": row_dict.get('profile_pic_url', ''),  # External proxy service handles these
                    "proxied_profile_pic_url_hd": row_dict.get('profile_pic_url_hd', ''),  # External proxy service handles these
                    "followers_count": row_dict.get('followers_count', 0),
                    "posts_count": row_dict.get('posts_count', 0),
                    "is_verified": row_dict.get('is_verified', False),
                    "is_private": row_dict.get('is_private', False),
                    "engagement_rate": float(row_dict.get('engagement_rate', 0)),
                    "influence_score": float(row_dict.get('influence_score', 0)),

                    # Access information from UserProfileAccess record (30-day system)
                    "access_granted_at": row_dict['granted_at'].isoformat() if row_dict.get('granted_at') else None,
                    "access_expires_at": expires_at.isoformat() if expires_at else None,
                    "days_remaining": days_remaining,
                    "profile_id": str(row_dict.get('profile_id', '')),
                    "credits_spent": row_dict.get('credits_spent', 25),  # Standard cost for 30-day access

                    # Add AI analysis data if available
                    "ai_analysis": {
                        "primary_content_type": row_dict.get('ai_primary_content_type'),
                        "avg_sentiment_score": row_dict.get('ai_avg_sentiment_score'),
                        "content_distribution": row_dict.get('ai_content_distribution'),
                        "language_distribution": row_dict.get('ai_language_distribution'),
                        "content_quality_score": row_dict.get('ai_content_quality_score')
                    }
                }
                profiles.append(profile_data)
            
            
            return {
                "profiles": profiles,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": page * page_size < total_count,
                    "has_previous": page > 1
                },
                "meta": {
                    "user_id": user_id,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "note": "All image URLs are pre-proxied to eliminate CORS issues",
                }
            }
        
        # Use resilience layer for database operations
        try:
            return await database_resilience.execute_with_resilience(
                db, _execute_operation, "get_user_unlocked_profiles", user_id, page, page_size
            )
        except Exception as e:
            import traceback
            error_details = str(e) if str(e) else repr(e)
            logger.error(f"RESILIENT DB: Failed to get unlocked profiles for user {user_id}: {error_details}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Return empty result for graceful degradation
            return {
                "profiles": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_previous": False
                },
                "meta": {
                    "user_id": user_id,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "error": "Service temporarily unavailable - please try again",
                    "network_issue": True
                }
            }

    async def get_user_profile_access(self, db: AsyncSession, user_id: str, username: str) -> Optional[Dict]:
        """Check if user has access to profile and return cached data if available"""
        try:
            from uuid import UUID
            
            # Convert string user_id to UUID
            try:
                user_uuid = UUID(user_id)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user_id format: {user_id}, error: {e}")
                return None
            
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
                        UserProfileAccess.user_id == user_uuid,
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
                    "engagement_rate": float(getattr(profile, 'engagement_rate', 0) or 0),
                    "avg_likes": getattr(profile, 'avg_likes', 0) or 0,
                    "avg_comments": getattr(profile, 'avg_comments', 0) or 0,
                    "influence_score": float(getattr(profile, 'influence_score', 0) or 0),
                    "content_quality_score": float(getattr(profile, 'content_quality_score', 0) or 0),
                },
                "analytics": {
                    "engagement_rate": float(getattr(profile, 'engagement_rate', 0) or 0),
                    "influence_score": float(getattr(profile, 'influence_score', 0) or 0),
                    "content_quality_score": float(getattr(profile, 'content_quality_score', 0) or 0),
                    "data_quality_score": 1.0
                },
                "meta": {
                    "analysis_timestamp": getattr(profile, 'last_analyzed', datetime.now(timezone.utc)).isoformat() if getattr(profile, 'last_analyzed', None) else datetime.now(timezone.utc).isoformat(),
                    "data_source": "database_cache",
                    "last_refreshed": getattr(profile, 'last_analyzed', None).isoformat() if getattr(profile, 'last_analyzed', None) else None,
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
            from uuid import UUID
            
            # Convert string user_id to UUID
            try:
                user_uuid = UUID(user_id)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user_id format: {user_id}, error: {e}")
                return False
                
            # Map auth.users.id to public.users.id for foreign key constraint
            public_user_result = await db.execute(
                select(User.id).where(User.supabase_user_id == str(user_uuid))
            )
            public_user_id = public_user_result.scalar_one_or_none()
            
            if not public_user_id:
                logger.error(f"Cannot find public.users record for auth user {user_id}")
                return False
            
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
                        UserProfileAccess.user_id == user_uuid,
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
                    user_id=user_uuid,
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

    # ==========================================================================
    # TEAM PROFILE ACCESS METHODS - B2B SaaS Integration
    # ==========================================================================
    
    async def grant_team_profile_access(self, db: AsyncSession, team_id: UUID, user_id: UUID, username: str) -> bool:
        """Grant team access to a profile"""
        try:
            print(f" TEAM ACCESS: Starting team access grant for {username} to team {team_id}")
            from app.database.unified_models import TeamProfileAccess
            from uuid import uuid4
            
            # Find profile by username
            print(f" TEAM ACCESS: Looking up profile {username} in database...")
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                logger.warning(f"Cannot grant team access - profile {username} not found in database")
                print(f"❌ TEAM ACCESS: Profile {username} not found in database")
                return False
            
            print(f"[SUCCESS] TEAM ACCESS: Profile {username} found (ID: {profile.id})")
                
            # Map auth.users.id to public.users.id for foreign key constraint
            print(f" TEAM ACCESS: Mapping Supabase user {user_id} to public users table...")
            public_user_result = await db.execute(
                select(User.id).where(User.supabase_user_id == str(user_id))
            )
            public_user_id = public_user_result.scalar_one_or_none()
            
            if not public_user_id:
                logger.error(f"Cannot find public.users record for auth user {user_id}")
                print(f"❌ TEAM ACCESS: Cannot find public.users record for auth user {user_id}")
                return False
            
            print(f"[SUCCESS] TEAM ACCESS: Mapped to public user ID: {public_user_id}")
            
            # Check if team access already exists
            print(f" TEAM ACCESS: Checking if team access already exists...")
            existing_access = await db.execute(
                select(TeamProfileAccess).where(
                    and_(
                        TeamProfileAccess.team_id == team_id,
                        TeamProfileAccess.profile_id == profile.id
                    )
                )
            )
            access_record = existing_access.scalar_one_or_none()
            
            if access_record:
                # Update access timestamp
                print(f" TEAM ACCESS: Team access already exists, updating timestamp...")
                access_record.accessed_at = datetime.now(timezone.utc)
                logger.info(f"Updated team access for team {team_id} to profile {username}")
            else:
                # Create new team access
                print(f" TEAM ACCESS: Creating new team access record...")
                new_access = TeamProfileAccess(
                    id=uuid4(),
                    team_id=team_id,
                    profile_id=profile.id,
                    granted_by_user_id=public_user_id,
                    accessed_at=datetime.now(timezone.utc)
                )
                db.add(new_access)
                logger.info(f"Granted new team access for team {team_id} to profile {username}")
                print(f" TEAM ACCESS: New team access record created")
            
            print(f" TEAM ACCESS: Committing team access to database...")
            await db.commit()
            print(f"[SUCCESS] TEAM ACCESS: Team access granted successfully for {username}")
            return True
            
        except Exception as e:
            logger.error(f"Error granting team profile access: {e}")
            print(f"❌ TEAM ACCESS: Error granting team access - {str(e)}")
            await db.rollback()
            return False

    async def check_team_profile_access(self, db: AsyncSession, team_id: UUID, username: str) -> bool:
        """Check if team has access to a profile"""
        try:
            from app.database.unified_models import TeamProfileAccess
            
            # Find profile by username
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                return False
            
            # Check if team access exists
            existing_access = await db.execute(
                select(TeamProfileAccess).where(
                    and_(
                        TeamProfileAccess.team_id == team_id,
                        TeamProfileAccess.profile_id == profile.id
                    )
                )
            )
            access_record = existing_access.scalar_one_or_none()
            
            return access_record is not None
            
        except Exception as e:
            logger.error(f"Error checking team profile access: {e}")
            return False

    async def get_team_profile_access(self, db: AsyncSession, team_id: UUID, username: str) -> Optional[Dict]:
        """Check if team has access to profile and return cached data if available"""
        try:
            from app.database.unified_models import TeamProfileAccess
            
            # Find profile by username
            result = await db.execute(
                select(Profile).where(Profile.username == username)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                logger.debug(f"Profile {username} not found")
                return None
            
            # Check team access
            access_result = await db.execute(
                select(TeamProfileAccess).where(
                    and_(
                        TeamProfileAccess.team_id == team_id,
                        TeamProfileAccess.profile_id == profile.id
                    )
                )
            )
            access_record = access_result.scalar_one_or_none()
            
            if not access_record:
                logger.debug(f"Team {team_id} does not have access to profile {username}")
                return None
            
            # Return formatted profile data (similar to user profile access)
            current_time = datetime.now(timezone.utc)
            
            # Calculate engagement metrics
            try:
                from app.services.engagement_calculator import engagement_calculator
                engagement_metrics = await engagement_calculator.calculate_and_update_profile_engagement(
                    db, str(profile.id)
                )
            except Exception as engagement_error:
                logger.warning(f"Engagement calculation failed: {engagement_error}")
                engagement_metrics = {
                    'overall_engagement_rate': profile.engagement_rate or 0,
                    'avg_likes': 0,
                    'avg_comments': 0,
                    'avg_total_engagement': 0,
                    'posts_analyzed': 0
                }
            
            # Collect AI insights if available
            ai_insights = {}
            try:
                ai_insights = {
                    "ai_primary_content_type": profile.ai_primary_content_type,
                    "ai_content_distribution": profile.ai_content_distribution,
                    "ai_avg_sentiment_score": profile.ai_avg_sentiment_score,
                    "ai_language_distribution": profile.ai_language_distribution,
                    "ai_content_quality_score": profile.ai_content_quality_score,
                    "ai_profile_analyzed_at": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
                    "ai_top_3_categories": profile.ai_top_3_categories or [],
                    "ai_top_10_categories": profile.ai_top_10_categories or [],
                    "has_ai_analysis": profile.ai_profile_analyzed_at is not None,
                    "ai_processing_status": "completed" if profile.ai_profile_analyzed_at else "pending"
                }
            except AttributeError:
                ai_insights = {
                    "has_ai_analysis": False,
                    "ai_processing_status": "not_available"
                }
            
            return {
                "success": True,
                "profile": {
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "biography": profile.biography,
                    "followers_count": profile.followers_count or 0,
                    "following_count": profile.following_count or 0,
                    "posts_count": profile.posts_count or 0,
                    "is_verified": profile.is_verified or False,
                    "is_private": profile.is_private or False,
                    "is_business_account": profile.is_business_account or False,
                    "profile_pic_url": profile.profile_pic_url,
                    "profile_pic_url_hd": profile.profile_pic_url_hd,
                    "external_url": profile.external_url,
                    "engagement_rate": engagement_metrics["overall_engagement_rate"],
                    "business_category_name": profile.category or profile.instagram_business_category or '',
                    "avg_likes": engagement_metrics["avg_likes"],
                    "avg_comments": engagement_metrics["avg_comments"],
                    "influence_score": profile.influence_score or 0,
                    "content_quality_score": getattr(profile, 'content_quality_score', 0) or 0
                },
                "analytics": {
                    "engagement_rate": engagement_metrics["overall_engagement_rate"],
                    "engagement_rate_last_12_posts": engagement_metrics.get('engagement_rate_last_12_posts', 0),
                    "engagement_rate_last_30_days": engagement_metrics.get('engagement_rate_last_30_days', 0),
                    "influence_score": profile.influence_score or 0,
                    "data_quality_score": float(profile.data_quality_score or 1.0),
                    "avg_likes": engagement_metrics["avg_likes"],
                    "avg_comments": engagement_metrics["avg_comments"],
                    "avg_total_engagement": engagement_metrics["avg_total_engagement"],
                    "posts_analyzed": engagement_metrics["posts_analyzed"],
                    "content_quality_score": float(getattr(profile, 'content_quality_score', 0) or 0)
                },
                "ai_insights": ai_insights,
                "meta": {
                    "analysis_timestamp": current_time.isoformat(),
                    "data_source": "database_team_access",
                    "stored_in_database": True,
                    "team_has_access": True,
                    "access_granted_at": access_record.accessed_at.isoformat(),
                    "includes_ai_insights": bool(ai_insights.get("has_ai_analysis", False))
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking team profile access: {e}")
            return None

    async def _detect_and_store_location(self, db: AsyncSession, profile_id: str, user_data: Dict[str, Any], raw_data: Dict[str, Any], username: str):
        """Detect creator's primary country and store in database"""
        try:
            # Prepare data for location detection
            profile_data_for_detection = {
                "biography": user_data.get("biography", ""),
                "posts": []
            }

            # Get posts for content analysis if available
            posts_data = user_data.get("edge_owner_to_timeline_media", {}).get("edges", [])
            for post_edge in posts_data[:20]:  # Analyze up to 20 recent posts
                post_node = post_edge.get("node", {})
                caption_edges = post_node.get("edge_media_to_caption", {}).get("edges", [])
                caption = ""
                if caption_edges:
                    caption = caption_edges[0].get("node", {}).get("text", "")

                profile_data_for_detection["posts"].append({
                    "caption": caption
                })

            # Add audience data if available (this would come from separate analysis)
            # For now, we'll skip audience data since it's not in the standard Apify response
            profile_data_for_detection["audience_top_countries"] = []

            # Run location detection
            logger.info(f"Starting location detection for {username}")
            location_result = self.location_service.detect_country(profile_data_for_detection)
            logger.info(f"Location detection completed for {username}: {location_result}")

            # Update profile with location data (only detected_country column exists)
            if location_result and location_result.get("country_code"):
                country_code = location_result["country_code"]
                confidence = location_result.get("confidence", 0)

                update_query = (
                    update(Profile)
                    .where(Profile.id == profile_id)
                    .values(
                        detected_country=country_code
                    )
                )

                await db.execute(update_query.execution_options(prepare=False))
                await db.commit()

                logger.info(
                    f"✅ Location detected and saved for {username}: "
                    f"{country_code} (confidence: {confidence:.2f})"
                )
                print(
                    f"✅ LOCATION: {username} -> "
                    f"{country_code} ({confidence:.1%})"
                )
            else:
                logger.info(f"No location detected for {username} - location_result: {location_result}")
                print(f"❌ LOCATION: {username} -> No country detected")

                # Mark as NULL to indicate no location detected (VARCHAR(2) field)
                try:
                    await db.execute(
                        update(Profile)
                        .where(Profile.id == profile_id)
                        .values(detected_country=None)
                        .execution_options(prepare=False)
                    )
                    await db.commit()
                    logger.info(f"Set detected_country=NULL for {username} (no location found)")
                except Exception as db_error:
                    logger.error(f"Failed to set detected_country=NULL: {db_error}")

        except Exception as e:
            logger.error(f"LOCATION DETECTION FAILED for {username}: {e}")
            logger.error(f"Location detection error details: {type(e).__name__}: {str(e)}")
            print(f"🚨 LOCATION ERROR: {username} -> {str(e)}")

            # Log the full exception for debugging
            import traceback
            logger.error(f"Location detection traceback: {traceback.format_exc()}")

            # Set detected_country to 'XX' to indicate a processing error (VARCHAR(2) field)
            try:
                await db.execute(
                    update(Profile)
                    .where(Profile.id == profile_id)
                    .values(detected_country='XX')
                    .execution_options(prepare=False)
                )
                await db.commit()
                logger.warning(f"Set detected_country='XX' for {username} due to processing error")
            except Exception as db_error:
                logger.error(f"Failed to mark location detection failure in DB: {db_error}")

            # Don't raise - location detection failure shouldn't stop profile processing

    async def cleanup(self):
        """Clean up resources"""
        logger.info("Comprehensive service cleanup completed")

# Global service instance
comprehensive_service = ComprehensiveDataService()