"""
Unified Background Processor - Production-Grade Processing Pipeline
Coordinates Apify → CDN → AI workflow with perfect sequencing
"""
import asyncio
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from enum import Enum

from app.services.comprehensive_cdn_service import comprehensive_cdn_service
from app.services.ai.production_ai_orchestrator import production_ai_orchestrator
from app.database.connection import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ProcessingStage(Enum):
    """Processing stages in correct order"""
    APIFY_COMPLETE = "apify_complete"
    CDN_PROCESSING = "cdn_processing"
    CDN_COMPLETE = "cdn_complete"
    AI_PROCESSING = "ai_processing"
    AI_COMPLETE = "ai_complete"
    FULLY_COMPLETE = "fully_complete"

class ProcessingStatus(Enum):
    """Processing status states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class UnifiedBackgroundProcessor:
    """
    Unified background processor managing the complete workflow:
    1. Apify API data storage (handled by main app)
    2. CDN image processing and R2 upload
    3. AI analysis with all 10 models
    """

    def __init__(self):
        self.cdn_service = comprehensive_cdn_service
        self.ai_orchestrator = production_ai_orchestrator
        self.max_processing_time = 600  # 10 minutes max

    async def initialize_system(self) -> Dict[str, Any]:
        """
        Initialize the unified processing system

        Returns:
            System initialization status
        """
        logger.info("[UNIFIED-PROCESSOR] Initializing complete background processing system")

        initialization_results = {
            'ai_system': False,
            'cdn_system': True,  # CDN system is always ready
            'overall_ready': False,
            'initialized_at': datetime.now(timezone.utc)
        }

        try:
            # Initialize AI system (all 10 models)
            ai_status = await self.ai_orchestrator.initialize_ai_system()
            initialization_results['ai_system'] = sum(ai_status.values()) >= 7  # 70% success threshold
            initialization_results['ai_details'] = ai_status

            # Overall system ready if core components are initialized
            initialization_results['overall_ready'] = initialization_results['ai_system'] and initialization_results['cdn_system']

            logger.info(f"[UNIFIED-PROCESSOR] System initialization complete. Ready: {initialization_results['overall_ready']}")

            return initialization_results

        except Exception as e:
            logger.error(f"[UNIFIED-PROCESSOR] System initialization failed: {e}")
            initialization_results['error'] = str(e)
            return initialization_results

    async def process_profile_complete_pipeline(self, profile_id: str, username: str) -> Dict[str, Any]:
        """
        Execute complete processing pipeline for a profile
        CRITICAL: Only starts AFTER Apify data is 100% stored

        Workflow:
        1. Verify Apify data is complete
        2. Process CDN images (download → optimize → R2 upload)
        3. Execute AI analysis with all 10 models
        4. Store all results in database

        Args:
            profile_id: Profile UUID in database
            username: Instagram username

        Returns:
            Complete processing results
        """
        pipeline_id = str(uuid.uuid4())
        logger.info(f"[UNIFIED-PROCESSOR] Starting complete pipeline for {username} (Profile: {profile_id})")

        pipeline_results = {
            'pipeline_id': pipeline_id,
            'profile_id': profile_id,
            'username': username,
            'started_at': datetime.now(timezone.utc),
            'completed_at': None,
            'current_stage': ProcessingStage.APIFY_COMPLETE.value,
            'stages': {
                'apify_verification': {'status': ProcessingStatus.PENDING.value, 'started_at': None, 'completed_at': None},
                'cdn_processing': {'status': ProcessingStatus.PENDING.value, 'started_at': None, 'completed_at': None},
                'ai_processing': {'status': ProcessingStatus.PENDING.value, 'started_at': None, 'completed_at': None}
            },
            'results': {
                'apify_data': {},
                'cdn_results': {},
                'ai_results': {}
            },
            'overall_success': False,
            'errors': []
        }

        try:
            # STAGE 1: Verify Apify data is complete
            logger.info(f"[UNIFIED-PROCESSOR] Stage 1: Verifying Apify data for {username}")
            pipeline_results['stages']['apify_verification']['started_at'] = datetime.now(timezone.utc)
            pipeline_results['stages']['apify_verification']['status'] = ProcessingStatus.PROCESSING.value

            apify_verification = await self._verify_apify_data_complete(profile_id)
            pipeline_results['results']['apify_data'] = apify_verification

            if not apify_verification['complete']:
                raise Exception(f"Apify data incomplete: {apify_verification['missing']}")

            pipeline_results['stages']['apify_verification']['status'] = ProcessingStatus.COMPLETED.value
            pipeline_results['stages']['apify_verification']['completed_at'] = datetime.now(timezone.utc)
            pipeline_results['current_stage'] = ProcessingStage.CDN_PROCESSING.value

            logger.info(f"[UNIFIED-PROCESSOR] Stage 1 complete: Apify data verified for {username}")

            # STAGE 2: Process CDN images
            logger.info(f"[UNIFIED-PROCESSOR] Stage 2: Processing CDN images for {username}")
            pipeline_results['stages']['cdn_processing']['started_at'] = datetime.now(timezone.utc)
            pipeline_results['stages']['cdn_processing']['status'] = ProcessingStatus.PROCESSING.value

            cdn_results = await self.cdn_service.process_profile_images_comprehensive(profile_id, username)
            pipeline_results['results']['cdn_results'] = cdn_results

            if not cdn_results['success']:
                logger.warning(f"[UNIFIED-PROCESSOR] CDN processing had issues for {username}, but continuing to AI")

            pipeline_results['stages']['cdn_processing']['status'] = ProcessingStatus.COMPLETED.value
            pipeline_results['stages']['cdn_processing']['completed_at'] = datetime.now(timezone.utc)
            pipeline_results['current_stage'] = ProcessingStage.AI_PROCESSING.value

            logger.info(f"[UNIFIED-PROCESSOR] Stage 2 complete: CDN processing for {username}")
            logger.info(f"[CDN-SUMMARY] Processed {cdn_results['processed_images']}/{cdn_results['total_images']} images")

            # STAGE 3: Execute AI analysis (all 10 models)
            logger.info(f"[UNIFIED-PROCESSOR] Stage 3: Executing AI analysis for {username}")
            pipeline_results['stages']['ai_processing']['started_at'] = datetime.now(timezone.utc)
            pipeline_results['stages']['ai_processing']['status'] = ProcessingStatus.PROCESSING.value

            ai_results = await self.ai_orchestrator.process_profile_complete_ai_analysis(profile_id, username)
            pipeline_results['results']['ai_results'] = ai_results

            if not ai_results['success']:
                logger.warning(f"[UNIFIED-PROCESSOR] AI processing had issues for {username}")

            pipeline_results['stages']['ai_processing']['status'] = ProcessingStatus.COMPLETED.value
            pipeline_results['stages']['ai_processing']['completed_at'] = datetime.now(timezone.utc)
            pipeline_results['current_stage'] = ProcessingStage.FULLY_COMPLETE.value

            # STAGE 4: Final completion
            pipeline_results['completed_at'] = datetime.now(timezone.utc)
            pipeline_results['overall_success'] = (
                cdn_results['success'] and ai_results['success']
            )

            processing_duration = (pipeline_results['completed_at'] - pipeline_results['started_at']).total_seconds()

            logger.info(f"[UNIFIED-PROCESSOR] Pipeline complete for {username} in {processing_duration:.1f}s")
            logger.info(f"[PIPELINE-SUMMARY] CDN: {cdn_results['processed_images']} images, AI: {ai_results['completed_models']}/10 models")

            # Store pipeline completion record
            await self._store_pipeline_completion(pipeline_results)

            return pipeline_results

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[UNIFIED-PROCESSOR] Pipeline failed for {username}: {error_msg}")

            pipeline_results['errors'].append(error_msg)
            pipeline_results['completed_at'] = datetime.now(timezone.utc)
            pipeline_results['overall_success'] = False

            # Mark current stage as failed
            for stage_name, stage_data in pipeline_results['stages'].items():
                if stage_data['status'] == ProcessingStatus.PROCESSING.value:
                    stage_data['status'] = ProcessingStatus.FAILED.value
                    stage_data['completed_at'] = datetime.now(timezone.utc)
                    break

            return pipeline_results

    async def _verify_apify_data_complete(self, profile_id: str) -> Dict[str, Any]:
        """
        Verify that Apify API data is completely stored in database

        Args:
            profile_id: Profile UUID

        Returns:
            Verification results
        """
        try:
            async with get_session() as db:
                # Check profile completeness
                profile_check = text("""
                    SELECT
                        p.id,
                        p.username,
                        p.full_name,
                        p.biography,
                        p.followers_count,
                        p.following_count,
                        p.posts_count,
                        p.profile_pic_url_hd,
                        COUNT(posts.id) as stored_posts_count,
                        COUNT(rp.id) as related_profiles_count
                    FROM profiles p
                    LEFT JOIN posts ON posts.profile_id = p.id
                    LEFT JOIN related_profiles rp ON rp.profile_id = p.id
                    WHERE p.id = :profile_id
                    GROUP BY p.id, p.username, p.full_name, p.biography, p.followers_count,
                             p.following_count, p.posts_count, p.profile_pic_url_hd
                """)

                result = await db.execute(profile_check, {'profile_id': profile_id})
                data = result.fetchone()

                if not data:
                    return {
                        'complete': False,
                        'missing': ['profile_not_found'],
                        'details': {}
                    }

                missing = []

                # Check essential profile data
                if not data.username:
                    missing.append('username_missing')
                if not data.followers_count or data.followers_count == 0:
                    missing.append('followers_count_missing')
                if not data.posts_count or data.posts_count == 0:
                    missing.append('posts_count_missing')

                # Check posts are stored
                if data.stored_posts_count == 0:
                    missing.append('no_posts_stored')
                elif data.stored_posts_count < min(data.posts_count or 0, 12):  # Expect at least 12 posts or all posts
                    missing.append(f'insufficient_posts_stored_{data.stored_posts_count}_of_{data.posts_count}')

                # Check related profiles (should have some)
                if data.related_profiles_count == 0:
                    missing.append('no_related_profiles')

                is_complete = len(missing) == 0

                return {
                    'complete': is_complete,
                    'missing': missing,
                    'details': {
                        'username': data.username,
                        'followers_count': data.followers_count,
                        'posts_count': data.posts_count,
                        'stored_posts_count': data.stored_posts_count,
                        'related_profiles_count': data.related_profiles_count,
                        'has_profile_pic': bool(data.profile_pic_url_hd),
                        'has_biography': bool(data.biography)
                    }
                }

        except Exception as e:
            logger.error(f"[UNIFIED-PROCESSOR] Apify verification failed: {e}")
            return {
                'complete': False,
                'missing': [f'verification_error_{str(e)}'],
                'details': {}
            }

    async def _store_pipeline_completion(self, pipeline_results: Dict[str, Any]) -> None:
        """Store pipeline completion record for monitoring"""
        try:
            async with get_session() as db:
                # Store in processing stats or create a pipeline tracking table
                pipeline_data = {
                    'pipeline_id': pipeline_results['pipeline_id'],
                    'profile_id': pipeline_results['profile_id'],
                    'username': pipeline_results['username'],
                    'overall_success': pipeline_results['overall_success'],
                    'processing_duration': (pipeline_results['completed_at'] - pipeline_results['started_at']).total_seconds(),
                    'cdn_images_processed': pipeline_results['results']['cdn_results'].get('processed_images', 0),
                    'ai_models_completed': pipeline_results['results']['ai_results'].get('completed_models', 0),
                    'errors_count': len(pipeline_results['errors']),
                    'created_at': pipeline_results['started_at']
                }

                # For now, store in cdn_processing_stats as extended record
                await db.execute(
                    text("""
                        INSERT INTO cdn_processing_stats
                        (processing_id, profile_id, username, total_images, processed_images,
                         failed_images, processing_duration, success_rate, cdn_urls_count,
                         errors_count, created_at)
                        VALUES
                        (:processing_id, :profile_id, :username, :total_images, :processed_images,
                         0, :processing_duration, :success_rate, :cdn_urls_count, :errors_count, :created_at)
                    """),
                    {
                        'processing_id': pipeline_data['pipeline_id'],
                        'profile_id': pipeline_data['profile_id'],
                        'username': pipeline_data['username'],
                        'total_images': pipeline_results['results']['cdn_results'].get('total_images', 0),
                        'processed_images': pipeline_data['cdn_images_processed'],
                        'processing_duration': pipeline_data['processing_duration'],
                        'success_rate': 1.0 if pipeline_data['overall_success'] else 0.0,
                        'cdn_urls_count': len(pipeline_results['results']['cdn_results'].get('cdn_urls_created', [])),
                        'errors_count': pipeline_data['errors_count'],
                        'created_at': pipeline_data['created_at']
                    }
                )

                await db.commit()
                logger.debug(f"[UNIFIED-PROCESSOR] Stored pipeline completion for {pipeline_results['username']}")

        except Exception as e:
            logger.warning(f"[UNIFIED-PROCESSOR] Failed to store pipeline completion: {e}")

    async def get_profile_processing_status(self, profile_id: str) -> Dict[str, Any]:
        """
        Get comprehensive processing status for a profile

        Args:
            profile_id: Profile UUID

        Returns:
            Complete processing status across all stages
        """
        try:
            # Get Apify data status
            apify_status = await self._verify_apify_data_complete(profile_id)

            # Get CDN processing status
            cdn_status = await self.cdn_service.get_profile_cdn_status(profile_id)

            # Get AI processing status
            ai_status = await self.ai_orchestrator.get_profile_ai_status(profile_id)

            # Determine overall stage
            current_stage = ProcessingStage.APIFY_COMPLETE.value
            if apify_status['complete']:
                if cdn_status.get('cdn_processing_complete', False):
                    if ai_status.get('ai_analysis_complete', False):
                        current_stage = ProcessingStage.FULLY_COMPLETE.value
                    else:
                        current_stage = ProcessingStage.AI_PROCESSING.value
                else:
                    current_stage = ProcessingStage.CDN_PROCESSING.value

            overall_complete = (
                apify_status['complete'] and
                cdn_status.get('cdn_processing_complete', False) and
                ai_status.get('ai_analysis_complete', False)
            )

            return {
                'profile_id': profile_id,
                'username': apify_status.get('details', {}).get('username', 'unknown'),
                'current_stage': current_stage,
                'overall_complete': overall_complete,
                'stages': {
                    'apify': apify_status,
                    'cdn': cdn_status,
                    'ai': ai_status
                },
                'completion_summary': {
                    'apify_complete': apify_status['complete'],
                    'cdn_complete': cdn_status.get('cdn_processing_complete', False),
                    'ai_complete': ai_status.get('ai_analysis_complete', False),
                    'cdn_completion_pct': cdn_status.get('cdn_completion_percentage', 0),
                    'ai_completion_pct': ai_status.get('ai_completion_percentage', 0)
                }
            }

        except Exception as e:
            logger.error(f"[UNIFIED-PROCESSOR] Failed to get processing status: {e}")
            return {
                'profile_id': profile_id,
                'error': str(e),
                'current_stage': 'error',
                'overall_complete': False
            }

# Global instance
unified_background_processor = UnifiedBackgroundProcessor()