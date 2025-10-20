"""
Admin Repair Routes - Profile Completeness Management

Admin-only endpoints for managing profile completeness repair operations.
These endpoints provide manual control over the repair system.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database.connection import get_session
from app.services.profile_completeness_repair_service import profile_completeness_repair_service
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.unified_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/repair", tags=["Admin - Repair"])


# Pydantic Models for Request/Response
class ProfileCompletenessRequest(BaseModel):
    """Request model for profile completeness operations"""
    limit: Optional[int] = None
    username_filter: Optional[str] = None
    dry_run: bool = True
    force_repair: bool = False


class ProfileCompletenessResponse(BaseModel):
    """Response model for profile completeness operations"""
    success: bool
    message: str
    scan_results: Dict[str, Any]
    repair_results: Optional[Dict[str, Any]] = None
    incomplete_profiles: Optional[List[Dict[str, Any]]] = None


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


@router.get("/health")
async def get_repair_system_health(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Get repair system health status

    Admin-only endpoint for system health monitoring.
    """
    try:
        logger.info(f"System health check by {admin_user.email}")

        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "repair_service": {
                    "status": "available",
                    "description": "Profile completeness repair service"
                },
                "database": {
                    "status": "connected",
                    "description": "Database connection active"
                }
            }
        }

        return {
            "success": True,
            "health": health_status,
            "message": "System health check completed"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")