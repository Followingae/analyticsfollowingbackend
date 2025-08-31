"""
Industry-Standard CDN Queue Manager
High-performance, resilient image processing queue with proper concurrency control
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
from uuid import UUID

logger = logging.getLogger(__name__)

class JobPriority(Enum):
    """Job priority levels for processing queue"""
    CRITICAL = 1    # Profile avatars, immediate user requests
    HIGH = 2        # Recent posts, active profiles  
    MEDIUM = 3      # Batch processing, background tasks
    LOW = 4         # Cleanup, maintenance tasks

class JobStatus(Enum):
    """Job status tracking"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"

@dataclass
class ProcessingConfig:
    """Configuration for CDN processing"""
    max_concurrent_jobs: int = 3           # Process max 3 jobs concurrently
    batch_size: int = 5                    # Process in batches of 5
    retry_attempts: int = 3                # Retry failed jobs 3 times
    retry_delay_seconds: int = 5           # Wait 5s between retries
    rate_limit_delay_ms: int = 200         # 200ms between jobs (5 jobs/sec)
    timeout_seconds: int = 60              # Job timeout
    
@dataclass 
class QueueStats:
    """Queue statistics for monitoring"""
    total_jobs: int = 0
    pending_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    avg_processing_time: float = 0.0
    success_rate: float = 0.0
    last_updated: datetime = None

