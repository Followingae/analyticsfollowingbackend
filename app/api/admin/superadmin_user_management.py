"""
SuperAdmin User Management Routes
Complete user management with subscription control, permissions, and credit topups
"""
from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, Field
import logging

from app.database.connection import get_db
from app.database.unified_models import User, CreditWallet, CreditTransaction
from app.models.subscription import (
    SubscriptionTier, UserRole, BillingType,
    FeaturePermission, TIER_LIMITS, TOPUP_PACKAGES
)
from app.services.user_permission_service import PermissionService
from app.services.credit_wallet_service import CreditWalletService
from app.middleware.role_based_auth import RoleBasedAuthService

router = APIRouter(prefix="/api/v1/admin/superadmin", tags=["SuperAdmin Management"])
logger = logging.getLogger(__name__)


# ============= Request/Response Models =============

class CreateUserRequest(BaseModel):
    """Request model for creating a new user"""
    email: EmailStr
    full_name: str
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    billing_type: BillingType = BillingType.OFFLINE  # Default to offline for admin-created

    # Optional feature permissions override
    custom_permissions: Optional[Dict[str, bool]] = None

    # Initial credit topup
    initial_credits: Optional[int] = Field(None, ge=0, le=100000)

    # Admin notes
    admin_notes: Optional[str] = None

    # Send welcome email
    send_welcome_email: bool = True


class UpdateUserSubscriptionRequest(BaseModel):
    """Request for updating user subscription"""
    subscription_tier: SubscriptionTier
    billing_type: Optional[BillingType] = None
    custom_permissions: Optional[Dict[str, bool]] = None
    admin_notes: Optional[str] = None


class CreditTopupRequest(BaseModel):
    """Request for giving credit topup to user"""
    user_id: UUID
    package_type: Optional[str] = Field(None, description="Package key from TOPUP_PACKAGES")
    custom_credits: Optional[int] = Field(None, ge=1, le=100000)
    reason: str = "Admin topup"
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class BulkCreditTopupRequest(BaseModel):
    """Request for bulk credit topups"""
    user_ids: List[UUID]
    package_type: Optional[str] = None
    custom_credits: Optional[int] = Field(None, ge=1, le=100000)
    reason: str = "Bulk admin topup"
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class UserPermissionUpdate(BaseModel):
    """Update individual feature permissions"""
    user_id: UUID
    permissions: Dict[str, bool]  # feature_name: enabled


class UserResponse(BaseModel):
    """User details response"""
    id: str
    email: str
    full_name: Optional[str]
    role: str
    subscription_tier: str
    billing_type: str
    status: str
    created_at: datetime
    permissions: Dict[str, Dict[str, Any]]  # Detailed permission matrix
    limits: Dict[str, Any]  # Usage limits
    credit_balance: int
    admin_notes: Optional[str]


# ============= Helper Functions =============

async def verify_super_admin(current_user: dict = Depends(RoleBasedAuthService.get_current_user)):
    """Verify that current user is a super admin"""
    if current_user.get("role") != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can perform this action"
        )
    return current_user


# ============= Routes =============

