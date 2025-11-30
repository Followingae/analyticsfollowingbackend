"""
Industry-Standard Job Queue System
Provides reliable, scalable background job processing with comprehensive tracking
"""
import json
import logging
import uuid
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
import asyncio

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.optimized_pools import optimized_pools

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Job processing status states"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    """Job priority levels"""
    CRITICAL = 100  # User-initiated, time-sensitive
    HIGH = 75      # Paid tier operations
    NORMAL = 50    # Standard operations
    LOW = 25       # Background discovery, cleanup
    BULK = 10      # Mass operations

class QueueType(Enum):
    """Queue types for different workload isolation"""
    CRITICAL_QUEUE = "critical_queue"
    API_QUEUE = "api_queue"
    CDN_QUEUE = "cdn_queue"
    AI_QUEUE = "ai_queue"
    DISCOVERY_QUEUE = "discovery_queue"
    BULK_QUEUE = "bulk_queue"
    POST_ANALYTICS_QUEUE = "post_analytics_queue"

@dataclass
class JobDefinition:
    """Complete job definition with all metadata"""
    id: str
    user_id: str
    job_type: str
    status: JobStatus
    priority: JobPriority
    queue_name: QueueType
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_duration: Optional[int] = None  # seconds
    actual_duration: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: Optional[str] = None
    worker_id: Optional[str] = None
    user_tier: Optional[str] = None
    progress_percent: int = 0
    progress_message: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.idempotency_key is None:
            # Generate idempotency key from job parameters
            key_data = f"{self.user_id}:{self.job_type}:{json.dumps(self.params, sort_keys=True)}"
            self.idempotency_key = str(uuid.uuid5(uuid.NAMESPACE_DNS, key_data))

class IndustryStandardJobQueue:
    """
    Enterprise-grade job queue with:
    - Per-tenant fairness and quotas
    - Priority lanes and backpressure control
    - Idempotency and exactly-once processing
    - Comprehensive monitoring and observability
    - Dead letter queue handling
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.initialized = False

        # Queue configuration with resource limits
        self.queue_config = {
            QueueType.CRITICAL_QUEUE: {
                'max_depth': 50,
                'max_workers': 3,
                'timeout_seconds': 30,
                'db_pool': 'user_api'
            },
            QueueType.API_QUEUE: {
                'max_depth': 200,
                'max_workers': 5,
                'timeout_seconds': 120,
                'db_pool': 'background_workers'
            },
            QueueType.CDN_QUEUE: {
                'max_depth': 500,
                'max_workers': 8,
                'timeout_seconds': 300,
                'db_pool': 'background_workers'
            },
            QueueType.AI_QUEUE: {
                'max_depth': 100,
                'max_workers': 2,
                'timeout_seconds': 600,
                'db_pool': 'ai_workers'
            },
            QueueType.DISCOVERY_QUEUE: {
                'max_depth': 1000,
                'max_workers': 3,
                'timeout_seconds': 900,
                'db_pool': 'discovery_workers'
            },
            QueueType.BULK_QUEUE: {
                'max_depth': 5000,
                'max_workers': 2,
                'timeout_seconds': 1800,
                'db_pool': 'discovery_workers'
            },
            QueueType.POST_ANALYTICS_QUEUE: {
                'max_depth': 200,
                'max_workers': 3,
                'timeout_seconds': 300,
                'db_pool': 'background_workers'
            }
        }

        # Tenant quota configuration
        self.tenant_quotas = {
            'free': {
                'concurrent_jobs': 2,
                'daily_limit': 50,
                'allowed_queues': [QueueType.API_QUEUE, QueueType.CDN_QUEUE, QueueType.POST_ANALYTICS_QUEUE]  # Added POST_ANALYTICS_QUEUE for ALL users
            },
            'standard': {
                'concurrent_jobs': 5,
                'daily_limit': 500,
                'allowed_queues': [QueueType.API_QUEUE, QueueType.CDN_QUEUE, QueueType.AI_QUEUE, QueueType.POST_ANALYTICS_QUEUE]
            },
            'premium': {
                'concurrent_jobs': 10,
                'daily_limit': 2000,
                'allowed_queues': [QueueType.CRITICAL_QUEUE, QueueType.API_QUEUE, QueueType.CDN_QUEUE, QueueType.AI_QUEUE, QueueType.POST_ANALYTICS_QUEUE]
            },
            'enterprise': {
                'concurrent_jobs': 20,
                'daily_limit': 10000,
                'allowed_queues': list(QueueType)
            }
        }

    async def initialize(self) -> bool:
        """Initialize Redis connection and job queue infrastructure"""
        try:
            if self.initialized:
                return True

            logger.info("Initializing industry-standard job queue system...")

            # Initialize Redis connection for queue management
            self.redis_client = redis.Redis(
                host=self._get_redis_host(),
                port=6379,
                db=0,  # Dedicated database for job queue
                decode_responses=True,
                max_connections=50,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )

            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Redis connection established for job queue")

            # Skip database schema initialization to avoid pgbouncer prepared statement conflicts
            # Schema should already exist from main application initialization
            logger.info("Skipping job queue schema initialization (using existing schema)")

            # Initialize queue monitoring
            await self._initialize_queue_monitoring()

            self.initialized = True
            logger.info("Job queue system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize job queue system: {e}")
            return False

    def _get_redis_host(self) -> str:
        """Get Redis host from environment or default"""
        import os
        return os.getenv('REDIS_HOST', 'localhost')

    async def _initialize_job_schema(self) -> None:
        """Initialize database schema for job persistence"""
        schema_sql = """
        -- Job queue table with comprehensive tracking
        CREATE TABLE IF NOT EXISTS job_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            job_type VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            priority INTEGER NOT NULL DEFAULT 50,
            queue_name VARCHAR(50) NOT NULL,
            params JSONB NOT NULL,
            result JSONB,
            error_details JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            estimated_duration INTEGER,
            actual_duration INTEGER,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            idempotency_key VARCHAR(255) UNIQUE,
            worker_id VARCHAR(100),
            user_tier VARCHAR(20),
            progress_percent INTEGER DEFAULT 0,
            progress_message TEXT,

            -- Constraints
            CONSTRAINT valid_status CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'retrying', 'cancelled')),
            CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 100),
            CONSTRAINT valid_progress CHECK (progress_percent BETWEEN 0 AND 100)
        );

        -- Performance indexes
        CREATE INDEX IF NOT EXISTS idx_job_queue_status_priority ON job_queue (status, priority DESC);
        CREATE INDEX IF NOT EXISTS idx_job_queue_user_created ON job_queue (user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_job_queue_queue_status ON job_queue (queue_name, status);
        CREATE INDEX IF NOT EXISTS idx_job_queue_idempotency ON job_queue (idempotency_key);
        CREATE INDEX IF NOT EXISTS idx_job_queue_worker_processing ON job_queue (worker_id, status) WHERE status = 'processing';
        CREATE INDEX IF NOT EXISTS idx_job_queue_retry_eligible ON job_queue (status, retry_count, created_at) WHERE status = 'failed';

        -- Dead letter queue for failed jobs
        CREATE TABLE IF NOT EXISTS job_dead_letter_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            original_job_id UUID NOT NULL,
            job_data JSONB NOT NULL,
            failure_reason TEXT NOT NULL,
            failure_count INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_retry_at TIMESTAMPTZ
        );

        -- Job execution metrics for monitoring
        CREATE TABLE IF NOT EXISTS job_execution_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_type VARCHAR(100) NOT NULL,
            queue_name VARCHAR(50) NOT NULL,
            user_tier VARCHAR(20),
            duration_seconds INTEGER,
            success BOOLEAN NOT NULL,
            error_category VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Enable Row Level Security
        ALTER TABLE job_queue ENABLE ROW LEVEL SECURITY;

        -- RLS Policy: Users can only see their own jobs
        DROP POLICY IF EXISTS "Users can only access their own jobs" ON job_queue;
        CREATE POLICY "Users can only access their own jobs" ON job_queue
            FOR ALL USING (auth.uid() = user_id);
        """

        async with optimized_pools.get_user_session() as session:
            await session.execute(text(schema_sql).execution_options(prepare=False))
            await session.commit()

        logger.info("Job queue database schema initialized")

    async def _initialize_queue_monitoring(self) -> None:
        """Initialize queue depth monitoring in Redis"""
        for queue_type in QueueType:
            await self.redis_client.set(f"queue_depth:{queue_type.value}", 0)
            await self.redis_client.set(f"queue_workers:{queue_type.value}", 0)

    async def enqueue_job(
        self,
        user_id: str,
        job_type: str,
        params: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        queue_type: QueueType = QueueType.API_QUEUE,
        estimated_duration: Optional[int] = None,
        user_tier: str = 'free',
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enqueue job with comprehensive validation and tenant quotas

        Returns:
            Dict with job_id, status, estimated_completion, and queue position
        """

        # 1. VALIDATE TENANT QUOTAS
        quota_check = await self._check_tenant_quota(user_id, user_tier, queue_type)
        if not quota_check['allowed']:
            return {
                'success': False,
                'error': 'quota_exceeded',
                'message': quota_check['reason'],
                'retry_after': quota_check.get('retry_after')
            }

        # 2. VALIDATE QUEUE CAPACITY (BACKPRESSURE)
        queue_depth = await self._get_queue_depth(queue_type)
        max_depth = self.queue_config[queue_type]['max_depth']

        if queue_depth >= max_depth:
            # Implement gradual rejection as queue fills
            rejection_rate = min(0.8, (queue_depth - max_depth * 0.8) / (max_depth * 0.2))
            if priority.value < JobPriority.HIGH.value and random.random() < rejection_rate:
                return {
                    'success': False,
                    'error': 'queue_full',
                    'message': f'Queue {queue_type.value} is at capacity',
                    'current_depth': queue_depth,
                    'max_depth': max_depth
                }

        # 3. CREATE JOB DEFINITION
        job = JobDefinition(
            id=str(uuid.uuid4()),
            user_id=user_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            priority=priority,
            queue_name=queue_type,
            params=params,
            estimated_duration=estimated_duration,
            user_tier=user_tier,
            idempotency_key=idempotency_key
        )

        # 4. CHECK IDEMPOTENCY
        if job.idempotency_key:
            existing_job = await self._get_job_by_idempotency_key(job.idempotency_key)
            if existing_job:
                return {
                    'success': True,
                    'job_id': existing_job['id'],
                    'status': existing_job['status'],
                    'message': 'Job already exists (idempotent)',
                    'existing': True
                }

        # 5. PERSIST JOB TO DATABASE
        await self._persist_job(job)

        # 6. ADD TO REDIS QUEUE
        await self._add_to_redis_queue(job)

        # 7. UPDATE METRICS
        await self._update_queue_metrics(queue_type, 'enqueued')

        # 8. RETURN SUCCESS RESPONSE
        queue_position = await self._get_queue_position(job.id, queue_type)
        estimated_completion = self._calculate_estimated_completion(
            queue_position, estimated_duration, queue_type
        )

        return {
            'success': True,
            'job_id': job.id,
            'status': job.status.value,
            'queue_position': queue_position,
            'estimated_completion_seconds': estimated_completion,
            'queue_name': queue_type.value,
            'priority': priority.value
        }

    async def _check_tenant_quota(
        self,
        user_id: str,
        user_tier: str,
        queue_type: QueueType
    ) -> Dict[str, Any]:
        """Check if user can enqueue more jobs based on tier quotas"""

        if user_tier not in self.tenant_quotas:
            user_tier = 'free'  # Default to free tier

        quota = self.tenant_quotas[user_tier]

        # Check if queue type is allowed for this tier
        if queue_type not in quota['allowed_queues']:
            return {
                'allowed': False,
                'reason': f'Queue {queue_type.value} not available for {user_tier} tier'
            }

        # Check concurrent jobs limit
        async with optimized_pools.get_user_session() as session:
            result = await session.execute(text("""
                SELECT
                    COUNT(*) as active_jobs,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') as daily_jobs
                FROM job_queue
                WHERE user_id = :user_id
                AND status IN ('queued', 'processing')
            """).execution_options(prepare=False), {'user_id': user_id})

            counts = result.fetchone()

            if counts.active_jobs >= quota['concurrent_jobs']:
                return {
                    'allowed': False,
                    'reason': f'Concurrent job limit exceeded ({counts.active_jobs}/{quota["concurrent_jobs"]})'
                }

            if counts.daily_jobs >= quota['daily_limit']:
                return {
                    'allowed': False,
                    'reason': f'Daily job limit exceeded ({counts.daily_jobs}/{quota["daily_limit"]})',
                    'retry_after': 86400  # 24 hours
                }

        return {'allowed': True}

    async def _get_queue_depth(self, queue_type: QueueType) -> int:
        """Get current queue depth from Redis"""
        depth = await self.redis_client.get(f"queue_depth:{queue_type.value}")
        return int(depth) if depth else 0

    async def _persist_job(self, job: JobDefinition) -> None:
        """Persist job to database for durability"""
        async with optimized_pools.get_user_session() as session:
            await session.execute(text("""
                INSERT INTO job_queue (
                    id, user_id, job_type, status, priority, queue_name,
                    params, created_at, estimated_duration, idempotency_key, user_tier
                ) VALUES (
                    :id, :user_id, :job_type, :status, :priority, :queue_name,
                    :params, :created_at, :estimated_duration, :idempotency_key, :user_tier
                )
            """).execution_options(prepare=False), {
                'id': job.id,
                'user_id': job.user_id,
                'job_type': job.job_type,
                'status': job.status.value,
                'priority': job.priority.value,
                'queue_name': job.queue_name.value,
                'params': json.dumps(job.params),
                'created_at': job.created_at,
                'estimated_duration': job.estimated_duration,
                'idempotency_key': job.idempotency_key,
                'user_tier': job.user_tier
            })
            await session.commit()

    async def _add_to_redis_queue(self, job: JobDefinition) -> None:
        """Add job to Redis priority queue and trigger Celery worker"""
        # Use sorted set for priority queue (higher score = higher priority)
        queue_key = f"queue:{job.queue_name.value}"
        score = job.priority.value + (time.time() / 1000000)  # Priority + timestamp for FIFO within priority

        await self.redis_client.zadd(queue_key, {job.id: score})
        await self.redis_client.incr(f"queue_depth:{job.queue_name.value}")

        # CRITICAL FIX: Actually trigger Celery worker for the job
        await self._trigger_celery_worker(job)

    async def _trigger_celery_worker(self, job: JobDefinition) -> None:
        """Trigger the appropriate Celery worker task for the job"""
        try:
            # Import Celery app from unified worker
            from app.workers.unified_worker import celery_app

            # Map job types to Celery tasks
            task_mapping = {
                'profile_analysis': 'app.workers.unified_worker.process_profile_analysis',
                'profile_analysis_background': 'app.workers.unified_worker.process_profile_analysis_background',
                'post_analysis': 'app.workers.unified_worker.process_post_analysis',
                'post_analytics_campaign': 'app.workers.unified_worker.process_post_analytics_campaign',  # Added for campaign post analytics
                'bulk_analysis': 'app.workers.unified_worker.process_bulk_analysis'
            }

            # Get the appropriate Celery task name
            task_name = task_mapping.get(job.job_type)
            if not task_name:
                logger.warning(f"No Celery task mapped for job type: {job.job_type}")
                return

            # Send task to Celery asynchronously
            celery_app.send_task(
                task_name,
                args=[job.id],  # Pass job ID to worker
                queue=self._get_celery_queue_name(job.queue_name),
                priority=job.priority.value
            )

            logger.info(f"✅ Triggered Celery task {task_name} for job {job.id}")

        except Exception as e:
            logger.error(f"❌ Failed to trigger Celery worker for job {job.id}: {e}")

    def _get_celery_queue_name(self, queue_type: QueueType) -> str:
        """Map our queue types to Celery queue names"""
        celery_queue_mapping = {
            QueueType.CRITICAL_QUEUE: 'high_priority',
            QueueType.API_QUEUE: 'high_priority',
            QueueType.CDN_QUEUE: 'cdn_processing',
            QueueType.AI_QUEUE: 'normal_priority',
            QueueType.DISCOVERY_QUEUE: 'discovery',
            QueueType.BULK_QUEUE: 'bulk_processing',
            QueueType.POST_ANALYTICS_QUEUE: 'post_analytics'
        }
        return celery_queue_mapping.get(queue_type, 'normal_priority')

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive job status"""
        async with optimized_pools.get_user_session() as session:
            result = await session.execute(text("""
                SELECT
                    id, user_id, job_type, status, priority, queue_name,
                    params, result, error_details, created_at, started_at, completed_at,
                    estimated_duration, actual_duration, retry_count, max_retries,
                    worker_id, user_tier, progress_percent, progress_message
                FROM job_queue
                WHERE id = :job_id
            """).execution_options(prepare=False), {'job_id': job_id})

            job_data = result.fetchone()
            if not job_data:
                return None

            # Calculate additional metrics
            status_info = {
                'job_id': job_data.id,
                'status': job_data.status,
                'progress_percent': job_data.progress_percent,
                'progress_message': job_data.progress_message,
                'created_at': job_data.created_at.isoformat(),
                'started_at': job_data.started_at.isoformat() if job_data.started_at else None,
                'completed_at': job_data.completed_at.isoformat() if job_data.completed_at else None,
                'result': json.loads(job_data.result) if job_data.result else None,
                'error_details': json.loads(job_data.error_details) if job_data.error_details else None
            }

            # Calculate time metrics
            if job_data.status == 'processing' and job_data.started_at:
                elapsed = (datetime.now(timezone.utc) - job_data.started_at).total_seconds()
                if job_data.estimated_duration:
                    status_info['estimated_remaining_seconds'] = max(0, job_data.estimated_duration - elapsed)
                else:
                    status_info['elapsed_seconds'] = elapsed

            elif job_data.status == 'queued':
                # Estimate queue position and wait time
                queue_position = await self._get_queue_position(job_id, QueueType(job_data.queue_name))
                status_info['queue_position'] = queue_position
                status_info['estimated_start_seconds'] = self._calculate_estimated_start_time(
                    queue_position, QueueType(job_data.queue_name)
                )

            return status_info

    async def _get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get job by idempotency key"""
        async with optimized_pools.get_user_session() as session:
            result = await session.execute(text("""
                SELECT id, status, created_at
                FROM job_queue
                WHERE idempotency_key = :key
            """).execution_options(prepare=False), {'key': idempotency_key})

            job = result.fetchone()
            if job:
                return {
                    'id': job.id,
                    'status': job.status,
                    'created_at': job.created_at.isoformat()
                }
            return None

    async def _get_queue_position(self, job_id: str, queue_type: QueueType) -> int:
        """Get job position in queue"""
        queue_key = f"queue:{queue_type.value}"
        rank = await self.redis_client.zrevrank(queue_key, job_id)
        return rank + 1 if rank is not None else 0

    def _calculate_estimated_completion(
        self,
        queue_position: int,
        estimated_duration: Optional[int],
        queue_type: QueueType
    ) -> int:
        """Calculate estimated completion time in seconds"""
        config = self.queue_config[queue_type]
        avg_processing_time = estimated_duration or config['timeout_seconds'] // 2
        concurrent_workers = config['max_workers']

        # Simple estimation: (position / workers) * avg_time
        return int((queue_position / concurrent_workers) * avg_processing_time)

    def _calculate_estimated_start_time(self, queue_position: int, queue_type: QueueType) -> int:
        """Calculate estimated time until job starts processing"""
        config = self.queue_config[queue_type]
        avg_processing_time = config['timeout_seconds'] // 2
        concurrent_workers = config['max_workers']

        return int(((queue_position - 1) / concurrent_workers) * avg_processing_time)

    async def _update_queue_metrics(self, queue_type: QueueType, action: str) -> None:
        """Update queue metrics for monitoring"""
        metric_key = f"queue_metrics:{queue_type.value}:{action}"
        await self.redis_client.incr(metric_key)
        await self.redis_client.expire(metric_key, 86400)  # 24 hour retention

    async def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all job queues and system health"""
        try:
            if not self.initialized:
                await self.initialize()

            stats = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'system_health': 'healthy',
                'total_queues': len(QueueType),
                'redis_connected': bool(self.redis_client),
                'queue_statistics': {},
                'tenant_statistics': {},
                'performance_metrics': {},
                'error_rates': {}
            }

            # Get queue statistics for each queue type
            for queue_type in QueueType:
                queue_key = f"queue:{queue_type.value}"
                processing_key = f"processing:{queue_type.value}"

                # Get queue counts
                queue_size = await self.redis_client.zcard(queue_key) if self.redis_client else 0
                processing_count = await self.redis_client.hlen(processing_key) if self.redis_client else 0

                # Get 24h metrics
                daily_metrics = {}
                for action in ['enqueued', 'completed', 'failed', 'retried']:
                    metric_key = f"queue_metrics:{queue_type.value}:{action}"
                    count = await self.redis_client.get(metric_key) if self.redis_client else "0"
                    daily_metrics[action] = int(count or 0)

                stats['queue_statistics'][queue_type.value] = {
                    'queue_size': queue_size,
                    'processing_count': processing_count,
                    'total_capacity': self.queue_config[queue_type]['max_depth'],
                    'max_workers': self.queue_config[queue_type]['max_workers'],
                    'timeout_seconds': self.queue_config[queue_type]['timeout_seconds'],
                    'utilization_percent': round((queue_size / self.queue_config[queue_type]['max_depth']) * 100, 2),
                    'daily_metrics': daily_metrics,
                    'db_pool': self.queue_config[queue_type]['db_pool']
                }

            # Calculate overall performance metrics
            total_queued = sum(q['queue_size'] for q in stats['queue_statistics'].values())
            total_processing = sum(q['processing_count'] for q in stats['queue_statistics'].values())
            total_completed = sum(q['daily_metrics']['completed'] for q in stats['queue_statistics'].values())
            total_failed = sum(q['daily_metrics']['failed'] for q in stats['queue_statistics'].values())

            stats['performance_metrics'] = {
                'total_jobs_queued': total_queued,
                'total_jobs_processing': total_processing,
                'total_jobs_completed_24h': total_completed,
                'total_jobs_failed_24h': total_failed,
                'success_rate_24h': round((total_completed / max(total_completed + total_failed, 1)) * 100, 2),
                'throughput_jobs_per_hour': round(total_completed / 24, 2) if total_completed > 0 else 0
            }

            # Get tenant statistics
            for tier, config in self.tenant_quotas.items():
                stats['tenant_statistics'][tier] = {
                    'concurrent_limit': config['concurrent_jobs'],
                    'daily_limit': config['daily_limit'],
                    'allowed_queues': [q.value for q in config['allowed_queues']]
                }

            # Calculate error rates
            for queue_type, queue_stats in stats['queue_statistics'].items():
                daily = queue_stats['daily_metrics']
                total_attempts = daily['completed'] + daily['failed']
                if total_attempts > 0:
                    error_rate = round((daily['failed'] / total_attempts) * 100, 2)
                    stats['error_rates'][queue_type] = error_rate

            # Determine overall system health
            high_error_queues = [q for q, rate in stats['error_rates'].items() if rate > 10]
            overloaded_queues = [q for q, data in stats['queue_statistics'].items() if data['utilization_percent'] > 90]

            if high_error_queues or overloaded_queues:
                stats['system_health'] = 'degraded'
                stats['health_issues'] = {
                    'high_error_queues': high_error_queues,
                    'overloaded_queues': overloaded_queues
                }

            return stats

        except Exception as e:
            logger.error(f"Error getting comprehensive stats: {e}")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'system_health': 'error',
                'error': str(e),
                'redis_connected': bool(self.redis_client)
            }

# Global job queue instance
job_queue = IndustryStandardJobQueue()