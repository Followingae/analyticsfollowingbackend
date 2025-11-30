"""
Async Campaign Routes - Non-blocking post analytics
This replaces the synchronous campaign routes for post addition
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user
from app.models.auth import UserInDB
from app.core.job_queue import job_queue, JobPriority, QueueType
from pydantic import BaseModel

# Define the schema locally (copied from campaign_routes.py)
class AddPostRequest(BaseModel):
    instagram_post_url: str

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{campaign_id}/posts/async")
async def add_post_to_campaign_async(
    campaign_id: UUID,
    request: AddPostRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add Instagram post to campaign - ASYNC VERSION

    This endpoint immediately returns a job_id and processes the post analytics
    in the background, keeping the backend responsive.

    Benefits:
    ✅ Backend stays responsive - users can navigate freely
    ✅ No timeout issues for long-running analytics
    ✅ Progress tracking via job status endpoint
    ✅ Same complete data quality (Option A - full analytics)

    Response includes:
    - job_id: Use this to poll for status and results
    - status_url: Endpoint to check job status
    - estimated_time: Estimated completion time
    """
    try:
        logger.info(f"🚀 Queuing post analytics job for campaign {campaign_id}")

        # Create job parameters
        job_params = {
            "campaign_id": str(campaign_id),
            "instagram_post_url": request.instagram_post_url,
            "user_id": str(current_user.id),
            "wait_for_full_analytics": True,  # Option A - wait for complete analytics
            "requested_at": datetime.now(timezone.utc).isoformat()
        }

        # Determine user tier for queue access
        # Map roles and subscription tiers to job queue tiers
        tier_mapping = {
            "free": "free",
            "standard": "standard",
            "professional": "standard",  # Professional maps to standard queue access
            "premium": "premium",
            "brand_premium": "premium",  # Brand premium maps to premium queue access
            "enterprise": "premium",
            "admin": "premium",
            "superadmin": "premium"
        }

        # Check both role (from UserInDB) and subscription_tier (from users table if available)
        user_role = getattr(current_user, 'role', 'free')
        user_subscription_tier = getattr(current_user, 'subscription_tier', None)

        # Use subscription_tier if available, otherwise fall back to role
        # Since you said this is a premium user, let's use the role which should be premium
        effective_tier = user_subscription_tier or user_role
        user_tier = tier_mapping.get(str(effective_tier).lower(), 'free')

        logger.info(f"🎫 User {current_user.email} role: {user_role}, subscription: {user_subscription_tier} → effective: {effective_tier} → queue tier: {user_tier}")

        # Queue the job
        enqueue_result = await job_queue.enqueue_job(
            user_id=str(current_user.id),
            job_type="post_analytics_campaign",
            params=job_params,
            priority=JobPriority.HIGH,
            queue_type=QueueType.POST_ANALYTICS_QUEUE,
            user_tier=user_tier
        )

        # Check if enqueue operation was successful
        if not enqueue_result.get('success', False):
            logger.error(f"❌ Failed to enqueue job: {enqueue_result}")
            error_message = enqueue_result.get('message', 'Failed to queue job')

            # Handle quota exceeded error specifically
            if enqueue_result.get('error') == 'quota_exceeded':
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "quota_exceeded",
                        "message": error_message,
                        "upgrade_required": True,
                        "available_tiers": ["standard", "premium"],
                        "current_tier": "free"
                    }
                )

            # Handle queue full error
            elif enqueue_result.get('error') == 'queue_full':
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": "queue_full",
                        "message": error_message,
                        "retry_after": 30
                    }
                )

            # Generic error
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": "enqueue_failed", "message": error_message}
                )

        # Extract job_id from successful response
        job_id = enqueue_result['job_id']
        logger.info(f"✅ Post analytics job {job_id} queued successfully")

        # Return immediately with job info
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Post analytics job queued successfully",
            "status_url": f"/api/v1/jobs/{job_id}/status",
            "result_url": f"/api/v1/jobs/{job_id}/result",
            "estimated_time_seconds": 180,  # 3 minutes estimate
            "instructions": {
                "poll_status": "Poll the status_url every 5 seconds to check progress",
                "get_result": "Once status is 'completed', fetch results from result_url"
            }
        }

    except HTTPException:
        # Re-raise HTTPExceptions without modification (quota, queue full, etc.)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error queueing post analytics job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error while queueing job"
        )


@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the status of a post analytics job

    Returns:
    - status: 'pending', 'processing', 'completed', 'failed'
    - progress_percent: 0-100
    - current_stage: Current processing stage
    - estimated_remaining: Estimated seconds remaining
    """
    try:
        # Validate job_id format
        if job_id == "[object Object]" or not job_id or job_id.startswith("[object"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid job_id format",
                    "message": "Frontend is passing [object Object] instead of actual job ID",
                    "received_job_id": job_id,
                    "expected_format": "UUID string (e.g., 123e4567-e89b-12d3-a456-426614174000)"
                }
            )

        # Validate UUID format
        try:
            UUID(job_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid UUID format",
                    "received_job_id": job_id,
                    "message": "job_id must be a valid UUID"
                }
            )
        # Query job status from database
        result = await db.execute(
            text("""
                SELECT
                    id, user_id, status, progress_percent, current_stage,
                    created_at, started_at, completed_at, failed_at, error
                FROM job_queue
                WHERE id = :job_id AND user_id = :user_id
            """).execution_options(prepare=False),
            {"job_id": job_id, "user_id": str(current_user.id)}
        )

        job = result.fetchone()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        # Calculate estimated time remaining
        estimated_remaining = None
        if job.status == "processing" and job.started_at:
            elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
            if job.progress_percent and job.progress_percent > 0:
                total_estimated = (elapsed / job.progress_percent) * 100
                estimated_remaining = max(0, int(total_estimated - elapsed))

        return {
            "job_id": job_id,
            "status": job.status,
            "progress_percent": job.progress_percent or 0,
            "current_stage": job.current_stage or "queued",
            "estimated_remaining_seconds": estimated_remaining,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error": job.error if job.status == "failed" else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the result of a completed post analytics job

    Returns the same data structure as the synchronous endpoint
    once the job is completed.
    """
    try:
        # Query job result from database
        result = await db.execute(
            text("""
                SELECT
                    id, user_id, status, result, error
                FROM job_queue
                WHERE id = :job_id AND user_id = :user_id
            """).execution_options(prepare=False),
            {"job_id": job_id, "user_id": str(current_user.id)}
        )

        job = result.fetchone()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        if job.status == "pending" or job.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail=f"Job is still {job.status}. Please check status endpoint."
            )

        if job.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Job failed: {job.error}"
            )

        if job.status == "completed":
            # Parse and return the result
            if job.result:
                result_data = json.loads(job.result)
                return result_data
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Job completed but no result found"
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown job status: {job.status}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job result"
        )