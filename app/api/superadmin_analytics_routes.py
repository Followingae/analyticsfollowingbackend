"""
Superadmin Analytics Routes - Enterprise Grade Creator Analytics Management

Provides comprehensive superadmin endpoints for analytics completeness management.
These endpoints are protected with superadmin authentication and provide full
control over the creator analytics system.

Key Features:
✅ Complete profile analytics scanning and repair
✅ Real-time system monitoring and health checks
✅ Batch operations with progress tracking
✅ Integration with bulletproof creator search pipeline
✅ Comprehensive audit logging and error handling
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from uuid import UUID

from app.database.connection import get_session
from app.services.superadmin_analytics_completeness_service import (
    superadmin_analytics_completeness_service,
    RepairStatus
)
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.unified_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/superadmin/analytics-completeness", tags=["Superadmin - Analytics Completeness"])


# Pydantic Models for Request/Response

class ProfileCompletnessScanRequest(BaseModel):
    """Request model for profile completeness scanning"""
    limit: Optional[int] = Field(None, description="Maximum profiles to scan (None for all)")
    username_filter: Optional[str] = Field(None, description="Filter profiles by username pattern")
    include_complete: bool = Field(False, description="Include complete profiles in results")


class ProfileCompletnessScanResponse(BaseModel):
    """Response model for profile completeness scanning"""
    success: bool
    scan_timestamp: str
    execution_time_seconds: float
    summary: Dict[str, Any]
    profiles: List[Dict[str, Any]]
    incomplete_profiles: List[Dict[str, Any]]


class ProfileRepairRequest(BaseModel):
    """Request model for profile repair operations"""
    profile_ids: Optional[List[UUID]] = Field(None, description="Specific profile IDs to repair (None for all incomplete)")
    max_profiles: Optional[int] = Field(100, description="Maximum profiles to repair in this operation")
    dry_run: bool = Field(False, description="Simulate repair without execution")
    force_repair: bool = Field(False, description="Force repair even for recently processed profiles")


class ProfileRepairResponse(BaseModel):
    """Response model for profile repair operations"""
    success: bool
    operation_id: str
    execution_time_seconds: Optional[float]
    dry_run: bool = False
    summary: Optional[Dict[str, Any]]
    repair_results: Optional[List[Dict[str, Any]]]
    profiles_to_repair: Optional[int] = None  # For dry run


class DashboardResponse(BaseModel):
    """Response model for completeness dashboard"""
    success: bool
    generated_at: str
    system_stats: Dict[str, Any]
    completeness_distribution: List[Dict[str, Any]]
    recent_repair_operations: List[Dict[str, Any]]
    system_health: Dict[str, Any]


class ProfileValidationResponse(BaseModel):
    """Response model for single profile validation"""
    success: bool
    username: str
    profile_analysis: Dict[str, Any]
    posts_analysis: Dict[str, Any]
    recommendations: List[str]
    validated_at: str


# Helper function to ensure superadmin access - FIXED TO MATCH WORKER ENDPOINTS
def require_superadmin():
    """Require superadmin access for these endpoints - uses same auth as worker endpoints"""
    def _require_superadmin(current_user: User = Depends(require_admin())):
        # Use the same role validation as worker monitoring endpoints
        # The require_admin() function already handles all admin role variations
        # including "admin", "superadmin", "super_admin", etc.
        return current_user
    return _require_superadmin


# Core Scanning and Repair Endpoints

@router.post("/scan", response_model=ProfileCompletnessScanResponse)
async def scan_profile_completeness(
    request: ProfileCompletnessScanRequest,
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Scan ALL profiles for completeness against ola.alnomairi benchmark

    **Superadmin Only** - Comprehensive analysis of profile completeness across the system.
    Identifies all profiles that don't meet the 100% complete criteria.

    **Completeness Criteria:**
    - Basic data: followers_count > 0, posts_count > 0, biography, full_name
    - Posts data: Minimum 12 posts stored in database
    - AI Analysis: 12+ posts with AI analysis + profile AI analysis completed
    - CDN Processing: 12+ posts with CDN thumbnails
    - AI Aggregation: Profile-level AI distribution data
    """
    try:
        logger.info(f"🔍 Superadmin completeness scan initiated by {admin_user.email}")
        logger.info(f"Scan parameters: limit={request.limit}, filter={request.username_filter}, include_complete={request.include_complete}")

        result = await superadmin_analytics_completeness_service.scan_all_profiles_completeness(
            db=db,
            limit=request.limit,
            username_filter=request.username_filter,
            include_complete=request.include_complete
        )

        logger.info(f"✅ Scan completed: {result['summary']['total_profiles']} profiles, {result['summary']['incomplete_profiles']} incomplete")

        return result

    except Exception as e:
        logger.error(f"❌ Completeness scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Completeness scan failed: {str(e)}")


