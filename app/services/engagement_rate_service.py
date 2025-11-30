"""
Engagement Rate Service for Instagram Analytics
Handles calculation and management of engagement rates for posts and profiles
"""

import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from app.database.unified_models import Profile, Post

logger = logging.getLogger(__name__)

class EngagementRateService:
    """Service for calculating and managing engagement rates"""
    
    @staticmethod
    def calculate_post_engagement_rate(
        likes_count: int = 0,
        comments_count: int = 0, 
        video_view_count: int = 0,
        is_video: bool = False,
        followers_count: int = 0
    ) -> float:
        """
        Calculate engagement rate for a single post
        
        Args:
            likes_count: Number of likes on the post
            comments_count: Number of comments on the post
            video_view_count: Number of views (for video content)
            is_video: Whether the post is a video
            followers_count: Profile's follower count
            
        Returns:
            Engagement rate as percentage (0.0 - 1000.0)
        """
        if not followers_count or followers_count <= 0:
            return 0.0
            
        # Calculate total interactions based on content type
        if is_video:
            # For videos: include views, likes, and comments
            total_interactions = likes_count + comments_count + video_view_count
        else:
            # For images: only likes and comments (views not meaningful)
            total_interactions = likes_count + comments_count
            
        # Calculate engagement rate as percentage
        engagement_rate = (total_interactions / followers_count) * 100.0
        
        # Cap at reasonable maximum (1000% for viral content)
        return min(round(engagement_rate, 4), 1000.0)
    
    @staticmethod
    def calculate_weighted_engagement_rate(
        likes_count: int = 0,
        comments_count: int = 0,
        video_view_count: int = 0, 
        is_video: bool = False,
        followers_count: int = 0,
        view_weight: float = 0.1,
        like_weight: float = 1.0,
        comment_weight: float = 3.0
    ) -> float:
        """
        Calculate weighted engagement rate giving different weights to interaction types
        
        Args:
            likes_count: Number of likes
            comments_count: Number of comments
            video_view_count: Number of views
            is_video: Whether content is video
            followers_count: Profile's follower count
            view_weight: Weight for views (default 0.1)
            like_weight: Weight for likes (default 1.0)
            comment_weight: Weight for comments (default 3.0)
            
        Returns:
            Weighted engagement rate as percentage
        """
        if not followers_count or followers_count <= 0:
            return 0.0
            
        # Calculate weighted interactions
        if is_video:
            weighted_interactions = (
                (video_view_count * view_weight) +
                (likes_count * like_weight) +
                (comments_count * comment_weight)
            )
        else:
            weighted_interactions = (
                (likes_count * like_weight) +
                (comments_count * comment_weight)
            )
            
        engagement_rate = (weighted_interactions / followers_count) * 100.0
        return min(round(engagement_rate, 4), 1000.0)
    
    @staticmethod
    def enhance_post_data_with_engagement(
        post_data: Dict[str, Any], 
        followers_count: int
    ) -> Dict[str, Any]:
        """
        Enhance post data dictionary with calculated engagement rate
        
        Args:
            post_data: Dictionary containing post data
            followers_count: Profile's follower count
            
        Returns:
            Enhanced post data with engagement_rate field
        """
        engagement_rate = EngagementRateService.calculate_post_engagement_rate(
            likes_count=post_data.get('likes_count', 0),
            comments_count=post_data.get('comments_count', 0),
            video_view_count=post_data.get('video_view_count', 0),
            is_video=post_data.get('is_video', False),
            followers_count=followers_count
        )
        
        post_data['engagement_rate'] = engagement_rate
        logger.debug(f"Calculated engagement rate: {engagement_rate}% for post")
        
        return post_data
    
    @staticmethod
    async def calculate_profile_engagement_rate(
        db: AsyncSession, 
        profile_id: str
    ) -> float:
        """
        Calculate average engagement rate for a profile based on all its posts
        
        Args:
            db: Database session
            profile_id: UUID of the profile
            
        Returns:
            Average engagement rate as percentage
        """
        try:
            # Get average engagement rate across all posts for the profile
            result = await db.execute(
                select(func.avg(Post.engagement_rate), func.count(Post.id))
                .where(Post.profile_id == profile_id)
                .where(Post.engagement_rate.isnot(None))
                .where(Post.engagement_rate > 0)
                .execution_options(prepare=False)
            )
            
            avg_engagement, post_count = result.first()
            
            if not post_count or avg_engagement is None:
                return 0.0
                
            return round(float(avg_engagement), 4)
            
        except Exception as e:
            logger.error(f"Error calculating profile engagement rate: {e}")
            return 0.0
    
    @staticmethod
    async def update_profile_engagement_rate(
        db: AsyncSession,
        profile_id: str
    ) -> bool:
        """
        Update profile's engagement rate based on current posts
        
        Args:
            db: Database session  
            profile_id: UUID of the profile
            
        Returns:
            True if updated successfully
        """
        try:
            # Calculate new engagement rate
            engagement_rate = await EngagementRateService.calculate_profile_engagement_rate(
                db, profile_id
            )
            
            # Update the profile
            await db.execute(
                text("UPDATE profiles SET engagement_rate = :rate, updated_at = now() WHERE id = :id").execution_options(prepare=False),
                {"rate": engagement_rate, "id": profile_id}
            )
            
            await db.commit()
            logger.info(f"Updated profile {profile_id} engagement rate to {engagement_rate}%")
            return True
            
        except Exception as e:
            logger.error(f"Error updating profile engagement rate: {e}")
            await db.rollback()
            return False
    
    @staticmethod
    async def bulk_calculate_engagement_rates(
        db: AsyncSession,
        limit: int = 1000
    ) -> Dict[str, int]:
        """
        Bulk calculate engagement rates for profiles and posts
        
        Args:
            db: Database session
            limit: Maximum number of profiles to process
            
        Returns:
            Dictionary with counts of updated profiles and posts
        """
        try:
            # Disable triggers for bulk operation
            await db.execute(text("SELECT disable_engagement_rate_triggers()"))
            
            # Get profiles to update
            result = await db.execute(
                text("""
                    SELECT id FROM profiles 
                    WHERE engagement_rate IS NULL 
                       OR engagement_rate = 0 
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            
            profile_ids = [row[0] for row in result.fetchall()]
            profiles_updated = 0
            posts_updated = 0
            
            for profile_id in profile_ids:
                # Update posts for this profile
                result = await db.execute(
                    text("SELECT update_profile_posts_engagement_rates(:profile_id)"),
                    {"profile_id": str(profile_id)}
                )
                posts_count = result.scalar()
                posts_updated += posts_count or 0
                
                # Update profile engagement rate
                success = await EngagementRateService.update_profile_engagement_rate(
                    db, str(profile_id)
                )
                if success:
                    profiles_updated += 1
            
            # Re-enable triggers
            await db.execute(text("SELECT enable_engagement_rate_triggers()"))
            await db.commit()
            
            logger.info(f"Bulk update complete: {profiles_updated} profiles, {posts_updated} posts")
            return {"profiles_updated": profiles_updated, "posts_updated": posts_updated}
            
        except Exception as e:
            logger.error(f"Error in bulk engagement rate calculation: {e}")
            await db.rollback()
            # Try to re-enable triggers even on error
            try:
                await db.execute(text("SELECT enable_engagement_rate_triggers()"))
                await db.commit()
            except:
                pass
            return {"profiles_updated": 0, "posts_updated": 0}
    
    @staticmethod
    def get_engagement_category(engagement_rate: float) -> str:
        """
        Categorize engagement rate into performance tiers
        
        Args:
            engagement_rate: Engagement rate percentage
            
        Returns:
            Category string
        """
        if engagement_rate >= 10.0:
            return "Excellent (10%+)"
        elif engagement_rate >= 5.0:
            return "Very Good (5-10%)"
        elif engagement_rate >= 2.0:
            return "Good (2-5%)"
        elif engagement_rate >= 1.0:
            return "Average (1-2%)"
        else:
            return "Below Average (<1%)"
    
    @staticmethod
    async def get_engagement_breakdown(
        db: AsyncSession,
        post_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed engagement breakdown for a post
        
        Args:
            db: Database session
            post_id: UUID of the post
            
        Returns:
            Dictionary with engagement breakdown or None
        """
        try:
            result = await db.execute(
                text("SELECT * FROM get_post_engagement_breakdown(:post_id)"),
                {"post_id": post_id}
            )
            
            row = result.first()
            if not row:
                return None
                
            return {
                "post_id": str(row.post_id),
                "likes_count": row.likes_count,
                "comments_count": row.comments_count,
                "video_view_count": row.video_view_count,
                "is_video": row.is_video,
                "followers_count": row.followers_count,
                "total_interactions": row.total_interactions,
                "engagement_rate": row.engagement_rate,
                "engagement_category": row.engagement_category
            }
            
        except Exception as e:
            logger.error(f"Error getting engagement breakdown: {e}")
            return None