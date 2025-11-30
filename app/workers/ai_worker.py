"""
AI-Specific Worker Service - Optimized for CPU/GPU Intensive Tasks
Handles AI model inference, batch processing, and resource-intensive computations
"""
import os
import logging
import json
import asyncio
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery import Celery
from sqlalchemy import text

from app.core.job_queue import job_queue, JobStatus
from app.database.optimized_pools import optimized_pools
from app.services.ai_services.ai_content_analyzer import AIContentAnalyzer
from app.services.ai_services.ai_sentiment_analyzer import AISentimentAnalyzer
from app.services.ai_services.ai_language_detector import AILanguageDetector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# AI WORKER CELERY CONFIGURATION
# ============================================================================

# Redis configuration optimized for AI workloads
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')

# Create AI-specific Celery app
ai_celery_app = Celery(
    'ai_worker',
    broker=redis_url,
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=['app.workers.ai_worker']
)

# AI worker configuration optimized for heavy computations
ai_celery_app.conf.update(
    # Task routing for AI operations
    task_routes={
        'ai_worker.process_ai_batch_analysis': {'queue': 'ai_heavy'},
        'ai_worker.process_single_post_ai': {'queue': 'ai_fast'},
        'ai_worker.process_model_warmup': {'queue': 'ai_maintenance'},
        'ai_worker.process_ai_health_check': {'queue': 'ai_maintenance'},
    },

    # AI worker optimization
    worker_prefetch_multiplier=1,  # Critical for memory management
    worker_max_tasks_per_child=50,  # Restart to prevent memory leaks
    task_acks_late=True,
    worker_disable_rate_limits=False,

    # AI-specific timeouts
    task_soft_time_limit=600,   # 10 minutes soft limit
    task_time_limit=900,        # 15 minutes hard limit
    task_track_started=True,

    # Memory and resource management
    worker_max_memory_per_child=2048000,  # 2GB max memory per worker

    # Queue configuration
    task_default_queue='ai_fast',
    task_default_exchange='ai_tasks',
    task_default_exchange_type='direct',

    # Monitoring for AI workers
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# ============================================================================
# AI MODEL MANAGEMENT
# ============================================================================

class AIModelManager:
    """Manages AI model lifecycle and resource optimization"""

    def __init__(self):
        self.models_loaded = False
        self.model_cache = {}
        self.last_activity = datetime.now(timezone.utc)
        self.warmup_lock = asyncio.Lock()

    async def ensure_models_loaded(self) -> None:
        """Ensure all AI models are loaded and warmed up"""
        if self.models_loaded:
            self.last_activity = datetime.now(timezone.utc)
            return

        async with self.warmup_lock:
            if self.models_loaded:  # Double-check after acquiring lock
                return

            logger.info("Loading AI models for worker...")

            try:
                # Initialize AI services (they handle their own model loading)
                self.content_analyzer = AIContentAnalyzer()
                self.sentiment_analyzer = AISentimentAnalyzer()
                self.language_detector = AILanguageDetector()

                # Warm up models with test data
                await self._warmup_models()

                self.models_loaded = True
                self.last_activity = datetime.now(timezone.utc)
                logger.info("AI models loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load AI models: {e}")
                raise

    async def _warmup_models(self) -> None:
        """Warm up all models with test inputs"""
        warmup_texts = [
            "This is a test post for model warmup",
            "Another test to ensure models are ready",
            "Final warmup text for AI models"
        ]

        for text in warmup_texts:
            try:
                # Warm up each model
                await self.content_analyzer.analyze_content(text)
                await self.sentiment_analyzer.analyze_sentiment(text)
                await self.language_detector.detect_language(text)
            except Exception as e:
                logger.warning(f"Model warmup warning: {e}")

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics"""
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }

    def should_restart_worker(self) -> bool:
        """Determine if worker should restart due to resource usage"""
        memory_stats = self.get_memory_usage()

        # Restart if using more than 1.5GB RSS or 80% of system memory
        if memory_stats['rss_mb'] > 1536 or memory_stats['percent'] > 80:
            logger.warning(f"Worker memory usage high: {memory_stats}")
            return True

        return False

# Global AI model manager
ai_model_manager = AIModelManager()

# ============================================================================
# AI JOB PROCESSOR
# ============================================================================

class AIJobProcessor:
    """Specialized job processor for AI tasks"""

    def __init__(self):
        self.model_manager = ai_model_manager

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress_percent: Optional[int] = None,
        progress_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        ai_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update AI job status with additional metrics"""
        try:
            async with optimized_pools.get_ai_session() as session:
                update_data = {
                    'job_id': job_id,
                    'status': status.value,
                    'updated_at': datetime.now(timezone.utc)
                }

                if progress_percent is not None:
                    update_data['progress_percent'] = progress_percent
                if progress_message:
                    update_data['progress_message'] = progress_message

                # Add AI-specific metrics to result
                if result and ai_metrics:
                    result['ai_metrics'] = ai_metrics

                if result:
                    update_data['result'] = json.dumps(result)
                if error_details:
                    update_data['error_details'] = json.dumps(error_details)
                if status == JobStatus.PROCESSING:
                    update_data['started_at'] = datetime.now(timezone.utc)
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    update_data['completed_at'] = datetime.now(timezone.utc)

                # Build dynamic UPDATE query
                set_clause = ', '.join([f"{key} = :{key}" for key in update_data.keys() if key != 'job_id'])

                await session.execute(text(f"""
                    UPDATE job_queue SET {set_clause}
                    WHERE id = :job_id
                """).execution_options(prepare=False), update_data)

                await session.commit()

        except Exception as e:
            logger.error(f"Failed to update AI job {job_id} status: {e}")

    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get AI job details"""
        try:
            async with optimized_pools.get_ai_session() as session:
                result = await session.execute(text("""
                    SELECT id, user_id, job_type, params, status, priority, created_at
                    FROM job_queue WHERE id = :job_id
                """).execution_options(prepare=False), {'job_id': job_id})

                job_data = result.fetchone()
                if not job_data:
                    return None

                return {
                    'id': job_data.id,
                    'user_id': job_data.user_id,
                    'job_type': job_data.job_type,
                    'params': json.loads(job_data.params) if job_data.params else {},
                    'status': job_data.status,
                    'priority': job_data.priority,
                    'created_at': job_data.created_at
                }

        except Exception as e:
            logger.error(f"Failed to get AI job details for {job_id}: {e}")
            return None

# Global AI job processor
ai_job_processor = AIJobProcessor()

# ============================================================================
# AI CELERY TASKS
# ============================================================================

@ai_celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def process_ai_batch_analysis(self, job_id: str):
    """Process batch AI analysis for multiple posts"""

    try:
        logger.info(f"Starting AI batch analysis job {job_id}")

        # Check memory before starting
        if ai_model_manager.should_restart_worker():
            logger.warning("Worker memory usage too high, rejecting task")
            raise Exception("Worker memory usage too high")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_ai_batch_analysis_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"AI batch analysis job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                ai_job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e), 'memory_stats': ai_model_manager.get_memory_usage()}
                )
            )
        finally:
            loop.close()

        # Retry with longer delay for AI tasks
        if self.request.retries < self.max_retries:
            retry_delay = 120 * (2 ** self.request.retries)  # 2min, 4min
            logger.info(f"Retrying AI job {job_id} in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)

        raise

async def _process_ai_batch_analysis_async(job_id: str) -> Dict[str, Any]:
    """Async implementation of AI batch analysis"""

    # Ensure models are loaded
    await ai_model_manager.ensure_models_loaded()

    job_details = await ai_job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"AI job {job_id} not found")

    params = job_details['params']
    profile_id = params.get('profile_id')
    batch_size = params.get('batch_size', 10)

    await ai_job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=0,
        progress_message="Loading posts for AI analysis"
    )

    try:
        # Get posts that need AI analysis
        async with optimized_pools.get_ai_session() as session:
            result = await session.execute(text("""
                SELECT id, caption, likes_count, comments_count
                FROM posts
                WHERE profile_id = :profile_id
                AND ai_analyzed_at IS NULL
                ORDER BY created_at DESC
                LIMIT :batch_size
            """).execution_options(prepare=False), {
                'profile_id': profile_id,
                'batch_size': batch_size
            })

            posts_to_analyze = result.fetchall()

        if not posts_to_analyze:
            return {'message': 'No posts require AI analysis', 'posts_processed': 0}

        # Process posts in parallel batches for efficiency
        batch_results = []
        total_posts = len(posts_to_analyze)

        # Process in smaller chunks to manage memory
        chunk_size = min(5, total_posts)  # Process 5 posts at a time

        for i in range(0, total_posts, chunk_size):
            chunk = posts_to_analyze[i:i + chunk_size]

            # Update progress
            progress = int((i / total_posts) * 90)
            await ai_job_processor.update_job_status(
                job_id, JobStatus.PROCESSING,
                progress_percent=progress,
                progress_message=f"Processing AI analysis {i+1}-{min(i+chunk_size, total_posts)}/{total_posts}"
            )

            # Process chunk in parallel
            chunk_results = await _process_posts_chunk(chunk)
            batch_results.extend(chunk_results)

            # Update database with chunk results
            await _update_posts_ai_analysis(chunk_results)

            # Small delay between chunks to prevent overload
            await asyncio.sleep(1)

        # Calculate metrics
        successful_analyses = len([r for r in batch_results if r.get('success')])
        ai_metrics = {
            'total_posts': total_posts,
            'successful_analyses': successful_analyses,
            'memory_usage': ai_model_manager.get_memory_usage(),
            'processing_time_per_post': len(batch_results) and (datetime.now(timezone.utc) - job_details['created_at']).total_seconds() / len(batch_results) or 0
        }

        result = {
            'posts_processed': total_posts,
            'successful_analyses': successful_analyses,
            'failed_analyses': total_posts - successful_analyses,
            'completion_time': datetime.now(timezone.utc).isoformat()
        }

        await ai_job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message=f"AI analysis completed: {successful_analyses}/{total_posts} successful",
            result=result,
            ai_metrics=ai_metrics
        )

        return result

    except Exception as e:
        logger.error(f"AI batch analysis failed: {e}")
        raise

async def _process_posts_chunk(posts_chunk: List) -> List[Dict[str, Any]]:
    """Process a chunk of posts with parallel AI analysis"""

    results = []

    # Use ThreadPoolExecutor for CPU-bound AI operations
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_to_post = {}

        for post in posts_chunk:
            future = executor.submit(_analyze_single_post_sync, post)
            future_to_post[future] = post

        # Collect results as they complete
        for future in as_completed(future_to_post):
            post = future_to_post[future]
            try:
                result = future.result(timeout=30)  # 30 second timeout per post
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze post {post.id}: {e}")
                results.append({
                    'post_id': post.id,
                    'success': False,
                    'error': str(e)
                })

    return results

def _analyze_single_post_sync(post) -> Dict[str, Any]:
    """Synchronous AI analysis for single post (runs in thread)"""
    try:
        caption = post.caption or ""

        # Perform AI analysis (synchronous versions)
        content_result = ai_model_manager.content_analyzer.analyze_content_sync(caption)
        sentiment_result = ai_model_manager.sentiment_analyzer.analyze_sentiment_sync(caption)
        language_result = ai_model_manager.language_detector.detect_language_sync(caption)

        return {
            'post_id': post.id,
            'success': True,
            'ai_content_category': content_result.get('category'),
            'ai_category_confidence': content_result.get('confidence'),
            'ai_sentiment': sentiment_result.get('sentiment'),
            'ai_sentiment_score': sentiment_result.get('score'),
            'ai_sentiment_confidence': sentiment_result.get('confidence'),
            'ai_language_code': language_result.get('language'),
            'ai_language_confidence': language_result.get('confidence'),
            'analysis_timestamp': datetime.now(timezone.utc)
        }

    except Exception as e:
        return {
            'post_id': post.id,
            'success': False,
            'error': str(e)
        }

async def _update_posts_ai_analysis(analysis_results: List[Dict[str, Any]]) -> None:
    """Update database with AI analysis results"""

    async with optimized_pools.get_ai_session() as session:
        for result in analysis_results:
            if result.get('success'):
                try:
                    await session.execute(text("""
                        UPDATE posts SET
                            ai_content_category = :category,
                            ai_category_confidence = :category_confidence,
                            ai_sentiment = :sentiment,
                            ai_sentiment_score = :sentiment_score,
                            ai_sentiment_confidence = :sentiment_confidence,
                            ai_language_code = :language_code,
                            ai_language_confidence = :language_confidence,
                            ai_analyzed_at = :analyzed_at
                        WHERE id = :post_id
                    """).execution_options(prepare=False), {
                        'category': result.get('ai_content_category'),
                        'category_confidence': result.get('ai_category_confidence'),
                        'sentiment': result.get('ai_sentiment'),
                        'sentiment_score': result.get('ai_sentiment_score'),
                        'sentiment_confidence': result.get('ai_sentiment_confidence'),
                        'language_code': result.get('ai_language_code'),
                        'language_confidence': result.get('ai_language_confidence'),
                        'analyzed_at': result.get('analysis_timestamp'),
                        'post_id': result.get('post_id')
                    })
                except Exception as e:
                    logger.error(f"Failed to update post {result.get('post_id')} AI analysis: {e}")

        await session.commit()

# ============================================================================
# SINGLE POST AI ANALYSIS
# ============================================================================

@ai_celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_single_post_ai(self, job_id: str):
    """Process AI analysis for a single post (fast lane)"""

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_process_single_post_ai_async(job_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Single post AI job {job_id} failed: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                ai_job_processor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_details={'error': str(e)}
                )
            )
        finally:
            loop.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)

        raise

async def _process_single_post_ai_async(job_id: str) -> Dict[str, Any]:
    """Fast AI analysis for single post"""

    await ai_model_manager.ensure_models_loaded()

    job_details = await ai_job_processor.get_job_details(job_id)
    if not job_details:
        raise Exception(f"AI job {job_id} not found")

    params = job_details['params']
    post_id = params.get('post_id')
    caption = params.get('caption', '')

    await ai_job_processor.update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress_percent=20,
        progress_message="Analyzing post with AI models"
    )

    try:
        # Fast AI analysis
        analysis_result = _analyze_single_post_sync({'id': post_id, 'caption': caption})

        if analysis_result.get('success'):
            # Update database
            await _update_posts_ai_analysis([analysis_result])

        result = {
            'post_id': post_id,
            'analysis_successful': analysis_result.get('success'),
            'ai_category': analysis_result.get('ai_content_category'),
            'ai_sentiment': analysis_result.get('ai_sentiment'),
            'ai_language': analysis_result.get('ai_language_code'),
            'completion_time': datetime.now(timezone.utc).isoformat()
        }

        await ai_job_processor.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Single post AI analysis completed",
            result=result,
            ai_metrics={'processing_type': 'single_post', 'memory_usage': ai_model_manager.get_memory_usage()}
        )

        return result

    except Exception as e:
        logger.error(f"Single post AI analysis failed: {e}")
        raise

# ============================================================================
# AI WORKER MAINTENANCE TASKS
# ============================================================================

@ai_celery_app.task
def process_model_warmup():
    """Warm up AI models (maintenance task)"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(ai_model_manager.ensure_models_loaded())
            return {
                'status': 'models_warmed_up',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'memory_usage': ai_model_manager.get_memory_usage()
            }
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Model warmup failed: {e}")
        return {'status': 'warmup_failed', 'error': str(e)}

@ai_celery_app.task
def process_ai_health_check():
    """AI worker health check with model validation"""
    try:
        memory_stats = ai_model_manager.get_memory_usage()

        return {
            'status': 'healthy',
            'models_loaded': ai_model_manager.models_loaded,
            'memory_usage_mb': memory_stats['rss_mb'],
            'memory_percent': memory_stats['percent'],
            'should_restart': ai_model_manager.should_restart_worker(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'worker_id': os.getpid()
        }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# ============================================================================
# AI WORKER STARTUP
# ============================================================================

if __name__ == '__main__':
    # Start AI worker when run directly
    ai_celery_app.start(['worker', '--loglevel=info', '--concurrency=2', '--pool=prefork'])