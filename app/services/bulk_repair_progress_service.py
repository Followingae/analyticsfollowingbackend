"""
Bulk Repair Progress Service - Real-time Sequential Processing with Stage Tracking

Provides comprehensive progress tracking for bulk profile repair operations with:
- Sequential one-by-one processing instead of simultaneous
- Real-time stage tracking (APIFY, CDN, AI Models)
- Live progress updates for frontend monitoring
- Queue management with pending/in-progress/completed states
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update
from app.database.connection import get_session
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from app.services.redis_cache_service import redis_cache

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    QUEUED = "queued"
    APIFY_FETCHING = "apify_fetching"
    APIFY_COMPLETED = "apify_completed"
    CDN_PROCESSING = "cdn_processing"
    CDN_COMPLETED = "cdn_completed"
    AI_PROCESSING = "ai_processing"
    AI_COMPLETED = "ai_completed"
    DATABASE_STORING = "database_storing"
    COMPLETED = "completed"
    FAILED = "failed"


class OperationStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProfileProgress:
    """Individual profile processing progress"""
    profile_id: str
    username: str
    stage: ProcessingStage
    stage_started_at: Optional[datetime]
    stage_completed_at: Optional[datetime]
    stage_progress_percent: int  # 0-100
    stage_message: str
    error_message: Optional[str]
    total_duration_seconds: Optional[float]
    created_at: datetime
    updated_at: datetime


@dataclass
class BulkRepairOperation:
    """Bulk repair operation with real-time tracking"""
    operation_id: str
    admin_email: str
    total_profiles: int
    current_profile_index: int
    profiles_completed: int
    profiles_failed: int
    operation_status: OperationStatus
    current_profile: Optional[ProfileProgress]
    queue: List[ProfileProgress]
    completed_profiles: List[ProfileProgress]
    failed_profiles: List[ProfileProgress]
    started_at: datetime
    estimated_completion: Optional[datetime]
    last_updated: datetime


class BulkRepairProgressService:
    """
    Sequential bulk repair service with comprehensive progress tracking
    """

    def __init__(self):
        self.redis_prefix = "bulk_repair"
        self.active_operations: Dict[str, BulkRepairOperation] = {}

    async def start_bulk_repair_operation(
        self,
        admin_email: str,
        profile_usernames: List[str]
    ) -> str:
        """
        Start a new sequential bulk repair operation

        Returns:
            operation_id for tracking progress
        """
        operation_id = str(uuid4())

        # Create profile progress entries for queue
        queue = []
        for username in profile_usernames:
            profile_progress = ProfileProgress(
                profile_id="",  # Will be populated when processing starts
                username=username,
                stage=ProcessingStage.QUEUED,
                stage_started_at=None,
                stage_completed_at=None,
                stage_progress_percent=0,
                stage_message=f"Queued for processing",
                error_message=None,
                total_duration_seconds=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            queue.append(profile_progress)

        # Create operation
        operation = BulkRepairOperation(
            operation_id=operation_id,
            admin_email=admin_email,
            total_profiles=len(profile_usernames),
            current_profile_index=0,
            profiles_completed=0,
            profiles_failed=0,
            operation_status=OperationStatus.QUEUED,
            current_profile=None,
            queue=queue,
            completed_profiles=[],
            failed_profiles=[],
            started_at=datetime.now(timezone.utc),
            estimated_completion=None,
            last_updated=datetime.now(timezone.utc)
        )

        # Store in memory and Redis
        self.active_operations[operation_id] = operation
        await self._store_operation_in_redis(operation)

        logger.info(f"🚀 Started bulk repair operation {operation_id} with {len(profile_usernames)} profiles")

        # Start background processing
        asyncio.create_task(self._process_operation_sequentially(operation_id))

        return operation_id

    async def _process_operation_sequentially(self, operation_id: str):
        """
        Process profiles one by one sequentially with detailed stage tracking
        """
        try:
            operation = self.active_operations.get(operation_id)
            if not operation:
                logger.error(f"❌ Operation {operation_id} not found")
                return

            operation.operation_status = OperationStatus.PROCESSING
            await self._update_operation_progress(operation_id)

            logger.info(f"🔄 Starting sequential processing for operation {operation_id}")

            # Process each profile one by one
            for index, profile_progress in enumerate(operation.queue.copy()):
                try:
                    operation.current_profile_index = index
                    operation.current_profile = profile_progress

                    # Update stage to processing
                    await self._update_profile_stage(
                        operation_id,
                        profile_progress.username,
                        ProcessingStage.APIFY_FETCHING,
                        "Starting APIFY data fetching...",
                        progress_percent=0
                    )

                    # Execute full creator analytics with stage tracking
                    success = await self._process_single_profile_with_tracking(
                        operation_id,
                        profile_progress.username
                    )

                    if success:
                        operation.profiles_completed += 1
                        # Move to completed list
                        completed_profile = operation.queue.pop(0)
                        completed_profile.stage = ProcessingStage.COMPLETED
                        completed_profile.stage_completed_at = datetime.now(timezone.utc)
                        operation.completed_profiles.append(completed_profile)
                    else:
                        operation.profiles_failed += 1
                        # Move to failed list
                        failed_profile = operation.queue.pop(0)
                        failed_profile.stage = ProcessingStage.FAILED
                        failed_profile.stage_completed_at = datetime.now(timezone.utc)
                        operation.failed_profiles.append(failed_profile)

                    await self._update_operation_progress(operation_id)

                except Exception as e:
                    logger.error(f"❌ Failed to process profile {profile_progress.username}: {e}")
                    operation.profiles_failed += 1

                    # Move to failed list with error
                    if operation.queue:
                        failed_profile = operation.queue.pop(0)
                        failed_profile.stage = ProcessingStage.FAILED
                        failed_profile.error_message = str(e)
                        failed_profile.stage_completed_at = datetime.now(timezone.utc)
                        operation.failed_profiles.append(failed_profile)

                    await self._update_operation_progress(operation_id)

            # Mark operation as completed
            operation.operation_status = OperationStatus.COMPLETED
            operation.current_profile = None
            await self._update_operation_progress(operation_id)

            logger.info(f"✅ Bulk repair operation {operation_id} completed: {operation.profiles_completed}/{operation.total_profiles} successful")

        except Exception as e:
            logger.error(f"❌ Bulk repair operation {operation_id} failed: {e}")
            if operation_id in self.active_operations:
                self.active_operations[operation_id].operation_status = OperationStatus.FAILED
                await self._update_operation_progress(operation_id)

    async def _process_single_profile_with_tracking(
        self,
        operation_id: str,
        username: str
    ) -> bool:
        """
        Process a single profile with detailed stage tracking

        Returns:
            True if successful, False if failed
        """
        try:
            # Stage 1: APIFY Data Fetching
            await self._update_profile_stage(
                operation_id, username,
                ProcessingStage.APIFY_FETCHING,
                "Fetching profile and posts data from Instagram...",
                progress_percent=10
            )

            # Trigger full creator analytics with custom tracking
            async with get_session() as db:
                # We'll hook into the creator analytics service stages
                repaired_profile, analytics_data = await self._execute_tracked_creator_analytics(
                    operation_id, username, db, "admin"
                )

            if repaired_profile and analytics_data.get("success", False):
                await self._update_profile_stage(
                    operation_id, username,
                    ProcessingStage.COMPLETED,
                    "Profile processing completed successfully!",
                    progress_percent=100
                )
                return True
            else:
                await self._update_profile_stage(
                    operation_id, username,
                    ProcessingStage.FAILED,
                    f"Processing failed: {analytics_data.get('error', 'Unknown error')}",
                    progress_percent=0
                )
                return False

        except Exception as e:
            await self._update_profile_stage(
                operation_id, username,
                ProcessingStage.FAILED,
                f"Processing failed with exception: {str(e)}",
                progress_percent=0
            )
            return False

    async def _execute_tracked_creator_analytics(
        self,
        operation_id: str,
        username: str,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> tuple:
        """
        Execute creator analytics via job queue with stage-by-stage progress tracking
        """
        try:
            # PRACTICAL SOLUTION: Use asyncio task with dedicated connection pool
            # This achieves isolation without complex worker setup

            # Stage 1: Start async processing
            await self._update_profile_stage(
                operation_id, username,
                ProcessingStage.APIFY_FETCHING,
                "Starting background processing with resource isolation...",
                progress_percent=10
            )

            # REAL BACKGROUND WORKER: Queue job for external worker processing
            from app.core.job_queue import job_queue, JobPriority, QueueType

            job_id = await job_queue.enqueue_job(
                user_id=user_id or "admin",
                job_type="profile_analysis",
                params={
                    "username": username,
                    "credit_cost": 0,  # No credit cost for admin repair
                    "operation_id": operation_id
                },
                priority=JobPriority.HIGH,
                queue_type=QueueType.BULK_QUEUE,
                estimated_duration=180,  # 3 minutes
                user_tier="admin"
            )

            # Update stage to queued
            await self._update_profile_stage(
                operation_id, username,
                ProcessingStage.APIFY_FETCHING,
                f"Queued for external worker processing (Job: {job_id[:8]})",
                progress_percent=20
            )

            # FAST HANDOFF: Return immediately - worker will handle processing
            return None, {
                "success": True,
                "processing_started": True,
                "processing_mode": "external_worker",
                "job_id": job_id,
                "message": f"Profile {username} queued for external worker processing"
            }

        except Exception as e:
            logger.error(f"❌ Tracked creator analytics failed for {username}: {e}")
            return None, {"success": False, "error": str(e)}

    async def _process_profile_isolated(self, operation_id: str, username: str):
        """
        Process profile using isolated resources (dedicated connection pool)
        This runs in background without blocking the main API
        """
        try:
            # Use dedicated background connection pool for isolation
            from app.database.optimized_pools import optimized_pools

            # Stage 2: APIFY processing
            await self._update_profile_stage(
                operation_id, username,
                ProcessingStage.APIFY_FETCHING,
                "Fetching Instagram data via APIFY...",
                progress_percent=30
            )

            # Use isolated background session
            async with optimized_pools.get_background_session() as db:
                # Import here to avoid circular imports
                from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service

                # Stage 3: Execute full creator analytics with isolated resources
                await self._update_profile_stage(
                    operation_id, username,
                    ProcessingStage.AI_PROCESSING,
                    "Running AI analysis and CDN processing...",
                    progress_percent=60
                )

                # Execute with isolated resources
                profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                    username=username,
                    db=db,
                    force_refresh=True  # Force refresh for repairs
                )

                # Stage 4: Complete
                if profile and metadata.get("success", False):
                    await self._update_profile_stage(
                        operation_id, username,
                        ProcessingStage.COMPLETED,
                        "Profile processing completed successfully!",
                        progress_percent=100
                    )
                    logger.info(f"✅ Isolated processing completed for {username}")
                else:
                    await self._update_profile_stage(
                        operation_id, username,
                        ProcessingStage.FAILED,
                        f"Processing failed: {metadata.get('error', 'Unknown error')}",
                        progress_percent=0
                    )
                    logger.error(f"❌ Isolated processing failed for {username}")

        except Exception as e:
            logger.error(f"❌ Isolated processing failed for {username}: {e}")
            await self._update_profile_stage(
                operation_id, username,
                ProcessingStage.FAILED,
                f"Processing failed with exception: {str(e)}",
                progress_percent=0
            )

    async def _handle_analytics_progress(
        self,
        operation_id: str,
        username: str,
        stage: str,
        message: str,
        percent: int
    ):
        """
        Handle progress callbacks from creator analytics service
        """
        # Map analytics stages to our ProcessingStage enum
        stage_mapping = {
            "apify_completed": ProcessingStage.APIFY_COMPLETED,
            "cdn_processing": ProcessingStage.CDN_PROCESSING,
            "cdn_completed": ProcessingStage.CDN_COMPLETED,
            "ai_processing": ProcessingStage.AI_PROCESSING,
            "ai_completed": ProcessingStage.AI_COMPLETED,
            "database_storing": ProcessingStage.DATABASE_STORING
        }

        processing_stage = stage_mapping.get(stage, ProcessingStage.APIFY_FETCHING)

        await self._update_profile_stage(
            operation_id, username, processing_stage, message, percent
        )

    async def _update_profile_stage(
        self,
        operation_id: str,
        username: str,
        stage: ProcessingStage,
        message: str,
        progress_percent: int
    ):
        """
        Update the current profile's processing stage
        """
        operation = self.active_operations.get(operation_id)
        if not operation or not operation.current_profile:
            return

        if operation.current_profile.username == username:
            operation.current_profile.stage = stage
            operation.current_profile.stage_message = message
            operation.current_profile.stage_progress_percent = progress_percent
            operation.current_profile.updated_at = datetime.now(timezone.utc)

            if stage == ProcessingStage.APIFY_FETCHING and not operation.current_profile.stage_started_at:
                operation.current_profile.stage_started_at = datetime.now(timezone.utc)

            operation.last_updated = datetime.now(timezone.utc)

            # Store in Redis for real-time access
            await self._store_operation_in_redis(operation)

    async def _update_operation_progress(self, operation_id: str):
        """
        Update operation-level progress and store in Redis
        """
        operation = self.active_operations.get(operation_id)
        if not operation:
            return

        operation.last_updated = datetime.now(timezone.utc)
        await self._store_operation_in_redis(operation)

    async def _store_operation_in_redis(self, operation: BulkRepairOperation):
        """
        Store operation progress in Redis for real-time access
        """
        try:
            operation_dict = asdict(operation)
            # Convert datetime objects to ISO strings for JSON serialization
            operation_dict = self._convert_datetimes_to_iso(operation_dict)

            await redis_cache.set(
                key_type=self.redis_prefix,
                identifier=f"operation:{operation.operation_id}",
                data=operation_dict,  # Pass dict directly, not JSON string
                ttl=7200  # 2 hours
            )
        except Exception as e:
            logger.error(f"Failed to store operation in Redis: {e}")

    def _convert_datetimes_to_iso(self, obj):
        """
        Recursively convert datetime objects to ISO strings for JSON serialization
        """
        if isinstance(obj, dict):
            return {k: self._convert_datetimes_to_iso(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetimes_to_iso(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (ProcessingStage, OperationStatus)):
            return obj.value
        else:
            return obj

    async def get_operation_progress(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current operation progress for real-time monitoring
        """
        try:
            # Try memory first
            if operation_id in self.active_operations:
                operation = self.active_operations[operation_id]
                return asdict(operation)

            # Fallback to Redis
            redis_data = await redis_cache.get(f"{self.redis_prefix}:operation:{operation_id}")
            if redis_data:
                return json.loads(redis_data)

            return None
        except Exception as e:
            logger.error(f"Failed to get operation progress: {e}")
            return None

    async def get_all_active_operations(self) -> List[Dict[str, Any]]:
        """
        Get all currently active operations for admin monitoring
        """
        try:
            operations = []
            for operation in self.active_operations.values():
                operations.append(asdict(operation))
            return operations
        except Exception as e:
            logger.error(f"Failed to get active operations: {e}")
            return []

    async def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel an active operation
        """
        try:
            if operation_id in self.active_operations:
                self.active_operations[operation_id].operation_status = OperationStatus.CANCELLED
                await self._update_operation_progress(operation_id)
                logger.info(f"🛑 Cancelled bulk repair operation {operation_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel operation: {e}")
            return False


# Global service instance
bulk_repair_progress_service = BulkRepairProgressService()