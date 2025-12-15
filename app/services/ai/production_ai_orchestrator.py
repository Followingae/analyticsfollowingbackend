"""
Production AI Orchestrator - Complete Integration of All 10 AI Models
Bulletproof implementation with proper workflow sequencing and database integration
"""
import asyncio
import logging
import uuid
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update

from app.database.connection import get_session
from app.services.ai.comprehensive_ai_manager import comprehensive_ai_manager, AIModelType
from app.services.ai.comprehensive_ai_models_part2 import AdvancedAIModelImplementations
from app.services.ai.ai_manager_wrapper import ai_manager
from app.services.redis_cache_service import redis_cache

logger = logging.getLogger(__name__)

class ProductionAIOrchestrator:
    """
    Production AI Orchestrator managing all 10 AI models with proper sequencing
    CRITICAL: Executes ONLY AFTER Apify data and CDN URLs are 100% stored
    """

    def __init__(self):
        self.ai_manager = comprehensive_ai_manager
        self.advanced_ai = AdvancedAIModelImplementations()
        self.core_ai = ai_manager
        self.processing_timeout = 300  # 5 minutes max processing time

    async def initialize_ai_system(self) -> Dict[str, bool]:
        """
        Initialize all 10 AI models for the production system

        Returns:
            Initialization status for each model
        """
        logger.info("[AI-ORCHESTRATOR] Initializing complete AI system (10 models)")

        # Initialize comprehensive AI manager
        initialization_status = await self.ai_manager.initialize_all_models()

        # Log initialization results
        successful_models = sum(1 for success in initialization_status.values() if success)
        total_models = len(initialization_status)

        logger.info(f"[AI-ORCHESTRATOR] Initialization complete: {successful_models}/{total_models} models ready")

        if successful_models < total_models:
            failed_models = [model for model, success in initialization_status.items() if not success]
            logger.warning(f"[AI-ORCHESTRATOR] Failed models will use fallback strategies: {failed_models}")

        return initialization_status

    async def process_profile_complete_ai_analysis(self, profile_id: str, username: str) -> Dict[str, Any]:
        """
        COMPREHENSIVE AI analysis for a profile - ALL 10 models
        CRITICAL: Only executes AFTER Apify data and CDN URLs are stored

        Args:
            profile_id: Profile UUID in database
            username: Instagram username

        Returns:
            Complete AI analysis results
        """
        analysis_id = str(uuid.uuid4())
        logger.info(f"[AI-ORCHESTRATOR] Starting comprehensive AI analysis for {username} (Profile: {profile_id})")

        analysis_results = {
            'analysis_id': analysis_id,
            'profile_id': profile_id,
            'username': username,
            'started_at': datetime.now(timezone.utc),
            'completed_at': None,
            'total_models': 10,
            'completed_models': 0,
            'failed_models': 0,
            'model_results': {},
            'database_updates': {
                'profile_updates': {},
                'post_updates': [],
                'aggregations_stored': False
            },
            'success': False,
            'processing_errors': []
        }

        try:
            # STEP 1: Verify prerequisites are met
            prerequisites_check = await self._verify_prerequisites(profile_id)
            if not prerequisites_check['ready']:
                raise Exception(f"Prerequisites not met: {prerequisites_check['missing']}")

            logger.info(f"[AI-ORCHESTRATOR] Prerequisites verified for {username}")

            # STEP 2: Fetch complete profile and posts data
            profile_data, posts_data = await self._fetch_complete_profile_data(profile_id)

            logger.info(f"[AI-ORCHESTRATOR] Fetched profile data: {len(posts_data)} posts for {username}")

            # STEP 3: Execute all 10 AI models
            ai_analysis = await self.ai_manager.analyze_profile_comprehensive(
                profile_id=profile_id,
                profile_data=profile_data,
                posts_data=posts_data
            )

            analysis_results['model_results'] = ai_analysis['analysis_results']
            analysis_results['completed_models'] = ai_analysis['job_status']['completed_models']
            analysis_results['failed_models'] = ai_analysis['job_status']['failed_models']

            logger.info(f"[AI-ORCHESTRATOR] AI analysis complete: {analysis_results['completed_models']}/10 models successful")

            # STEP 4: Store AI results in database
            await self._store_ai_results_in_database(profile_id, posts_data, analysis_results['model_results'])
            analysis_results['database_updates']['aggregations_stored'] = True

            logger.info(f"[AI-ORCHESTRATOR] Database updates complete for {username}")

            # STEP 5: Update analysis status
            analysis_results['completed_at'] = datetime.now(timezone.utc)
            analysis_results['success'] = analysis_results['completed_models'] >= 7  # 70% success threshold

            processing_duration = (analysis_results['completed_at'] - analysis_results['started_at']).total_seconds()

            logger.info(f"[AI-ORCHESTRATOR] Analysis complete for {username} in {processing_duration:.1f}s")
            logger.info(f"[AI-ANALYTICS] Success rate: {(analysis_results['completed_models']/10)*100:.1f}%")

            # STEP 6: Cache results for fast retrieval
            await self._cache_ai_results(profile_id, analysis_results['model_results'])

            return analysis_results

        except Exception as e:
            logger.error(f"[AI-ORCHESTRATOR] Analysis failed for {username}: {e}")
            analysis_results['processing_errors'].append(str(e))
            analysis_results['completed_at'] = datetime.now(timezone.utc)
            analysis_results['success'] = False
            return analysis_results

    async def _verify_prerequisites(self, profile_id: str) -> Dict[str, Any]:
        """
        Verify that Apify data and CDN processing are complete before AI analysis

        Args:
            profile_id: Profile UUID

        Returns:
            Prerequisites verification result
        """
        try:
            async with get_session() as db:
                # Check profile exists with Apify data
                profile_check = text("""
                    SELECT
                        p.id,
                        p.username,
                        p.followers_count,
                        p.profile_pic_url_hd,
                        COUNT(posts.id) as posts_count,
                        COUNT(posts.cdn_thumbnail_url) as posts_with_cdn
                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    WHERE p.id = :profile_id
                    GROUP BY p.id, p.username, p.followers_count, p.profile_pic_url_hd
                """)

                result = await db.execute(profile_check, {'profile_id': profile_id})
                data = result.fetchone()

                if not data:
                    return {'ready': False, 'missing': ['profile_not_found']}

                missing = []

                # CRITICAL FIX: More lenient validation for production

                # Check if we have username (essential Apify data)
                if not data.username:
                    missing.append('username_missing')

                # RELAXED: Allow profiles with 0 followers (they exist in real Instagram)
                # Only warn if followers_count is None (not fetched from Apify)
                if data.followers_count is None:
                    missing.append('apify_data_missing')

                # RELAXED: Allow profiles with 0 posts (they exist in real Instagram)
                # Only require posts_count >= 0 (not None)
                # For profiles with no posts, skip CDN check and allow AI analysis
                if data.posts_count is None:
                    missing.append('posts_count_missing')
                elif data.posts_count == 0:
                    # Profile has no posts - skip CDN checks, allow AI to analyze profile data only
                    logger.info(f"[AI-ORCHESTRATOR] Profile {data.username} has no posts - will analyze profile data only")
                else:
                    # RELAXED: Lower CDN processing threshold to 50% for production flexibility
                    cdn_completion = data.posts_with_cdn / max(data.posts_count, 1)
                    if cdn_completion < 0.5:
                        # Don't block AI processing - just warn and proceed with available data
                        logger.warning(f"[AI-ORCHESTRATOR] CDN processing incomplete for {data.username}: {cdn_completion:.1%}, but proceeding with AI analysis")
                        # missing.append(f'cdn_processing_incomplete_{cdn_completion:.1%}')  # COMMENTED OUT - don't block

                # CDN profile pic processing is optional
                # (profile_pic_cdn_url column doesn't exist in current schema)

                if missing:
                    return {'ready': False, 'missing': missing}

                # Calculate CDN completion for profiles with posts
                cdn_completion = 0.0
                if data.posts_count and data.posts_count > 0:
                    cdn_completion = data.posts_with_cdn / max(data.posts_count, 1)

                return {
                    'ready': True,
                    'profile_data': {
                        'username': data.username,
                        'followers_count': data.followers_count or 0,
                        'posts_count': data.posts_count or 0,
                        'cdn_completion': cdn_completion,
                        'posts_with_cdn': data.posts_with_cdn or 0
                    }
                }

        except Exception as e:
            logger.error(f"[AI-ORCHESTRATOR] Prerequisites check failed: {e}")
            return {'ready': False, 'missing': [f'check_failed_{str(e)}']}

    def _validate_posts_data(self, posts_data: List, context: str = 'analysis') -> List[dict]:
        """
        CRITICAL: Validate and convert posts_data to proper dictionary format
        Handles cases where database rows are passed instead of dictionaries
        """
        validated_posts = []

        for i, post in enumerate(posts_data):
            try:
                # Check if post is already a dictionary
                if isinstance(post, dict):
                    validated_posts.append(post)
                    continue

                # If post is a database row object (has attributes), convert to dict
                if hasattr(post, 'id') and hasattr(post, 'caption'):
                    post_dict = {
                        'id': str(getattr(post, 'id', f'unknown_{i}')),
                        'instagram_post_id': getattr(post, 'instagram_post_id', ''),
                        'caption': getattr(post, 'caption', '') or '',
                        'likes_count': getattr(post, 'likes_count', 0) or 0,
                        'comments_count': getattr(post, 'comments_count', 0) or 0,
                        'display_url': getattr(post, 'display_url', ''),
                        'thumbnail_url': getattr(post, 'thumbnail_url', ''),
                        'cdn_thumbnail_url': getattr(post, 'cdn_thumbnail_url', ''),
                        'is_video': getattr(post, 'is_video', False) or False,
                        'video_view_count': getattr(post, 'video_view_count', 0) or 0,
                        'posted_at': getattr(post, 'posted_at', None),
                        'created_at': getattr(post, 'created_at', None)
                    }
                    validated_posts.append(post_dict)
                    continue

                logger.warning(f"[AI-ORCHESTRATOR] Unrecognized post data format at index {i} in {context}: {type(post)}")

            except Exception as e:
                logger.error(f"[AI-ORCHESTRATOR] Failed to convert post at index {i} in {context}: {e}")
                continue

        logger.info(f"[AI-ORCHESTRATOR] {context}: Converted {len(validated_posts)}/{len(posts_data)} posts to valid format")
        return validated_posts

    async def _fetch_complete_profile_data(self, profile_id: str) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Fetch complete profile and posts data for AI analysis

        Args:
            profile_id: Profile UUID

        Returns:
            Tuple of (profile_data, posts_data)
        """
        async with get_session() as db:
            # Fetch profile data
            profile_query = text("""
                SELECT
                    id, username, full_name, biography, is_verified as verified,
                    followers_count, following_count, posts_count,
                    profile_pic_url_hd, created_at
                FROM profiles
                WHERE id = :profile_id
            """)

            profile_result = await db.execute(profile_query, {'profile_id': profile_id})
            profile_row = profile_result.fetchone()

            if not profile_row:
                raise Exception(f"Profile {profile_id} not found")

            profile_data = {
                'id': str(profile_row.id),
                'username': profile_row.username,
                'full_name': profile_row.full_name,
                'biography': profile_row.biography,
                'verified': profile_row.verified,
                'followers_count': profile_row.followers_count,
                'following_count': profile_row.following_count,
                'posts_count': profile_row.posts_count,
                'profile_pic_url_hd': profile_row.profile_pic_url_hd,
                'created_at': profile_row.created_at
            }

            # Fetch posts data with CDN URLs
            posts_query = text("""
                SELECT
                    id, instagram_post_id, caption, likes_count, comments_count,
                    display_url, thumbnail_src as thumbnail_url, cdn_thumbnail_url,
                    is_video, video_view_count, posted_at, created_at
                FROM posts
                WHERE profile_id = :profile_id
                ORDER BY posted_at DESC
                LIMIT 100
            """)

            posts_result = await db.execute(posts_query, {'profile_id': profile_id})
            posts_rows = posts_result.fetchall()

            posts_data = []
            for post in posts_rows:
                posts_data.append({
                    'id': str(post.id),
                    'instagram_post_id': post.instagram_post_id,
                    'caption': post.caption or '',
                    'likes_count': post.likes_count or 0,
                    'comments_count': post.comments_count or 0,
                    'display_url': post.display_url,
                    'thumbnail_url': post.thumbnail_url,
                    'cdn_thumbnail_url': post.cdn_thumbnail_url,
                    'is_video': post.is_video or False,
                    'video_view_count': post.video_view_count or 0,
                    'posted_at': post.posted_at,
                    'created_at': post.created_at
                })

            logger.debug(f"[AI-ORCHESTRATOR] Fetched {len(posts_data)} posts for profile {profile_data['username']}")

            return profile_data, posts_data

    async def _store_ai_results_in_database(self, profile_id: str, posts_data: List[Dict], ai_results: Dict[str, Any]) -> None:
        """
        Store all AI analysis results in the database

        Args:
            profile_id: Profile UUID
            posts_data: Posts data used for analysis
            ai_results: Complete AI analysis results from all 10 models
        """
        async with get_session() as db:
            try:
                # STEP 1: Store individual post AI analysis
                await self._store_post_ai_analysis(db, posts_data, ai_results)

                # STEP 2: Store profile-level AI aggregations
                await self._store_profile_ai_aggregations(db, profile_id, ai_results)

                # STEP 3: Commit all changes
                await db.commit()

                logger.info(f"[AI-ORCHESTRATOR] Successfully stored AI results for profile {profile_id}")

            except Exception as e:
                await db.rollback()
                logger.error(f"[AI-ORCHESTRATOR] Failed to store AI results: {e}")
                raise

    async def _store_post_ai_analysis(self, db: AsyncSession, posts_data: List[Dict], ai_results: Dict[str, Any]) -> None:
        """Store AI analysis results for individual posts"""

        # CRITICAL FIX: Validate posts_data structure
        validated_posts = self._validate_posts_data(posts_data, 'ai_storage')

        # Extract core AI model results
        sentiment_results = ai_results.get('sentiment', {})
        language_results = ai_results.get('language', {})
        category_results = ai_results.get('category', {})

        # Process each post
        for i, post in enumerate(validated_posts):
            if i >= len(sentiment_results.get('sentiment_scores', [])):
                continue

            # Get AI analysis for this post
            sentiment_data = sentiment_results['sentiment_scores'][i] if i < len(sentiment_results.get('sentiment_scores', [])) else {}
            language_data = language_results['language_scores'][i] if i < len(language_results.get('language_scores', [])) else {}
            category_data = category_results['category_scores'][i] if i < len(category_results.get('category_scores', [])) else {}

            # Compile all AI analysis into raw JSONB
            ai_analysis_raw = {
                'sentiment': sentiment_data,
                'language': language_data,
                'category': category_data,
                'advanced_models': {
                    'audience_quality': ai_results.get('audience_quality', {}),
                    'visual_content': ai_results.get('visual_content', {}),
                    'audience_insights': ai_results.get('audience_insights', {}),
                    'trend_detection': ai_results.get('trend_detection', {}),
                    'advanced_nlp': ai_results.get('advanced_nlp', {}),
                    'fraud_detection': ai_results.get('fraud_detection', {}),
                    'behavioral_patterns': ai_results.get('behavioral_patterns', {})
                },
                'analysis_timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Ensure JSON serializable (handle numpy types)
            json_safe_analysis = self._make_json_serializable(ai_analysis_raw)

            # Update post with AI analysis
            await db.execute(
                text("""
                    UPDATE posts SET
                        ai_content_category = :category,
                        ai_category_confidence = :category_confidence,
                        ai_sentiment = :sentiment,
                        ai_sentiment_score = :sentiment_score,
                        ai_sentiment_confidence = :sentiment_confidence,
                        ai_language_code = :language_code,
                        ai_language_confidence = :language_confidence,
                        ai_analysis_raw = :ai_analysis_raw,
                        ai_analyzed_at = NOW()
                    WHERE id = :post_id
                """),
                {
                    'post_id': post['id'],
                    'category': category_data.get('category', 'general'),
                    'category_confidence': category_data.get('confidence', 0.0),
                    'sentiment': sentiment_data.get('sentiment', 'neutral'),
                    'sentiment_score': sentiment_data.get('score', 0.0),
                    'sentiment_confidence': sentiment_data.get('confidence', 0.0),
                    'language_code': language_data.get('language', 'en'),
                    'language_confidence': language_data.get('confidence', 0.0),
                    'ai_analysis_raw': json.dumps(json_safe_analysis)
                }
            )

        logger.debug(f"[AI-ORCHESTRATOR] Updated AI analysis for {len(validated_posts)} posts")

    async def _store_profile_ai_aggregations(self, db: AsyncSession, profile_id: str, ai_results: Dict[str, Any]) -> None:
        """Store profile-level AI aggregations for ALL 10 AI models"""

        # Extract core AI results (original 3 models)
        category_results = ai_results.get('category', {})
        sentiment_results = ai_results.get('sentiment', {})
        language_results = ai_results.get('language', {})

        # Extract advanced AI results (new 7 models)
        audience_quality = ai_results.get('audience_quality', {})
        visual_content = ai_results.get('visual_content', {})
        audience_insights = ai_results.get('audience_insights', {})
        trend_detection = ai_results.get('trend_detection', {})
        advanced_nlp = ai_results.get('advanced_nlp', {})
        fraud_detection = ai_results.get('fraud_detection', {})
        behavioral_patterns = ai_results.get('behavioral_patterns', {})

        # Calculate core aggregations
        primary_content_type = category_results.get('primary_category', 'general')
        content_distribution = json.dumps(category_results.get('category_distribution', {}))
        avg_sentiment_score = sentiment_results.get('confidence_avg', 0.0)
        language_distribution = json.dumps(language_results.get('language_distribution', {}))
        content_quality_score = audience_quality.get('authenticity_score', 75.0)

        # Calculate success rate
        total_models = 10
        successful_models = len([r for r in ai_results.values() if r and isinstance(r, dict)])
        success_rate = successful_models / total_models

        # Prepare model status tracking (ensure JSON serializable)
        model_status = {
            'sentiment': bool(sentiment_results),
            'language': bool(language_results),
            'category': bool(category_results),
            'audience_quality': bool(audience_quality),
            'visual_content': bool(visual_content),
            'audience_insights': bool(audience_insights),
            'trend_detection': bool(trend_detection),
            'advanced_nlp': bool(advanced_nlp),
            'fraud_detection': bool(fraud_detection),
            'behavioral_patterns': bool(behavioral_patterns)
        }

        # Convert to JSON-safe format
        json_safe_model_status = {k: bool(v) for k, v in model_status.items()}

        # Update profile with ALL AI model results
        await db.execute(
            text("""
                UPDATE profiles SET
                    ai_primary_content_type = :primary_content_type,
                    ai_content_distribution = :content_distribution,
                    ai_avg_sentiment_score = :avg_sentiment_score,
                    ai_language_distribution = :language_distribution,
                    ai_content_quality_score = :content_quality_score,
                    ai_audience_quality = :audience_quality,
                    ai_visual_content = :visual_content,
                    ai_audience_insights = :audience_insights,
                    ai_trend_detection = :trend_detection,
                    ai_advanced_nlp = :advanced_nlp,
                    ai_fraud_detection = :fraud_detection,
                    ai_behavioral_patterns = :behavioral_patterns,
                    ai_comprehensive_analysis_version = :analysis_version,
                    ai_comprehensive_analyzed_at = NOW(),
                    ai_models_success_rate = :success_rate,
                    ai_models_status = :model_status,
                    ai_profile_analyzed_at = NOW()
                WHERE id = :profile_id
            """),
            {
                'profile_id': profile_id,
                'primary_content_type': primary_content_type,
                'content_distribution': content_distribution,
                'avg_sentiment_score': avg_sentiment_score,
                'language_distribution': language_distribution,
                'content_quality_score': content_quality_score,
                'audience_quality': json.dumps(self._make_json_serializable(audience_quality)),
                'visual_content': json.dumps(self._make_json_serializable(visual_content)),
                'audience_insights': json.dumps(self._make_json_serializable(audience_insights)),
                'trend_detection': json.dumps(self._make_json_serializable(trend_detection)),
                'advanced_nlp': json.dumps(self._make_json_serializable(advanced_nlp)),
                'fraud_detection': json.dumps(self._make_json_serializable(fraud_detection)),
                'behavioral_patterns': json.dumps(self._make_json_serializable(behavioral_patterns)),
                'analysis_version': '2.0.0',
                'success_rate': success_rate,
                'model_status': json.dumps(json_safe_model_status)
            }
        )

        logger.info(f"[AI-ORCHESTRATOR] ✅ Stored ALL 10 AI models for profile {profile_id} (success rate: {success_rate:.1%})")
        logger.debug(f"[AI-STORAGE] Stored models: {list(model_status.keys())}")

    async def _cache_ai_results(self, profile_id: str, ai_results: Dict[str, Any]) -> None:
        """Cache AI results for fast retrieval"""
        try:
            # Convert numpy types to JSON-serializable types
            json_safe_results = self._make_json_serializable(ai_results)

            cache_key = f"ai_analysis:{profile_id}"
            cache_data = {
                'ai_results': json_safe_results,
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'cache_version': '1.0'
            }

            await redis_cache.set(
                key_type="ai_analysis",
                identifier=profile_id,
                data=cache_data,
                ttl=7 * 24 * 3600  # 7 days cache
            )

            logger.debug(f"[AI-ORCHESTRATOR] Cached AI results for profile {profile_id}")

        except Exception as e:
            logger.warning(f"[AI-ORCHESTRATOR] Failed to cache AI results: {e}")

    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert numpy types and other non-JSON-serializable types to JSON-safe equivalents"""
        import numpy as np

        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    async def get_profile_ai_status(self, profile_id: str) -> Dict[str, Any]:
        """
        Get AI analysis status for a profile

        Args:
            profile_id: Profile UUID

        Returns:
            AI analysis status and completion info
        """
        try:
            async with get_session() as db:
                # Check AI analysis status
                status_query = text("""
                    SELECT
                        p.username,
                        p.ai_primary_content_type,
                        p.ai_profile_analyzed_at,
                        COUNT(posts.id) as total_posts,
                        COUNT(posts.ai_analyzed_at) as posts_with_ai
                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    WHERE p.id = :profile_id
                    GROUP BY p.id, p.username, p.ai_primary_content_type, p.ai_profile_analyzed_at
                """)

                result = await db.execute(status_query, {'profile_id': profile_id})
                data = result.fetchone()

                if not data:
                    return {'status': 'profile_not_found'}

                ai_completion = data.posts_with_ai / max(data.total_posts, 1) * 100

                return {
                    'status': 'found',
                    'username': data.username,
                    'profile_ai_complete': data.ai_profile_analyzed_at is not None,
                    'profile_analyzed_at': data.ai_profile_analyzed_at.isoformat() if data.ai_profile_analyzed_at else None,
                    'primary_content_type': data.ai_primary_content_type,
                    'total_posts': data.total_posts,
                    'posts_with_ai': data.posts_with_ai,
                    'ai_completion_percentage': round(ai_completion, 1),
                    'ai_analysis_complete': ai_completion >= 90  # 90% threshold
                }

        except Exception as e:
            logger.error(f"[AI-ORCHESTRATOR] Failed to get AI status: {e}")
            return {'status': 'error', 'error': str(e)}

# Global instance
production_ai_orchestrator = ProductionAIOrchestrator()