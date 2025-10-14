"""
Background Similar Profiles Processor

Advanced background processor that integrates with the existing ComprehensiveDataService
to hook into related_profiles storage and trigger discovery processing.

This processor provides:
- Integration hooks for existing analytics flows
- Queue-based background processing
- Advanced retry and error handling
- Rate limiting and quality filtering
- Zero interference with existing systems
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass, field
from enum import Enum

from app.database.connection import get_session
from app.services.similar_profiles_discovery_service import similar_profiles_discovery_service
from app.core.discovery_config import discovery_settings, DiscoveryConstants

logger = logging.getLogger(__name__)


class ProcessorEventType(Enum):
    """Types of processor events"""
    RELATED_PROFILES_STORED = "related_profiles_stored"
    POST_ANALYTICS_COMPLETE = "post_analytics_complete"
    CREATOR_ANALYTICS_COMPLETE = "creator_analytics_complete"
    MANUAL_DISCOVERY_REQUEST = "manual_discovery_request"


@dataclass
class ProcessorEvent:
    """Background processor event"""
    event_type: ProcessorEventType
    source_username: str
    profile_id: UUID
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    last_error: Optional[str] = None


@dataclass
class ProcessorStats:
    """Background processor statistics"""
    events_processed: int = 0
    events_successful: int = 0
    events_failed: int = 0
    profiles_discovered: int = 0
    last_processed_at: Optional[datetime] = None
    total_processing_time: float = 0.0


class SimilarProfilesBackgroundProcessor:
    """
    Background processor for similar profiles discovery

    This processor integrates with existing analytics flows by providing
    hook functions that can be called after related_profiles are stored.
    """

    def __init__(self):
        self.stats = ProcessorStats()
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background processor"""
        if self.is_running:
            logger.warning("Background processor already running")
            return

        self.is_running = True
        self.worker_task = asyncio.create_task(self._background_worker())
        logger.info("🚀 Similar Profiles Background Processor started")

        # Use delayed startup processing to wait for full app initialization
        asyncio.create_task(self._delayed_startup_processing())

    async def stop(self) -> None:
        """Stop the background processor"""
        if not self.is_running:
            return

        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Similar Profiles Background Processor stopped")

    async def queue_event(self, event: ProcessorEvent) -> None:
        """Queue an event for background processing"""
        if not discovery_settings.DISCOVERY_ENABLED:
            logger.debug(f"Discovery disabled - skipping event for @{event.source_username}")
            return

        try:
            await self.event_queue.put(event)
            logger.debug(f"📥 Queued {event.event_type.value} event for @{event.source_username}")
        except Exception as e:
            logger.error(f"Failed to queue event for @{event.source_username}: {e}")

    async def _background_worker(self) -> None:
        """Main background worker loop with RESOURCE THROTTLING"""
        logger.info("🔄 Background worker started with resource throttling")

        while self.is_running:
            try:
                # Wait for events with timeout
                try:
                    event = await asyncio.wait_for(self.event_queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    continue  # Check if still running

                # Process the event with RESOURCE CONTROL
                await self._process_event(event)

                # CRITICAL: Add delay between processing to not overwhelm system
                # This ensures users can still use the app while discovery runs
                await asyncio.sleep(5)  # 5 second pause between each profile processing

            except asyncio.CancelledError:
                logger.info("Background worker cancelled")
                break
            except Exception as e:
                logger.error(f"Background worker error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue processing despite errors
                await asyncio.sleep(10)  # Longer pause on errors

        logger.info("🔄 Background worker stopped")

    async def _delayed_startup_processing(self) -> None:
        """Handle delayed startup processing - truly in background without blocking"""
        try:
            # Start immediately in background without blocking startup
            logger.info("🎯 Starting background processing of existing discovered profiles...")

            # Add delay to let app finish startup first
            await asyncio.sleep(90)  # 90 seconds as requested

            if not self.is_running:
                logger.warning("Background processor stopped during startup")
                return

            await self._process_existing_discovered_profiles()
            logger.info("✅ Background processing of existing profiles completed")

        except Exception as e:
            logger.error(f"Background processing failed: {e}")
            # Don't print full traceback to keep logs clean
            logger.debug(f"Full error trace: {e}")

    async def _process_existing_discovered_profiles(self) -> None:
        """Process existing discovered profiles from related_profiles table"""
        try:
            from app.database.connection import get_session
            from app.database.unified_models import RelatedProfile, Profile
            from sqlalchemy import select

            async with get_session() as db:
                # Try to get only user search profiles, fallback to all if source_type doesn't exist
                discovered_usernames = []

                try:
                    # Preferred: Only process user search profiles (prevents infinite loops)
                    query = select(RelatedProfile.related_username).distinct().where(
                        RelatedProfile.source_type == 'user_search'
                    )
                    result = await db.execute(query)
                    discovered_usernames = [row[0] for row in result.fetchall()]
                    # Reduce logging to be less intrusive
                    if len(discovered_usernames) > 0:
                        logger.debug(f"📊 Processing {len(discovered_usernames)} user search profiles")
                except Exception as e:
                    # Fallback: If source_type column doesn't exist, get all (legacy behavior)
                    if "source_type does not exist" in str(e):
                        logger.info("📊 Fallback: source_type column not found, using all profiles")
                        query = select(RelatedProfile.related_username).distinct()
                        result = await db.execute(query)
                        discovered_usernames = [row[0] for row in result.fetchall()]
                    else:
                        raise e

                if not discovered_usernames:
                    logger.info("📊 No existing discovered profiles found")
                    return

                logger.info(f"📊 Found {len(discovered_usernames)} discovered profiles to process")

                # Check which ones are not yet in profiles table (unprocessed)
                profiles_query = select(Profile.username).where(Profile.username.in_(discovered_usernames))
                profiles_result = await db.execute(profiles_query)
                existing_profiles = {row[0] for row in profiles_result.fetchall()}

                unprocessed_profiles = [username for username in discovered_usernames if username not in existing_profiles]

                if not unprocessed_profiles:
                    logger.info("📊 All discovered profiles already processed")
                    return

                logger.info(f"🎯 Queuing {len(unprocessed_profiles)} unprocessed profiles for background processing")

                # 🏭 INDUSTRY STANDARD: Queue profiles to separate Celery worker process
                logger.info(f"🎯 Queuing {len(unprocessed_profiles)} discovered profiles for CELERY WORKER processing")

                try:
                    from app.services.celery_discovery_service import celery_discovery_service

                    # Queue all profiles to separate worker process (takes ~0.01 seconds)
                    result = await celery_discovery_service.queue_bulk_discovered_profiles(
                        usernames=unprocessed_profiles,
                        source_type='background_discovery'
                    )

                    if result['success']:
                        logger.info(f"✅ Successfully queued {len(unprocessed_profiles)} profiles to CELERY WORKER")
                        logger.info(f"🏭 Profiles will be processed in separate process with ZERO impact on main app")
                        logger.info(f"⚡ Main app remains 100% responsive for users")
                    else:
                        logger.error(f"❌ Failed to queue profiles to Celery worker: {result.get('error')}")
                        # Fallback to old method if Celery unavailable
                        logger.info("🔄 Falling back to local processing...")
                        await self._fallback_local_processing(unprocessed_profiles)

                except ImportError:
                    logger.warning("🔄 Celery worker not available, falling back to local processing")
                    await self._fallback_local_processing(unprocessed_profiles)
                except Exception as e:
                    logger.error(f"❌ Celery queuing failed: {e}")
                    await self._fallback_local_processing(unprocessed_profiles)

        except Exception as e:
            logger.error(f"Failed to process existing discovered profiles: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _fallback_local_processing(self, unprocessed_profiles: list) -> None:
        """Fallback to local processing if Celery worker unavailable"""
        logger.warning(f"🔄 Using fallback local processing for {len(unprocessed_profiles)} profiles")

        for i, username in enumerate(unprocessed_profiles):
            try:
                event = ProcessorEvent(
                    event_type=ProcessorEventType.MANUAL_DISCOVERY_REQUEST,
                    source_username=username,
                    profile_id=None,  # Will be created during processing
                    metadata={"startup_processing": True, "discovered_profile": True, "fallback": True}
                )
                await self.queue_event(event)

                # Add delay to prevent overwhelming
                if i % 10 == 0 and i > 0:
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to queue discovered profile @{username}: {e}")

        logger.info(f"✅ Fallback: Queued {len(unprocessed_profiles)} profiles for local processing")

    async def _process_event(self, event: ProcessorEvent) -> None:
        """Process a single background event"""
        start_time = datetime.now(timezone.utc)

        try:
            logger.info(f"🔄 Processing {event.event_type.value} for @{event.source_username}")

            event.attempts += 1
            self.stats.events_processed += 1

            # Route event to appropriate handler
            if event.event_type == ProcessorEventType.RELATED_PROFILES_STORED:
                await self._handle_related_profiles_stored(event)
            elif event.event_type == ProcessorEventType.POST_ANALYTICS_COMPLETE:
                await self._handle_post_analytics_complete(event)
            elif event.event_type == ProcessorEventType.CREATOR_ANALYTICS_COMPLETE:
                await self._handle_creator_analytics_complete(event)
            elif event.event_type == ProcessorEventType.MANUAL_DISCOVERY_REQUEST:
                await self._handle_manual_discovery_request(event)
            else:
                logger.warning(f"Unknown event type: {event.event_type}")
                return

            # Update success stats
            self.stats.events_successful += 1
            self.stats.last_processed_at = datetime.now(timezone.utc)

            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.stats.total_processing_time += processing_time

            logger.info(f"✅ Event processed successfully for @{event.source_username} ({processing_time:.2f}s)")

        except Exception as e:
            self.stats.events_failed += 1
            event.last_error = str(e)

            logger.error(f"❌ Event processing failed for @{event.source_username}: {e}")

            # Retry logic for failed events
            if event.attempts < discovery_settings.DISCOVERY_RETRY_ATTEMPTS:
                logger.info(f"🔄 Retrying event for @{event.source_username} (attempt {event.attempts + 1})")
                # Re-queue with delay
                asyncio.create_task(self._retry_event_with_delay(event))
            else:
                logger.error(f"❌ Max retries exceeded for @{event.source_username}")

    async def _handle_related_profiles_stored(self, event: ProcessorEvent) -> None:
        """Handle related_profiles stored event"""
        try:
            # Create new database session for background processing
            async with get_session() as db:
                # Trigger similar profiles discovery through existing service
                await similar_profiles_discovery_service.hook_creator_analytics_similar_profiles(
                    source_username=event.source_username,
                    profile_id=event.profile_id,
                    db=db
                )

        except Exception as e:
            logger.error(f"Failed to handle related_profiles_stored for @{event.source_username}: {e}")
            raise

    async def _handle_post_analytics_complete(self, event: ProcessorEvent) -> None:
        """Handle post analytics completion event"""
        try:
            # Create new database session for background processing
            async with get_session() as db:
                # Extract post shortcode from metadata
                post_shortcode = event.metadata.get("post_shortcode", "unknown")

                # Trigger similar profiles discovery through existing service
                await similar_profiles_discovery_service.hook_post_analytics_similar_profiles(
                    source_username=event.source_username,
                    post_shortcode=post_shortcode,
                    profile_id=event.profile_id,
                    db=db
                )

        except Exception as e:
            logger.error(f"Failed to handle post_analytics_complete for @{event.source_username}: {e}")
            raise

    async def _handle_creator_analytics_complete(self, event: ProcessorEvent) -> None:
        """Handle creator analytics completion event"""
        try:
            # Create new database session for background processing
            async with get_session() as db:
                # Trigger similar profiles discovery through existing service
                await similar_profiles_discovery_service.hook_creator_analytics_similar_profiles(
                    source_username=event.source_username,
                    profile_id=event.profile_id,
                    db=db
                )

        except Exception as e:
            logger.error(f"Failed to handle creator_analytics_complete for @{event.source_username}: {e}")
            raise

    async def _handle_manual_discovery_request(self, event: ProcessorEvent) -> None:
        """Handle manual discovery request - process discovered profile with full Creator Analytics"""
        try:
            # Create new database session for background processing
            async with get_session() as db:
                # 🎯 CRITICAL FIX: Process the discovered profile with FULL Creator Analytics
                # This should run APIFY + CDN + AI for the discovered profile
                logger.info(f"🎯 Processing discovered profile @{event.source_username} with full Creator Analytics")

                from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service

                # Run full Creator Analytics for the discovered profile
                profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                    username=event.source_username,
                    force_refresh=True,  # Always process discovered profiles completely
                    is_background_discovery=True,  # Prevent further discovery loops
                    db=db
                )

                if profile and metadata:
                    logger.info(f"✅ Successfully processed discovered profile @{event.source_username}")
                else:
                    logger.warning(f"⚠️ Discovered profile processing failed for @{event.source_username}")

        except Exception as e:
            logger.error(f"Failed to handle manual_discovery_request for @{event.source_username}: {e}")
            raise

    async def _retry_event_with_delay(self, event: ProcessorEvent) -> None:
        """Retry an event after delay"""
        delay = discovery_settings.DISCOVERY_RETRY_DELAY_SECONDS * (event.attempts ** 2)  # Exponential backoff
        await asyncio.sleep(delay)
        await self.queue_event(event)

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            "is_running": self.is_running,
            "queue_size": self.event_queue.qsize(),
            "events_processed": self.stats.events_processed,
            "events_successful": self.stats.events_successful,
            "events_failed": self.stats.events_failed,
            "profiles_discovered": self.stats.profiles_discovered,
            "last_processed_at": self.stats.last_processed_at.isoformat() if self.stats.last_processed_at else None,
            "total_processing_time": self.stats.total_processing_time,
            "average_processing_time": (
                self.stats.total_processing_time / self.stats.events_processed
                if self.stats.events_processed > 0 else 0.0
            )
        }

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status information"""
        return {
            "queue_size": self.event_queue.qsize(),
            "is_running": self.is_running,
            "worker_active": self.worker_task is not None and not self.worker_task.done(),
            "stats": self.get_stats()
        }


# Global processor instance
similar_profiles_background_processor = SimilarProfilesBackgroundProcessor()


# Integration Hook Functions
# These functions can be called from existing analytics services

async def hook_related_profiles_stored(
    source_username: str,
    profile_id: UUID,
    related_profiles_count: int
) -> None:
    """
    Hook to call after related_profiles are stored in the database

    🏭 INDUSTRY STANDARD: Queues discovery to separate Celery worker process
    """
    if not discovery_settings.DISCOVERY_ENABLED:
        return

    try:
        # Try Celery worker first (industry standard)
        try:
            from app.services.celery_discovery_service import celery_discovery_service

            # Get related profiles from database
            from app.database.connection import get_session
            from app.database.unified_models import RelatedProfile
            from sqlalchemy import select

            async with get_session() as db:
                # Get the related usernames for this profile
                query = select(RelatedProfile.related_username).where(
                    RelatedProfile.profile_id == profile_id
                ).distinct()
                result = await db.execute(query)
                related_usernames = [row[0] for row in result.fetchall()]

                if related_usernames:
                    # Queue to Celery worker (takes ~0.001 seconds)
                    celery_result = await celery_discovery_service.queue_bulk_discovered_profiles(
                        usernames=related_usernames,
                        source_type='user_search'  # These come from user searches
                    )

                    if celery_result['success']:
                        logger.info(f"🏭 [CELERY HOOK] Queued {len(related_usernames)} related profiles to worker for @{source_username}")
                        return
                    else:
                        logger.warning(f"🔄 Celery queuing failed, falling back to local processing")

        except ImportError:
            logger.debug("Celery worker not available, using local processing")

        # Fallback to local processing
        event = ProcessorEvent(
            event_type=ProcessorEventType.RELATED_PROFILES_STORED,
            source_username=source_username,
            profile_id=profile_id,
            metadata={"related_profiles_count": related_profiles_count}
        )

        await similar_profiles_background_processor.queue_event(event)
        logger.info(f"🔗 [LOCAL HOOK] Queued related_profiles processing for @{source_username} ({related_profiles_count} profiles)")

    except Exception as e:
        logger.error(f"Failed to hook related_profiles storage for @{source_username}: {e}")


async def hook_creator_analytics_complete(
    source_username: str,
    profile_id: UUID,
    analytics_metadata: Dict[str, Any]
) -> None:
    """
    Hook to call after creator analytics is complete

    This function can be integrated into CreatorAnalyticsTriggerService
    """
    if not discovery_settings.DISCOVERY_ENABLED:
        return

    try:
        event = ProcessorEvent(
            event_type=ProcessorEventType.CREATOR_ANALYTICS_COMPLETE,
            source_username=source_username,
            profile_id=profile_id,
            metadata=analytics_metadata
        )

        await similar_profiles_background_processor.queue_event(event)
        logger.info(f"🎯 Hooked creator analytics completion for @{source_username}")

    except Exception as e:
        logger.error(f"Failed to hook creator analytics completion for @{source_username}: {e}")


async def hook_post_analytics_complete(
    source_username: str,
    profile_id: UUID,
    post_shortcode: str,
    analytics_metadata: Dict[str, Any]
) -> None:
    """
    Hook to call after post analytics is complete

    This function can be integrated into Post Analytics services
    """
    if not discovery_settings.DISCOVERY_ENABLED:
        return

    try:
        event = ProcessorEvent(
            event_type=ProcessorEventType.POST_ANALYTICS_COMPLETE,
            source_username=source_username,
            profile_id=profile_id,
            metadata={
                "post_shortcode": post_shortcode,
                **analytics_metadata
            }
        )

        await similar_profiles_background_processor.queue_event(event)
        logger.info(f"📸 Hooked post analytics completion for @{source_username}/{post_shortcode}")

    except Exception as e:
        logger.error(f"Failed to hook post analytics completion for @{source_username}: {e}")


# Lifecycle Management
async def start_background_processor() -> None:
    """Start the background processor (call at application startup)"""
    await similar_profiles_background_processor.start()


async def stop_background_processor() -> None:
    """Stop the background processor (call at application shutdown)"""
    await similar_profiles_background_processor.stop()