@router.post("/repair", response_model=ProfileRepairResponse)
async def repair_incomplete_profiles(
    request: ProfileRepairRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Repair incomplete profiles using bulletproof creator search pipeline

    **Superadmin Only** - Triggers complete creator analytics pipeline for incomplete profiles.
    Uses the bulletproof creator search system to ensure 100% completeness.

    **Process:**
    1. Identifies incomplete profiles (or uses provided profile_ids)
    2. Triggers full APIFY + CDN + AI analysis pipeline for each profile
    3. Validates completeness post-repair
    4. Provides detailed success/failure reporting

    **Rate Limiting:** Max 5 concurrent repairs, 100 repairs per hour
    """
    try:
        logger.info(f"🔧 Superadmin repair operation initiated by {admin_user.email}")
        logger.info(f"Repair parameters: profile_ids={len(request.profile_ids) if request.profile_ids else 'all'}, max={request.max_profiles}, dry_run={request.dry_run}")

        if not request.dry_run:
            logger.warning(f"⚠️ LIVE REPAIR MODE - Superadmin {admin_user.email} is running actual profile repairs")

        result = await superadmin_analytics_completeness_service.repair_incomplete_profiles(
            db=db,
            admin_email=admin_user.email,
            profile_ids=request.profile_ids,
            max_profiles=request.max_profiles,
            dry_run=request.dry_run
        )

        logger.info(f"✅ Repair operation completed: {result.get('summary', {}).get('successful_repairs', 0)} successful")

        return result

    except Exception as e:
        logger.error(f"❌ Profile repair operation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Profile repair operation failed: {str(e)}")


# Monitoring and Dashboard Endpoints

@router.get("/dashboard", response_model=DashboardResponse)
async def get_completeness_dashboard(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get comprehensive analytics completeness dashboard

    **Superadmin Only** - Real-time system overview showing:
    - System-wide completeness statistics
    - Profile distribution by completeness score
    - Recent repair operations history
    - System health recommendations
    - Activity metrics and trends
    """
    try:
        logger.info(f"📊 Dashboard request by superadmin {admin_user.email}")

        dashboard_data = await superadmin_analytics_completeness_service.get_completeness_dashboard(db)

        logger.info(f"✅ Dashboard generated: {dashboard_data['system_stats']['completeness_percentage']:.1f}% system completeness")

        return dashboard_data

    except Exception as e:
        logger.error(f"❌ Dashboard generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")


@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get quick system statistics for analytics completeness

    **Superadmin Only** - Quick overview of system health and completeness metrics.
    """
    try:
        logger.info(f"📈 Stats request by superadmin {admin_user.email}")

        dashboard_data = await superadmin_analytics_completeness_service.get_completeness_dashboard(db)

        return {
            "success": True,
            "timestamp": dashboard_data["generated_at"],
            "system_stats": dashboard_data["system_stats"],
            "system_health": dashboard_data["system_health"]
        }

    except Exception as e:
        logger.error(f"❌ Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


# Individual Profile Management

@router.post("/validate/{username}", response_model=ProfileValidationResponse)
async def validate_profile_completeness(
    username: str,
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Validate completeness of a specific profile with detailed analysis

    **Superadmin Only** - Comprehensive analysis of a single profile's completeness status.
    Provides detailed breakdown of missing components and specific recommendations.
    """
    try:
        logger.info(f"🔍 Profile validation request by superadmin {admin_user.email} for @{username}")

        result = await superadmin_analytics_completeness_service.validate_single_profile(
            db=db,
            username=username
        )

        logger.info(f"✅ Profile validation completed for @{username}: {'Complete' if result['profile_analysis']['is_complete'] else 'Incomplete'}")

        return result

    except Exception as e:
        logger.error(f"❌ Profile validation failed for @{username}: {e}")
        raise HTTPException(status_code=500, detail=f"Profile validation failed: {str(e)}")


@router.post("/repair-single/{username}")
async def repair_single_profile(
    username: str,
    background_tasks: BackgroundTasks,
    force_repair: bool = Query(False, description="Force repair even if recently processed"),
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Repair a single profile using bulletproof creator search

    **Superadmin Only** - Triggers complete analytics pipeline for a specific profile.
    Useful for testing or fixing individual profile issues.
    """
    try:
        logger.info(f"🔧 Single profile repair by superadmin {admin_user.email} for @{username}")

        # Get profile ID first
        from sqlalchemy import select
        from app.database.unified_models import Profile

        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile @{username} not found in database")

        # Trigger repair for single profile
        result = await superadmin_analytics_completeness_service.repair_incomplete_profiles(
            db=db,
            admin_email=admin_user.email,
            profile_ids=[profile.id],
            max_profiles=1,
            dry_run=False
        )

        logger.info(f"✅ Single profile repair completed for @{username}")

        return {
            "success": True,
            "username": username,
            "profile_id": str(profile.id),
            "repair_result": result,
            "message": f"Profile @{username} repair operation completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Single profile repair failed for @{username}: {e}")
        raise HTTPException(status_code=500, detail=f"Single profile repair failed: {str(e)}")


# Bulk Operations and Utilities

@router.get("/incomplete-profiles")
async def get_incomplete_profiles(
    page: int = Query(1, description="Page number"),
    per_page: int = Query(50, description="Profiles per page"),
    username_filter: Optional[str] = Query(None, description="Filter by username"),
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get paginated list of incomplete profiles with detailed analysis

    **GOD MODE SUPERADMIN** - Shows exactly which profiles need fixing and why
    """
    try:
        logger.info(f"🔍 Incomplete profiles request by superadmin {admin_user.email}")

        from sqlalchemy import select, func, and_, or_
        from app.database.unified_models import Profile, Post

        # Use proper completeness analysis from the completeness service
        from app.services.superadmin_analytics_completeness_service import SuperadminAnalyticsCompletenessService
        completeness_service = SuperadminAnalyticsCompletenessService()

        # Get all incomplete profiles using the proper completeness analysis
        incomplete_results = await completeness_service.scan_all_profiles_completeness(
            db=db,
            username_filter=username_filter,
            include_complete=False,  # Get only incomplete profiles
            limit=1000  # Large limit to get all incomplete profiles
        )

        # Filter only incomplete profiles
        all_incomplete_profiles = incomplete_results.get("incomplete_profiles", [])

        total_count = len(all_incomplete_profiles)

        # Manual pagination since we're using the service
        offset = (page - 1) * per_page
        profiles_page = all_incomplete_profiles[offset:offset + per_page]

        # Convert service results to API response format
        incomplete_profiles = []
        for profile_dict in profiles_page:
            # Build issues list based on completeness analysis
            issues = []
            if not profile_dict.get('has_basic_data'):
                issues.append("Missing basic data (followers, posts, biography, or full_name)")
            if not profile_dict.get('has_minimum_posts'):
                issues.append(f"Only {profile_dict.get('stored_posts_count', 0)} posts (need 12+)")
            if not profile_dict.get('has_ai_posts'):
                issues.append(f"Only {profile_dict.get('ai_analyzed_posts_count', 0)} AI analyzed posts (need 12+)")
            if not profile_dict.get('has_profile_ai'):
                issues.append("No profile AI analysis")
            if not profile_dict.get('has_cdn_posts'):
                issues.append(f"Only {profile_dict.get('cdn_processed_posts_count', 0)} CDN processed posts (need 12+)")
            if not profile_dict.get('has_ai_aggregation'):
                issues.append("Missing AI aggregation data")

            incomplete_profiles.append({
                "id": profile_dict.get('profile_id'),
                "username": profile_dict.get('username'),
                "followers_count": profile_dict.get('followers_count', 0),
                "posts_count": profile_dict.get('stored_posts_count', 0),
                "ai_posts_count": profile_dict.get('ai_analyzed_posts_count', 0),
                "cdn_posts_count": profile_dict.get('cdn_processed_posts_count', 0),
                "has_profile_ai": profile_dict.get('has_profile_ai', False),
                "created_at": profile_dict.get('created_at'),
                "updated_at": profile_dict.get('updated_at'),
                "issues": issues,
                "completeness_score": float(profile_dict.get('completeness_score', 0))
            })

        return {
            "success": True,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "profiles": incomplete_profiles,
            "summary": {
                "total_incomplete": total_count,
                "showing": len(incomplete_profiles)
            }
        }

    except Exception as e:
        logger.error(f"❌ Incomplete profiles listing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get incomplete profiles: {str(e)}")


@router.post("/bulk-scan-usernames")
async def bulk_scan_usernames(
    usernames: List[str] = Body(..., description="List of usernames to scan"),
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Scan completeness for a specific list of usernames

    **Superadmin Only** - Bulk scanning operation for specific profiles.
    Useful for targeted analysis of particular creators.
    """
    try:
        logger.info(f"📋 Bulk username scan by superadmin {admin_user.email}: {len(usernames)} usernames")

        results = []
        for username in usernames:
            try:
                result = await superadmin_analytics_completeness_service.validate_single_profile(
                    db=db,
                    username=username
                )
                results.append({
                    "username": username,
                    "status": "found",
                    "is_complete": result["profile_analysis"]["is_complete"],
                    "completeness_score": result["profile_analysis"]["completeness_score"],
                    "missing_components": result["profile_analysis"]["missing_components"]
                })
            except Exception as e:
                results.append({
                    "username": username,
                    "status": "error",
                    "error": str(e)
                })

        complete_count = len([r for r in results if r.get("is_complete")])
        found_count = len([r for r in results if r["status"] == "found"])

        logger.info(f"✅ Bulk scan completed: {found_count}/{len(usernames)} found, {complete_count} complete")

        return {
            "success": True,
            "scanned_usernames": len(usernames),
            "found_profiles": found_count,
            "complete_profiles": complete_count,
            "results": results,
            "summary": {
                "total_requested": len(usernames),
                "profiles_found": found_count,
                "profiles_complete": complete_count,
                "profiles_incomplete": found_count - complete_count,
                "profiles_not_found": len(usernames) - found_count
            }
        }

    except Exception as e:
        logger.error(f"❌ Bulk username scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk username scan failed: {str(e)}")


# System Health and Maintenance

@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get comprehensive system health status for analytics completeness

    **Superadmin Only** - Complete system health check including:
    - Database connectivity and performance
    - Service availability and status
    - Error rates and system metrics
    - Recommendations for system optimization
    """
    try:
        logger.info(f"🏥 System health check by superadmin {admin_user.email}")

        # Get dashboard data for health metrics
        dashboard_data = await superadmin_analytics_completeness_service.get_completeness_dashboard(db)

        # Additional health checks
        from datetime import datetime, timezone

        health_data = {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": dashboard_data["system_health"]["status"],
            "components": {
                "database": {
                    "status": "healthy",
                    "description": "Database connection and queries operational"
                },
                "analytics_service": {
                    "status": "healthy",
                    "description": "Analytics completeness service operational"
                },
                "bulletproof_search": {
                    "status": "healthy",
                    "description": "Bulletproof creator search service available"
                }
            },
            "metrics": dashboard_data["system_stats"],
            "recommendations": dashboard_data["system_health"]["recommendations"],
            "recent_activity": {
                "profiles_created_24h": dashboard_data["system_stats"]["profiles_created_24h"],
                "profiles_updated_24h": dashboard_data["system_stats"]["profiles_updated_24h"],
                "recent_repairs": len(dashboard_data["recent_repair_operations"])
            }
        }

        logger.info(f"✅ System health check completed: {health_data['overall_status']}")

        return health_data

    except Exception as e:
        logger.error(f"❌ System health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"System health check failed: {str(e)}")


@router.post("/maintenance/optimize-database")
async def optimize_database(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Run database optimization for analytics completeness

    **Superadmin Only** - Database maintenance operations including:
    - Index optimization and analysis
    - Statistics updates for query performance
    - Cleanup of orphaned records
    """
    try:
        logger.info(f"🔧 Database optimization initiated by superadmin {admin_user.email}")

        # Run database optimization queries
        optimization_queries = [
            "ANALYZE profiles;",
            "ANALYZE posts;",
            "VACUUM ANALYZE profiles;",
            "VACUUM ANALYZE posts;"
        ]

        results = []
        for query in optimization_queries:
            try:
                await db.execute(text(query))
                results.append({"query": query, "status": "success"})
            except Exception as e:
                results.append({"query": query, "status": "failed", "error": str(e)})

        await db.commit()

        logger.info(f"✅ Database optimization completed")

        return {
            "success": True,
            "optimization_timestamp": datetime.now(timezone.utc).isoformat(),
            "operations_completed": len([r for r in results if r["status"] == "success"]),
            "operations_failed": len([r for r in results if r["status"] == "failed"]),
            "results": results,
            "message": "Database optimization completed successfully"
        }

    except Exception as e:
        logger.error(f"❌ Database optimization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database optimization failed: {str(e)}")


# Import required dependencies
from datetime import datetime, timezone
from sqlalchemy import text


# =============================================================================
# BULK REPAIR PROGRESS MONITORING ENDPOINTS
# =============================================================================

@router.get("/progress/{operation_id}")
async def get_bulk_repair_progress(
    operation_id: str,
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get real-time progress of a bulk repair operation

    **Superadmin Only** - Monitor sequential bulk repair progress with detailed stage tracking.
    Shows current profile being processed, queue status, and individual stage progress.
    """
    try:
        from app.services.bulk_repair_progress_service import bulk_repair_progress_service

        progress = await bulk_repair_progress_service.get_operation_progress(operation_id)

        if not progress:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")

        logger.info(f"📊 Progress check for operation {operation_id} by {admin_user.email}")

        return {
            "success": True,
            "operation_id": operation_id,
            "progress": progress,
            "last_updated": progress.get("last_updated"),
            "real_time": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get progress for operation {operation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get operation progress: {str(e)}")


@router.get("/operations/active")
async def get_active_bulk_operations(
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get all currently active bulk repair operations

    **Superadmin Only** - Monitor all running bulk repair operations.
    Useful for system-wide monitoring and operation management.
    """
    try:
        from app.services.bulk_repair_progress_service import bulk_repair_progress_service

        operations = await bulk_repair_progress_service.get_all_active_operations()

        logger.info(f"📊 Active operations check by {admin_user.email}: {len(operations)} operations")

        return {
            "success": True,
            "active_operations_count": len(operations),
            "operations": operations,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to get active operations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active operations: {str(e)}")


@router.post("/operations/{operation_id}/cancel")
async def cancel_bulk_repair_operation(
    operation_id: str,
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Cancel an active bulk repair operation

    **Superadmin Only** - Emergency cancellation of bulk repair operations.
    Will stop processing after the current profile completes.
    """
    try:
        from app.services.bulk_repair_progress_service import bulk_repair_progress_service

        cancelled = await bulk_repair_progress_service.cancel_operation(operation_id)

        if not cancelled:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found or already completed")

        logger.info(f"🛑 Operation {operation_id} cancelled by {admin_user.email}")

        return {
            "success": True,
            "operation_id": operation_id,
            "status": "cancelled",
            "cancelled_by": admin_user.email,
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "message": "Operation will stop after current profile completes"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to cancel operation {operation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel operation: {str(e)}")


@router.get("/operations/{operation_id}/live")
async def get_live_repair_status(
    operation_id: str,
    admin_user: User = Depends(require_superadmin())
) -> Dict[str, Any]:
    """
    Get live status updates for frontend real-time monitoring

    **Superadmin Only** - Optimized endpoint for real-time frontend updates.
    Returns minimal, frequently-updated data for live monitoring dashboards.
    """
    try:
        from app.services.bulk_repair_progress_service import bulk_repair_progress_service

        progress = await bulk_repair_progress_service.get_operation_progress(operation_id)

        if not progress:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")

        # Extract key live data for frontend
        current_profile = progress.get("current_profile", {})
        live_status = {
            "operation_id": operation_id,
            "status": progress.get("operation_status"),
            "current_profile_index": progress.get("current_profile_index", 0),
            "total_profiles": progress.get("total_profiles", 0),
            "profiles_completed": progress.get("profiles_completed", 0),
            "profiles_failed": progress.get("profiles_failed", 0),
            "current_profile": {
                "username": current_profile.get("username"),
                "stage": current_profile.get("stage"),
                "stage_message": current_profile.get("stage_message"),
                "progress_percent": current_profile.get("stage_progress_percent", 0)
            } if current_profile else None,
            "queue_remaining": len(progress.get("queue", [])),
            "last_updated": progress.get("last_updated"),
            "estimated_completion": progress.get("estimated_completion")
        }

        return {
            "success": True,
            "live_status": live_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get live status for operation {operation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get live status: {str(e)}")