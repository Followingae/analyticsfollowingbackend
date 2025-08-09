"""
Comprehensive Engagement Rate Calculator Service
Handles both profile-level and post-level engagement calculations
Removes the need for frontend calculations
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.database.unified_models import Profile, Post

logger = logging.getLogger(__name__)

class EngagementCalculatorService:
    """Service to calculate engagement rates for profiles and posts"""
    
    @staticmethod
    def calculate_post_engagement_rate(
        likes_count: int,
        comments_count: int, 
        profile_followers: int
    ) -> float:
        """
        Calculate engagement rate for a single post
        Formula: ((likes + comments) / followers) * 100
        """
        if profile_followers <= 0:
            return 0.0
        
        total_engagement = likes_count + comments_count
        engagement_rate = (total_engagement / profile_followers) * 100
        
        # Round to 2 decimal places
        return round(engagement_rate, 2)
    
    @staticmethod
    def calculate_profile_engagement_rate(
        posts_data: List[Dict[str, Any]],
        profile_followers: int,
        days_to_analyze: int = 30
    ) -> Dict[str, float]:
        """
        Calculate comprehensive profile engagement metrics
        
        Args:
            posts_data: List of post dictionaries with likes_count, comments_count, taken_at_timestamp
            profile_followers: Current follower count
            days_to_analyze: Number of recent days to analyze (default: 30)
        
        Returns:
            Dict with engagement metrics
        """
        if not posts_data or profile_followers <= 0:
            return {
                'overall_engagement_rate': 0.0,
                'avg_likes': 0.0,
                'avg_comments': 0.0,
                'avg_total_engagement': 0.0,
                'posts_analyzed': 0,
                'engagement_rate_last_12_posts': 0.0,
                'engagement_rate_last_30_days': 0.0
            }
        
        # Filter posts by date if needed
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_analyze)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        # All posts for overall calculation
        total_likes = sum(post.get('likes_count', 0) for post in posts_data)
        total_comments = sum(post.get('comments_count', 0) for post in posts_data)
        posts_count = len(posts_data)
        
        # Last 12 posts (Instagram's typical engagement calculation)
        last_12_posts = sorted(posts_data, 
                              key=lambda x: x.get('taken_at_timestamp', 0), 
                              reverse=True)[:12]
        
        last_12_likes = sum(post.get('likes_count', 0) for post in last_12_posts)
        last_12_comments = sum(post.get('comments_count', 0) for post in last_12_posts)
        last_12_count = len(last_12_posts)
        
        # Last 30 days posts
        recent_posts = [
            post for post in posts_data 
            if post.get('taken_at_timestamp', 0) >= cutoff_timestamp
        ]
        
        recent_likes = sum(post.get('likes_count', 0) for post in recent_posts)
        recent_comments = sum(post.get('comments_count', 0) for post in recent_posts)
        recent_count = len(recent_posts)
        
        # Calculate metrics
        avg_likes = total_likes / posts_count if posts_count > 0 else 0
        avg_comments = total_comments / posts_count if posts_count > 0 else 0
        avg_total_engagement = avg_likes + avg_comments
        
        # Overall engagement rate
        overall_engagement_rate = (avg_total_engagement / profile_followers) * 100
        
        # Last 12 posts engagement rate
        avg_engagement_last_12 = (last_12_likes + last_12_comments) / last_12_count if last_12_count > 0 else 0
        engagement_rate_last_12 = (avg_engagement_last_12 / profile_followers) * 100
        
        # Last 30 days engagement rate
        avg_engagement_recent = (recent_likes + recent_comments) / recent_count if recent_count > 0 else 0
        engagement_rate_last_30_days = (avg_engagement_recent / profile_followers) * 100
        
        return {
            'overall_engagement_rate': round(overall_engagement_rate, 2),
            'avg_likes': round(avg_likes, 1),
            'avg_comments': round(avg_comments, 1),
            'avg_total_engagement': round(avg_total_engagement, 1),
            'posts_analyzed': posts_count,
            'engagement_rate_last_12_posts': round(engagement_rate_last_12, 2),
            'engagement_rate_last_30_days': round(engagement_rate_last_30_days, 2),
            'recent_posts_count': recent_count
        }
    
    async def calculate_and_update_profile_engagement(
        self, 
        db: AsyncSession, 
        profile_id: str
    ) -> Dict[str, float]:
        """
        Calculate engagement rate for a profile and update the database
        
        Args:
            db: Database session
            profile_id: Profile UUID
            
        Returns:
            Engagement metrics dictionary
        """
        try:
            # Get profile data
            profile_result = await db.execute(
                select(Profile).where(Profile.id == profile_id)
            )
            profile = profile_result.scalar_one_or_none()
            
            if not profile:
                logger.warning(f"Profile not found: {profile_id}")
                return {'error': 'Profile not found'}
            
            # Get posts data
            posts_result = await db.execute(
                select(Post.likes_count, Post.comments_count, Post.taken_at_timestamp)
                .where(Post.profile_id == profile_id)
                .order_by(Post.taken_at_timestamp.desc())
                .limit(50)  # Analyze last 50 posts maximum
            )
            
            posts_data = [
                {
                    'likes_count': row.likes_count or 0,
                    'comments_count': row.comments_count or 0,
                    'taken_at_timestamp': row.taken_at_timestamp or 0
                }
                for row in posts_result.fetchall()
            ]
            
            # Calculate engagement metrics
            engagement_metrics = self.calculate_profile_engagement_rate(
                posts_data=posts_data,
                profile_followers=profile.followers_count or 0
            )
            
            # Update profile with calculated engagement rate
            profile.engagement_rate = engagement_metrics['overall_engagement_rate']
            
            # Commit the update
            await db.commit()
            
            logger.info(f"Updated engagement rate for {profile.username}: {profile.engagement_rate}%")
            
            return engagement_metrics
            
        except Exception as e:
            logger.error(f"Error calculating profile engagement: {e}")
            await db.rollback()
            return {'error': str(e)}
    
    async def calculate_and_update_post_engagement(
        self, 
        db: AsyncSession, 
        post_id: str
    ) -> float:
        """
        Calculate engagement rate for a single post and update the database
        
        Args:
            db: Database session
            post_id: Post UUID
            
        Returns:
            Engagement rate for the post
        """
        try:
            # Get post and profile data
            result = await db.execute(
                select(Post, Profile.followers_count)
                .join(Profile, Post.profile_id == Profile.id)
                .where(Post.id == post_id)
            )
            
            row = result.first()
            if not row:
                logger.warning(f"Post not found: {post_id}")
                return 0.0
            
            post, profile_followers = row
            
            # Calculate post engagement rate
            engagement_rate = self.calculate_post_engagement_rate(
                likes_count=post.likes_count or 0,
                comments_count=post.comments_count or 0,
                profile_followers=profile_followers or 0
            )
            
            # Update post with calculated engagement rate
            post.engagement_rate = engagement_rate
            
            await db.commit()
            
            logger.info(f"Updated post engagement rate: {engagement_rate}%")
            
            return engagement_rate
            
        except Exception as e:
            logger.error(f"Error calculating post engagement: {e}")
            await db.rollback()
            return 0.0
    
    async def bulk_update_profile_engagement_rates(
        self, 
        db: AsyncSession, 
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Bulk update engagement rates for profiles that need recalculation
        
        Args:
            db: Database session  
            limit: Maximum number of profiles to update
            
        Returns:
            Summary of updates performed
        """
        try:
            # Get profiles that need engagement rate updates (those with 0.0 or null engagement rates)
            profiles_result = await db.execute(
                select(Profile.id, Profile.username, Profile.followers_count, Profile.engagement_rate)
                .where(
                    and_(
                        Profile.followers_count > 0,
                        func.coalesce(Profile.engagement_rate, 0) == 0
                    )
                )
                .limit(limit)
            )
            
            profiles = profiles_result.fetchall()
            
            updated_count = 0
            failed_count = 0
            results = []
            
            for profile_row in profiles:
                try:
                    profile_id = str(profile_row.id)
                    username = profile_row.username
                    
                    # Calculate engagement for this profile
                    engagement_metrics = await self.calculate_and_update_profile_engagement(
                        db, profile_id
                    )
                    
                    if 'error' not in engagement_metrics:
                        updated_count += 1
                        results.append({
                            'username': username,
                            'engagement_rate': engagement_metrics['overall_engagement_rate'],
                            'posts_analyzed': engagement_metrics['posts_analyzed']
                        })
                        logger.info(f"✓ Updated {username}: {engagement_metrics['overall_engagement_rate']}%")
                    else:
                        failed_count += 1
                        logger.error(f"✗ Failed to update {username}: {engagement_metrics['error']}")
                        
                except Exception as profile_error:
                    failed_count += 1
                    logger.error(f"✗ Error processing profile {profile_row.username}: {profile_error}")
            
            return {
                'total_profiles_processed': len(profiles),
                'successfully_updated': updated_count,
                'failed_updates': failed_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in bulk engagement update: {e}")
            return {
                'error': str(e),
                'total_profiles_processed': 0,
                'successfully_updated': 0,
                'failed_updates': 0
            }
    
    @staticmethod
    def calculate_influence_score(
        followers_count: int,
        following_count: int,
        engagement_rate: float,
        is_verified: bool = False,
        is_business: bool = False,
        posts_count: int = 0
    ) -> float:
        """
        Calculate influence score based on multiple factors
        Score range: 0-10
        """
        score = 0.0
        
        # Follower count impact (0-3 points)
        if followers_count >= 10_000_000:  # 10M+
            score += 3.0
        elif followers_count >= 1_000_000:  # 1M+
            score += 2.5
        elif followers_count >= 100_000:   # 100K+
            score += 2.0
        elif followers_count >= 10_000:    # 10K+
            score += 1.5
        elif followers_count >= 1_000:     # 1K+
            score += 1.0
        else:
            score += 0.5
        
        # Follower-to-following ratio (0-2 points)
        if following_count > 0:
            ratio = followers_count / following_count
            if ratio >= 100:
                score += 2.0
            elif ratio >= 10:
                score += 1.5
            elif ratio >= 5:
                score += 1.0
            else:
                score += 0.5
        
        # Engagement rate impact (0-3 points)
        if engagement_rate >= 10.0:
            score += 3.0
        elif engagement_rate >= 5.0:
            score += 2.5
        elif engagement_rate >= 3.0:
            score += 2.0
        elif engagement_rate >= 1.0:
            score += 1.5
        elif engagement_rate >= 0.5:
            score += 1.0
        else:
            score += 0.5
        
        # Verification bonus (0-1.5 points)
        if is_verified:
            score += 1.5
        
        # Business account bonus (0-0.5 points)
        if is_business:
            score += 0.5
        
        # Posts count factor (0-0.5 points)
        if posts_count >= 1000:
            score += 0.5
        elif posts_count >= 500:
            score += 0.3
        elif posts_count >= 100:
            score += 0.2
        
        # Cap at 10.0
        return min(round(score, 1), 10.0)

# Global service instance
engagement_calculator = EngagementCalculatorService()