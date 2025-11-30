"""
Debug routes for monitoring background workers and job queue
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["Debug Workers"])


@router.get("/workers/status")
async def get_worker_status(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get status of all background workers"""
    try:
        # Import worker references
        from app.workers.post_analytics_worker import post_analytics_worker

        status = {
            "post_analytics_worker": {
                "running": getattr(post_analytics_worker, 'running', False),
                "current_job": getattr(post_analytics_worker, 'current_job', None),
                "initialized": hasattr(post_analytics_worker, 'start')
            }
        }

        return {
            "success": True,
            "workers": status,
            "message": "Worker status retrieved"
        }

    except Exception as e:
        logger.error(f"Failed to get worker status: {e}")
        return {
            "success": False,
            "error": str(e),
            "workers": {}
        }


@router.get("/queue/jobs")
async def get_queue_jobs(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current jobs in the queue"""
    try:
        result = await db.execute(
            text("""
                SELECT id, job_type, status, user_id, created_at, updated_at
                FROM job_queue
                ORDER BY created_at DESC
                LIMIT 20
            """).execution_options(prepare=False)
        )

        jobs = []
        for row in result:
            jobs.append({
                "id": row.id,
                "job_type": row.job_type,
                "status": row.status,
                "user_id": row.user_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None
            })

        return {
            "success": True,
            "jobs": jobs,
            "total_count": len(jobs),
            "message": "Queue jobs retrieved"
        }

    except Exception as e:
        logger.error(f"Failed to get queue jobs: {e}")
        return {
            "success": False,
            "error": str(e),
            "jobs": []
        }


@router.get("/queue/stats")
async def get_queue_stats(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get queue statistics"""
    try:
        result = await db.execute(
            text("""
                SELECT status, COUNT(*) as count
                FROM job_queue
                GROUP BY status
            """).execution_options(prepare=False)
        )

        stats = {}
        for row in result:
            stats[row.status] = row.count

        return {
            "success": True,
            "stats": stats,
            "message": "Queue statistics retrieved"
        }

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return {
            "success": False,
            "error": str(e),
            "stats": {}
        }


@router.post("/workers/restart")
async def restart_post_analytics_worker(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Restart the Post Analytics Worker"""
    try:
        from app.workers.post_analytics_worker import post_analytics_worker
        import asyncio

        # Stop current worker if running
        if hasattr(post_analytics_worker, 'running'):
            post_analytics_worker.running = False

        # Start new worker
        asyncio.create_task(post_analytics_worker.start())

        return {
            "success": True,
            "message": "Post Analytics Worker restarted"
        }

    except Exception as e:
        logger.error(f"Failed to restart worker: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to restart worker"
        }