# app/api/v1/admin/cdn_repair.py

import logging
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.middleware.auth_middleware import get_current_active_user
from app.database.unified_models import User
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.cdn_sync_repair_service import CDNSyncRepairService
# from app.tasks.cdn_sync_monitor import cdn_sync_monitor_task, cdn_sync_health_check_task
# NOTE: Using the fixed worker instead: app.workers.cdn_background_worker_fixed

logger = logging.getLogger(__name__)

def require_superadmin_role(current_user: User):
    """Simple superadmin role check"""
    if not current_user or current_user.role != 'superadmin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required"
        )
    return current_user

router = APIRouter(
    prefix="/admin/cdn",
    tags=["Admin - CDN Repair"]
)


# Response Models
class SyncGapInfo(BaseModel):
    asset_id: str
    media_id: str
    username: str
    source_type: str
    expected_path: str
    file_size: int
    created_at: datetime


class SyncGapsResponse(BaseModel):
    gaps_found: int
    gaps: List[SyncGapInfo]
    scan_time: datetime
    checked_assets: int


class RepairResponse(BaseModel):
    status: str
    gaps_found: int
    repaired: int
    failed: int
    errors: List[str]
    repaired_assets: List[Dict]
    execution_time: float


class HealthReportResponse(BaseModel):
    total_assets: int
    pending_assets: int
    completed_assets: int
    failed_assets: int
    potential_sync_gaps: int
    health_score: float
    last_check: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Dict = None
    error: str = None


# Endpoints
@router.get("/sync/detect", response_model=SyncGapsResponse)
async def detect_sync_gaps(
    max_age_hours: int = Query(2, ge=1, le=168, description="Check assets older than X hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Detect sync gaps between R2 storage and database

    **Superadmin Only**: Scan for assets that exist in Cloudflare R2
    but have incorrect database status (pending/processing).

    - **max_age_hours**: Only check assets older than this (1-168 hours)
    - Returns list of detected gaps with file information
    """
    require_superadmin_role(current_user)
    logger.info(f"Superadmin {current_user.email} initiated sync gap detection")

    try:
        scan_start = datetime.utcnow()
        service = CDNSyncRepairService()

        # Get all pending assets for counting

        # Detect gaps
        gaps = await service.detect_sync_gaps(db, max_age_hours=max_age_hours)

        # Format gaps for response
        formatted_gaps = [
            SyncGapInfo(
                asset_id=gap["asset_id"],
                media_id=gap["media_id"],
                username=gap["username"],
                source_type=gap["source_type"],
                expected_path=gap["expected_path"],
                file_size=gap["file_info"].get("size", 0),
                created_at=gap["created_at"]
            )
            for gap in gaps
        ]

        logger.info(f"Sync gap detection completed: {len(gaps)} gaps found")

        return SyncGapsResponse(
            gaps_found=len(gaps),
            gaps=formatted_gaps,
            scan_time=scan_start,
            checked_assets=len(gaps)  # For now, just use gaps count
        )

    except Exception as e:
        logger.error(f"Sync gap detection failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect sync gaps: {str(e)}"
        )


@router.post("/sync/repair", response_model=RepairResponse)
async def repair_sync_gaps(
    max_age_hours: int = Query(2, ge=1, le=168, description="Repair assets older than X hours"),
    dry_run: bool = Query(False, description="Preview changes without applying them"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Repair detected sync gaps

    **Superadmin Only**: Fix database records for assets that exist in R2
    but have incorrect status.

    - **max_age_hours**: Only repair assets older than this (1-168 hours)
    - **dry_run**: Preview changes without applying them
    - Updates database records to match R2 reality
    """
    require_superadmin_role(current_user)
    action = "previewing" if dry_run else "repairing"
    logger.info(f"Superadmin {current_user.email} initiated sync gap {action}")

    try:
        repair_start = datetime.utcnow()
        service = CDNSyncRepairService()

        # Detect gaps first
        gaps = await service.detect_sync_gaps(db, max_age_hours=max_age_hours)

        if not gaps:
            return RepairResponse(
                status="success",
                gaps_found=0,
                repaired=0,
                failed=0,
                errors=[],
                repaired_assets=[],
                execution_time=0
            )

        if dry_run:
            # Dry run - just return what would be repaired
            logger.info(f"Dry run: Would repair {len(gaps)} gaps")
            return RepairResponse(
                status="dry_run",
                gaps_found=len(gaps),
                repaired=0,
                failed=0,
                errors=[],
                repaired_assets=[
                    {
                        "asset_id": gap["asset_id"],
                        "media_id": gap["media_id"],
                        "username": gap["username"],
                        "action": "would_repair"
                    }
                    for gap in gaps
                ],
                execution_time=(datetime.utcnow() - repair_start).total_seconds()
            )

        # Actual repair
        results = await service.repair_sync_gaps(db, gaps)
        execution_time = (datetime.utcnow() - repair_start).total_seconds()

        logger.info(
            f"Manual sync repair completed by {current_user.email}: "
            f"{results['repaired']} repaired, {results['failed']} failed"
        )

        return RepairResponse(
            status="success" if results['failed'] == 0 else "partial_success",
            gaps_found=len(gaps),
            repaired=results['repaired'],
            failed=results['failed'],
            errors=results['errors'],
            repaired_assets=results['repaired_assets'],
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"Sync gap repair failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to repair sync gaps: {str(e)}"
        )


@router.get("/health", response_model=HealthReportResponse)
async def get_sync_health_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get comprehensive CDN sync health report

    **Superadmin Only**: View detailed health metrics for CDN sync system.

    - Total assets by status
    - Potential sync gaps
    - Overall health score (0-100)
    - System performance metrics
    """
    require_superadmin_role(current_user)
    logger.info(f"Superadmin {current_user.email} requested sync health report")

    try:
        service = CDNSyncRepairService()
        health_report = await service.get_sync_health_report(db)

        logger.info(f"Health report generated: {health_report['health_score']:.1f}% health score")

        return HealthReportResponse(**health_report)

    except Exception as e:
        logger.error(f"Health report generation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate health report: {str(e)}"
        )


# COMMENTED OUT - Use the fixed worker instead
# @router.post("/sync/run-monitor", response_model=TaskStatusResponse)
# async def trigger_sync_monitor_task(
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_active_user)
# ):
#     """Use app.workers.cdn_background_worker_fixed instead"""
#     pass


# COMMENTED OUT - Use the fixed worker instead
# @router.post("/health/run-check", response_model=TaskStatusResponse)
# async def trigger_health_check_task(...):
#     """Use app.workers.cdn_background_worker_fixed instead"""
#     pass


# COMMENTED OUT - Use the fixed worker instead
# @router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
# async def get_task_status(...):
#     """Use app.workers.cdn_background_worker_fixed instead"""
#     pass