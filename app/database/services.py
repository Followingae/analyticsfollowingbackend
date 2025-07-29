from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import selectinload
import logging

from .models import (
    User, Profile, Post, UserProfileAccess, AudienceDemographics,
    CreatorMetadata, CommentSentiment, Mention, Campaign, CampaignPost
)

logger = logging.getLogger(__name__)

class ProfileService:
    """Service for managing Instagram profiles and their data"""
    
    @staticmethod
    async def create_or_update_profile(db: AsyncSession, username: str, raw_data: Dict[str, Any]) -> Profile:
        """Create or update a profile with complete Decodo data mapping"""
        try:
            # Extract user data from Decodo response
            user_data = ProfileService._extract_user_data(raw_data)
            if not user_data:
                raise ValueError("Invalid Decodo response structure")
            
            # Check if profile exists
            result = await db.execute(select(Profile).where(Profile.username == username))
            profile = result.scalar_one_or_none()
            
            # Map all Decodo datapoints to structured columns
            profile_data = ProfileService._map_decodo_to_profile(user_data, raw_data)
            profile_data['username'] = username  # Ensure username is set
            profile_data['raw_data'] = raw_data  # Keep raw data backup
            profile_data['last_refreshed'] = func.now()
            
            if profile:
                # Update existing profile with all new data
                for key, value in profile_data.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                logger.info(f"Updated profile for {username} with {len(profile_data)} fields")
            else:
                # Create new profile
                profile = Profile(**profile_data)
                db.add(profile)
                logger.info(f"Created new profile for {username} with {len(profile_data)} fields")
            
            await db.commit()
            await db.refresh(profile)
            
            # Also extract and store related profiles
            await ProfileService._store_related_profiles(db, profile.id, user_data)
            
            return profile
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating/updating profile {username}: {str(e)}")
            raise
    
    @staticmethod
    def _extract_user_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user data from Decodo response structure"""
        try:
            results = raw_data.get('results', [])
            if not results:
                return {}
            
            content = results[0].get('content', {})
            data = content.get('data', {})
            user_data = data.get('user', {})
            
            return user_data
        except (KeyError, IndexError, TypeError):
            return {}
    
    @staticmethod
    def _map_decodo_to_profile(user_data: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map all 69 Decodo datapoints to Profile model fields"""
        def safe_get(data, path, default=None):
            """Safely extract nested data"""
            try:
                result = data
                for key in path.split('.'):
                    result = result[key]
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        # Calculate data quality score
        total_fields = 69  # Based on our mapping
        populated_fields = 0
        
        profile_data = {}
        
        # Core Profile Information
        profile_data['full_name'] = safe_get(user_data, 'full_name', '')
        profile_data['biography'] = safe_get(user_data, 'biography', '')
        profile_data['instagram_user_id'] = safe_get(user_data, 'id', '')
        profile_data['fb_id'] = safe_get(user_data, 'fbid', '')
        profile_data['eimu_id'] = safe_get(user_data, 'eimu_id', '')
        
        # Follow Statistics
        edge_followed_by = safe_get(user_data, 'edge_followed_by', {})
        edge_follow = safe_get(user_data, 'edge_follow', {})
        edge_media = safe_get(user_data, 'edge_owner_to_timeline_media', {})
        edge_mutual = safe_get(user_data, 'edge_mutual_followed_by', {})
        
        profile_data['followers_count'] = safe_get(edge_followed_by, 'count', 0)
        profile_data['following_count'] = safe_get(edge_follow, 'count', 0)
        profile_data['posts_count'] = safe_get(edge_media, 'count', 0)
        profile_data['mutual_followers_count'] = safe_get(edge_mutual, 'count', 0)
        
        # Account Settings & Status
        profile_data['is_verified'] = safe_get(user_data, 'is_verified', False)
        profile_data['is_private'] = safe_get(user_data, 'is_private', False)
        profile_data['is_business_account'] = safe_get(user_data, 'is_business_account', False)
        profile_data['is_professional_account'] = safe_get(user_data, 'is_professional_account', False)
        profile_data['country_block'] = safe_get(user_data, 'country_block', False)
        profile_data['is_embeds_disabled'] = safe_get(user_data, 'is_embeds_disabled', False)
        profile_data['is_joined_recently'] = safe_get(user_data, 'is_joined_recently', False)
        
        # Profile Media & Links
        profile_data['profile_pic_url'] = safe_get(user_data, 'profile_pic_url', '')
        profile_data['profile_pic_url_hd'] = safe_get(user_data, 'profile_pic_url_hd', '')
        profile_data['external_url'] = safe_get(user_data, 'external_url', '')
        profile_data['external_url_shimmed'] = safe_get(user_data, 'external_url_linkshimmed', '')
        
        # Business Information
        profile_data['business_category_name'] = safe_get(user_data, 'business_category_name', '')
        profile_data['overall_category_name'] = safe_get(user_data, 'overall_category_name', '')
        profile_data['category_enum'] = safe_get(user_data, 'category_enum', '')
        profile_data['business_address_json'] = safe_get(user_data, 'business_address_json', '')
        profile_data['business_contact_method'] = safe_get(user_data, 'business_contact_method', '')
        profile_data['business_email'] = safe_get(user_data, 'business_email', '')
        profile_data['business_phone_number'] = safe_get(user_data, 'business_phone_number', '')
        
        # Content & Features
        profile_data['has_ar_effects'] = safe_get(user_data, 'has_ar_effects', False)
        profile_data['has_clips'] = safe_get(user_data, 'has_clips', False)
        profile_data['has_guides'] = safe_get(user_data, 'has_guides', False)
        profile_data['has_channel'] = safe_get(user_data, 'has_channel', False)
        profile_data['highlight_reel_count'] = safe_get(user_data, 'highlight_reel_count', 0)
        profile_data['pinned_channels_list_count'] = safe_get(user_data, 'pinned_channels_list_count', 0)
        
        # Privacy & Restrictions
        profile_data['blocked_by_viewer'] = safe_get(user_data, 'blocked_by_viewer')
        profile_data['has_blocked_viewer'] = safe_get(user_data, 'has_blocked_viewer')
        profile_data['restricted_by_viewer'] = safe_get(user_data, 'restricted_by_viewer')
        profile_data['followed_by_viewer'] = safe_get(user_data, 'followed_by_viewer')
        profile_data['follows_viewer'] = safe_get(user_data, 'follows_viewer')
        profile_data['requested_by_viewer'] = safe_get(user_data, 'requested_by_viewer')
        profile_data['has_requested_viewer'] = safe_get(user_data, 'has_requested_viewer')
        
        # Account Features & Settings
        profile_data['hide_like_and_view_counts'] = safe_get(user_data, 'hide_like_and_view_counts', False)
        profile_data['should_show_category'] = safe_get(user_data, 'should_show_category', True)
        profile_data['should_show_public_contacts'] = safe_get(user_data, 'should_show_public_contacts', True)
        profile_data['show_account_transparency_details'] = safe_get(user_data, 'show_account_transparency_details', True)
        profile_data['show_text_post_app_badge'] = safe_get(user_data, 'show_text_post_app_badge', False)
        profile_data['has_onboarded_to_text_post_app'] = safe_get(user_data, 'has_onboarded_to_text_post_app', False)
        profile_data['remove_message_entrypoint'] = safe_get(user_data, 'remove_message_entrypoint', False)
        
        # AI & Special Features
        profile_data['ai_agent_type'] = safe_get(user_data, 'ai_agent_type', '')
        profile_data['ai_agent_owner_username'] = safe_get(user_data, 'ai_agent_owner_username', '')
        profile_data['transparency_label'] = safe_get(user_data, 'transparency_label', '')
        profile_data['transparency_product'] = safe_get(user_data, 'transparency_product', '')
        
        # Supervision & Safety
        profile_data['is_supervision_enabled'] = safe_get(user_data, 'is_supervision_enabled', False)
        profile_data['is_guardian_of_viewer'] = safe_get(user_data, 'is_guardian_of_viewer', False)
        profile_data['is_supervised_by_viewer'] = safe_get(user_data, 'is_supervised_by_viewer', False)
        profile_data['is_supervised_user'] = safe_get(user_data, 'is_supervised_user', False)
        profile_data['guardian_id'] = safe_get(user_data, 'guardian_id', '')
        profile_data['is_regulated_c18'] = safe_get(user_data, 'is_regulated_c18', False)
        profile_data['is_verified_by_mv4b'] = safe_get(user_data, 'is_verified_by_mv4b', False)
        
        # Structured Data (keep as JSONB)
        profile_data['biography_with_entities'] = safe_get(user_data, 'biography_with_entities', {})
        profile_data['bio_links'] = safe_get(user_data, 'bio_links', [])
        profile_data['pronouns'] = safe_get(user_data, 'pronouns', [])
        
        # Count populated fields for data quality score
        for key, value in profile_data.items():
            if value not in [None, '', [], {}]:
                populated_fields += 1
        
        profile_data['data_quality_score'] = int((populated_fields / total_fields) * 100)
        
        logger.info(f"Mapped {populated_fields}/{total_fields} fields ({profile_data['data_quality_score']}% quality)")
        
        return profile_data
    
    @staticmethod
    async def _store_related_profiles(db: AsyncSession, profile_id: UUID, user_data: Dict[str, Any]):
        """Store related profiles data"""
        try:
            from .models import RelatedProfile
            
            # Delete existing related profiles
            await db.execute(delete(RelatedProfile).where(RelatedProfile.profile_id == profile_id))
            
            # Extract related profiles
            edge_related = user_data.get('edge_related_profiles', {})
            related_edges = edge_related.get('edges', [])
            
            for i, edge in enumerate(related_edges[:10]):  # Limit to 10 related profiles
                node = edge.get('node', {})
                if not node.get('username'):
                    continue
                
                related_profile = RelatedProfile(
                    profile_id=profile_id,
                    related_username=node.get('username', ''),
                    related_full_name=node.get('full_name', ''),
                    related_is_verified=node.get('is_verified', False),
                    related_is_private=node.get('is_private', False),
                    related_profile_pic_url=node.get('profile_pic_url', ''),
                    similarity_score=100 - (i * 10)  # Higher score for earlier positions
                )
                db.add(related_profile)
            
            await db.commit()
            logger.info(f"Stored {len(related_edges)} related profiles")
            
        except Exception as e:
            logger.error(f"Error storing related profiles: {str(e)}")
    
    @staticmethod
    async def get_profile_by_username(db: AsyncSession, username: str) -> Optional[Profile]:
        """Get profile by username"""
        result = await db.execute(
            select(Profile)
            .where(Profile.username == username)
            .options(selectinload(Profile.posts))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_profile_with_posts(db: AsyncSession, profile_id: UUID, limit: int = 20) -> Optional[Profile]:
        """Get profile with recent posts"""
        result = await db.execute(
            select(Profile)
            .where(Profile.id == profile_id)
            .options(selectinload(Profile.posts))
        )
        profile = result.scalar_one_or_none()
        
        if profile and profile.posts:
            # Sort posts by most recent (if timestamp available in raw_data)
            profile.posts = profile.posts[:limit]
        
        return profile
    
    @staticmethod
    async def is_profile_fresh(db: AsyncSession, username: str, max_age_hours: int = 24) -> bool:
        """Check if profile data is fresh (within max_age_hours)"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        result = await db.execute(
            select(Profile.last_refreshed)
            .where(
                and_(
                    Profile.username == username,
                    Profile.last_refreshed > cutoff_time
                )
            )
        )
        return result.scalar_one_or_none() is not None

class PostService:
    """Service for managing Instagram posts"""
    
    @staticmethod
    async def create_posts_from_decodo(db: AsyncSession, profile_id: UUID, posts_data: List[Dict[str, Any]]) -> List[Post]:
        """Create posts from Decodo timeline data"""
        try:
            posts = []
            
            for post_data in posts_data:
                # Extract post ID from raw data to avoid duplicates
                post_shortcode = post_data.get('shortcode')
                if not post_shortcode:
                    continue
                
                # Check if post already exists
                result = await db.execute(
                    select(Post).where(
                        and_(
                            Post.profile_id == profile_id,
                            Post.raw_data['shortcode'].astext == post_shortcode
                        )
                    )
                )
                existing_post = result.scalar_one_or_none()
                
                if not existing_post:
                    post = Post(
                        profile_id=profile_id,
                        raw_data=post_data
                    )
                    db.add(post)
                    posts.append(post)
            
            await db.commit()
            logger.info(f"Created {len(posts)} new posts for profile {profile_id}")
            return posts
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating posts for profile {profile_id}: {str(e)}")
            raise
    
    @staticmethod
    async def get_posts_by_profile(db: AsyncSession, profile_id: UUID, limit: int = 50) -> List[Post]:
        """Get posts for a profile"""
        result = await db.execute(
            select(Post)
            .where(Post.profile_id == profile_id)
            .limit(limit)
        )
        return result.scalars().all()

class UserService:
    """Service for managing users and their access"""
    
    @staticmethod
    async def create_user(db: AsyncSession, email: str, hashed_password: str, role: str = "user") -> User:
        """Create a new user"""
        try:
            user = User(
                email=email,
                hashed_password=hashed_password,
                role=role
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created new user: {email}")
            return user
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating user {email}: {str(e)}")
            raise
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user_credits(db: AsyncSession, user_id: UUID, credits: int) -> bool:
        """Update user credits"""
        try:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(credits=credits)
            )
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating credits for user {user_id}: {str(e)}")
            return False

class AccessService:
    """Service for managing user profile access (30-day unlock system)"""
    
    @staticmethod
    async def grant_profile_access(db: AsyncSession, user_id: UUID, profile_id: UUID) -> UserProfileAccess:
        """Grant user access to a profile"""
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
            
            if access:
                # Update last accessed time
                access.last_accessed = func.now()
            else:
                # Create new access record
                access = UserProfileAccess(
                    user_id=user_id,
                    profile_id=profile_id
                )
                db.add(access)
            
            await db.commit()
            await db.refresh(access)
            return access
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error granting access to profile {profile_id} for user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    async def check_profile_access(db: AsyncSession, user_id: UUID, profile_id: UUID, days_valid: int = 30) -> bool:
        """Check if user has valid access to a profile"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_valid)
        
        result = await db.execute(
            select(UserProfileAccess).where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.profile_id == profile_id,
                    UserProfileAccess.last_accessed > cutoff_date
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    @staticmethod
    async def get_user_accessible_profiles(db: AsyncSession, user_id: UUID, days_valid: int = 30) -> List[Profile]:
        """Get all profiles accessible to a user"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_valid)
        
        result = await db.execute(
            select(Profile)
            .join(UserProfileAccess)
            .where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.last_accessed > cutoff_date
                )
            )
        )
        return result.scalars().all()

class CampaignService:
    """Service for managing campaigns"""
    
    @staticmethod
    async def create_campaign(db: AsyncSession, user_id: UUID, name: str, logo_url: Optional[str] = None,
                            start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Campaign:
        """Create a new campaign"""
        try:
            campaign = Campaign(
                user_id=user_id,
                name=name,
                logo_url=logo_url,
                start_date=start_date,
                end_date=end_date
            )
            db.add(campaign)
            await db.commit()
            await db.refresh(campaign)
            logger.info(f"Created campaign '{name}' for user {user_id}")
            return campaign
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating campaign '{name}' for user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    async def add_post_to_campaign(db: AsyncSession, campaign_id: UUID, post_id: UUID) -> CampaignPost:
        """Add a post to a campaign"""
        try:
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                post_id=post_id
            )
            db.add(campaign_post)
            await db.commit()
            await db.refresh(campaign_post)
            return campaign_post
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error adding post {post_id} to campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    async def get_user_campaigns(db: AsyncSession, user_id: UUID) -> List[Campaign]:
        """Get all campaigns for a user"""
        result = await db.execute(
            select(Campaign)
            .where(Campaign.user_id == user_id)
            .options(selectinload(Campaign.campaign_posts))
        )
        return result.scalars().all()

class AnalyticsService:
    """Service for managing analytics data (AI/ML features)"""
    
    @staticmethod
    async def store_audience_demographics(db: AsyncSession, profile_id: UUID, 
                                        gender_dist: Dict, age_dist: Dict, location_dist: Dict) -> AudienceDemographics:
        """Store audience demographics analysis"""
        try:
            # Check if demographics already exist
            result = await db.execute(
                select(AudienceDemographics).where(AudienceDemographics.profile_id == profile_id)
            )
            demographics = result.scalar_one_or_none()
            
            if demographics:
                # Update existing
                demographics.gender_dist = gender_dist
                demographics.age_dist = age_dist
                demographics.location_dist = location_dist
                demographics.last_sampled = func.now()
            else:
                # Create new
                demographics = AudienceDemographics(
                    profile_id=profile_id,
                    gender_dist=gender_dist,
                    age_dist=age_dist,
                    location_dist=location_dist
                )
                db.add(demographics)
            
            await db.commit()
            await db.refresh(demographics)
            return demographics
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error storing demographics for profile {profile_id}: {str(e)}")
            raise
    
    @staticmethod
    async def store_creator_metadata(db: AsyncSession, profile_id: UUID, 
                                   extracted_location: Optional[str], categories: List[str]) -> CreatorMetadata:
        """Store creator metadata analysis"""
        try:
            # Check if metadata already exists
            result = await db.execute(
                select(CreatorMetadata).where(CreatorMetadata.profile_id == profile_id)
            )
            metadata = result.scalar_one_or_none()
            
            if metadata:
                # Update existing
                metadata.extracted_location = extracted_location
                metadata.categories = categories
                metadata.last_updated = func.now()
            else:
                # Create new
                metadata = CreatorMetadata(
                    profile_id=profile_id,
                    extracted_location=extracted_location,
                    categories=categories
                )
                db.add(metadata)
            
            await db.commit()
            await db.refresh(metadata)
            return metadata
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error storing metadata for profile {profile_id}: {str(e)}")
            raise