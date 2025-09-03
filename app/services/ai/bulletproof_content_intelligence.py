"""
Bulletproof Content Intelligence Service - Production Ready
Uses singleton AI manager and robust components for reliable AI analysis
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.database.unified_models import Profile, Post
from .ai_manager_singleton import ai_manager
from .components.robust_sentiment_analyzer import robust_sentiment_analyzer
from .components.robust_language_detector import robust_language_detector
from .components.robust_category_classifier import robust_category_classifier

logger = logging.getLogger(__name__)

class BulletproofContentIntelligence:
    """
    Production-ready content intelligence service with bulletproof error handling
    Uses singleton AI manager for optimal performance and reliability
    """
    
    def __init__(self):
        self.initialized = False
        self.initialization_error = None
        self.components_health = {}
        
    async def initialize(self) -> bool:
        """Initialize all AI components with comprehensive error handling"""
        try:
            logger.info("[INIT] Initializing Bulletproof Content Intelligence Service...")
            
            # Initialize global AI manager with ALL models for comprehensive analysis
            await ai_manager.initialize_models(['sentiment', 'language', 'category'])
            
            # Initialize all components
            init_results = await asyncio.gather(
                robust_sentiment_analyzer.initialize(),
                robust_language_detector.initialize(),
                robust_category_classifier.initialize(),
                return_exceptions=True
            )
            
            # Check initialization results (None = success, Exception = failure)
            sentiment_ok = init_results[0] is None
            language_ok = init_results[1] is None
            category_ok = init_results[2] is None
            
            self.components_health = {
                "sentiment_analyzer": {"initialized": sentiment_ok, "error": None if sentiment_ok else str(init_results[0])},
                "language_detector": {"initialized": language_ok, "error": None if language_ok else str(init_results[1])},
                "category_classifier": {"initialized": category_ok, "error": None if category_ok else str(init_results[2])},
            }
            
            # Service is considered initialized if at least one component works
            self.initialized = any([sentiment_ok, language_ok, category_ok])
            
            if self.initialized:
                logger.info("[SUCCESS] Bulletproof Content Intelligence Service initialized successfully")
                logger.info(f"Components status: Sentiment={sentiment_ok}, Language={language_ok}, Category={category_ok}")
                return True
            else:
                self.initialization_error = "All AI components failed to initialize"
                logger.error("[FAILED] All AI components failed to initialize")
                return False
            
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"[FAILED] Failed to initialize Bulletproof Content Intelligence Service: {e}")
            return False
    
    async def analyze_post_content(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive post content analysis with bulletproof error handling
        
        Args:
            post_data: Dictionary containing post data (caption, hashtags, media_type, etc.)
            
        Returns:
            Complete AI analysis results with processing metadata
        """
        if not self.initialized:
            await self.initialize()
            if not self.initialized:
                return self._create_error_response(f"AI service not initialized: {self.initialization_error}")
        
        analysis_start_time = datetime.now(timezone.utc)
        
        try:
            # Extract COMPREHENSIVE text content for analysis
            caption_text = post_data.get('caption', '') or ''
            hashtags_list = post_data.get('hashtags', []) or []
            hashtags_text = " ".join(hashtags_list) if hashtags_list else ""
            accessibility_caption = post_data.get('accessibility_caption', '') or ''
            location_text = post_data.get('location', '') or ''
            
            # ENHANCED: Combine all textual data for comprehensive analysis
            combined_text = f"{caption_text} {hashtags_text} {accessibility_caption} {location_text}".strip()
            
            # Basic validation
            if not combined_text and not hashtags_list:
                return self._create_empty_content_response()
            
            # Run all analyses in parallel with individual error handling
            analysis_tasks = [
                self._safe_sentiment_analysis(combined_text),
                self._safe_language_detection(combined_text),
                self._safe_category_classification(combined_text, hashtags_list, post_data.get('media_type'))
            ]
            
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            sentiment_result, language_result, category_result = results
            
            # Process results with error handling
            final_sentiment = self._process_sentiment_result(sentiment_result)
            final_language = self._process_language_result(language_result)
            final_category = self._process_category_result(category_result)
            
            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - analysis_start_time).total_seconds()
            
            # Compile comprehensive analysis
            analysis_result = {
                "ai_content_category": final_category.get("category"),
                "ai_category_confidence": final_category.get("confidence", 0.0),
                "ai_sentiment": final_sentiment.get("label"),
                "ai_sentiment_score": final_sentiment.get("score", 0.0),
                "ai_sentiment_confidence": final_sentiment.get("confidence", 0.0),
                "ai_language_code": final_language.get("language"),
                "ai_language_confidence": final_language.get("confidence", 0.0),
                "ai_analysis_raw": {
                    "sentiment_analysis": final_sentiment,
                    "language_detection": final_language,
                    "category_classification": final_category
                },
                "ai_analyzed_at": analysis_start_time.isoformat(),
                "ai_analysis_version": "3.0_comprehensive",
                "analysis_metadata": {
                    "processing_time_seconds": round(processing_time, 3),
                    "text_length": len(combined_text),
                    "hashtags_count": len(hashtags_list),
                    "has_caption": bool(caption_text),
                    "has_hashtags": bool(hashtags_list),
                    "has_accessibility_caption": bool(accessibility_caption),
                    "has_location": bool(location_text),
                    "media_type": post_data.get('media_type'),
                    "is_video": post_data.get('is_video', False),
                    "video_duration": post_data.get('video_duration', 0),
                    "engagement_rate": post_data.get('engagement_rate', 0),
                    "tagged_users": post_data.get('tagged_users', 0),
                    "dimensions": post_data.get('dimensions'),
                    "components_used": {
                        "sentiment": final_sentiment.get("method", "unknown"),
                        "language": final_language.get("method", "unknown"),
                        "category": final_category.get("method", "unknown")
                    },
                    "analysis_quality": self._calculate_analysis_quality(final_sentiment, final_language, final_category),
                    "comprehensive_analysis": True,
                    "data_sources": ["caption", "hashtags", "accessibility", "location", "metadata"]
                }
            }
            
            logger.debug(f"Post analysis completed in {processing_time:.3f}s")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Post content analysis failed: {e}")
            return self._create_error_response(f"Analysis failed: {str(e)}")
    
    async def _safe_sentiment_analysis(self, text: str) -> Dict[str, Any]:
        """Sentiment analysis with error handling"""
        try:
            if self.components_health.get("sentiment_analyzer", {}).get("initialized"):
                return await robust_sentiment_analyzer.analyze_sentiment(text)
            else:
                return {"label": "neutral", "score": 0.0, "confidence": 0.3, "method": "disabled"}
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return {"label": "neutral", "score": 0.0, "confidence": 0.0, "method": "error", "error": str(e)}
    
    async def _safe_language_detection(self, text: str) -> Dict[str, Any]:
        """Language detection with error handling"""
        try:
            if self.components_health.get("language_detector", {}).get("initialized"):
                return await robust_language_detector.detect_language(text)
            else:
                return {"language": "en", "confidence": 0.3, "method": "disabled"}
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return {"language": "en", "confidence": 0.0, "method": "error", "error": str(e)}
    
    async def _safe_category_classification(self, text: str, hashtags: List[str], media_type: str) -> Dict[str, Any]:
        """Category classification with error handling"""
        try:
            if self.components_health.get("category_classifier", {}).get("initialized"):
                return await robust_category_classifier.classify_content(text, hashtags, media_type)
            else:
                return {"category": "General", "confidence": 0.3, "method": "disabled"}
        except Exception as e:
            logger.warning(f"Category classification failed: {e}")
            return {"category": "General", "confidence": 0.0, "method": "error", "error": str(e)}
    
    def _process_sentiment_result(self, result) -> Dict[str, Any]:
        """Process sentiment analysis result with validation"""
        if isinstance(result, Exception):
            return {"label": "neutral", "score": 0.0, "confidence": 0.0, "method": "exception"}
        
        if not isinstance(result, dict):
            return {"label": "neutral", "score": 0.0, "confidence": 0.0, "method": "invalid"}
        
        return {
            "label": result.get("label", "neutral"),
            "score": float(result.get("score", 0.0)),
            "confidence": float(result.get("confidence", 0.0)),
            "method": result.get("method", "unknown")
        }
    
    def _process_language_result(self, result) -> Dict[str, Any]:
        """Process language detection result with validation"""
        if isinstance(result, Exception):
            return {"language": "en", "confidence": 0.0, "method": "exception"}
        
        if not isinstance(result, dict):
            return {"language": "en", "confidence": 0.0, "method": "invalid"}
        
        return {
            "language": result.get("language", "en"),
            "confidence": float(result.get("confidence", 0.0)),
            "method": result.get("method", "unknown")
        }
    
    def _process_category_result(self, result) -> Dict[str, Any]:
        """Process category classification result with validation"""
        if isinstance(result, Exception):
            return {"category": "General", "confidence": 0.0, "method": "exception"}
        
        if not isinstance(result, dict):
            return {"category": "General", "confidence": 0.0, "method": "invalid"}
        
        return {
            "category": result.get("category", "General"),
            "confidence": float(result.get("confidence", 0.0)),
            "method": result.get("method", "unknown")
        }
    
    def _calculate_analysis_quality(self, sentiment: Dict, language: Dict, category: Dict) -> float:
        """Calculate overall analysis quality score"""
        quality_factors = []
        
        # Sentiment quality
        if sentiment.get("method") == "ai":
            quality_factors.append(0.9)
        elif sentiment.get("method") == "fallback":
            quality_factors.append(0.6)
        else:
            quality_factors.append(0.3)
        
        # Language quality
        if language.get("method") == "ai":
            quality_factors.append(0.9)
        elif language.get("method") == "fallback":
            quality_factors.append(0.7)
        else:
            quality_factors.append(0.4)
        
        # Category quality
        if category.get("method") == "hybrid":
            quality_factors.append(0.95)
        elif category.get("method") == "ai":
            quality_factors.append(0.85)
        elif category.get("method") == "fallback":
            quality_factors.append(0.6)
        else:
            quality_factors.append(0.3)
        
        return round(sum(quality_factors) / len(quality_factors), 3)
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "error": error_message,
            "ai_content_category": None,
            "ai_category_confidence": 0.0,
            "ai_sentiment": "neutral",
            "ai_sentiment_score": 0.0,
            "ai_sentiment_confidence": 0.0,
            "ai_language_code": "en",
            "ai_language_confidence": 0.0,
            "ai_analyzed_at": datetime.now(timezone.utc).isoformat(),
            "analysis_metadata": {
                "error": True,
                "error_message": error_message
            }
        }
    
    def _create_empty_content_response(self) -> Dict[str, Any]:
        """Create response for empty content"""
        return {
            "ai_content_category": None,
            "ai_category_confidence": 0.0,
            "ai_sentiment": "neutral",
            "ai_sentiment_score": 0.0,
            "ai_sentiment_confidence": 0.0,
            "ai_language_code": "en",
            "ai_language_confidence": 0.5,
            "ai_analyzed_at": datetime.now(timezone.utc).isoformat(),
            "analysis_metadata": {
                "text_analyzed": False,
                "reason": "No caption or hashtags found",
                "analysis_quality": 0.3
            }
        }
    
    async def update_post_ai_analysis(self, db: AsyncSession, post_id: str, analysis_results: Dict[str, Any]) -> bool:
        """Update post with AI analysis results"""
        try:
            await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(
                    ai_content_category=analysis_results.get("ai_content_category"),
                    ai_category_confidence=analysis_results.get("ai_category_confidence"),
                    ai_sentiment=analysis_results.get("ai_sentiment"),
                    ai_sentiment_score=analysis_results.get("ai_sentiment_score"),
                    ai_sentiment_confidence=analysis_results.get("ai_sentiment_confidence"),
                    ai_language_code=analysis_results.get("ai_language_code"),
                    ai_language_confidence=analysis_results.get("ai_language_confidence"),
                    ai_analysis_raw=analysis_results.get("ai_analysis_raw"),
                    ai_analyzed_at=datetime.now(timezone.utc),
                    ai_analysis_version=analysis_results.get("ai_analysis_version", "3.0_comprehensive")
                )
            )
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update post AI analysis: {e}")
            try:
                await db.rollback()
            except:
                pass
            return False
    
    async def batch_analyze_posts(self, posts_data: List[Dict[str, Any]], 
                                batch_size: int = 10) -> Dict[str, Any]:
        """
        Analyze multiple posts in batches for optimal performance
        """
        total_posts = len(posts_data)
        successful_analyses = 0
        failed_analyses = 0
        batch_results = []
        
        logger.info(f"Starting COMPREHENSIVE batch analysis of {total_posts} posts (batch size: {batch_size})")
        logger.info("Using ALL AI models: sentiment, language detection, content categorization")
        
        try:
            # Process in batches to manage memory and performance
            for i in range(0, total_posts, batch_size):
                batch = posts_data[i:i + batch_size]
                
                # Analyze batch in parallel
                batch_tasks = [
                    self.analyze_post_content(post_data) 
                    for post_data in batch
                ]
                
                batch_analysis_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process batch results
                for j, result in enumerate(batch_analysis_results):
                    post_data = batch[j]
                    
                    if isinstance(result, Exception):
                        logger.error(f"Batch analysis failed for post {post_data.get('id')}: {result}")
                        failed_analyses += 1
                        batch_results.append({
                            "post_id": post_data.get('id'),
                            "success": False,
                            "error": str(result)
                        })
                    elif result.get("error"):
                        logger.warning(f"Analysis error for post {post_data.get('id')}: {result['error']}")
                        failed_analyses += 1
                        batch_results.append({
                            "post_id": post_data.get('id'),
                            "success": False,
                            "error": result.get("error")
                        })
                    else:
                        successful_analyses += 1
                        batch_results.append({
                            "post_id": post_data.get('id'),
                            "success": True,
                            "analysis": result
                        })
                
                # Log progress
                completed = i + len(batch)
                logger.info(f"Batch analysis progress: {completed}/{total_posts} posts processed")
                
                # Small delay to prevent overwhelming the system
                if i + batch_size < total_posts:
                    await asyncio.sleep(0.1)
            
            success_rate = (successful_analyses / total_posts) * 100 if total_posts > 0 else 0
            
            logger.info(f"Batch analysis completed: {successful_analyses}/{total_posts} successful ({success_rate:.1f}%)")
            
            return {
                "total_posts": total_posts,
                "successful_analyses": successful_analyses,
                "failed_analyses": failed_analyses,
                "success_rate": round(success_rate, 1),
                "batch_results": batch_results,
                "processing_completed": True
            }
            
        except Exception as e:
            logger.error(f"Batch analysis failed: {e}")
            return {
                "total_posts": total_posts,
                "successful_analyses": successful_analyses,
                "failed_analyses": total_posts - successful_analyses,
                "error": str(e),
                "processing_completed": False
            }
    
    async def update_profile_aggregates(self, db: AsyncSession, profile_id: str) -> bool:
        """Update profile with aggregate AI analysis data"""
        try:
            from uuid import UUID
            from sqlalchemy import select, update
            from sqlalchemy.sql import and_
            
            # Convert string UUID to UUID object
            profile_uuid = UUID(profile_id) if isinstance(profile_id, str) else profile_id
            
            # Calculate aggregate statistics
            content_categories = {}
            sentiment_scores = []
            languages = {}
            
            # Get AI analysis for all posts
            posts_query = select(Post).where(
                and_(
                    Post.profile_id == profile_uuid,
                    Post.ai_analyzed_at.is_not(None)
                )
            )
            posts_result = await db.execute(posts_query)
            analyzed_posts = posts_result.scalars().all()
            
            for post in analyzed_posts:
                # Content categories
                if post.ai_content_category:
                    content_categories[post.ai_content_category] = content_categories.get(post.ai_content_category, 0) + 1
                
                # Sentiment scores
                if post.ai_sentiment_score is not None:
                    sentiment_scores.append(post.ai_sentiment_score)
                
                # Languages
                if post.ai_language_code:
                    languages[post.ai_language_code] = languages.get(post.ai_language_code, 0) + 1
            
            # Calculate aggregates
            primary_content_type = max(content_categories.items(), key=lambda x: x[1])[0] if content_categories else None
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
            
            # Content distribution (percentages)
            total_posts = len(analyzed_posts)
            content_distribution = {
                cat: round((count / total_posts) * 100, 1) 
                for cat, count in content_categories.items()
            } if total_posts > 0 else {}
            
            # Language distribution
            language_distribution = {
                lang: round((count / total_posts) * 100, 1) 
                for lang, count in languages.items()
            } if total_posts > 0 else {}
            
            # Content quality score (based on engagement and AI analysis)
            content_quality_score = min(10.0, (abs(avg_sentiment) * 5) + 5)  # Scale to 0-10
            
            # Update profile with aggregate data
            await db.execute(
                update(Profile).where(Profile.id == profile_uuid).values(
                    ai_primary_content_type=primary_content_type,
                    ai_content_distribution=content_distribution,
                    ai_avg_sentiment_score=avg_sentiment,
                    ai_language_distribution=language_distribution,
                    ai_content_quality_score=content_quality_score,
                    ai_profile_analyzed_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()
            
            logger.info(f"✅ Profile AI aggregates updated: {primary_content_type}, sentiment: {avg_sentiment:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update profile AI aggregates: {e}")
            await db.rollback()
            return False

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        return {
            "service_initialized": self.initialized,
            "initialization_error": self.initialization_error,
            "components_health": self.components_health,
            "ai_manager_stats": ai_manager.get_system_stats(),
            "overall_status": "healthy" if self.initialized else "unhealthy",
            "last_check": datetime.now(timezone.utc).isoformat()
        }

# Global instance - bulletproof singleton
bulletproof_content_intelligence = BulletproofContentIntelligence()