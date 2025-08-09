"""
Content Intelligence Service - AI/ML Content Analysis
Provides sentiment analysis, content categorization, and language detection for Instagram posts
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.database.unified_models import Profile, Post
from .models.ai_models_manager import AIModelsManager
from .components.sentiment_analyzer import SentimentAnalyzer
from .components.language_detector import LanguageDetector
from .components.category_classifier import CategoryClassifier

logger = logging.getLogger(__name__)

class ContentIntelligenceService:
    """
    Main service for AI-powered content analysis
    Orchestrates sentiment analysis, category classification, and language detection
    """
    
    def __init__(self):
        self.models_manager = None
        self.sentiment_analyzer = None
        self.language_detector = None
        self.category_classifier = None
        self.initialized = False
        self.initialization_error = None
        
    async def initialize(self) -> bool:
        """Initialize AI models and components"""
        try:
            logger.info("Initializing Content Intelligence Service...")
            
            # Initialize models manager
            self.models_manager = AIModelsManager()
            await self.models_manager.initialize()
            
            # Initialize individual components
            self.sentiment_analyzer = SentimentAnalyzer(self.models_manager)
            self.language_detector = LanguageDetector(self.models_manager)
            self.category_classifier = CategoryClassifier(self.models_manager)
            
            # Initialize each component
            await self.sentiment_analyzer.initialize()
            await self.language_detector.initialize()
            await self.category_classifier.initialize()
            
            self.initialized = True
            logger.info("✅ Content Intelligence Service initialized successfully")
            return True
            
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"❌ Failed to initialize Content Intelligence Service: {e}")
            return False
    
    async def analyze_post_content(self, post: Post, profile_followers: int = 0) -> Dict[str, Any]:
        """
        Analyze a single post's content for sentiment, category, and language
        """
        if not self.initialized:
            await self.initialize()
            if not self.initialized:
                return {"error": f"AI service not initialized: {self.initialization_error}"}
        
        try:
            # Extract text content for analysis
            caption_text = post.caption or ""
            hashtags_text = " ".join(post.hashtags or []) if post.hashtags else ""
            combined_text = f"{caption_text} {hashtags_text}".strip()
            
            if not combined_text:
                return {
                    "ai_content_category": None,
                    "ai_category_confidence": 0.0,
                    "ai_sentiment": "neutral",
                    "ai_sentiment_score": 0.0,
                    "ai_sentiment_confidence": 0.0,
                    "ai_language_code": "en",
                    "ai_language_confidence": 0.5,
                    "analysis_metadata": {
                        "text_analyzed": False,
                        "reason": "No caption or hashtags found"
                    }
                }
            
            # Run all analyses in parallel for better performance
            sentiment_result, language_result, category_result = await asyncio.gather(
                self.sentiment_analyzer.analyze_sentiment(combined_text),
                self.language_detector.detect_language(combined_text),
                self.category_classifier.classify_content(
                    text=combined_text, 
                    hashtags=post.hashtags or [],
                    media_type=post.media_type
                ),
                return_exceptions=True
            )
            
            # Handle potential errors
            if isinstance(sentiment_result, Exception):
                logger.error(f"Sentiment analysis failed: {sentiment_result}")
                sentiment_result = {"label": "neutral", "score": 0.0, "confidence": 0.0}
            
            if isinstance(language_result, Exception):
                logger.error(f"Language detection failed: {language_result}")
                language_result = {"language": "en", "confidence": 0.5}
            
            if isinstance(category_result, Exception):
                logger.error(f"Category classification failed: {category_result}")
                category_result = {"category": "General", "confidence": 0.0}
            
            return {
                "ai_content_category": category_result.get("category"),
                "ai_category_confidence": float(category_result.get("confidence", 0.0)),
                "ai_sentiment": sentiment_result.get("label"),
                "ai_sentiment_score": float(sentiment_result.get("score", 0.0)),
                "ai_sentiment_confidence": float(sentiment_result.get("confidence", 0.0)),
                "ai_language_code": language_result.get("language"),
                "ai_language_confidence": float(language_result.get("confidence", 0.0)),
                "analysis_metadata": {
                    "text_length": len(combined_text),
                    "has_hashtags": bool(post.hashtags),
                    "media_type": post.media_type,
                    "analyzed_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Post content analysis failed for post {post.id}: {e}")
            return {"error": f"Analysis failed: {str(e)}"}
    
    async def analyze_post_content_from_data(self, post_data: Dict[str, Any], profile_followers: int = 0) -> Dict[str, Any]:
        """
        Analyze a single post's content using pre-extracted data (avoids SQLAlchemy lazy loading issues)
        """
        if not self.initialized:
            await self.initialize()
            if not self.initialized:
                return {"error": f"AI service not initialized: {self.initialization_error}"}
        
        try:
            # Extract text content for analysis
            caption_text = post_data.get('caption') or ""
            hashtags_list = post_data.get('hashtags', [])
            hashtags_text = " ".join(hashtags_list) if hashtags_list else ""
            combined_text = f"{caption_text} {hashtags_text}".strip()
            
            if not combined_text:
                return {
                    "ai_content_category": None,
                    "ai_category_confidence": 0.0,
                    "ai_sentiment": "neutral",
                    "ai_sentiment_score": 0.0,
                    "ai_sentiment_confidence": 0.0,
                    "ai_language_code": "en",
                    "ai_language_confidence": 0.5,
                    "analysis_metadata": {
                        "text_analyzed": False,
                        "reason": "No caption or hashtags found"
                    }
                }
            
            # Run all analyses in parallel for better performance
            sentiment_result, language_result, category_result = await asyncio.gather(
                self.sentiment_analyzer.analyze_sentiment(combined_text),
                self.language_detector.detect_language(combined_text),
                self.category_classifier.classify_content(
                    text=combined_text, 
                    hashtags=hashtags_list,
                    media_type=post_data.get('media_type')
                ),
                return_exceptions=True
            )
            
            # Handle potential errors
            if isinstance(sentiment_result, Exception):
                logger.error(f"Sentiment analysis failed: {sentiment_result}")
                sentiment_result = {"label": "neutral", "score": 0.0, "confidence": 0.0}
            
            if isinstance(language_result, Exception):
                logger.error(f"Language detection failed: {language_result}")
                language_result = {"language": "en", "confidence": 0.5}
            
            if isinstance(category_result, Exception):
                logger.error(f"Category classification failed: {category_result}")
                category_result = {"category": "General", "confidence": 0.0}
            
            return {
                "ai_content_category": category_result.get("category"),
                "ai_category_confidence": float(category_result.get("confidence", 0.0)),
                "ai_sentiment": sentiment_result.get("label"),
                "ai_sentiment_score": float(sentiment_result.get("score", 0.0)),
                "ai_sentiment_confidence": float(sentiment_result.get("confidence", 0.0)),
                "ai_language_code": language_result.get("language"),
                "ai_language_confidence": float(language_result.get("confidence", 0.0)),
                "analysis_metadata": {
                    "text_length": len(combined_text),
                    "has_hashtags": bool(hashtags_list),
                    "media_type": post_data.get('media_type'),
                    "analyzed_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Post content analysis failed for post {post_data.get('id')}: {e}")
            return {"error": f"Analysis failed: {str(e)}"}
    
    async def update_post_ai_analysis(self, db: AsyncSession, post_id: str, analysis_results: Dict[str, Any]) -> bool:
        """Update post with AI analysis results"""
        try:
            await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(
                    ai_content_category=analysis_results.get("ai_content_category"),
                    ai_sentiment=analysis_results.get("ai_sentiment"),
                    ai_sentiment_score=analysis_results.get("ai_sentiment_score"),
                    ai_language=analysis_results.get("ai_language_code"),
                    ai_language_confidence=analysis_results.get("ai_language_confidence"),
                    ai_post_analyzed_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update post AI analysis: {e}")
            return False
    
    async def analyze_profile_content(self, db: AsyncSession, profile_id: str) -> Dict[str, Any]:
        """
        Analyze all posts for a profile and generate aggregated insights
        """
        try:
            # Get profile and posts - load all necessary data upfront
            profile_result = await db.execute(
                select(Profile).where(Profile.id == profile_id)
            )
            profile = profile_result.scalar_one_or_none()
            
            if not profile:
                return {"error": "Profile not found"}
            
            posts_result = await db.execute(
                select(Post)
                .where(Post.profile_id == profile_id)
                .order_by(Post.taken_at_timestamp.desc())
                .limit(20)  # Analyze last 20 posts
            )
            posts = posts_result.scalars().all()
            
            if not posts:
                return {"message": "No posts found for analysis"}
            
            logger.info(f"Analyzing {len(posts)} posts for profile {profile.username}")
            
            # Extract post data immediately to avoid lazy loading issues
            posts_data = []
            for post in posts:
                posts_data.append({
                    'id': str(post.id),
                    'caption': post.caption,
                    'hashtags': post.hashtags or [],
                    'media_type': post.media_type
                })
            
            # Analyze each post using extracted data
            analysis_tasks = []
            for post_data in posts_data:
                task = self.analyze_post_content_from_data(post_data, profile.followers_count or 0)
                analysis_tasks.append((post_data['id'], task))
            
            # Process analyses and update posts
            successful_analyses = 0
            category_distribution = {}
            sentiment_scores = []
            language_counts = {}
            total_tasks = len(analysis_tasks)
            
            logger.info(f"🔄 Starting analysis of {total_tasks} posts for profile {profile.username}")
            
            for i, (post_id, analysis_task) in enumerate(analysis_tasks, 1):
                try:
                    logger.info(f"📊 Analyzing post {i}/{total_tasks} (ID: {str(post_id)[:8]}...)")
                    analysis_result = await analysis_task
                    
                    if "error" not in analysis_result:
                        # Update post in database
                        await self.update_post_ai_analysis(db, str(post_id), analysis_result)
                        successful_analyses += 1
                        
                        # Log analysis results
                        category = analysis_result.get("ai_content_category")
                        sentiment = analysis_result.get("ai_sentiment")
                        language = analysis_result.get("ai_language_code")
                        logger.info(f"✅ Post {i}/{total_tasks} analyzed - Category: {category}, Sentiment: {sentiment}, Language: {language}")
                        
                        # Aggregate data for profile insights
                        if category:
                            category_distribution[category] = category_distribution.get(category, 0) + 1
                        
                        sentiment_score = analysis_result.get("ai_sentiment_score", 0.0)
                        if sentiment_score is not None:
                            sentiment_scores.append(sentiment_score)
                        
                        if language:
                            language_counts[language] = language_counts.get(language, 0) + 1
                    else:
                        logger.warning(f"❌ Post {i}/{total_tasks} analysis failed: {analysis_result.get('error')}")
                    
                    # Progress indicator
                    progress_pct = int((i / total_tasks) * 100)
                    logger.info(f"📈 Progress: {progress_pct}% ({i}/{total_tasks} posts processed)")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to analyze post {i}/{total_tasks} (ID: {post_id}): {e}")
                    continue
            
            # Calculate profile-level insights
            profile_insights = self._calculate_profile_insights(
                category_distribution, sentiment_scores, language_counts, len(posts)
            )
            
            # Update profile with aggregated insights
            logger.info(f"💾 Updating profile {profile.username} with aggregated AI insights...")
            await self.update_profile_ai_insights(db, profile_id, profile_insights)
            
            # Log completion summary
            logger.info(f"🎉 AI Analysis COMPLETE for {profile.username}!")
            logger.info(f"📊 Summary: {successful_analyses}/{len(posts)} posts analyzed")
            logger.info(f"🏷️ Top categories: {dict(list(category_distribution.items())[:3])}")
            logger.info(f"💭 Avg sentiment: {profile_insights.get('ai_avg_sentiment_score', 0)}")
            logger.info(f"🌍 Languages: {list(language_counts.keys())}")
            logger.info(f"⭐ Content quality score: {profile_insights.get('ai_content_quality_score', 0)}")
            
            return {
                "profile_id": profile_id,
                "username": profile.username,
                "posts_analyzed": successful_analyses,
                "total_posts": len(posts),
                "profile_insights": profile_insights,
                "analysis_completed": True
            }
            
        except Exception as e:
            logger.error(f"Profile content analysis failed: {e}")
            return {"error": f"Profile analysis failed: {str(e)}"}
    
    def _calculate_profile_insights(
        self, 
        category_distribution: Dict[str, int], 
        sentiment_scores: List[float], 
        language_counts: Dict[str, int],
        total_posts: int
    ) -> Dict[str, Any]:
        """Calculate aggregated profile insights from post analyses"""
        
        # Primary content type (most common category)
        primary_content_type = None
        if category_distribution:
            primary_content_type = max(category_distribution, key=category_distribution.get)
        
        # Content distribution (normalized)
        content_distribution = {}
        if category_distribution:
            for category, count in category_distribution.items():
                content_distribution[category] = round(count / total_posts, 2)
        
        # Average sentiment score
        avg_sentiment = 0.0
        if sentiment_scores:
            avg_sentiment = round(sum(sentiment_scores) / len(sentiment_scores), 3)
        
        # Language distribution (normalized) 
        language_distribution = {}
        if language_counts:
            for language, count in language_counts.items():
                language_distribution[language] = round(count / total_posts, 2)
        
        # Content quality score (based on sentiment and category consistency)
        content_quality_score = self._calculate_content_quality_score(
            content_distribution, avg_sentiment, len(sentiment_scores), total_posts
        )
        
        return {
            "ai_primary_content_type": primary_content_type,
            "ai_content_distribution": content_distribution,
            "ai_avg_sentiment_score": avg_sentiment,
            "ai_language_distribution": language_distribution,
            "ai_content_quality_score": content_quality_score
        }
    
    def _calculate_content_quality_score(
        self, 
        content_distribution: Dict[str, float], 
        avg_sentiment: float,
        analyzed_posts: int, 
        total_posts: int
    ) -> float:
        """Calculate overall content quality score"""
        
        score = 0.0
        
        # Sentiment contribution (positive sentiment is better)
        sentiment_contribution = max(0, (avg_sentiment + 1) / 2)  # Normalize -1,1 to 0,1
        score += sentiment_contribution * 0.4  # 40% weight
        
        # Content consistency (focused content is better)
        consistency_score = 0.0
        if content_distribution:
            # Higher score for focused content (one dominant category)
            max_category_ratio = max(content_distribution.values())
            consistency_score = max_category_ratio
        score += consistency_score * 0.3  # 30% weight
        
        # Analysis coverage (more analyzed posts is better)
        coverage_score = min(1.0, analyzed_posts / max(1, total_posts))
        score += coverage_score * 0.3  # 30% weight
        
        return round(score, 3)
    
    async def update_profile_ai_insights(self, db: AsyncSession, profile_id: str, insights: Dict[str, Any]) -> bool:
        """Update profile with aggregated AI insights"""
        try:
            await db.execute(
                update(Profile)
                .where(Profile.id == profile_id)
                .values(
                    ai_primary_content_type=insights.get("ai_primary_content_type"),
                    ai_content_distribution=insights.get("ai_content_distribution"),
                    ai_avg_sentiment_score=insights.get("ai_avg_sentiment_score"),
                    ai_language_distribution=insights.get("ai_language_distribution"),
                    ai_content_quality_score=insights.get("ai_content_quality_score"),
                    ai_profile_analyzed_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update profile AI insights: {e}")
            return False
    
    async def get_ai_analytics_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get statistics about AI analysis coverage"""
        try:
            # Posts analysis stats
            posts_total = await db.execute(select(func.count(Post.id)))
            posts_analyzed = await db.execute(
                select(func.count(Post.id)).where(Post.ai_analyzed_at.isnot(None))
            )
            
            # Profiles analysis stats
            profiles_total = await db.execute(select(func.count(Profile.id)))
            profiles_analyzed = await db.execute(
                select(func.count(Profile.id)).where(Profile.ai_profile_analyzed_at.isnot(None))
            )
            
            # Category distribution
            category_stats = await db.execute(
                select(Post.ai_content_category, func.count(Post.id))
                .where(Post.ai_content_category.isnot(None))
                .group_by(Post.ai_content_category)
                .order_by(func.count(Post.id).desc())
            )
            
            # Sentiment distribution
            sentiment_stats = await db.execute(
                select(Post.ai_sentiment, func.count(Post.id))
                .where(Post.ai_sentiment.isnot(None))
                .group_by(Post.ai_sentiment)
            )
            
            return {
                "posts": {
                    "total": posts_total.scalar(),
                    "analyzed": posts_analyzed.scalar(),
                    "analysis_coverage": round(
                        (posts_analyzed.scalar() / max(1, posts_total.scalar())) * 100, 1
                    )
                },
                "profiles": {
                    "total": profiles_total.scalar(),
                    "analyzed": profiles_analyzed.scalar(),
                    "analysis_coverage": round(
                        (profiles_analyzed.scalar() / max(1, profiles_total.scalar())) * 100, 1
                    )
                },
                "content_categories": {
                    row[0]: row[1] for row in category_stats.fetchall()
                },
                "sentiment_distribution": {
                    row[0]: row[1] for row in sentiment_stats.fetchall()
                },
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get AI analytics stats: {e}")
            return {"error": f"Failed to retrieve stats: {str(e)}"}

# Global instance
content_intelligence_service = ContentIntelligenceService()