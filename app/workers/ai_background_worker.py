"""
AI Background Worker - Celery-based background processing for AI analysis
Handles AI analysis tasks asynchronously to prevent blocking main API
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update

# Import our bulletproof AI service
from app.services.ai.bulletproof_content_intelligence import bulletproof_content_intelligence
from app.database.unified_models import Profile, Post
from app.database.connection import get_database_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'ai_background_worker',
    broker='redis://localhost:6379/0',  # Redis as message broker
    backend='redis://localhost:6379/0'  # Redis as result backend
)

# Celery configuration for production
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,  # Don't prefetch too many tasks
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_default_retry_delay=60,  # 1 minute retry delay
    task_max_retries=3,
    # Performance tuning
    worker_concurrency=2,  # Limit concurrent tasks to prevent memory issues
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
)

# Database setup for background tasks
engine = None
async_session_factory = None

def get_async_engine():
    """Get or create async database engine"""
    global engine
    if engine is None:
        database_url = get_database_url()
        # Convert to async URL if needed
        if not database_url.startswith('postgresql+asyncpg'):
            database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return engine

def get_async_session_factory():
    """Get or create async session factory"""
    global async_session_factory
    if async_session_factory is None:
        engine = get_async_engine()
        async_session_factory = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return async_session_factory

@celery_app.task(bind=True, name='ai_worker.analyze_profile_posts')
def analyze_profile_posts(self, profile_id: str, profile_username: str) -> Dict[str, Any]:
    """
    Background task to analyze all posts for a profile
    
    Args:
        profile_id: UUID of the profile
        profile_username: Username for logging
        
    Returns:
        Analysis results summary
    """
    task_id = self.request.id
    logger.info(f"🚀 Starting AI analysis task {task_id} for profile {profile_username} ({profile_id})")
    
    try:
        # Run the async analysis in the background thread
        result = asyncio.run(_async_analyze_profile_posts(profile_id, profile_username, task_id))
        
        logger.info(f"[SUCCESS] AI analysis task {task_id} completed for {profile_username}: {result.get('posts_analyzed', 0)} posts")
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] AI analysis task {task_id} failed for {profile_username}: {e}")
        
        # Retry on failure (Celery will handle this based on configuration)
        raise self.retry(exc=e, countdown=60, max_retries=3)

async def _async_analyze_profile_posts(profile_id: str, profile_username: str, task_id: str) -> Dict[str, Any]:
    """Async implementation of profile posts analysis"""
    session_factory = get_async_session_factory()
    
    async with session_factory() as db:
        try:
                # Initialize AI service with ALL models for comprehensive analysis
            if not bulletproof_content_intelligence.initialized:
                logger.info(f"Task {task_id}: Initializing AI service with all models...")
                init_success = await bulletproof_content_intelligence.initialize()
                if not init_success:
                    logger.error(f"Task {task_id}: Failed to initialize AI service")
                    raise Exception("AI service initialization failed")
                logger.info(f"Task {task_id}: AI service initialized successfully with all models")
            
            # Get all posts for this profile that haven't been analyzed - COMPREHENSIVE PROCESSING
            posts_query = select(Post).where(
                Post.profile_id == profile_id,
                Post.ai_analyzed_at.is_(None)  # Only unanalyzed posts
            ).limit(200)  # INCREASED: Process up to 200 posts per batch for comprehensive analysis
            
            posts_result = await db.execute(posts_query)
            posts = posts_result.scalars().all()
            
            if not posts:
                return {
                    "success": True,
                    "posts_analyzed": 0,
                    "message": "No posts to analyze",
                    "profile_insights": False
                }
            
            logger.info(f"Task {task_id}: Found {len(posts)} posts to analyze for {profile_username}")
            
            # Prepare COMPREHENSIVE posts data for advanced analysis
            posts_data = []
            for post in posts:
                # ENHANCED: Extract more data from Decodo raw data for comprehensive analysis
                raw_data = post.raw_data or {}
                
                post_data = {
                    'id': str(post.id),
                    'caption': post.caption,
                    'hashtags': post.hashtags,
                    'media_type': post.media_type,
                    'likes': post.likes_count,  # CRITICAL FIX: Use likes_count not likes
                    'comments': post.comments_count,  # CRITICAL FIX: Use comments_count not comments
                    # ENHANCED: Additional metadata for deeper AI analysis
                    'engagement_rate': post.engagement_rate if hasattr(post, 'engagement_rate') else 0,
                    'post_timestamp': post.taken_at_timestamp,
                    'is_video': post.is_video,
                    'video_duration': post.video_duration if post.is_video else 0,
                    'accessibility_caption': raw_data.get('accessibility_caption'),
                    'location': raw_data.get('location', {}).get('name') if raw_data.get('location') else None,
                    'tagged_users': len(raw_data.get('edge_media_to_tagged_user', {}).get('edges', [])),
                    'dimensions': {'width': post.width, 'height': post.height} if post.width and post.height else None,
                    'raw_insights': raw_data  # Include full raw data for advanced analysis
                }
                posts_data.append(post_data)
            
            # Run COMPREHENSIVE batch analysis with all AI models
            batch_results = await bulletproof_content_intelligence.batch_analyze_posts(
                posts_data, 
                batch_size=25  # INCREASED: Process 25 posts per batch for better throughput
            )
            
            # Update database with results
            successful_updates = 0
            for batch_result in batch_results.get("batch_results", []):
                if batch_result.get("success"):
                    post_id = batch_result["post_id"]
                    analysis = batch_result["analysis"]
                    
                    # Update post with AI analysis
                    update_success = await bulletproof_content_intelligence.update_post_ai_analysis(
                        db, post_id, analysis
                    )
                    
                    if update_success:
                        successful_updates += 1
                    else:
                        logger.warning(f"Failed to update post {post_id} with AI analysis")
            
            # Generate profile insights if we have enough data
            profile_insights_updated = False
            if successful_updates > 0:
                profile_insights_updated = await _update_profile_ai_insights(
                    db, profile_id, profile_username
                )
            
            # Final results
            result = {
                "success": True,
                "posts_analyzed": successful_updates,
                "total_posts_found": len(posts),
                "batch_success_rate": batch_results.get("success_rate", 0),
                "profile_insights": profile_insights_updated,
                "task_id": task_id,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Task {task_id}: Successfully analyzed {successful_updates}/{len(posts)} posts for {profile_username}")
            return result
            
        except Exception as e:
            logger.error(f"Task {task_id}: Database error during analysis: {e}")
            try:
                await db.rollback()
            except:
                pass
            raise e

async def _update_profile_ai_insights(db: AsyncSession, profile_id: str, profile_username: str) -> bool:
    """Update profile with aggregated AI insights"""
    try:
        # Get all analyzed posts for this profile
        analyzed_posts_query = select(Post).where(
            Post.profile_id == profile_id,
            Post.ai_analyzed_at.isnot(None)
        )
        
        posts_result = await db.execute(analyzed_posts_query)
        analyzed_posts = posts_result.scalars().all()
        
        if not analyzed_posts:
            return False
        
        # Calculate aggregated insights
        category_counts = {}
        sentiment_scores = []
        language_counts = {}
        
        for post in analyzed_posts:
            # Category distribution
            if post.ai_content_category:
                category_counts[post.ai_content_category] = category_counts.get(post.ai_content_category, 0) + 1
            
            # Sentiment scores
            if post.ai_sentiment_score is not None:
                sentiment_scores.append(float(post.ai_sentiment_score))
            
            # Language distribution
            if post.ai_language_code:
                language_counts[post.ai_language_code] = language_counts.get(post.ai_language_code, 0) + 1
        
        total_analyzed = len(analyzed_posts)
        
        # Calculate insights
        primary_content_type = None
        content_distribution = {}
        ai_top_3_categories = []
        ai_top_10_categories = []
        
        if category_counts:
            # Sort categories by count (descending)
            sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
            primary_content_type = sorted_categories[0][0]  # Keep for backwards compatibility
            
            # Calculate percentages and build structured data
            for category, count in sorted_categories:
                percentage = round((count / total_analyzed) * 100, 1)
                content_distribution[category] = round(count / total_analyzed, 2)  # Keep for backwards compatibility
                
                category_data = {
                    "category": category,
                    "percentage": percentage,
                    "count": count,
                    "confidence": 0.85  # Default confidence for aggregated data
                }
                
                # Add to appropriate lists
                if len(ai_top_3_categories) < 3:
                    ai_top_3_categories.append(category_data)
                if len(ai_top_10_categories) < 10:
                    ai_top_10_categories.append(category_data)
        
        avg_sentiment_score = 0.0
        if sentiment_scores:
            avg_sentiment_score = round(sum(sentiment_scores) / len(sentiment_scores), 3)
        
        language_distribution = {}
        if language_counts:
            language_distribution = {
                lang: round(count / total_analyzed, 2)
                for lang, count in language_counts.items()
            }
        
        # Content quality score (based on sentiment and category consistency)
        content_quality_score = _calculate_content_quality_score(
            content_distribution, avg_sentiment_score, len(sentiment_scores), total_analyzed
        )
        
        # Update profile with insights
        await db.execute(
            update(Profile)
            .where(Profile.id == profile_id)
            .values(
                ai_primary_content_type=primary_content_type,
                ai_content_distribution=content_distribution,
                ai_avg_sentiment_score=avg_sentiment_score,
                ai_language_distribution=language_distribution,
                ai_content_quality_score=content_quality_score,
                ai_profile_analyzed_at=datetime.now(timezone.utc),
                # NEW: Store top 3 and top 10 categories
                ai_top_3_categories=ai_top_3_categories if ai_top_3_categories else None,
                ai_top_10_categories=ai_top_10_categories if ai_top_10_categories else None
            )
        )
        
        await db.commit()
        
        logger.info(f"Updated profile insights for {profile_username}: {total_analyzed} posts analyzed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update profile insights for {profile_username}: {e}")
        try:
            await db.rollback()
        except:
            pass
        return False

def _calculate_content_quality_score(content_distribution: Dict[str, float], 
                                   avg_sentiment: float, analyzed_posts: int, 
                                   total_posts: int) -> float:
    """Calculate overall content quality score"""
    score = 0.0
    
    # Sentiment contribution (positive sentiment is better)
    sentiment_contribution = max(0, (avg_sentiment + 1) / 2)  # Normalize -1,1 to 0,1
    score += sentiment_contribution * 0.4  # 40% weight
    
    # Content consistency (focused content is better)
    consistency_score = 0.0
    if content_distribution:
        max_category_ratio = max(content_distribution.values())
        consistency_score = max_category_ratio
    score += consistency_score * 0.3  # 30% weight
    
    # Analysis coverage (more analyzed posts is better)
    coverage_score = min(1.0, analyzed_posts / max(1, total_posts))
    score += coverage_score * 0.3  # 30% weight
    
    return round(score, 3)

@celery_app.task(bind=True, name='ai_worker.health_check')
def health_check(self):
    """Health check task for monitoring"""
    try:
        # Test AI service
        health_status = asyncio.run(_async_health_check())
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ai_service": health_status,
            "worker_id": self.request.hostname
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

async def _async_health_check() -> Dict[str, Any]:
    """Async health check implementation"""
    if not bulletproof_content_intelligence.initialized:
        await bulletproof_content_intelligence.initialize()
    
    return bulletproof_content_intelligence.get_system_health()

# Task routing configuration
celery_app.conf.task_routes = {
    'ai_worker.analyze_profile_posts': {'queue': 'ai_analysis'},
    'ai_worker.health_check': {'queue': 'health_checks'}
}

if __name__ == '__main__':
    # Start worker for testing: celery -A ai_background_worker worker --loglevel=info
    celery_app.start()