@router.post("/users/create", response_model=UserResponse)
async def create_user_with_permissions(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    Create a new user with specific subscription tier and permissions

    SuperAdmin can:
    - Set subscription tier (free/standard/premium)
    - Set billing type (offline for admin-created users)
    - Give initial credit topup
    - Override specific feature permissions
    """
    try:
        # Check if user already exists
        existing = await db.execute(
            select(User).where(User.email == request.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create new user
        new_user = User(
            id=uuid4(),
            email=request.email,
            full_name=request.full_name,
            role=UserRole.USER,  # Always create as regular user, not admin
            subscription_tier=request.subscription_tier,
            billing_type=request.billing_type,
            status='active',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            preferences=request.custom_permissions or {}
        )

        # Add admin notes if provided
        if request.admin_notes:
            new_user.preferences['admin_notes'] = request.admin_notes

        db.add(new_user)
        await db.flush()

        # Create credit wallet
        wallet_service = CreditWalletService()
        wallet = await wallet_service.create_wallet(
            user_id=new_user.id,
            initial_balance=request.initial_credits or 0
        )

        # Record initial credit topup if provided
        if request.initial_credits:
            transaction = CreditTransaction(
                id=uuid4(),
                wallet_id=wallet.id,
                user_id=new_user.id,
                transaction_type='topup',
                amount=request.initial_credits,
                balance_after=request.initial_credits,
                description=f"Initial admin topup by {current_user.get('email')}",
                metadata={
                    "admin_id": current_user.get("id"),
                    "admin_email": current_user.get("email"),
                    "reason": "Account creation"
                },
                created_at=datetime.utcnow()
            )
            db.add(transaction)

        await db.commit()

        # Get permissions for response
        permissions = await PermissionService.get_all_user_permissions(db, str(new_user.id))

        return UserResponse(
            id=str(new_user.id),
            email=new_user.email,
            full_name=new_user.full_name,
            role=new_user.role,
            subscription_tier=new_user.subscription_tier,
            billing_type=new_user.billing_type,
            status=new_user.status,
            created_at=new_user.created_at,
            permissions=permissions.get("permissions", {}),
            limits=permissions.get("limits", {}),
            credit_balance=wallet.current_balance,
            admin_notes=request.admin_notes
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.put("/users/{user_id}/subscription", response_model=UserResponse)
async def update_user_subscription(
    user_id: UUID,
    request: UpdateUserSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    Update user's subscription tier and permissions

    SuperAdmin can change:
    - Subscription tier (upgrade/downgrade)
    - Billing type (stripe/offline)
    - Custom feature permissions
    """
    try:
        # Get user
        user = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prevent changing SuperAdmin's own subscription
        if user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify SuperAdmin subscription"
            )

        # Update subscription
        user.subscription_tier = request.subscription_tier
        if request.billing_type:
            user.billing_type = request.billing_type

        # Update custom permissions if provided
        if request.custom_permissions:
            if not user.preferences:
                user.preferences = {}
            user.preferences['custom_permissions'] = request.custom_permissions

        # Add admin notes
        if request.admin_notes:
            if not user.preferences:
                user.preferences = {}
            user.preferences['admin_notes'] = request.admin_notes

        user.updated_at = datetime.utcnow()

        # Update credit wallet package if tier changed
        wallet = await db.execute(
            select(CreditWallet).where(CreditWallet.user_id == user_id)
        )
        wallet = wallet.scalar_one_or_none()

        if wallet:
            # Update wallet based on new tier
            tier_limits = TIER_LIMITS.get(request.subscription_tier)
            if tier_limits:
                # Reset monthly limits based on new tier
                wallet.updated_at = datetime.utcnow()

        await db.commit()

        # Get updated permissions
        permissions = await PermissionService.get_all_user_permissions(db, str(user_id))

        return UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            subscription_tier=user.subscription_tier,
            billing_type=user.billing_type,
            status=user.status,
            created_at=user.created_at,
            permissions=permissions.get("permissions", {}),
            limits=permissions.get("limits", {}),
            credit_balance=wallet.current_balance if wallet else 0,
            admin_notes=user.preferences.get('admin_notes') if user.preferences else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(e)}"
        )


