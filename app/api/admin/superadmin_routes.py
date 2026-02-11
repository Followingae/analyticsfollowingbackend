"""
Streamlined Superadmin Routes
Core admin functionality without unnecessary clutter
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_, func, desc
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, Field
import logging

from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.connection import get_db
from app.database.unified_models import (
    User, Team, TeamMember, CreditWallet, CreditTransaction,
    UserProfileAccess, Profile, Post,
    CreditPricingRule, UserList
)
from app.services.credit_wallet_service import CreditWalletService
from app.services.credit_transaction_service import CreditTransactionService

router = APIRouter(tags=["Superadmin"])
logger = logging.getLogger(__name__)


# ============= Response Models =============

class DashboardStats(BaseModel):
    """Simple dashboard statistics"""
    total_users: int
    active_users: int
    total_profiles: int
    total_revenue_this_month: float
    total_credits_consumed: int
    new_users_this_month: int


class UserListResponse(BaseModel):
    """User listing response"""
    users: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class TransactionListResponse(BaseModel):
    """Transaction listing response"""
    transactions: List[Dict[str, Any]]
    total: int
    total_amount: float


class ProfileListResponse(BaseModel):
    """Profile listing response"""
    profiles: List[Dict[str, Any]]
    total: int
    incomplete_count: int


# ============= Dashboard Endpoints =============

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Get simple dashboard statistics with proper error handling"""
    # Initialize default values
    total_users = 0
    active_users = 0
    total_profiles = 0
    total_revenue = 0.0
    total_credits = 0
    new_users = 0

    try:
        # Try to get stats with individual error handling
        try:
            # Total users
            total_users_result = await db.execute(text("SELECT COUNT(*) FROM users"))
            total_users = total_users_result.scalar() or 0
        except Exception as e:
            logger.warning(f"Failed to get total users: {e}")
            await db.rollback()  # Clear the failed transaction

        try:
            # Active users (with status = 'active')
            active_users_result = await db.execute(
                text("SELECT COUNT(*) FROM users WHERE status = 'active'")
            )
            active_users = active_users_result.scalar() or 0
        except Exception as e:
            logger.warning(f"Failed to get active users: {e}")
            await db.rollback()

        try:
            # Total profiles
            total_profiles_result = await db.execute(text("SELECT COUNT(*) FROM profiles"))
            total_profiles = total_profiles_result.scalar() or 0
        except Exception as e:
            logger.warning(f"Failed to get total profiles: {e}")
            await db.rollback()

        # Date calculations
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)

        try:
            # Revenue this month - use string formatting for date to avoid parameter issues
            revenue_query = f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM credit_transactions
                WHERE transaction_type = 'purchase'
                AND created_at >= '{current_month.isoformat()}'
            """
            revenue_result = await db.execute(text(revenue_query))
            total_revenue = float(revenue_result.scalar() or 0)
        except Exception as e:
            logger.warning(f"Failed to get revenue: {e}")
            await db.rollback()

        try:
            # Credits consumed this month
            credits_query = f"""
                SELECT COALESCE(SUM(ABS(amount)), 0)
                FROM credit_transactions
                WHERE transaction_type = 'spend'
                AND created_at >= '{current_month.isoformat()}'
            """
            credits_result = await db.execute(text(credits_query))
            total_credits = int(credits_result.scalar() or 0)
        except Exception as e:
            logger.warning(f"Failed to get credits consumed: {e}")
            await db.rollback()

        try:
            # New users this month
            new_users_query = f"""
                SELECT COUNT(*)
                FROM users
                WHERE created_at >= '{current_month.isoformat()}'
            """
            new_users_result = await db.execute(text(new_users_query))
            new_users = new_users_result.scalar() or 0
        except Exception as e:
            logger.warning(f"Failed to get new users: {e}")
            await db.rollback()

    except Exception as e:
        logger.error(f"Critical error getting dashboard stats: {e}")

    # Always return data, even if partial
    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_profiles=total_profiles,
        total_revenue_this_month=total_revenue,
        total_credits_consumed=total_credits,
        new_users_this_month=new_users
    )


# ============= User Management =============

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    include_deleted: bool = Query(False, description="Include deleted users in results"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
) -> UserListResponse:
    """List all users with filters

    By default, deleted users are excluded unless:
    1. include_deleted=true is passed
    2. status='deleted' is explicitly requested
    """
    try:
        query = select(User)

        # Apply filters
        conditions = []

        # Handle deleted users filtering (industry standard)
        if not include_deleted and status != 'deleted':
            # Exclude deleted users by default unless explicitly requested
            conditions.append(User.status != 'deleted')

        if search:
            conditions.append(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%")
                )
            )
        if role:
            conditions.append(User.role == role)
        if status:
            conditions.append(User.status == status)

        if conditions:
            query = query.where(and_(*conditions))

        # Count total using text query to avoid PGBouncer issues
        # Build WHERE clause for count query
        where_clauses = []
        params = {}

        if not include_deleted and status != 'deleted':
            where_clauses.append("status != :deleted_status")
            params["deleted_status"] = 'deleted'

        if search:
            where_clauses.append("(email ILIKE :search OR full_name ILIKE :search)")
            params["search"] = f"%{search}%"

        if role:
            where_clauses.append("role = :role")
            params["role"] = role

        if status:
            where_clauses.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        count_query = text(f"SELECT COUNT(*) FROM users WHERE {where_clause}")
        total_result = await db.execute(count_query, params)
        total = total_result.scalar() or 0

        # Paginate and Execute using text query to avoid PGBouncer issues
        offset = (page - 1) * page_size

        # Build the full SELECT query with WHERE and ORDER BY (including company fields)
        select_query = text(f"""
            SELECT id, supabase_user_id, email, full_name, role, status,
                   subscription_tier, billing_type, credits, created_at, updated_at,
                   company, job_title, phone_number, industry, company_size,
                   use_case, marketing_budget, company_logo_url
            FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        params["limit"] = page_size
        params["offset"] = offset

        result = await db.execute(select_query, params)
        users = result.fetchall()

        # Get all supabase user IDs for batch wallet fetching (credit_wallets uses auth.users IDs)
        supabase_user_ids = [user.supabase_user_id for user in users if user.supabase_user_id]

        # Batch fetch all wallets to avoid N+1 queries and PGBouncer issues
        wallets_dict = {}
        if supabase_user_ids:
            try:
                # Use text query to avoid prepared statement issues with PGBouncer
                # Note: credit_wallets.user_id references auth.users.id which is stored as supabase_user_id in our users table
                wallet_query = text("""
                    SELECT user_id::text as user_id, current_balance
                    FROM credit_wallets
                    WHERE user_id::text = ANY(:user_ids)
                """)
                wallet_result = await db.execute(
                    wallet_query,
                    {"user_ids": supabase_user_ids}
                )
                for row in wallet_result:
                    wallets_dict[row.user_id] = row.current_balance
            except Exception as e:
                logger.warning(f"Failed to fetch wallets, using fallback: {e}")
                # Continue without wallet data, will use user.credits as fallback

        # Build user list
        user_list = []
        for user in users:
            # Get wallet balance from batch fetch using supabase_user_id
            wallet_balance = wallets_dict.get(user.supabase_user_id) if user.supabase_user_id else None

            # Determine the actual current balance
            # Use wallet balance if available, otherwise fall back to user.credits
            actual_balance = wallet_balance if wallet_balance is not None else user.credits

            user_list.append({
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "company": user.company,  # NEW: Company name
                "job_title": user.job_title,  # NEW: Job title
                "phone_number": user.phone_number,  # NEW: Phone
                "industry": user.industry,  # NEW: Industry
                "company_size": user.company_size,  # NEW: Company size
                "use_case": user.use_case,  # NEW: Use case
                "marketing_budget": user.marketing_budget,  # NEW: Budget
                "company_logo_url": user.company_logo_url,  # NEW: Logo URL
                "role": user.role,
                "status": user.status,
                "subscription_tier": user.subscription_tier,
                "billing_type": user.billing_type,  # Added billing type
                "credits": actual_balance,  # For backwards compatibility
                "current_balance": actual_balance,  # NEW: Explicit current_balance field
                "credits_balance": actual_balance,  # Alternative field name for frontend flexibility
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.updated_at.isoformat() if user.updated_at else None,
                "is_self_paid": user.billing_type == "online_payment",  # Helper flag
                "is_admin_managed": user.billing_type in ["offline", "admin_managed"]  # Helper flag
            })

        return UserListResponse(
            users=user_list,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}")
