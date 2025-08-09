"""
AI Data Refresh Service
Handles detection and refreshing of incomplete/missing AI analysis data
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload

from app.database.connection import SessionLocal
from app.database.unified_models import Profile, Post
from app.services.ai.content_intelligence_service import ContentIntelligenceService

logger = logging.getLogger(__name__)


class AIDataRefreshService:
    """Service for detecting and refreshing incomplete AI analysis data"""
    
    def __init__(self):
        self.ai_service = ContentIntelligenceService()
        
    async def check_profile_ai_completeness(self, profile: Profile) -> Dict[str, bool]:
        """Check if profile has complete AI analysis data"""
        return {
            'profile_ai_complete': all([
                profile.ai_primary_content_type is not None,
                profile.ai_content_distribution is not None,
                profile.ai_avg_sentiment_score is not None,
                profile.ai_language_distribution is not None,
                profile.ai_profile_analyzed_at is not None
            ]),
            'profile_ai_missing': (
                profile.ai_profile_analyzed_at is None or
                profile.ai_primary_content_type is None or
                profile.ai_content_distribution is None
            )
        }
    
    async def check_post_ai_completeness(self, post: Post) -> Dict[str, bool]:
        """Check if post has complete AI analysis data"""
        return {
            'post_ai_complete': all([
                post.ai_content_category is not None,
                post.ai_sentiment is not None,
                post.ai_language_code is not None,
                post.ai_analyzed_at is not None
            ]),
            'post_ai_missing': (
                post.ai_analyzed_at is None or
                post.ai_content_category is None or
                post.ai_sentiment is None
            )
        }
    
    async def find_profiles_needing_ai_refresh(self, limit: int = 50) -> List[Profile]:
        """Find profiles that need AI data refresh (missing data only)"""
        async with SessionLocal() as db:
            # Find profiles with incomplete AI data only (no staleness check)
            query = select(Profile).where(
                or_(
                    # Missing core AI data
                    Profile.ai_primary_content_type.is_(None),
                    Profile.ai_profile_analyzed_at.is_(None),
                    # Missing critical fields
                    Profile.ai_content_distribution.is_(None),
                    Profile.ai_avg_sentiment_score.is_(None)
                )
            ).limit(limit).order_by(Profile.updated_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def find_posts_needing_ai_refresh(self, profile_id: Optional[str] = None, limit: int = 100) -> List[Post]:
        """Find posts that need AI data refresh (missing data only)"""
        async with SessionLocal() as db:
            query = select(Post).where(
                or_(
                    # Missing core AI data
                    Post.ai_content_category.is_(None),
                    Post.ai_sentiment.is_(None),
                    Post.ai_language_code.is_(None),
                    Post.ai_analyzed_at.is_(None)
                )
            )
            
            if profile_id:
                query = query.where(Post.profile_id == profile_id)
            
            query = query.limit(limit).order_by(Post.created_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def refresh_profile_ai_data(self, profile: Profile) -> bool:
        """Refresh AI data for a specific profile"""
        try:
            logger.info(f"AI_REFRESH: Starting AI refresh for profile {profile.username}")
            
            # Get profile's posts that need analysis
            posts_needing_refresh = await self.find_posts_needing_ai_refresh(
                profile_id=str(profile.id), 
                limit=50  # Analyze up to 50 recent posts
            )
            
            if not posts_needing_refresh:
                logger.info(f"AI_REFRESH: No posts need refresh for profile {profile.username}")
                return True
            
            # Refresh post-level AI data
            refreshed_posts = 0
            for post in posts_needing_refresh:
                try:
                    success = await self._refresh_post_ai_data(post)
                    if success:
                        refreshed_posts += 1
                except Exception as e:
                    logger.error(f"AI_REFRESH: Failed to refresh post {post.id}: {e}")
                    continue
            
            logger.info(f"AI_REFRESH: Refreshed {refreshed_posts}/{len(posts_needing_refresh)} posts for {profile.username}")
            
            # Re-aggregate profile-level AI insights
            await self._refresh_profile_level_ai_data(profile)
            
            logger.info(f"AI_REFRESH: Successfully refreshed AI data for profile {profile.username}")
            return True
            
        except Exception as e:
            logger.error(f"AI_REFRESH: Failed to refresh profile {profile.username}: {e}")
            return False
    
    async def _refresh_post_ai_data(self, post: Post) -> bool:
        """Refresh AI data for a single post"""
        try:
            # Analyze post content using AI service
            analysis_result = await self.ai_service.analyze_post_content(
                post_text=post.caption or "",
                post_id=str(post.id)
            )
            
            if not analysis_result or not analysis_result.get("success"):
                logger.warning(f"AI_REFRESH: Analysis failed for post {post.id}")
                return False
            
            # Update post with AI data
            async with SessionLocal() as db:
                # Refresh the post object
                await db.refresh(post)
                
                analysis = analysis_result.get("analysis", {})
                
                # Update AI fields
                post.ai_content_category = analysis.get("ai_content_category")
                post.ai_category_confidence = analysis.get("ai_category_confidence", 0.0)
                post.ai_sentiment = analysis.get("ai_sentiment")
                post.ai_sentiment_score = analysis.get("ai_sentiment_score", 0.0)
                post.ai_sentiment_confidence = analysis.get("ai_sentiment_confidence", 0.0)
                post.ai_language_code = analysis.get("ai_language_code")
                post.ai_language_confidence = analysis.get("ai_language_confidence", 0.0)
                post.ai_analysis_raw = analysis
                post.ai_analyzed_at = datetime.now()
                post.ai_analysis_version = "1.0.0"
                
                await db.commit()
                logger.debug(f"AI_REFRESH: Successfully refreshed post {post.id}")
                return True
                
        except Exception as e:
            logger.error(f"AI_REFRESH: Error refreshing post {post.id}: {e}")
            return False
    
    async def _refresh_profile_level_ai_data(self, profile: Profile) -> bool:
        """Re-aggregate profile-level AI insights from posts"""
        try:
            async with SessionLocal() as db:
                # Get all analyzed posts for this profile
                query = select(Post).where(
                    and_(
                        Post.profile_id == profile.id,
                        Post.ai_analyzed_at.isnot(None),
                        Post.ai_content_category.isnot(None)
                    )
                ).order_by(Post.created_at.desc()).limit(100)  # Use recent 100 posts
                
                result = await db.execute(query)
                analyzed_posts = result.scalars().all()
                
                if not analyzed_posts:
                    logger.warning(f"AI_REFRESH: No analyzed posts found for profile {profile.username}")
                    return False
                
                # Aggregate insights
                category_counts = {}
                language_counts = {}
                sentiment_scores = []
                
                for post in analyzed_posts:
                    # Category distribution
                    if post.ai_content_category:
                        category_counts[post.ai_content_category] = category_counts.get(post.ai_content_category, 0) + 1
                    
                    # Language distribution
                    if post.ai_language_code:
                        language_counts[post.ai_language_code] = language_counts.get(post.ai_language_code, 0) + 1
                    
                    # Sentiment scores
                    if post.ai_sentiment_score is not None:
                        sentiment_scores.append(post.ai_sentiment_score)
                
                # Calculate distributions as percentages
                total_posts = len(analyzed_posts)
                content_distribution = {cat: count/total_posts for cat, count in category_counts.items()}
                language_distribution = {lang: count/total_posts for lang, count in language_counts.items()}
                
                # Calculate average sentiment
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
                
                # Determine primary content type
                primary_content_type = max(category_counts, key=category_counts.get) if category_counts else None
                
                # Calculate quality score (placeholder - can be enhanced)
                quality_score = min(1.0, len(analyzed_posts) / 20)  # More posts = higher quality score
                
                # Update profile with aggregated data
                await db.refresh(profile)
                profile.ai_primary_content_type = primary_content_type
                profile.ai_content_distribution = content_distribution
                profile.ai_avg_sentiment_score = avg_sentiment
                profile.ai_language_distribution = language_distribution
                profile.ai_content_quality_score = quality_score
                profile.ai_profile_analyzed_at = datetime.now()
                
                await db.commit()
                
                logger.info(f"AI_REFRESH: Profile-level AI data updated for {profile.username}")
                logger.info(f"  - Primary content: {primary_content_type}")
                logger.info(f"  - Avg sentiment: {avg_sentiment:.2f}")
                logger.info(f"  - Categories: {list(category_counts.keys())}")
                
                return True
                
        except Exception as e:
            logger.error(f"AI_REFRESH: Error aggregating profile data for {profile.username}: {e}")
            return False
    
    async def get_ai_refresh_statistics(self) -> Dict[str, int]:
        """Get statistics on AI data completeness (missing data only)"""
        async with SessionLocal() as db:
            # Count profiles with missing AI data
            profiles_missing_ai = await db.execute(
                select(func.count(Profile.id)).where(
                    or_(
                        Profile.ai_primary_content_type.is_(None),
                        Profile.ai_profile_analyzed_at.is_(None),
                        Profile.ai_content_distribution.is_(None)
                    )
                )
            )
            
            # Count posts with missing AI data
            posts_missing_ai = await db.execute(
                select(func.count(Post.id)).where(
                    or_(
                        Post.ai_content_category.is_(None),
                        Post.ai_analyzed_at.is_(None),
                        Post.ai_sentiment.is_(None)
                    )
                )
            )
            
            # Count total profiles and posts
            total_profiles = await db.execute(select(func.count(Profile.id)))
            total_posts = await db.execute(select(func.count(Post.id)))
            
            return {
                'profiles_missing_ai': profiles_missing_ai.scalar(),
                'posts_missing_ai': posts_missing_ai.scalar(),
                'total_profiles': total_profiles.scalar(),
                'total_posts': total_posts.scalar()
            }
    
    async def run_batch_ai_refresh(self, batch_size: int = 10) -> Dict[str, int]:
        """Run batch AI refresh for profiles needing it"""
        logger.info(f"AI_REFRESH: Starting batch refresh (batch_size={batch_size})")
        
        profiles_to_refresh = await self.find_profiles_needing_ai_refresh(limit=batch_size)
        
        results = {
            'attempted': len(profiles_to_refresh),
            'successful': 0,
            'failed': 0
        }
        
        for profile in profiles_to_refresh:
            try:
                success = await self.refresh_profile_ai_data(profile)
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"AI_REFRESH: Batch refresh failed for {profile.username}: {e}")
                results['failed'] += 1
        
        logger.info(f"AI_REFRESH: Batch complete - {results['successful']}/{results['attempted']} successful")
        return results


# Global service instance
ai_refresh_service = AIDataRefreshService()