@router.post("/credits/topup")
async def give_credit_topup(
    request: CreditTopupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    Give credit topup to a user

    SuperAdmin can:
    - Give predefined topup packages
    - Give custom credit amounts
    - Set expiry dates for credits
    """
    try:
        # Get user and wallet
        user = await db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = user.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        wallet_service = CreditWalletService()

        # Determine credit amount
        credit_amount = 0
        package_info = None

        if request.package_type and request.package_type in TOPUP_PACKAGES:
            package = TOPUP_PACKAGES[request.package_type]
            credit_amount = package.credits if package.credits > 0 else request.custom_credits or 0
            package_info = {
                "package": request.package_type,
                "name": package.name,
                "description": package.description
            }
        elif request.custom_credits:
            credit_amount = request.custom_credits
            package_info = {"custom": True, "amount": credit_amount}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must specify either package_type or custom_credits"
            )

        if credit_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit amount must be positive"
            )

        # Add credits to wallet
        result = await wallet_service.add_credits(
            user_id=str(request.user_id),
            amount=credit_amount,
            description=request.reason,
            metadata={
                "admin_id": current_user.get("id"),
                "admin_email": current_user.get("email"),
                "package_info": package_info,
                "expires_in_days": request.expires_in_days
            }
        )

        return {
            "success": True,
            "user_id": str(request.user_id),
            "user_email": user.email,
            "credits_added": credit_amount,
            "new_balance": result["new_balance"],
            "package_info": package_info,
            "reason": request.reason,
            "admin": current_user.get("email")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error giving topup: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to give topup: {str(e)}"
        )


@router.post("/credits/bulk-topup")
async def bulk_credit_topup(
    request: BulkCreditTopupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    Give credit topup to multiple users at once
    """
    results = []
    errors = []

    for user_id in request.user_ids:
        try:
            topup_request = CreditTopupRequest(
                user_id=user_id,
                package_type=request.package_type,
                custom_credits=request.custom_credits,
                reason=request.reason,
                expires_in_days=request.expires_in_days
            )

            result = await give_credit_topup(topup_request, db, current_user)
            results.append(result)

        except Exception as e:
            errors.append({
                "user_id": str(user_id),
                "error": str(e)
            })

    return {
        "success": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


@router.get("/users", response_model=List[UserResponse])
async def list_all_users(
    subscription_tier: Optional[str] = None,
    billing_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    List all users with filtering options
    """
    try:
        query = select(User).where(User.role != UserRole.SUPER_ADMIN)

        # Apply filters
        if subscription_tier:
            query = query.where(User.subscription_tier == subscription_tier)
        if billing_type:
            query = query.where(User.billing_type == billing_type)
        if status:
            query = query.where(User.status == status)

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        users = result.scalars().all()

        # Build response with permissions
        user_responses = []
        for user in users:
            permissions = await PermissionService.get_all_user_permissions(db, str(user.id))

            # Get wallet balance
            wallet = await db.execute(
                select(CreditWallet).where(CreditWallet.user_id == user.id)
            )
            wallet = wallet.scalar_one_or_none()

            user_responses.append(UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                subscription_tier=user.subscription_tier,
                billing_type=user.billing_type,
                status=user.status,
                created_at=user.created_at,
                permissions=permissions.get("permissions", {}),
                limits=permissions.get("limits", {}),
                credit_balance=wallet.current_balance if wallet else 0,
                admin_notes=user.preferences.get('admin_notes') if user.preferences else None
            ))

        return user_responses

    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: UUID,
    permissions: Dict[str, bool] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    Update specific feature permissions for a user

    Allows SuperAdmin to enable/disable specific features regardless of subscription tier
    """
    try:
        user = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update custom permissions
        if not user.preferences:
            user.preferences = {}

        user.preferences['custom_permissions'] = permissions
        user.updated_at = datetime.utcnow()

        await db.commit()

        # Get updated permissions
        updated_permissions = await PermissionService.get_all_user_permissions(db, str(user_id))

        return {
            "success": True,
            "user_id": str(user_id),
            "email": user.email,
            "permissions": updated_permissions.get("permissions", {}),
            "custom_overrides": permissions
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating permissions: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update permissions: {str(e)}"
        )


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_super_admin)
):
    """
    Get detailed permission matrix for a user
    """
    try:
        permissions = await PermissionService.get_all_user_permissions(db, str(user_id))

        if "error" in permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=permissions["error"]
            )

        return permissions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get permissions: {str(e)}"
        )