async def update_user(
    user_id: UUID,
    updates: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Update user details including all company information"""
    try:
        # Get user using text query to avoid PGBouncer issues
        user_query = text("""
            SELECT id, email, role, status, billing_type, subscription_tier
            FROM users
            WHERE id = :user_id
        """)

        result = await db.execute(user_query, {"user_id": user_id})
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # CRITICAL: Prevent modifying certain fields for superadmin accounts
        if user.role in ['superadmin', 'super_admin']:
            # Prevent changing status of superadmin accounts
            if 'status' in updates and updates['status'] != user.status:
                raise HTTPException(
                    status_code=403,
                    detail="FORBIDDEN: Cannot change status of superadmin accounts."
                )
            # Prevent changing role of superadmin accounts
            if 'role' in updates and updates['role'] != user.role:
                raise HTTPException(
                    status_code=403,
                    detail="FORBIDDEN: Cannot change role of superadmin accounts."
                )

        # Define all updatable fields
        all_allowed_fields = [
            'full_name', 'company', 'job_title', 'phone_number',
            'industry', 'company_size', 'use_case', 'marketing_budget',
            'company_logo_url', 'timezone', 'language'
        ]

        # Add status for non-superadmin users
        if user.role not in ['superadmin', 'super_admin']:
            all_allowed_fields.append('status')

        # Handle subscription tier change with validation
        if 'subscription_tier' in updates:
            # Only allow for admin-managed accounts
            if user.billing_type not in ['offline', 'admin_managed']:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot change subscription tier for self-paid accounts. User must manage through Stripe."
                )
            # Validate tier value
            valid_tiers = ['free', 'standard', 'premium']
            if updates['subscription_tier'] not in valid_tiers:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid subscription tier. Must be one of: {valid_tiers}"
                )
            all_allowed_fields.append('subscription_tier')

        # Build UPDATE query dynamically with only allowed and provided fields
        update_fields = []
        update_params = {"user_id": user_id}

        for field in all_allowed_fields:
            if field in updates:
                update_fields.append(f"{field} = :{field}")
                update_params[field] = updates[field]

        # Add updated_at timestamp
        update_fields.append("updated_at = NOW()")

        if not update_fields:
            return {"success": True, "message": "No fields to update"}

        # Execute UPDATE query using text to avoid PGBouncer issues
        update_query = text(f"""
            UPDATE users
            SET {', '.join(update_fields)}
            WHERE id = :user_id
        """)

        await db.execute(update_query, update_params)
        await db.commit()

        logger.info(f"User {user_id} updated successfully by {current_user.email}. Fields updated: {list(updates.keys())}")

        return {
            "success": True,
            "message": "User updated successfully",
            "updated_fields": list(updates.keys())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Delete a user (soft delete by setting status to deleted)

    Industry standard soft delete implementation:
    - Sets status to 'deleted'
    - Preserves all user data for audit/recovery
    - Records deletion timestamp
    - User can be restored by changing status back to 'active'
    """
    try:
        # Get user using text query to avoid PGBouncer issues
        user_query = text("""
            SELECT id, email, role, status, preferences
            FROM users
            WHERE id = :user_id
        """)

        result = await db.execute(user_query, {"user_id": user_id})
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # CRITICAL: Prevent deletion of ANY superadmin account
        if user.role in ['superadmin', 'super_admin']:
            raise HTTPException(
                status_code=403,
                detail="FORBIDDEN: Superadmin accounts cannot be deleted. This would cause catastrophic system failure."
            )

        # Prevent deleting already deleted users
        if user.status == 'deleted':
            raise HTTPException(status_code=400, detail="User is already deleted")

        # Prevent self-deletion
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")

        # Store previous status for audit
        previous_status = user.status

        # Prepare deletion metadata
        import json
        preferences = user.preferences or {}
        if isinstance(preferences, str):
            preferences = json.loads(preferences)

        preferences['deleted_at'] = datetime.utcnow().isoformat()
        preferences['deleted_by'] = str(current_user.id)
        preferences['previous_status'] = previous_status

        # Soft delete using text query to avoid PGBouncer issues
        update_query = text("""
            UPDATE users
            SET status = 'deleted',
                updated_at = :updated_at,
                preferences = :preferences
            WHERE id = :user_id
        """)

        await db.execute(update_query, {
            "user_id": user_id,
            "updated_at": datetime.utcnow(),
            "preferences": json.dumps(preferences)
        })

        await db.commit()

        logger.info(f"User {user.email} soft deleted by {current_user.email}")

        return {
            "success": True,
            "message": "User deleted successfully",
            "user_id": str(user_id),
            "deleted_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/restore")
async def restore_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Restore a soft-deleted user"""
    try:
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.status != 'deleted':
            raise HTTPException(status_code=400, detail="User is not deleted")

        # Restore to previous status or default to 'active'
        previous_status = 'active'
        if user.preferences and 'previous_status' in user.preferences:
            previous_status = user.preferences['previous_status']

        user.status = previous_status
        user.updated_at = datetime.utcnow()

        # Add restoration metadata
        if not user.preferences:
            user.preferences = {}
        user.preferences['restored_at'] = datetime.utcnow().isoformat()
        user.preferences['restored_by'] = str(current_user.id)

        await db.commit()

        logger.info(f"User {user.email} restored by {current_user.email}")

        return {
            "success": True,
            "message": "User restored successfully",
            "user_id": str(user_id),
            "status": user.status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring user: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============= Billing & Credits =============

@router.get("/billing/transactions")
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: Optional[UUID] = None,
    transaction_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
) -> TransactionListResponse:
    """List all credit transactions"""
    try:
        query = select(CreditTransaction)

        # Apply filters
        conditions = []
        if user_id:
            conditions.append(CreditTransaction.user_id == user_id)
        if transaction_type:
            conditions.append(CreditTransaction.transaction_type == transaction_type)

        if conditions:
            query = query.where(and_(*conditions))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Sum amounts
        sum_query = select(func.sum(CreditTransaction.amount)).select_from(query.subquery())
        sum_result = await db.execute(sum_query)
        total_amount = float(sum_result.scalar() or 0)

        # Paginate
        offset = (page - 1) * page_size
        query = query.order_by(desc(CreditTransaction.created_at)).offset(offset).limit(page_size)

        # Execute
        result = await db.execute(query)
        transactions = result.scalars().all()

        transaction_list = []
        for txn in transactions:
            # Get user info
            user_result = await db.execute(
                select(User).where(User.id == txn.user_id)
            )
            user = user_result.scalar_one_or_none()

            transaction_list.append({
                "id": str(txn.id),
                "user_email": user.email if user else "Unknown",
                "transaction_type": txn.transaction_type,
                "action": txn.action,
                "credits": txn.credits,
                "amount": float(txn.amount) if txn.amount else 0,
                "balance_after": txn.balance_after,
                "created_at": txn.created_at.isoformat() if txn.created_at else None
            })

        return TransactionListResponse(
            transactions=transaction_list,
            total=total,
            total_amount=total_amount
        )
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/credits/add")
async def add_credits(
    user_id: UUID = Body(...),
    credits: int = Body(..., ge=1, le=100000),
    reason: str = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Add credits to a user"""
    try:
        # First, get the supabase_user_id for this user
        user_result = await db.execute(
            text("SELECT supabase_user_id FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = user_result.first()

        if not user or not user.supabase_user_id:
            raise HTTPException(status_code=404, detail="User not found or no auth account")

        wallet_service = CreditWalletService()

        # Add credits using the supabase_user_id (auth.users.id)
        transaction = await wallet_service.add_credits(
            user_id=user.supabase_user_id,  # Use supabase_user_id for wallet
            amount=credits,
            transaction_type="admin_credit",
            description=f"Admin added: {reason}",
            reference_id=str(current_user.id),
            reference_type="admin_action"
        )

        if transaction:
            # Get the updated balance
            balance = await wallet_service.get_balance(user.supabase_user_id)
            return {
                "success": True,
                "new_balance": balance.current_balance if balance else credits,
                "message": f"Added {credits} credits successfully"
            }
        else:
            raise Exception("Failed to add credits")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding credits: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/credits/remove")
async def remove_credits(
    user_id: UUID = Body(...),
    credits: int = Body(..., ge=1, le=100000),
    reason: str = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Remove credits from a user"""
    try:
        # First, get the supabase_user_id for this user
        user_result = await db.execute(
            text("SELECT supabase_user_id FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = user_result.first()

        if not user or not user.supabase_user_id:
            raise HTTPException(status_code=404, detail="User not found or no auth account")

        wallet_service = CreditWalletService()

        # Remove credits using the supabase_user_id (auth.users.id)
        transaction = await wallet_service.spend_credits(
            user_id=user.supabase_user_id,  # Use supabase_user_id for wallet
            amount=credits,
            action_type="admin_removal",
            description=f"Admin removed: {reason}",
            reference_id=str(current_user.id),
            reference_type="admin_action"
        )

        if not transaction:
            raise HTTPException(status_code=400, detail="Failed to remove credits - insufficient balance or wallet not found")

        # Get the updated balance
        balance = await wallet_service.get_balance(user.supabase_user_id)
        return {
            "success": True,
            "new_balance": balance.current_balance if balance else 0,
            "message": f"Removed {credits} credits successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing credits: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/billing/revenue")
async def get_revenue_summary(
    months: int = Query(6, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Get monthly revenue summary"""
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)

        # Query monthly revenue using ORM to avoid PGBouncer issues
        from sqlalchemy import extract

        # Build the query using ORM
        monthly_query = select(
            func.date_trunc('month', CreditTransaction.created_at).label('month'),
            func.sum(CreditTransaction.amount).label('revenue'),
            func.count(CreditTransaction.id).label('transaction_count')
        ).where(
            and_(
                CreditTransaction.transaction_type == 'purchase',
                CreditTransaction.created_at >= start_date
            )
        ).group_by(
            func.date_trunc('month', CreditTransaction.created_at)
        ).order_by(
            func.date_trunc('month', CreditTransaction.created_at).desc()
        )

        result = await db.execute(monthly_query)

        monthly_revenue = []
        for row in result:
            monthly_revenue.append({
                "month": row.month.isoformat() if row.month else None,
                "revenue": float(row.revenue or 0),
                "transaction_count": row.transaction_count
            })

        # Total revenue
        total_result = await db.execute(
            select(func.sum(CreditTransaction.amount))
            .where(
                and_(
                    CreditTransaction.transaction_type == 'purchase',
                    CreditTransaction.created_at >= start_date
                )
            )
        )
        total_revenue = float(total_result.scalar() or 0)

        return {
            "monthly_revenue": monthly_revenue,
            "total_revenue": total_revenue,
            "months_included": months
        }
    except Exception as e:
        logger.error(f"Error getting revenue summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Content Management =============

@router.get("/content/profiles")
async def list_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    incomplete_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
) -> ProfileListResponse:
    """List all profiles in database"""
    try:
        query = select(Profile)

        # Filter incomplete if requested
        if incomplete_only:
            query = query.where(
                or_(
                    Profile.followers_count == None,
                    Profile.followers_count == 0,
                    Profile.ai_profile_analyzed_at == None
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Count incomplete
        incomplete_query = select(func.count(Profile.id)).where(
            or_(
                Profile.followers_count == None,
                Profile.followers_count == 0,
                Profile.ai_profile_analyzed_at == None
            )
        )
        incomplete_result = await db.execute(incomplete_query)
        incomplete_count = incomplete_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.order_by(desc(Profile.created_at)).offset(offset).limit(page_size)

        # Execute
        result = await db.execute(query)
        profiles = result.scalars().all()

        profile_list = []
        for profile in profiles:
            # Check completeness
            is_complete = (
                profile.followers_count and
                profile.followers_count > 0 and
                profile.ai_profile_analyzed_at is not None
            )

            profile_list.append({
                "id": str(profile.id),
                "username": profile.username,
                "full_name": profile.full_name,
                "followers_count": profile.followers_count,
                "following_count": profile.following_count,
                "posts_count": profile.posts_count,
                "is_complete": is_complete,
                "ai_analyzed": profile.ai_profile_analyzed_at is not None,
                "created_at": profile.created_at.isoformat() if profile.created_at else None
            })

        return ProfileListResponse(
            profiles=profile_list,
            total=total,
            incomplete_count=incomplete_count
        )
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content/unlocks")
async def list_unlocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """List profile unlock history"""
    try:
        query = select(UserProfileAccess)

        if user_id:
            query = query.where(UserProfileAccess.user_id == user_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.order_by(desc(UserProfileAccess.accessed_at)).offset(offset).limit(page_size)

        # Execute
        result = await db.execute(query)
        unlocks = result.scalars().all()

        unlock_list = []
        for unlock in unlocks:
            # Get user and profile info
            user_result = await db.execute(
                select(User).where(User.id == unlock.user_id)
            )
            user = user_result.scalar_one_or_none()

            profile_result = await db.execute(
                select(Profile).where(Profile.id == unlock.profile_id)
            )
            profile = profile_result.scalar_one_or_none()

            unlock_list.append({
                "user_email": user.email if user else "Unknown",
                "profile_username": profile.username if profile else "Unknown",
                "unlocked_at": unlock.accessed_at.isoformat() if unlock.accessed_at else None,
                "expires_at": unlock.expires_at.isoformat() if unlock.expires_at else None,
                "is_expired": unlock.expires_at < datetime.utcnow() if unlock.expires_at else False
            })

        return {
            "unlocks": unlock_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error(f"Error listing unlocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Password Management =============

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    new_password: str = Body(..., min_length=8, description="New password for the user"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Reset a user's password (admin override)

    WARNING: This is a powerful admin action that should be logged.
    Only use for legitimate support requests.
    """
    try:
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent changing superadmin passwords by non-superadmins
        if user.role in ['super_admin', 'superadmin'] and current_user.role not in ['super_admin', 'superadmin']:
            raise HTTPException(status_code=403, detail="Cannot reset password for superadmin accounts")

        # Use Supabase to update password
        from app.services.supabase_auth_service import SupabaseAuthService
        auth_service = SupabaseAuthService()

        # Update password in Supabase
        success = await auth_service.admin_update_user_password(
            user_id=str(user.supabase_user_id) if user.supabase_user_id else str(user.id),
            new_password=new_password
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset password in authentication system")

        # Log the action
        logger.info(f"Password reset for user {user.email} by admin {current_user.email}")

        # Update user metadata
        user.updated_at = datetime.utcnow()
        if not user.preferences:
            user.preferences = {}
        user.preferences['password_reset_by_admin'] = {
            'admin_id': str(current_user.id),
            'admin_email': current_user.email,
            'reset_at': datetime.utcnow().isoformat()
        }

        await db.commit()

        return {
            "success": True,
            "message": "Password reset successfully",
            "user_email": user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


class SetPasswordRequest(BaseModel):
    """Request model for setting user password"""
    password: str = Field(..., min_length=8, description="New password for the user")


@router.post("/users/{user_id}/set-password")
async def set_user_password(
    user_id: UUID,
    request: SetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Set a user's password (admin action) - alias for reset-password

    This endpoint is an alias for reset-password to maintain compatibility
    with frontend expectations.
    """
    return await reset_user_password(user_id, request.password, db, current_user)


@router.post("/users/{user_id}/send-password-reset")
async def send_password_reset_email(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Send a password reset email to the user

    This is the preferred method - lets users reset their own password
    """
    try:
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Use Supabase to send reset email
        from app.services.supabase_auth_service import SupabaseAuthService
        auth_service = SupabaseAuthService()

        # Send password reset email
        success = await auth_service.send_password_reset_email(user.email)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to send password reset email")

        logger.info(f"Password reset email sent to {user.email} by admin {current_user.email}")

        return {
            "success": True,
            "message": "Password reset email sent successfully",
            "user_email": user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending password reset email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Simple System Health =============

@router.get("/system/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """Simple system health check"""
    try:
        # Check database
        db_status = "healthy"
        try:
            await db.execute(text("SELECT 1"))
        except:
            db_status = "unhealthy"

        # Check Redis (if available)
        redis_status = "unknown"
        try:
            from app.services.redis_cache_service import RedisCacheService
            redis_service = RedisCacheService()
            await redis_service.redis.ping()
            redis_status = "healthy"
        except:
            redis_status = "unhealthy"

        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "database": db_status,
            "redis": redis_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }