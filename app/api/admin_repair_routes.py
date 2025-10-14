"""
Admin Repair Routes - Profile Completeness and Discovery Management

Admin-only endpoints for managing profile completeness repair and discovery operations.
These endpoints provide manual control over the repair and discovery systems.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database.connection import get_session
from app.services.profile_completeness_repair_service import profile_completeness_repair_service
from app.services.similar_profiles_discovery_service import similar_profiles_discovery_service
from app.services.background.similar_profiles_processor import similar_profiles_background_processor
from app.core.discovery_config import discovery_settings, validate_discovery_config
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.unified_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/repair", tags=["Admin - Repair & Discovery"])


# Pydantic Models for Request/Response
class ProfileCompletenessRequest(BaseModel):
    """Request model for profile completeness operations"""
    limit: Optional[int] = None
    username_filter: Optional[str] = None
    dry_run: bool = False
    force_repair: bool = False


class ProfileCompletenessResponse(BaseModel):
    """Response model for profile completeness operations"""
    success: bool
    message: str
    scan_results: Dict[str, Any]
    repair_results: Optional[Dict[str, Any]] = None
    incomplete_profiles: Optional[List[Dict[str, Any]]] = None


class DiscoveryStatsResponse(BaseModel):
    """Response model for discovery statistics"""
    config: Dict[str, Any]
    stats: Dict[str, Any]
    rate_limits: Dict[str, Any]
    processor_stats: Dict[str, Any]


# Profile Completeness Repair Endpoints

@router.get("/profile-completeness/scan")
async def scan_profile_completeness(
    limit: Optional[int] = Query(None, description="Maximum profiles to check"),
    username_filter: Optional[str] = Query(None, description="Filter profiles by username pattern"),
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Scan database for profile completeness status

    Admin-only endpoint to check which profiles are incomplete.
    """
    try:
        logger.info(f"Admin scan request by {admin_user.email}: limit={limit}, filter={username_filter}")

        statuses = await profile_completeness_repair_service.scan_profile_completeness(
            db=db,
            limit=limit,
            username_filter=username_filter
        )

        incomplete_profiles = [s for s in statuses if not s.is_complete]

        return {
            "success": True,
            "message": f"Scanned {len(statuses)} profiles",
            "summary": {
                "total_profiles": len(statuses),
                "complete_profiles": len(statuses) - len(incomplete_profiles),
                "incomplete_profiles": len(incomplete_profiles)
            },
            "incomplete_profiles": [
                {
                    "username": p.username,
                    "profile_id": str(p.profile_id),
                    "missing_components": p.missing_components,
                    "followers_count": p.followers_count,
                    "posts_count": p.posts_count,
                    "stored_posts_count": p.stored_posts_count,
                    "has_ai_analysis": p.has_ai_analysis
                }
                for p in incomplete_profiles
            ]
        }

    except Exception as e:
        logger.error(f"Profile completeness scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.post("/profile-completeness/repair")
async def repair_profile_completeness(
    request: ProfileCompletenessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> ProfileCompletenessResponse:
    """
    Repair incomplete profiles in database

    Admin-only endpoint to trigger profile completeness repair operation.
    Can be run as dry-run for testing or with actual repair execution.
    """
    try:
        logger.info(f"Admin repair request by {admin_user.email}: {request.dict()}")

        if not request.dry_run:
            logger.warning(f"⚠️ LIVE REPAIR MODE - Admin {admin_user.email} is running actual repairs")

        # Run the full repair operation
        result = await profile_completeness_repair_service.run_full_repair_scan(
            db=db,
            limit=request.limit,
            username_filter=request.username_filter,
            dry_run=request.dry_run,
            force_repair=request.force_repair
        )

        return ProfileCompletenessResponse(
            success=True,
            message=f"Repair operation completed ({'dry run' if request.dry_run else 'live mode'})",
            scan_results=result["scan_results"],
            repair_results=result.get("repair_results"),
            incomplete_profiles=result.get("incomplete_profiles_details")
        )

    except Exception as e:
        logger.error(f"Profile completeness repair failed: {e}")
        raise HTTPException(status_code=500, detail=f"Repair failed: {str(e)}")


# Discovery System Endpoints

@router.get("/discovery/stats")
async def get_discovery_stats(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> DiscoveryStatsResponse:
    """
    Get discovery system statistics and status

    Admin-only endpoint for monitoring discovery system health and performance.
    """
    try:
        logger.info(f"Discovery stats request by {admin_user.email}")

        # Get discovery service stats
        discovery_stats = await similar_profiles_discovery_service.get_discovery_stats(db)

        # Get background processor stats
        processor_stats = similar_profiles_background_processor.get_stats()

        # Get configuration validation
        config_validation = validate_discovery_config()

        return DiscoveryStatsResponse(
            config=config_validation["settings"],
            stats=discovery_stats.get("stats", {}),
            rate_limits=discovery_stats.get("rate_limits", {}),
            processor_stats=processor_stats
        )

    except Exception as e:
        logger.error(f"Discovery stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.get("/discovery/config")
async def get_discovery_config(
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Get discovery system configuration and validation status

    Admin-only endpoint for reviewing discovery system configuration.
    """
    try:
        logger.info(f"Discovery config request by {admin_user.email}")

        config_validation = validate_discovery_config()

        return {
            "success": True,
            "config_valid": config_validation["valid"],
            "issues": config_validation["issues"],
            "warnings": config_validation["warnings"],
            "current_settings": {
                "enabled": discovery_settings.DISCOVERY_ENABLED,
                "max_concurrent": discovery_settings.DISCOVERY_MAX_CONCURRENT_PROFILES,
                "batch_size": discovery_settings.DISCOVERY_BATCH_SIZE,
                "min_followers": discovery_settings.DISCOVERY_MIN_FOLLOWERS_COUNT,
                "daily_limit": discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY,
                "hourly_limit": discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_HOUR,
                "skip_existing": discovery_settings.DISCOVERY_SKIP_EXISTING_PROFILES,
                "continue_on_error": discovery_settings.DISCOVERY_CONTINUE_ON_ERROR
            }
        }

    except Exception as e:
        logger.error(f"Discovery config retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Config retrieval failed: {str(e)}")


@router.get("/discovery/queue-status")
async def get_discovery_queue_status(
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Get discovery background processor queue status

    Admin-only endpoint for monitoring background processing queue.
    """
    try:
        logger.info(f"Discovery queue status request by {admin_user.email}")

        queue_status = await similar_profiles_background_processor.get_queue_status()

        return {
            "success": True,
            **queue_status
        }

    except Exception as e:
        logger.error(f"Discovery queue status failed: {e}")
        raise HTTPException(status_code=500, detail=f"Queue status retrieval failed: {str(e)}")


@router.post("/discovery/manual-trigger/{username}")
async def manual_trigger_discovery(
    username: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Manually trigger discovery for a specific profile

    Admin-only endpoint to manually trigger similar profiles discovery
    for a specific username. Useful for testing and debugging.
    """
    try:
        logger.info(f"Manual discovery trigger by {admin_user.email} for @{username}")

        # Check if profile exists
        from sqlalchemy import select
        from app.database.unified_models import Profile

        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile @{username} not found in database")

        # Trigger discovery using the background processor hook
        from app.services.background.similar_profiles_processor import hook_creator_analytics_complete

        await hook_creator_analytics_complete(
            source_username=username,
            profile_id=profile.id,
            analytics_metadata={"manual_trigger": True, "admin_user": admin_user.email}
        )

        return {
            "success": True,
            "message": f"Discovery manually triggered for @{username}",
            "profile_id": str(profile.id),
            "triggered_by": admin_user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual discovery trigger failed for @{username}: {e}")
        raise HTTPException(status_code=500, detail=f"Manual trigger failed: {str(e)}")


# System Health and Monitoring

@router.get("/health")
async def repair_system_health(
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Get repair and discovery system health status

    Admin-only endpoint for comprehensive system health monitoring.
    """
    try:
        logger.info(f"System health check by {admin_user.email}")

        # Check discovery configuration
        config_validation = validate_discovery_config()

        # Get background processor status
        processor_stats = similar_profiles_background_processor.get_stats()
        queue_status = await similar_profiles_background_processor.get_queue_status()

        # Get discovery service stats (if possible)
        discovery_stats = {}
        try:
            async with get_session() as db:
                discovery_stats = await similar_profiles_discovery_service.get_discovery_stats(db)
        except Exception as e:
            discovery_stats = {"error": str(e)}

        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "repair_service": {
                    "status": "available",
                    "description": "Profile completeness repair service"
                },
                "discovery_service": {
                    "status": "available" if discovery_settings.DISCOVERY_ENABLED else "disabled",
                    "description": "Similar profiles discovery service"
                },
                "background_processor": {
                    "status": "running" if queue_status["is_running"] else "stopped",
                    "queue_size": queue_status["queue_size"],
                    "worker_active": queue_status["worker_active"]
                },
                "configuration": {
                    "status": "valid" if config_validation["valid"] else "invalid",
                    "issues": config_validation["issues"],
                    "warnings": config_validation["warnings"]
                }
            },
            "stats": {
                "processor": processor_stats,
                "discovery": discovery_stats
            }
        }

        # Determine overall health
        if config_validation["issues"] or not queue_status["is_running"]:
            health_status["overall_status"] = "degraded"

        return health_status

    except Exception as e:
        logger.error(f"System health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Utility endpoint for testing
@router.post("/test/validate-completeness/{username}")
async def test_validate_profile_completeness(
    username: str,
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Test profile completeness validation for a specific username

    Admin-only endpoint for testing completeness logic on individual profiles.
    """
    try:
        logger.info(f"Profile completeness test by {admin_user.email} for @{username}")

        # Get profile completeness status
        statuses = await profile_completeness_repair_service.scan_profile_completeness(
            db=db,
            limit=1,
            username_filter=username
        )

        if not statuses:
            raise HTTPException(status_code=404, detail=f"Profile @{username} not found")

        status = statuses[0]

        return {
            "success": True,
            "username": status.username,
            "profile_id": str(status.profile_id),
            "is_complete": status.is_complete,
            "missing_components": status.missing_components,
            "details": {
                "followers_count": status.followers_count,
                "posts_count": status.posts_count,
                "has_biography": status.has_biography,
                "has_ai_analysis": status.has_ai_analysis,
                "stored_posts_count": status.stored_posts_count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile completeness test failed for @{username}: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


# Import datetime for health endpoint
from datetime import datetime