class CDNQueueManager:
    """
    Industry-standard CDN processing queue manager
    
    Features:
    - Proper concurrency control with semaphores
    - Priority-based job scheduling  
    - Exponential backoff retry logic
    - Rate limiting to prevent API overload
    - Graceful error handling and recovery
    - Comprehensive monitoring and statistics
    - Circuit breaker for external service protection
    """
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_jobs)
        self.processing_jobs = set()
        
        # Queue management
        self.job_queue = asyncio.PriorityQueue()
        self._queue_counter = 0  # Counter to ensure unique queue items
        self.completed_jobs = {}
        self.failed_jobs = {}
        
        # Statistics and monitoring
        self.stats = QueueStats()
        self.start_time = datetime.utcnow()
        
        # Circuit breaker for R2 service protection
        self.circuit_breaker = {
            'failures': 0,
            'last_failure': None,
            'is_open': False,
            'failure_threshold': 5,
            'recovery_timeout': 30  # seconds
        }
        
        logger.info(f"🎯 CDN Queue Manager initialized with {self.config.max_concurrent_jobs} concurrent jobs")
    
    async def enqueue_job(self, 
                         job_id: str,
                         asset_data: Dict[str, Any], 
                         priority: JobPriority = JobPriority.MEDIUM) -> bool:
        """
        Enqueue a CDN processing job with proper priority handling
        
        Args:
            job_id: Unique job identifier
            asset_data: Job data (asset_id, source_url, target_sizes, etc.)
            priority: Job priority level
            
        Returns:
            bool: True if job was enqueued successfully
        """
        try:
            job_item = {
                'id': job_id,
                'asset_data': asset_data,
                'priority': priority,
                'enqueued_at': datetime.utcnow(),
                'retry_count': 0,
                'status': JobStatus.PENDING
            }
            
            # Priority queue: lower number = higher priority, use counter to avoid dict comparison
            self._queue_counter += 1
            await self.job_queue.put((priority.value, self._queue_counter, job_item))
            
            self.stats.total_jobs += 1
            self.stats.pending_jobs += 1
            
            logger.info(f"📥 Job {job_id} enqueued with priority {priority.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to enqueue job {job_id}: {e}")
            return False
    
    async def process_queue(self) -> Dict[str, Any]:
        """
        Process the entire queue with proper concurrency and error handling
        
        Returns:
            Processing results and statistics
        """
        logger.info(f"🚀 Starting queue processing - {self.stats.pending_jobs} jobs pending")
        processing_start = datetime.utcnow()
        
        # Create worker tasks for concurrent processing
        workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.config.max_concurrent_jobs)
        ]
        
        try:
            # Wait for all jobs to complete
            await self.job_queue.join()
            
            # Cancel worker tasks
            for worker in workers:
                worker.cancel()
            
            # Wait for workers to finish cleanup
            await asyncio.gather(*workers, return_exceptions=True)
            
            processing_time = (datetime.utcnow() - processing_start).total_seconds()
            
            # Update statistics
            self._update_stats(processing_time)
            
            results = {
                'success': True,
                'processing_time': processing_time,
                'jobs_processed': self.stats.completed_jobs,
                'jobs_failed': self.stats.failed_jobs,
                'success_rate': self.stats.success_rate,
                'stats': self.stats
            }
            
            logger.info(f"✅ Queue processing completed in {processing_time:.2f}s - {self.stats.completed_jobs} successful, {self.stats.failed_jobs} failed")
            return results
            
        except Exception as e:
            logger.error(f"❌ Queue processing failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _worker(self, worker_name: str):
        """
        Worker task for processing jobs concurrently
        
        Args:
            worker_name: Identifier for this worker
        """
        while True:
            try:
                # Get next job from queue (with timeout to allow graceful shutdown)
                try:
                    priority, counter, job_item = await asyncio.wait_for(
                        self.job_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check circuit breaker
                if self._is_circuit_breaker_open():
                    logger.warning(f"⚡ Circuit breaker open - re-queuing job {job_item['id']}")
                    self._queue_counter += 1
                    await self.job_queue.put((priority, self._queue_counter, job_item))
                    self.job_queue.task_done()
                    await asyncio.sleep(5)  # Wait before retrying
                    continue
                
                # Process job with semaphore for concurrency control
                async with self.semaphore:
                    await self._process_single_job(worker_name, job_item)
                
                # Rate limiting - prevent API overload
                await asyncio.sleep(self.config.rate_limit_delay_ms / 1000)
                
                self.job_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Worker {worker_name} error: {e}")
                self.job_queue.task_done()
    
    async def _process_single_job(self, worker_name: str, job_item: Dict[str, Any]):
        """
        Process a single CDN job with proper error handling and retries
        
        Args:
            worker_name: Worker processing this job
            job_item: Job data to process
        """
        job_id = job_item['id']
        job_start = datetime.utcnow()
        
        try:
            logger.info(f"🔄 {worker_name} processing job {job_id}")
            
            # Update job status
            job_item['status'] = JobStatus.PROCESSING
            job_item['started_at'] = job_start
            self.processing_jobs.add(job_id)
            
            self.stats.pending_jobs -= 1
            self.stats.processing_jobs += 1
            
            # Process the actual CDN job directly (bypassing Celery for now)
            from app.services.image_transcoder_service import image_transcoder_service
            
            # Get job data from our internal tracking
            job_data = job_item.get('asset_data', {})
            
            # Process the image directly
            result = await asyncio.wait_for(
                image_transcoder_service.process_job(job_data),
                timeout=self.config.timeout_seconds
            )
            
            if result and result.get('success'):
                # Job completed successfully
                job_item['status'] = JobStatus.COMPLETED
                job_item['completed_at'] = datetime.utcnow()
                job_item['result'] = result
                
                self.completed_jobs[job_id] = job_item
                self.stats.completed_jobs += 1
                
                # Reset circuit breaker on success
                self._reset_circuit_breaker()
                
                processing_time = (datetime.utcnow() - job_start).total_seconds()
                logger.info(f"✅ {worker_name} completed job {job_id} in {processing_time:.2f}s")
                
            else:
                # Job failed - handle retry logic
                await self._handle_job_failure(job_item, result.get('error', 'Unknown error'))
                
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Job {job_id} timed out after {self.config.timeout_seconds}s")
            await self._handle_job_failure(job_item, "Job timeout")
            
        except Exception as e:
            logger.error(f"❌ Job {job_id} processing error: {e}")
            await self._handle_job_failure(job_item, str(e))
            
        finally:
            self.processing_jobs.discard(job_id)
            self.stats.processing_jobs -= 1
    
    async def _handle_job_failure(self, job_item: Dict[str, Any], error_message: str):
        """
        Handle job failure with exponential backoff retry logic
        
        Args:
            job_item: Failed job data
            error_message: Error description
        """
        job_id = job_item['id']
        job_item['retry_count'] += 1
        
        # Update circuit breaker
        self._record_failure()
        
        if job_item['retry_count'] <= self.config.retry_attempts:
            # Retry with exponential backoff
            delay = self.config.retry_delay_seconds * (2 ** (job_item['retry_count'] - 1))
            
            logger.warning(f"🔄 Retrying job {job_id} in {delay}s (attempt {job_item['retry_count']}/{self.config.retry_attempts})")
            
            job_item['status'] = JobStatus.RETRY
            
            # Re-queue with delay
            asyncio.create_task(self._requeue_with_delay(job_item, delay))
            
        else:
            # Max retries exceeded - mark as permanently failed
            job_item['status'] = JobStatus.FAILED
            job_item['failed_at'] = datetime.utcnow()
            job_item['final_error'] = error_message
            
            self.failed_jobs[job_id] = job_item
            self.stats.failed_jobs += 1
            
            logger.error(f"❌ Job {job_id} permanently failed after {self.config.retry_attempts} attempts: {error_message}")
    
    async def _requeue_with_delay(self, job_item: Dict[str, Any], delay_seconds: int):
        """Re-queue job after delay for retry"""
        await asyncio.sleep(delay_seconds)
        
        priority = job_item['priority']
        self._queue_counter += 1
        await self.job_queue.put((priority.value, self._queue_counter, job_item))
        
        self.stats.pending_jobs += 1
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open to protect external services"""
        if not self.circuit_breaker['is_open']:
            return False
            
        # Check if recovery timeout has passed
        if (datetime.utcnow() - self.circuit_breaker['last_failure']).total_seconds() > self.circuit_breaker['recovery_timeout']:
            logger.info("⚡ Circuit breaker half-open - allowing test request")
            self.circuit_breaker['is_open'] = False
            return False
            
        return True
    
    def _record_failure(self):
        """Record failure for circuit breaker logic"""
        self.circuit_breaker['failures'] += 1
        self.circuit_breaker['last_failure'] = datetime.utcnow()
        
        if self.circuit_breaker['failures'] >= self.circuit_breaker['failure_threshold']:
            self.circuit_breaker['is_open'] = True
            logger.warning(f"⚡ Circuit breaker OPEN - too many failures ({self.circuit_breaker['failures']})")
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker on successful operation"""
        if self.circuit_breaker['failures'] > 0:
            self.circuit_breaker['failures'] = 0
            self.circuit_breaker['is_open'] = False
            logger.info("⚡ Circuit breaker reset - service healthy")
    
    def _update_stats(self, processing_time: float):
        """Update processing statistics"""
        self.stats.avg_processing_time = processing_time
        self.stats.last_updated = datetime.utcnow()
        
        total_processed = self.stats.completed_jobs + self.stats.failed_jobs
        if total_processed > 0:
            self.stats.success_rate = (self.stats.completed_jobs / total_processed) * 100
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics"""
        return {
            'queue_size': self.job_queue.qsize(),
            'processing_jobs': len(self.processing_jobs),
            'circuit_breaker_open': self.circuit_breaker['is_open'],
            'uptime_seconds': (datetime.utcnow() - self.start_time).total_seconds(),
            'stats': {
                'total_jobs': self.stats.total_jobs,
                'pending_jobs': self.stats.pending_jobs,
                'processing_jobs': self.stats.processing_jobs,
                'completed_jobs': self.stats.completed_jobs,
                'failed_jobs': self.stats.failed_jobs,
                'success_rate': self.stats.success_rate,
                'avg_processing_time': self.stats.avg_processing_time
            }
        }


# Global queue manager instance
cdn_queue_manager = CDNQueueManager()