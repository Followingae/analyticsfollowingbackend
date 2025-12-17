"""
Admin Billing Routes - Manage offline/admin-managed billing accounts
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from typing import Optional, List
import logging
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
import uuid

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user, require_admin
from app.database.unified_models import User
from app.models.auth import BillingType, UserRole, UserStatus
from app.services.supabase_auth_service import ProductionSupabaseAuthService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/billing",
    tags=["admin-billing"]
)

# Request/Response Models
class PendingUserResponse(BaseModel):
    """Pending user awaiting approval"""
    id: str
    email: str
    full_name: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    created_at: datetime
    requested_tier: Optional[str]
    status: str


class ApproveUserRequest(BaseModel):
    """Request to approve user with billing details"""
    user_id: str
    subscription_tier: str  # "free", "standard", "premium"
    credits: int
    subscription_expires_at: datetime
    send_welcome_email: bool = True
    notes: Optional[str] = None


class RejectUserRequest(BaseModel):
    """Request to reject user application"""
    user_id: str
    reason: str
    send_notification: bool = True


class UpdateBillingRequest(BaseModel):
    """Update billing for existing admin-managed user"""
    user_id: str
    credits: Optional[int] = None
    add_credits: Optional[int] = None  # Add to existing credits
    subscription_tier: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None
    notes: Optional[str] = None


@router.get("/pending-users", response_model=List[PendingUserResponse])
async def get_pending_users(
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get list of users pending admin approval"""
    try:
        # Get users with admin_managed billing and pending status
        result = await db.execute(
            select(User)
            .where(
                and_(
                    User.billing_type == BillingType.ADMIN_MANAGED.value,
                    User.status == UserStatus.PENDING.value
                )
            )
            .order_by(User.created_at.desc())
        )

        pending_users = result.scalars().all()

        return [
            PendingUserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                company=user.company,
                job_title=user.job_title,
                created_at=user.created_at,
                requested_tier=user.subscription_tier,
                status=user.status
            )
            for user in pending_users
        ]

    except Exception as e:
        logger.error(f"Error getting pending users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending users"
        )


@router.post("/approve-user")
async def approve_user(
    request: ApproveUserRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve pending user and activate their account"""
    try:
        # Get the pending user
        result = await db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.billing_type != BillingType.ADMIN_MANAGED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not using admin-managed billing"
            )

        # Update user with approved details
        await db.execute(
            update(User)
            .where(User.id == request.user_id)
            .values(
                status=UserStatus.ACTIVE.value,
                subscription_tier=request.subscription_tier,
                credits=request.credits,
                credits_used_this_month=0,
                subscription_expires_at=request.subscription_expires_at,
                subscription_status='active',
                subscription_activated_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()

        # TODO: Send welcome email if requested
        if request.send_welcome_email:
            background_tasks.add_task(
                _send_activation_email,
                user.email,
                user.full_name,
                request.subscription_tier,
                request.credits
            )

        logger.info(f"Admin {current_user.email} approved user {user.email} with {request.subscription_tier} tier")

        return {
            "status": "success",
            "message": f"User {user.email} has been approved and activated",
            "user_id": request.user_id,
            "subscription_tier": request.subscription_tier,
            "credits": request.credits,
            "expires_at": request.subscription_expires_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve user"
        )


@router.post("/reject-user")
async def reject_user(
    request: RejectUserRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject pending user application"""
    try:
        # Update user status to rejected/suspended
        result = await db.execute(
            update(User)
            .where(User.id == request.user_id)
            .values(
                status=UserStatus.SUSPENDED.value,
                updated_at=datetime.now(timezone.utc)
            )
            .returning(User.email, User.full_name)
        )

        user_data = result.fetchone()

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        await db.commit()

        # TODO: Send rejection email if requested
        if request.send_notification:
            background_tasks.add_task(
                _send_rejection_email,
                user_data.email,
                user_data.full_name,
                request.reason
            )

        logger.info(f"Admin {current_user.email} rejected user {user_data.email}")

        return {
            "status": "success",
            "message": f"User {user_data.email} has been rejected",
            "reason": request.reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject user"
        )


@router.post("/update-billing")
async def update_user_billing(
    request: UpdateBillingRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update billing details for admin-managed user"""
    try:
        # Get current user data
        result = await db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.billing_type != BillingType.ADMIN_MANAGED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not using admin-managed billing"
            )

        # Build update values
        update_values = {
            "updated_at": datetime.now(timezone.utc)
        }

        # Handle credits update
        if request.credits is not None:
            update_values["credits"] = request.credits
        elif request.add_credits is not None:
            update_values["credits"] = User.credits + request.add_credits

        if request.subscription_tier:
            update_values["subscription_tier"] = request.subscription_tier

        if request.subscription_expires_at:
            update_values["subscription_expires_at"] = request.subscription_expires_at

        # Update user
        await db.execute(
            update(User)
            .where(User.id == request.user_id)
            .values(**update_values)
        )
        await db.commit()

        logger.info(f"Admin {current_user.email} updated billing for user {user.email}")

        return {
            "status": "success",
            "message": f"Billing updated for {user.email}",
            "user_id": request.user_id,
            "updates": {
                k: v for k, v in update_values.items()
                if k not in ["updated_at"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating billing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update billing"
        )


@router.get("/managed-users")
async def get_managed_users(
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all admin-managed billing users"""
    try:
        result = await db.execute(
            select(User)
            .where(
                and_(
                    User.billing_type == BillingType.ADMIN_MANAGED.value,
                    User.status == UserStatus.ACTIVE.value
                )
            )
            .order_by(User.subscription_expires_at.asc())
        )

        users = result.scalars().all()

        return [
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "company": user.company,
                "subscription_tier": user.subscription_tier,
                "credits": user.credits,
                "credits_used": user.credits_used_this_month,
                "expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
                "status": user.status,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]

    except Exception as e:
        logger.error(f"Error getting managed users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get managed users"
        )


@router.post("/extend-subscription")
async def extend_subscription(
    user_id: str,
    days: int = 30,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Extend subscription for admin-managed user"""
    try:
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Calculate new expiry
        current_expiry = user.subscription_expires_at or datetime.now(timezone.utc)
        if current_expiry < datetime.now(timezone.utc):
            # If already expired, extend from today
            current_expiry = datetime.now(timezone.utc)

        new_expiry = current_expiry + timedelta(days=days)

        # Update expiry
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                subscription_expires_at=new_expiry,
                subscription_status='active' if new_expiry > datetime.now(timezone.utc) else 'expired',
                updated_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()

        logger.info(f"Admin {current_user.email} extended subscription for {user.email} by {days} days")

        return {
            "status": "success",
            "message": f"Subscription extended by {days} days",
            "new_expiry": new_expiry.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend subscription"
        )


# Helper functions for email notifications
async def _send_activation_email(email: str, name: str, tier: str, credits: int):
    """Send activation email to approved user"""
    # TODO: Implement email sending via SendGrid or similar
    logger.info(f"Would send activation email to {email} for {tier} tier with {credits} credits")


async def _send_rejection_email(email: str, name: str, reason: str):
    """Send rejection email to user"""
    # TODO: Implement email sending
    logger.info(f"Would send rejection email to {email} with reason: {reason}")