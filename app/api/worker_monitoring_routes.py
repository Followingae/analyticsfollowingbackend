"""
Background Worker Real-Time Monitoring Routes

Provides comprehensive real-time monitoring of background workers including:
- Unified background processor status
- AI processing pipeline monitoring
- CDN processing queue status
- Real-time worker health and performance metrics

All endpoints provide live data for real-time dashboard monitoring.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import json
import time

from app.database.connection import get_session
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.unified_models import User
from app.services.unified_background_processor import unified_background_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workers", tags=["Worker Monitoring"])


class WorkerStatsResponse(BaseModel):
    """Response model for worker statistics"""
    timestamp: str
    overall_health: str
    active_workers: int
    total_tasks_processed: int
    total_tasks_in_queue: int
    workers: Dict[str, Any]
    system_metrics: Dict[str, Any]


@router.get("/stats")
async def get_worker_stats(
    db: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin())
) -> WorkerStatsResponse:
    """
    Get comprehensive worker statistics and health status

    Admin-only endpoint for monitoring all background worker activity.
    """
    try:
        logger.info(f"Worker stats request by {admin_user.email}")

        # Get stats from unified background processor
        unified_stats = await _get_unified_processor_stats()
        system_metrics = await _get_system_metrics()

        # Calculate overall health
        overall_health = "healthy"
        active_workers = 1 if unified_stats["status"] == "active" else 0

        if active_workers == 0:
            overall_health = "degraded"

        return WorkerStatsResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            overall_health=overall_health,
            active_workers=active_workers,
            total_tasks_processed=unified_stats["tasks_processed"],
            total_tasks_in_queue=unified_stats["queue_size"],
            workers={
                "unified_processor": {
                    "status": unified_stats["status"],
                    "uptime_seconds": unified_stats["uptime_seconds"],
                    "tasks_processed": unified_stats["tasks_processed"],
                    "tasks_successful": unified_stats["tasks_successful"],
                    "tasks_failed": unified_stats["tasks_failed"],
                    "current_queue_size": unified_stats["queue_size"],
                    "avg_processing_time": unified_stats["avg_processing_time"],
                    "last_activity": unified_stats["last_activity"],
                    "error_rate": unified_stats["error_rate"],
                    "worker_type": "Unified Background Processor",
                    "description": "Handles AI analysis, CDN processing, and system maintenance",
                    "current_job": "Background Processing" if unified_stats["status"] == "active" else "Idle"
                }
            },
            system_metrics=system_metrics
        )

    except Exception as e:
        logger.error(f"Worker stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.get("/health")
async def get_worker_health(
    admin_user: User = Depends(require_admin())
) -> Dict[str, Any]:
    """
    Get simple worker health status

    Admin-only endpoint for basic health monitoring.
    """
    try:
        logger.info(f"Worker health check by {admin_user.email}")

        unified_stats = await _get_unified_processor_stats()

        health_status = {
            "overall_status": "healthy" if unified_stats["status"] == "active" else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workers": {
                "unified_processor": {
                    "status": unified_stats["status"],
                    "health": "good" if unified_stats["error_rate"] < 0.1 else "poor",
                    "last_activity": unified_stats["last_activity"]
                }
            }
        }

        return {
            "success": True,
            "health": health_status,
            "message": "Worker health check completed"
        }

    except Exception as e:
        logger.error(f"Worker health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Helper Functions

async def _get_unified_processor_stats() -> Dict[str, Any]:
    """Get unified processor statistics"""
    try:
        # Get stats from the unified background processor
        stats = unified_background_processor.get_stats()

        return {
            "status": "active" if stats.get("is_running", False) else "inactive",
            "uptime_seconds": stats.get("uptime_seconds", 0),
            "tasks_processed": stats.get("tasks_completed", 0),
            "tasks_successful": stats.get("successful_tasks", 0),
            "tasks_failed": stats.get("failed_tasks", 0),
            "queue_size": stats.get("queue_size", 0),
            "avg_processing_time": stats.get("avg_processing_time", 0),
            "last_activity": stats.get("last_activity", "Never"),
            "error_rate": stats.get("error_rate", 0.0)
        }
    except Exception as e:
        logger.warning(f"Failed to get unified processor stats: {e}")
        return {
            "status": "unknown",
            "uptime_seconds": 0,
            "tasks_processed": 0,
            "tasks_successful": 0,
            "tasks_failed": 0,
            "queue_size": 0,
            "avg_processing_time": 0,
            "last_activity": "Unknown",
            "error_rate": 0.0
        }


async def _get_system_metrics() -> Dict[str, Any]:
    """Get basic system metrics"""
    try:
        import psutil

        # Get system resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "disk_usage_percent": disk.percent,
            "available_memory_gb": round(memory.available / (1024**3), 2),
            "total_memory_gb": round(memory.total / (1024**3), 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.warning(f"Failed to get system metrics: {e}")
        return {
            "cpu_usage_percent": 0,
            "memory_usage_percent": 0,
            "disk_usage_percent": 0,
            "available_memory_gb": 0,
            "total_memory_gb": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }