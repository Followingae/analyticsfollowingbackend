"""
Admin User Management API Routes
Comprehensive user account management for super admins and admins
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date
import csv
import io
from pydantic import BaseModel, EmailStr, Field

from app.middleware.role_based_auth import (
    RoleBasedAuthService,
    AuthenticationError,
    AuthorizationError
)
from app.database.connection import get_db
from app.database.unified_models import (
    User, UserProfile, CreditWallet
)

router = APIRouter(prefix="/admin/users", tags=["Admin - User Management"])

# Pydantic Models for Request/Response
class UserCreateRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., regex="^(brand_free|brand_standard|brand_premium|brand_enterprise|admin|super_admin)$")
    subscription_tier: str = Field(default="brand_free")
    monthly_search_limit: Optional[int] = None
    monthly_export_limit: Optional[int] = None
    api_rate_limit: Optional[int] = None
    admin_notes: Optional[str] = None

class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, regex="^(brand_free|brand_standard|brand_premium|brand_enterprise|admin|super_admin)$")
    subscription_tier: Optional[str] = None
    account_status: Optional[str] = Field(None, regex="^(active|suspended|pending|archived)$")
    suspension_reason: Optional[str] = None
    monthly_search_limit: Optional[int] = None
    monthly_export_limit: Optional[int] = None
    api_rate_limit: Optional[int] = None
    admin_notes: Optional[str] = None
    custom_permissions: Optional[Dict[str, Any]] = None

class BulkUserUpdateRequest(BaseModel):
    user_ids: List[UUID]
    updates: UserUpdateRequest

class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    subscription_tier: str
    account_status: str
    created_at: datetime
    last_login_at: Optional[datetime]
    total_spent_usd: Optional[float]
    admin_notes: Optional[str]

class UserDetailResponse(UserResponse):
    subscription_expires_at: Optional[datetime]
    monthly_search_limit: Optional[int]
    monthly_export_limit: Optional[int]
    api_rate_limit: Optional[int]
    failed_login_attempts: int
    custom_permissions: Dict[str, Any]
    created_by: Optional[str]
    managed_by: Optional[str]
    onboarding_completed: bool

class UserActivityResponse(BaseModel):
    id: str
    action_type: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    success: bool
    ip_address: Optional[str]
    user_agent: Optional[str]
    credits_spent: int
    created_at: datetime

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

@router.get("/", response_model=UserListResponse)
@requires_permission("can_view_all_users")
@audit_action("view_all_users")
async def get_all_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by email, name, or ID"),
    role: Optional[str] = Query(None, description="Filter by user role"),
    subscription_tier: Optional[str] = Query(None, description="Filter by subscription tier"),
    account_status: Optional[str] = Query(None, description="Filter by account status"),
    sort_by: Optional[str] = Query("created_at", description="Sort by field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of all users with filtering and search"""
    
    # Build base query
    query = select(Users)
    count_query = select(func.count(Users.id))
    
    # Apply filters
    conditions = []
    
    if search:
        search_condition = or_(
            Users.email.icontains(search),
            Users.first_name.icontains(search),
            Users.last_name.icontains(search),
            Users.id.cast(text("TEXT")).icontains(search)
        )
        conditions.append(search_condition)
    
    if role:
        conditions.append(Users.role == role)
    
    if subscription_tier:
        conditions.append(Users.subscription_tier == subscription_tier)
    
    if account_status:
        conditions.append(Users.account_status == account_status)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply sorting
    sort_column = getattr(Users, sort_by, Users.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    
    # Format response
    user_list = []
    for user in users:
        user_list.append(UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            subscription_tier=user.subscription_tier,
            account_status=user.account_status,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            total_spent_usd=float(user.total_spent_usd) if user.total_spent_usd else 0.0,
            admin_notes=user.admin_notes
        ))
    
    return UserListResponse(
        users=user_list,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.get("/{user_id}", response_model=UserDetailResponse)
@requires_permission("can_view_all_users")
@audit_action("view_user_details")
async def get_user_details(
    user_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific user"""
    
    # Get user
    query = select(Users).where(Users.id == user_id)
    result = await db.execute(query)
    user = result.scalar()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get creator and manager info
    created_by_name = None
    managed_by_name = None
    
    if user.created_by:
        creator_query = select(Users.email).where(Users.id == user.created_by)
        creator_result = await db.execute(creator_query)
        created_by_name = creator_result.scalar()
    
    if user.managed_by:
        manager_query = select(Users.email).where(Users.id == user.managed_by)
        manager_result = await db.execute(manager_query)
        managed_by_name = manager_result.scalar()
    
    return UserDetailResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        subscription_tier=user.subscription_tier,
        account_status=user.account_status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        subscription_expires_at=user.subscription_expires_at,
        monthly_search_limit=user.monthly_search_limit,
        monthly_export_limit=user.monthly_export_limit,
        api_rate_limit=user.api_rate_limit,
        failed_login_attempts=user.failed_login_attempts,
        custom_permissions=user.custom_permissions or {},
        created_by=created_by_name,
        managed_by=managed_by_name,
        onboarding_completed=user.onboarding_completed,
        total_spent_usd=float(user.total_spent_usd) if user.total_spent_usd else 0.0,
        admin_notes=user.admin_notes
    )

@router.post("/", response_model=UserDetailResponse)
@requires_permission("can_create_users")
@audit_action("create_user")
async def create_user(
    user_data: UserCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user account"""
    
    # Check if user with email already exists
    existing_user_query = select(Users).where(Users.email == user_data.email)
    existing_user_result = await db.execute(existing_user_query)
    
    if existing_user_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    try:
        # Create new user
        new_user = Users(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            subscription_tier=user_data.subscription_tier,
            monthly_search_limit=user_data.monthly_search_limit,
            monthly_export_limit=user_data.monthly_export_limit,
            api_rate_limit=user_data.api_rate_limit,
            admin_notes=user_data.admin_notes,
            created_by=UUID(current_user["id"]),
            managed_by=UUID(current_user["id"]),
            account_status="active"
        )
        
        db.add(new_user)
        await db.flush()  # Get the ID
        
        # Create credit wallet for the user
        from app.services.credit_wallet_service import credit_wallet_service
        await credit_wallet_service.create_wallet(new_user.id, db)
        
        await db.commit()
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="user_create",
            target_user_id=new_user.id,
            new_values={
                "email": user_data.email,
                "role": user_data.role,
                "subscription_tier": user_data.subscription_tier
            },
            reason="User created via admin panel",
            db=db
        )
        
        # Return created user details
        return await get_user_details(new_user.id, current_user, db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.put("/{user_id}", response_model=UserDetailResponse)
@requires_permission("can_edit_users")
@audit_action("update_user")
async def update_user(
    user_id: UUID,
    user_updates: UserUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Update user account details"""
    
    # Get existing user
    query = select(Users).where(Users.id == user_id)
    result = await db.execute(query)
    user = result.scalar()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Store old values for audit
    old_values = {
        "role": user.role,
        "subscription_tier": user.subscription_tier,
        "account_status": user.account_status
    }
    
    try:
        # Update user fields
        update_data = user_updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        # Set managed_by to current admin
        user.managed_by = UUID(current_user["id"])
        
        await db.commit()
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="user_update",
            target_user_id=user_id,
            old_values=old_values,
            new_values=update_data,
            reason="User updated via admin panel",
            db=db
        )
        
        # Invalidate user cache
        await auth_service.invalidate_user_cache(user_id)
        
        # Return updated user details
        return await get_user_details(user_id, current_user, db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.delete("/{user_id}")
@requires_permission("can_delete_users")
@audit_action("delete_user")
async def delete_user(
    user_id: UUID,
    permanent: bool = Query(False, description="Permanently delete user data"),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Delete or archive user account"""
    
    # Prevent self-deletion
    if str(user_id) == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Get user
    query = select(Users).where(Users.id == user_id)
    result = await db.execute(query)
    user = result.scalar()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        if permanent:
            # Permanent deletion - remove from database
            await db.delete(user)
            action_type = "user_permanent_delete"
        else:
            # Soft delete - archive the account
            user.account_status = "archived"
            user.suspension_reason = f"Account archived by admin on {datetime.utcnow()}"
            action_type = "user_archive"
        
        await db.commit()
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type=action_type,
            target_user_id=user_id,
            old_values={"account_status": "active"},
            new_values={"account_status": "archived" if not permanent else "deleted"},
            reason="User deleted via admin panel",
            severity="critical" if permanent else "warning",
            db=db
        )
        
        # Invalidate user cache
        await auth_service.invalidate_user_cache(user_id)
        
        return {"message": f"User {'permanently deleted' if permanent else 'archived'} successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.post("/bulk-update")
@requires_permission("can_edit_users")
@audit_action("bulk_update_users")
async def bulk_update_users(
    bulk_update: BulkUserUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Bulk update multiple users"""
    
    if len(bulk_update.user_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update more than 100 users at once"
        )
    
    try:
        # Get users to update
        query = select(Users).where(Users.id.in_(bulk_update.user_ids))
        result = await db.execute(query)
        users = result.scalars().all()
        
        if len(users) != len(bulk_update.user_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Some users not found"
            )
        
        # Update each user
        update_data = bulk_update.updates.dict(exclude_unset=True)
        updated_users = []
        
        for user in users:
            old_values = {
                "role": user.role,
                "subscription_tier": user.subscription_tier,
                "account_status": user.account_status
            }
            
            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)
            
            user.managed_by = UUID(current_user["id"])
            updated_users.append(user.id)
            
            # Log individual admin action
            await auth_service.log_admin_action(
                admin_user_id=UUID(current_user["id"]),
                action_type="bulk_user_update",
                target_user_id=user.id,
                old_values=old_values,
                new_values=update_data,
                reason="Bulk user update via admin panel",
                db=db
            )
        
        await db.commit()
        
        # Invalidate user caches
        for user_id in updated_users:
            await auth_service.invalidate_user_cache(user_id)
        
        return {
            "message": f"Successfully updated {len(updated_users)} users",
            "updated_users": [str(uid) for uid in updated_users]
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update users: {str(e)}"
        )

@router.get("/{user_id}/activity", response_model=List[UserActivityResponse])
@requires_permission("can_view_user_activity")
@audit_action("view_user_activity")
async def get_user_activity(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    action_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get user activity history"""
    
    # Build query
    query = select(UserActivityLogs).where(UserActivityLogs.user_id == user_id)
    
    # Apply filters
    if action_type:
        query = query.where(UserActivityLogs.action_type == action_type)
    
    if date_from:
        query = query.where(UserActivityLogs.created_at >= date_from)
    
    if date_to:
        query = query.where(UserActivityLogs.created_at <= date_to)
    
    # Apply pagination and sorting
    offset = (page - 1) * per_page
    query = query.order_by(desc(UserActivityLogs.created_at)).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    activities = result.scalars().all()
    
    # Format response
    activity_list = []
    for activity in activities:
        activity_list.append(UserActivityResponse(
            id=str(activity.id),
            action_type=activity.action_type,
            resource_type=activity.resource_type,
            resource_id=str(activity.resource_id) if activity.resource_id else None,
            success=activity.success,
            ip_address=activity.ip_address,
            user_agent=activity.user_agent,
            credits_spent=activity.credits_spent,
            created_at=activity.created_at
        ))
    
    return activity_list

@router.get("/export/csv")
@requires_permission("can_export_platform_data")
@audit_action("export_users_csv")
async def export_users_csv(
    role: Optional[str] = Query(None),
    subscription_tier: Optional[str] = Query(None),
    account_status: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Export users data as CSV"""
    
    # Build query
    query = select(Users)
    
    # Apply filters
    conditions = []
    if role:
        conditions.append(Users.role == role)
    if subscription_tier:
        conditions.append(Users.subscription_tier == subscription_tier)
    if account_status:
        conditions.append(Users.account_status == account_status)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Email', 'First Name', 'Last Name', 'Role', 'Subscription Tier',
        'Account Status', 'Created At', 'Last Login', 'Total Spent USD'
    ])
    
    # Write data
    for user in users:
        writer.writerow([
            str(user.id),
            user.email,
            user.first_name,
            user.last_name,
            user.role,
            user.subscription_tier,
            user.account_status,
            user.created_at.isoformat() if user.created_at else '',
            user.last_login_at.isoformat() if user.last_login_at else '',
            float(user.total_spent_usd) if user.total_spent_usd else 0.0
        ])
    
    # Create streaming response
    output.seek(0)
    
    def iter_csv():
        yield output.getvalue()
    
    filename = f"users_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )