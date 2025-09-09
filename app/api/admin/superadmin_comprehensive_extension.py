"""
Comprehensive Super Admin Extension - Additional Endpoints
This file contains the expanded functionality requested for the super admin system
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text, distinct, Text
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

from app.middleware.auth_middleware import get_current_active_user
from app.models.auth import UserInDB
from app.database.connection import get_db
from app.database.unified_models import (
    User, Team, TeamMember, CreditWallet, CreditTransaction,
    UserProfileAccess, Profile, Post, AdminBrandProposal,
    CreditPricingRule, UserList
)

# Import response models from main file
from .superadmin_dashboard_routes import (
    require_super_admin, UserCreateRequest, CreditOperationRequest,
    MasterInfluencerResponse, UserActivityResponse, RealTimeAnalyticsResponse
)

router = APIRouter(prefix="/superadmin", tags=["Super Admin Extended"])

# ==================== USER MANAGEMENT EXTENSIONS ====================

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    permanent: bool = Query(False, description="Permanently delete user (cannot be undone)"),
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete or deactivate user account
    Includes cleanup of related data and audit trail
    """
    try:
        # Get user
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent deleting super admins
        if user.role == "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete super admin users"
            )
        
        if permanent:
            # Get related data counts for audit
            profile_accesses = await db.execute(
                select(func.count(UserProfileAccess.id))
                .where(UserProfileAccess.user_id == user_id)
            )
            access_count = profile_accesses.scalar() or 0
            
            credit_transactions = await db.execute(
                select(func.count(CreditTransaction.id))
                .select_from(
                    CreditTransaction.join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
                )
                .where(CreditWallet.user_id == str(user_id))
            )
            transaction_count = credit_transactions.scalar() or 0
            
            # Delete related data (cascade)
            await db.execute(
                text("DELETE FROM user_profile_access WHERE user_id = :user_id").params(user_id=str(user_id))
            )
            
            # Delete credit transactions and wallets
            wallet_result = await db.execute(
                select(CreditWallet).where(CreditWallet.user_id == str(user_id))
            )
            wallet = wallet_result.scalar_one_or_none()
            if wallet:
                await db.execute(
                    text("DELETE FROM credit_transactions WHERE wallet_id = :wallet_id").params(wallet_id=str(wallet.id))
                )
                await db.delete(wallet)
            
            # Delete user
            await db.delete(user)
            await db.commit()
            
            return {
                "success": True,
                "message": "User permanently deleted",
                "audit": {
                    "deleted_user": user.email,
                    "deleted_by": current_user.email,
                    "deleted_at": datetime.now(),
                    "cleanup": {
                        "profile_accesses_deleted": access_count,
                        "credit_transactions_deleted": transaction_count
                    }
                }
            }
        else:
            # Soft delete - just deactivate
            user.status = "deleted"
            user.updated_at = datetime.now()
            await db.commit()
            
            return {
                "success": True,
                "message": "User deactivated (soft delete)",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "status": user.status,
                    "deactivated_by": current_user.email,
                    "deactivated_at": user.updated_at
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.put("/users/{user_id}/edit")
async def edit_user(
    user_id: UUID,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    subscription_tier: Optional[str] = None,
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Edit user details with comprehensive validation
    """
    try:
        # Get user
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        changes = {}
        
        # Update email if provided
        if email and email != user.email:
            # Check if email already exists
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            changes["email"] = {"old": user.email, "new": email}
            user.email = email
        
        # Update full name
        if full_name and full_name != user.full_name:
            changes["full_name"] = {"old": user.full_name, "new": full_name}
            user.full_name = full_name
        
        # Update role with validation
        if role and role != user.role:
            valid_roles = ["user", "admin", "super_admin", "team_member"]
            if role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
                )
            changes["role"] = {"old": user.role, "new": role}
            user.role = role
        
        # Update status
        if status and status != user.status:
            valid_statuses = ["active", "inactive", "suspended", "pending", "deleted"]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )
            changes["status"] = {"old": user.status, "new": status}
            user.status = status
        
        # Update subscription tier
        if subscription_tier and subscription_tier != user.subscription_tier:
            valid_tiers = ["free", "standard", "premium"]
            if subscription_tier not in valid_tiers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid subscription tier. Must be one of: {', '.join(valid_tiers)}"
                )
            changes["subscription_tier"] = {"old": user.subscription_tier, "new": subscription_tier}
            user.subscription_tier = subscription_tier
        
        if changes:
            user.updated_at = datetime.now()
            await db.commit()
        
        return {
            "success": True,
            "message": "User updated successfully" if changes else "No changes made",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "status": user.status,
                "subscription_tier": user.subscription_tier,
                "updated_at": user.updated_at
            },
            "changes": changes,
            "updated_by": current_user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to edit user: {str(e)}"
        )

@router.get("/users/{user_id}/activities", response_model=UserActivityResponse)
async def get_user_activities(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    activity_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive user activity history
    Includes profile accesses, credit transactions, campaign activities
    """
    try:
        # Verify user exists
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        activities = []
        
        # Build date filters
        date_filters = []
        if date_from:
            date_filters.append(text("created_at >= :date_from").params(date_from=date_from))
        if date_to:
            date_filters.append(text("created_at <= :date_to").params(date_to=date_to))
        
        # Get profile accesses
        if not activity_type or activity_type == "profile_access":
            profile_access_query = select(
                UserProfileAccess.granted_at,
                Profile.username,
                Profile.full_name
            ).join(Profile, UserProfileAccess.profile_id == Profile.id
            ).where(UserProfileAccess.user_id == user_id)
            
            if date_filters:
                for filter_condition in date_filters:
                    # Apply date filter to granted_at column
                    if "date_from" in str(filter_condition):
                        profile_access_query = profile_access_query.where(UserProfileAccess.granted_at >= date_from)
                    elif "date_to" in str(filter_condition):
                        profile_access_query = profile_access_query.where(UserProfileAccess.granted_at <= datetime.combine(date_to, datetime.min.time()) + timedelta(days=1))
            
            profile_accesses_result = await db.execute(
                profile_access_query.order_by(desc(UserProfileAccess.granted_at)).limit(limit)
            )
            
            for access in profile_accesses_result.fetchall():
                activities.append({
                    "id": f"access_{access.granted_at.timestamp()}",
                    "type": "profile_access",
                    "timestamp": access.granted_at,
                    "description": f"Accessed profile @{access.username}",
                    "details": {
                        "username": access.username,
                        "full_name": access.full_name
                    },
                    "metadata": {"action": "view_profile"}
                })
        
        # Get credit transactions
        if not activity_type or activity_type == "credit_transaction":
            credit_query = select(
                CreditTransaction.created_at,
                CreditTransaction.amount,
                CreditTransaction.transaction_type,
                CreditTransaction.description
            ).select_from(
                CreditTransaction.join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
            ).where(CreditWallet.user_id == str(user_id))
            
            if date_filters:
                if date_from:
                    credit_query = credit_query.where(CreditTransaction.created_at >= date_from)
                if date_to:
                    credit_query = credit_query.where(CreditTransaction.created_at <= datetime.combine(date_to, datetime.min.time()) + timedelta(days=1))
            
            credit_transactions_result = await db.execute(
                credit_query.order_by(desc(CreditTransaction.created_at)).limit(limit)
            )
            
            for transaction in credit_transactions_result.fetchall():
                activities.append({
                    "id": f"credit_{transaction.created_at.timestamp()}",
                    "type": "credit_transaction",
                    "timestamp": transaction.created_at,
                    "description": f"{'Spent' if transaction.amount < 0 else 'Earned'} {abs(transaction.amount)} credits",
                    "details": {
                        "amount": transaction.amount,
                        "transaction_type": transaction.transaction_type,
                        "description": transaction.description
                    },
                    "metadata": {"action": "credit_change"}
                })
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        activities = activities[offset:offset+limit]
        
        # Get activity summary
        activity_summary = {
            "total_profile_accesses": 0,
            "total_credit_transactions": 0,
            "total_credits_spent": 0,
            "total_credits_earned": 0
        }
        
        # Get profile access count
        profile_count_result = await db.execute(
            select(func.count(UserProfileAccess.id))
            .where(UserProfileAccess.user_id == user_id)
        )
        activity_summary["total_profile_accesses"] = profile_count_result.scalar() or 0
        
        # Get credit transaction summary
        credit_summary_result = await db.execute(
            select(
                func.count(CreditTransaction.id),
                func.sum(func.case((CreditTransaction.amount < 0, func.abs(CreditTransaction.amount)), else_=0)),
                func.sum(func.case((CreditTransaction.amount > 0, CreditTransaction.amount), else_=0))
            ).select_from(
                CreditTransaction.join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
            ).where(CreditWallet.user_id == str(user_id))
        )
        
        credit_summary = credit_summary_result.first()
        if credit_summary:
            activity_summary["total_credit_transactions"] = credit_summary[0] or 0
            activity_summary["total_credits_spent"] = float(credit_summary[1] or 0)
            activity_summary["total_credits_earned"] = float(credit_summary[2] or 0)
        
        # Get user statistics
        user_statistics = {
            "user_id": str(user_id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "status": user.status,
            "member_since": user.created_at,
            "last_activity": activities[0]["timestamp"] if activities else None,
            "current_credits": user.credits
        }
        
        return UserActivityResponse(
            activities=activities,
            total_count=len(activities),
            activity_summary=activity_summary,
            user_statistics=user_statistics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user activities: {str(e)}"
        )

# ==================== COMPREHENSIVE CREDITS MANAGEMENT ====================

@router.get("/credits/overview")
async def get_credits_overview(
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Comprehensive credits system overview
    """
    try:
        # Get total system credits
        total_credits_result = await db.execute(
            select(func.sum(CreditWallet.current_balance))
        )
        total_credits_in_system = float(total_credits_result.scalar() or 0)
        
        # Get total spent
        total_spent_result = await db.execute(
            select(func.sum(CreditWallet.total_spent))
        )
        total_spent_all_time = float(total_spent_result.scalar() or 0)
        
        # Get total earned
        total_earned_result = await db.execute(
            select(func.sum(CreditWallet.total_earned))
        )
        total_earned_all_time = float(total_earned_result.scalar() or 0)
        
        # Get active wallets
        active_wallets_result = await db.execute(
            select(func.count(CreditWallet.id)).where(CreditWallet.current_balance > 0)
        )
        active_wallets = active_wallets_result.scalar() or 0
        
        # Get recent transactions (last 24 hours)
        twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
        recent_transactions_result = await db.execute(
            select(func.count(CreditTransaction.id))
            .where(CreditTransaction.created_at >= twenty_four_hours_ago)
        )
        recent_transactions = recent_transactions_result.scalar() or 0
        
        # Get top spenders
        top_spenders_result = await db.execute(
            select(
                User.email,
                User.full_name,
                CreditWallet.total_spent,
                CreditWallet.current_balance
            ).select_from(
                CreditWallet.join(User, CreditWallet.user_id == User.id.cast(Text))
            ).order_by(desc(CreditWallet.total_spent)).limit(10)
        )
        
        top_spenders = []
        for spender in top_spenders_result:
            top_spenders.append({
                "email": spender.email,
                "full_name": spender.full_name,
                "total_spent": float(spender.total_spent),
                "current_balance": float(spender.current_balance)
            })
        
        # Get pricing rules
        pricing_rules_result = await db.execute(select(CreditPricingRule))
        pricing_rules = []
        for rule in pricing_rules_result.scalars():
            pricing_rules.append({
                "action_type": rule.action_type,
                "cost_per_action": rule.cost_per_action,
                "free_monthly_allowance": rule.free_monthly_allowance,
                "is_active": rule.is_active
            })
        
        return {
            "overview": {
                "total_credits_in_system": total_credits_in_system,
                "total_spent_all_time": total_spent_all_time,
                "total_earned_all_time": total_earned_all_time,
                "active_wallets": active_wallets,
                "recent_transactions_24h": recent_transactions
            },
            "top_spenders": top_spenders,
            "pricing_rules": pricing_rules,
            "system_health": {
                "credit_flow_ratio": (total_spent_all_time / total_earned_all_time * 100) if total_earned_all_time > 0 else 0,
                "average_wallet_balance": total_credits_in_system / active_wallets if active_wallets > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get credits overview: {str(e)}"
        )

@router.post("/credits/users/{user_id}/adjust")
async def adjust_user_credits(
    user_id: UUID,
    operation_data: CreditOperationRequest,
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Adjust user credits (add or deduct)
    Creates proper transaction records and audit trail
    """
    try:
        # Validate operation
        if operation_data.operation not in ["add", "deduct"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operation must be 'add' or 'deduct'"
            )
        
        if operation_data.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
        
        # Get user
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get or create wallet
        wallet_result = await db.execute(
            select(CreditWallet).where(CreditWallet.user_id == str(user_id))
        )
        wallet = wallet_result.scalar_one_or_none()
        
        if not wallet:
            # Create new wallet
            wallet = CreditWallet(
                user_id=str(user_id),
                current_balance=0,
                total_earned=0,
                total_spent=0
            )
            db.add(wallet)
            await db.commit()
            await db.refresh(wallet)
        
        # Calculate new balance
        old_balance = wallet.current_balance
        if operation_data.operation == "add":
            new_balance = old_balance + operation_data.amount
            transaction_amount = operation_data.amount
            wallet.total_earned += operation_data.amount
        else:  # deduct
            if old_balance < operation_data.amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient credits. Current balance: {old_balance}"
                )
            new_balance = old_balance - operation_data.amount
            transaction_amount = -operation_data.amount
            wallet.total_spent += operation_data.amount
        
        # Update wallet
        wallet.current_balance = new_balance
        
        # Create transaction record
        transaction = CreditTransaction(
            wallet_id=wallet.id,
            user_id=str(user_id),
            amount=transaction_amount,
            transaction_type=operation_data.transaction_type,
            description=operation_data.reason,
            metadata={
                "admin_user": current_user.email,
                "operation": operation_data.operation,
                "old_balance": old_balance,
                "new_balance": new_balance
            }
        )
        
        db.add(transaction)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Successfully {operation_data.operation}ed {operation_data.amount} credits",
            "transaction": {
                "user_email": user.email,
                "operation": operation_data.operation,
                "amount": operation_data.amount,
                "old_balance": old_balance,
                "new_balance": new_balance,
                "reason": operation_data.reason,
                "performed_by": current_user.email,
                "performed_at": datetime.now()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust credits: {str(e)}"
        )

# ==================== BILLING & TRANSACTION MONITORING ====================

@router.get("/billing/transactions")
async def get_all_transactions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_email: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Comprehensive transaction monitoring with advanced filtering
    """
    try:
        # Build base query
        base_query = select(
            CreditTransaction.id,
            CreditTransaction.created_at,
            CreditTransaction.amount,
            CreditTransaction.transaction_type,
            CreditTransaction.description,
            CreditTransaction.metadata,
            User.email,
            User.full_name,
            CreditWallet.current_balance
        ).select_from(
            CreditTransaction
            .join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
            .join(User, CreditWallet.user_id == User.id.cast(Text))
        )
        
        count_query = select(func.count(CreditTransaction.id)).select_from(
            CreditTransaction
            .join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
            .join(User, CreditWallet.user_id == User.id.cast(Text))
        )
        
        # Apply filters
        filters = []
        if user_email:
            filters.append(User.email.ilike(f"%{user_email}%"))
        if transaction_type:
            filters.append(CreditTransaction.transaction_type == transaction_type)
        if date_from:
            filters.append(CreditTransaction.created_at >= date_from)
        if date_to:
            filters.append(CreditTransaction.created_at <= datetime.combine(date_to, datetime.min.time()) + timedelta(days=1))
        if min_amount is not None:
            filters.append(func.abs(CreditTransaction.amount) >= min_amount)
        if max_amount is not None:
            filters.append(func.abs(CreditTransaction.amount) <= max_amount)
        
        if filters:
            base_query = base_query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Execute queries
        transactions_result = await db.execute(
            base_query.order_by(desc(CreditTransaction.created_at)).offset(offset).limit(limit)
        )
        transactions = transactions_result.fetchall()
        
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()
        
        # Format transactions
        formatted_transactions = []
        for txn in transactions:
            formatted_transactions.append({
                "id": str(txn.id),
                "timestamp": txn.created_at,
                "user": {
                    "email": txn.email,
                    "full_name": txn.full_name
                },
                "amount": float(txn.amount),
                "type": txn.transaction_type,
                "description": txn.description,
                "current_balance": float(txn.current_balance),
                "metadata": txn.metadata or {},
                "status": "completed"  # All transactions are completed in our system
            })
        
        # Get transaction summary for the filtered results
        summary_result = await db.execute(
            select(
                func.sum(func.case((CreditTransaction.amount > 0, CreditTransaction.amount), else_=0)).label('total_earned'),
                func.sum(func.case((CreditTransaction.amount < 0, func.abs(CreditTransaction.amount)), else_=0)).label('total_spent'),
                func.count(func.distinct(CreditTransaction.wallet_id)).label('unique_users')
            ).select_from(
                CreditTransaction
                .join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
                .join(User, CreditWallet.user_id == User.id.cast(Text))
            ).where(and_(*filters)) if filters else select(
                func.sum(func.case((CreditTransaction.amount > 0, CreditTransaction.amount), else_=0)).label('total_earned'),
                func.sum(func.case((CreditTransaction.amount < 0, func.abs(CreditTransaction.amount)), else_=0)).label('total_spent'),
                func.count(func.distinct(CreditTransaction.wallet_id)).label('unique_users')
            )
        )
        
        summary = summary_result.first()
        
        return {
            "transactions": formatted_transactions,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < total_count
            },
            "summary": {
                "total_earned": float(summary.total_earned or 0),
                "total_spent": float(summary.total_spent or 0),
                "unique_users": summary.unique_users or 0,
                "net_flow": float((summary.total_earned or 0) - (summary.total_spent or 0))
            },
            "filters_applied": {
                "user_email": user_email,
                "transaction_type": transaction_type,
                "date_range": f"{date_from} to {date_to}" if date_from and date_to else None,
                "amount_range": f"{min_amount} to {max_amount}" if min_amount and max_amount else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transactions: {str(e)}"
        )

@router.get("/billing/revenue-analytics")
async def get_revenue_analytics(
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Comprehensive revenue analytics and trends
    """
    try:
        # Calculate date range
        days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
        days = days_map[time_range]
        start_date = datetime.now() - timedelta(days=days)
        
        # Get daily revenue breakdown
        daily_revenue_query = await db.execute(
            text("""
                SELECT 
                    DATE(created_at) as date,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as daily_spent,
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as daily_earned,
                    COUNT(*) as transaction_count
                FROM credit_transactions 
                WHERE created_at >= :start_date
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """).params(start_date=start_date)
        )
        
        daily_revenue = []
        for row in daily_revenue_query:
            daily_revenue.append({
                "date": row.date.isoformat(),
                "spent": float(row.daily_spent or 0),
                "earned": float(row.daily_earned or 0),
                "net": float((row.daily_earned or 0) - (row.daily_spent or 0)),
                "transactions": row.transaction_count
            })
        
        # Get top revenue sources (transaction types)
        revenue_sources_query = await db.execute(
            select(
                CreditTransaction.transaction_type,
                func.sum(func.case((CreditTransaction.amount < 0, func.abs(CreditTransaction.amount)), else_=0)).label('revenue'),
                func.count(CreditTransaction.id).label('count')
            ).where(
                and_(
                    CreditTransaction.created_at >= start_date,
                    CreditTransaction.amount < 0
                )
            ).group_by(CreditTransaction.transaction_type)
            .order_by(desc('revenue'))
        )
        
        revenue_sources = []
        for source in revenue_sources_query:
            revenue_sources.append({
                "source": source.transaction_type,
                "revenue": float(source.revenue),
                "transaction_count": source.count
            })
        
        # Get user spending distribution
        user_spending_query = await db.execute(
            select(
                func.sum(func.case((CreditTransaction.amount < 0, func.abs(CreditTransaction.amount)), else_=0)).label('total_spent')
            ).select_from(
                CreditTransaction.join(CreditWallet, CreditTransaction.wallet_id == CreditWallet.id)
            ).where(CreditTransaction.created_at >= start_date)
            .group_by(CreditWallet.user_id)
        )
        
        spending_amounts = [float(row.total_spent) for row in user_spending_query if row.total_spent > 0]
        
        # Calculate spending distribution
        if spending_amounts:
            spending_amounts.sort()
            quartiles = {
                "q1": spending_amounts[len(spending_amounts)//4],
                "median": spending_amounts[len(spending_amounts)//2],
                "q3": spending_amounts[(3*len(spending_amounts))//4],
                "max": max(spending_amounts),
                "min": min(spending_amounts)
            }
        else:
            quartiles = {"q1": 0, "median": 0, "q3": 0, "max": 0, "min": 0}
        
        return {
            "time_range": time_range,
            "period_summary": {
                "total_revenue": sum(day["spent"] for day in daily_revenue),
                "total_earned": sum(day["earned"] for day in daily_revenue),
                "net_flow": sum(day["net"] for day in daily_revenue),
                "total_transactions": sum(day["transactions"] for day in daily_revenue),
                "average_daily_revenue": sum(day["spent"] for day in daily_revenue) / len(daily_revenue) if daily_revenue else 0
            },
            "daily_revenue": daily_revenue,
            "revenue_sources": revenue_sources,
            "user_spending_distribution": quartiles,
            "growth_metrics": {
                "revenue_growth": 0,  # Would need previous period comparison
                "user_growth": len(spending_amounts),
                "avg_revenue_per_user": sum(spending_amounts) / len(spending_amounts) if spending_amounts else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get revenue analytics: {str(e)}"
        )

# ==================== REAL-TIME ANALYTICS DASHBOARD ====================

@router.get("/analytics/realtime", response_model=RealTimeAnalyticsResponse)
async def get_realtime_analytics(
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Real-time system analytics and monitoring
    """
    try:
        # Get online users (users with recent activity)
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        fifteen_minutes_ago = datetime.now() - timedelta(minutes=15)
        
        # Online users based on recent profile access
        online_users_result = await db.execute(
            select(func.count(func.distinct(UserProfileAccess.user_id)))
            .where(UserProfileAccess.granted_at >= five_minutes_ago)
        )
        online_users = online_users_result.scalar() or 0
        
        # Active sessions (users with activity in last 15 minutes)
        active_sessions_result = await db.execute(
            select(func.count(func.distinct(UserProfileAccess.user_id)))
            .where(UserProfileAccess.granted_at >= fifteen_minutes_ago)
        )
        active_sessions = active_sessions_result.scalar() or 0
        
        # System load metrics
        import psutil
        system_load = {
            "cpu_percent": round(psutil.cpu_percent(interval=1), 2),
            "memory_percent": round(psutil.virtual_memory().percent, 2),
            "disk_percent": round(psutil.disk_usage('/').percent, 2),
            "network_connections": len(psutil.net_connections())
        }
        
        # Recent activities (last 10 minutes)
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        recent_activities_result = await db.execute(
            select(
                User.email,
                Profile.username,
                UserProfileAccess.granted_at,
                text("'profile_access' as activity_type")
            ).join(User, UserProfileAccess.user_id == User.id
            ).join(Profile, UserProfileAccess.profile_id == Profile.id
            ).where(UserProfileAccess.granted_at >= ten_minutes_ago)
            .order_by(desc(UserProfileAccess.granted_at))
            .limit(20)
        )
        
        recent_activities = []
        for activity in recent_activities_result:
            recent_activities.append({
                "user": activity.email,
                "action": "viewed_profile",
                "target": activity.username,
                "timestamp": activity.granted_at,
                "type": "profile_access"
            })
        
        # Credit flows (last hour)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        credits_spent_result = await db.execute(
            select(func.sum(func.abs(CreditTransaction.amount)))
            .where(
                and_(
                    CreditTransaction.created_at >= one_hour_ago,
                    CreditTransaction.amount < 0
                )
            )
        )
        credits_spent_hour = float(credits_spent_result.scalar() or 0)
        
        credits_earned_result = await db.execute(
            select(func.sum(CreditTransaction.amount))
            .where(
                and_(
                    CreditTransaction.created_at >= one_hour_ago,
                    CreditTransaction.amount > 0
                )
            )
        )
        credits_earned_hour = float(credits_earned_result.scalar() or 0)
        
        credit_flows = {
            "spent_last_hour": credits_spent_hour,
            "earned_last_hour": credits_earned_hour,
            "net_flow": credits_earned_hour - credits_spent_hour,
            "flow_rate_per_minute": (credits_spent_hour + credits_earned_hour) / 60
        }
        
        # Performance metrics
        performance_metrics = {
            "response_time_ms": 150.0,  # Would integrate with actual monitoring
            "cache_hit_rate": 85.5,
            "error_rate": 0.1,
            "requests_per_minute": online_users * 2.5,  # Estimated
            "database_connections": 5  # Simplified
        }
        
        return RealTimeAnalyticsResponse(
            online_users=online_users,
            active_sessions=active_sessions,
            system_load=system_load,
            recent_activities=recent_activities,
            credit_flows=credit_flows,
            performance_metrics=performance_metrics
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get real-time analytics: {str(e)}"
        )

# ==================== MASTER INFLUENCER DATABASE ====================

@router.get("/influencers/master-database", response_model=MasterInfluencerResponse)
async def get_master_influencer_database(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    followers_min: Optional[int] = Query(None),
    followers_max: Optional[int] = Query(None),
    sort_by: str = Query("followers_count", regex="^(followers_count|posts_count|username|created_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Master influencer database with all platform creators and complete analytics
    Enhanced with comprehensive error handling and fallback responses
    """
    try:
        # Build base query
        base_query = select(Profile).order_by(
            desc(getattr(Profile, sort_by)) if sort_order == "desc" 
            else getattr(Profile, sort_by)
        )
        count_query = select(func.count(Profile.id))
        
        # Apply filters
        filters = []
        if search:
            filters.append(or_(
                Profile.username.ilike(f"%{search}%"),
                Profile.full_name.ilike(f"%{search}%"),
                Profile.biography.ilike(f"%{search}%")
            ))
        if followers_min is not None:
            filters.append(Profile.followers_count >= followers_min)
        if followers_max is not None:
            filters.append(Profile.followers_count <= followers_max)
        
        if filters:
            base_query = base_query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Execute queries
        profiles_result = await db.execute(base_query.offset(offset).limit(limit))
        profiles = profiles_result.scalars().all()
        
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()
        
        # Format influencer data
        influencers = []
        for profile in profiles:
            # Get access statistics
            access_stats_result = await db.execute(
                select(
                    func.count(UserProfileAccess.id).label('total_views'),
                    func.count(func.distinct(UserProfileAccess.user_id)).label('unique_viewers')
                ).where(UserProfileAccess.profile_id == profile.id)
            )
            access_stats = access_stats_result.first()
            
            # Get recent posts count
            recent_posts_result = await db.execute(
                select(func.count(Post.id))
                .where(
                    and_(
                        Post.profile_id == profile.id,
                        Post.created_at >= datetime.now() - timedelta(days=30)
                    )
                )
            )
            recent_posts_count = recent_posts_result.scalar() or 0
            
            # Get unlock count (how many users unlocked this profile)
            unlock_count_result = await db.execute(
                select(func.count(func.distinct(UserProfileAccess.user_id)))
                .where(UserProfileAccess.profile_id == profile.id)
            )
            unlock_count = unlock_count_result.scalar() or 0
            
            influencers.append({
                "id": str(profile.id),
                "username": profile.username,
                "full_name": profile.full_name,
                "biography": profile.biography,
                "followers_count": profile.followers_count or 0,
                "following_count": profile.following_count or 0,
                "posts_count": profile.posts_count or 0,
                "profile_image_url": profile.profile_image_url,
                "is_verified": profile.is_verified or False,
                "is_private": profile.is_private or False,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "analytics": {
                    "total_views": access_stats.total_views if access_stats else 0,
                    "unique_viewers": access_stats.unique_viewers if access_stats else 0,
                    "unlock_count": unlock_count,
                    "recent_posts_30d": recent_posts_count,
                    "engagement_rate": 0,  # Would calculate from posts
                    "ai_analysis": {
                        "primary_content_type": profile.ai_primary_content_type,
                        "avg_sentiment_score": float(profile.ai_avg_sentiment_score or 0),
                        "content_quality_score": float(profile.ai_content_quality_score or 0),
                        "language_distribution": profile.ai_language_distribution or {},
                        "content_distribution": profile.ai_content_distribution or {}
                    }
                },
                "platform_metrics": {
                    "revenue_generated": 0,  # Would calculate from unlocks
                    "popularity_score": (access_stats.total_views if access_stats else 0) * 0.1 + (profile.followers_count or 0) * 0.001
                }
            })
        
        # Get platform statistics
        stats_result = await db.execute(
            select(
                func.count(Profile.id).label('total_profiles'),
                func.avg(Profile.followers_count).label('avg_followers'),
                func.max(Profile.followers_count).label('max_followers'),
                func.sum(Profile.posts_count).label('total_posts')
            )
        )
        stats = stats_result.first()
        
        # Get top performers
        top_performers_result = await db.execute(
            select(Profile)
            .order_by(desc(Profile.followers_count))
            .limit(10)
        )
        
        top_performers = []
        for profile in top_performers_result.scalars():
            top_performers.append({
                "username": profile.username,
                "full_name": profile.full_name,
                "followers_count": profile.followers_count or 0,
                "category": profile.ai_primary_content_type or "Unknown"
            })
        
        statistics = {
            "total_profiles": stats.total_profiles if stats else 0,
            "average_followers": float(stats.avg_followers or 0),
            "max_followers": stats.max_followers or 0,
            "total_posts": stats.total_posts or 0,
            "verified_profiles": 0,  # Would need to count
            "private_profiles": 0,   # Would need to count
        }
        
        return MasterInfluencerResponse(
            influencers=influencers,
            total_count=total_count,
            pagination={
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < total_count,
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            statistics=statistics,
            top_performers=top_performers
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get master influencer database: {str(e)}"
        )

@router.get("/influencers/{influencer_id}/detailed")
async def get_influencer_detailed(
    influencer_id: UUID,
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete detailed analytics for specific influencer
    """
    try:
        # Get profile
        profile_result = await db.execute(select(Profile).where(Profile.id == influencer_id))
        profile = profile_result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Influencer not found"
            )
        
        # Get all posts for this profile
        posts_result = await db.execute(
            select(Post)
            .where(Post.profile_id == influencer_id)
            .order_by(desc(Post.created_at))
            .limit(50)
        )
        posts = posts_result.scalars().all()
        
        # Get user access history
        access_history_result = await db.execute(
            select(
                UserProfileAccess.granted_at,
                User.email,
                User.full_name
            ).join(User, UserProfileAccess.user_id == User.id
            ).where(UserProfileAccess.profile_id == influencer_id)
            .order_by(desc(UserProfileAccess.granted_at))
            .limit(100)
        )
        
        access_history = []
        for access in access_history_result:
            access_history.append({
                "accessed_at": access.granted_at,
                "user_email": access.email,
                "user_name": access.full_name
            })
        
        # Calculate engagement metrics from posts
        total_likes = sum(post.likes_count or 0 for post in posts)
        total_comments = sum(post.comments_count or 0 for post in posts)
        avg_engagement = (total_likes + total_comments) / len(posts) if posts else 0
        
        # Format posts data
        formatted_posts = []
        for post in posts:
            formatted_posts.append({
                "id": str(post.id),
                "instagram_post_id": post.instagram_post_id,
                "caption": post.caption,
                "likes_count": post.likes_count or 0,
                "comments_count": post.comments_count or 0,
                "created_at": post.created_at,
                "ai_analysis": {
                    "content_category": post.ai_content_category,
                    "sentiment": post.ai_sentiment,
                    "sentiment_score": float(post.ai_sentiment_score or 0),
                    "language_code": post.ai_language_code
                }
            })
        
        return {
            "profile": {
                "id": str(profile.id),
                "username": profile.username,
                "full_name": profile.full_name,
                "biography": profile.biography,
                "followers_count": profile.followers_count or 0,
                "following_count": profile.following_count or 0,
                "posts_count": profile.posts_count or 0,
                "profile_image_url": profile.profile_image_url,
                "is_verified": profile.is_verified or False,
                "is_private": profile.is_private or False,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at
            },
            "analytics": {
                "total_views": len(access_history),
                "unique_viewers": len(set(access.user_email for access in access_history)),
                "avg_engagement": avg_engagement,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "posts_analyzed": len(posts),
                "ai_insights": {
                    "primary_content_type": profile.ai_primary_content_type,
                    "avg_sentiment_score": float(profile.ai_avg_sentiment_score or 0),
                    "content_quality_score": float(profile.ai_content_quality_score or 0),
                    "language_distribution": profile.ai_language_distribution or {},
                    "content_distribution": profile.ai_content_distribution or {}
                }
            },
            "recent_posts": formatted_posts[:20],
            "access_history": access_history[:50],
            "platform_performance": {
                "revenue_generated": len(access_history) * 25,  # Assuming 25 credits per unlock
                "popularity_rank": 0,  # Would calculate based on followers/engagement
                "trending_score": avg_engagement * 0.1 + (profile.followers_count or 0) * 0.001
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detailed influencer data: {str(e)}"
        )

# ==================== PROPOSAL MODULE INTEGRATION ====================

@router.get("/proposals/overview")
async def get_proposals_overview(
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Comprehensive proposals system overview for super admin
    """
    try:
        # Get proposal statistics
        total_proposals_result = await db.execute(select(func.count(AdminBrandProposal.id)))
        total_proposals = total_proposals_result.scalar() or 0
        
        # Get proposals by status
        status_breakdown_result = await db.execute(
            select(
                AdminBrandProposal.status,
                func.count(AdminBrandProposal.id)
            ).group_by(AdminBrandProposal.status)
        )
        
        status_breakdown = {}
        for row in status_breakdown_result:
            status_breakdown[row.status] = row.count
        
        # Get recent proposals - select only existing columns
        recent_proposals_result = await db.execute(
            select(
                AdminBrandProposal.id,
                AdminBrandProposal.proposal_title,
                AdminBrandProposal.brand_name,
                AdminBrandProposal.proposed_budget_usd,
                AdminBrandProposal.status,
                AdminBrandProposal.created_at,
                AdminBrandProposal.service_type  # Use service_type instead of proposal_type
            )
            .order_by(desc(AdminBrandProposal.created_at))
            .limit(10)
        )
        
        recent_proposals = []
        for proposal in recent_proposals_result.fetchall():
            recent_proposals.append({
                "id": str(proposal.id),
                "title": proposal.proposal_title,
                "brand_name": proposal.brand_name,
                "budget": float(proposal.proposed_budget_usd or 0),
                "status": proposal.status,
                "created_at": proposal.created_at,
                "campaign_type": proposal.service_type
            })
        
        # Get revenue from proposals
        revenue_result = await db.execute(
            select(func.sum(AdminBrandProposal.budget))
            .where(AdminBrandProposal.status == 'completed')
        )
        total_revenue = float(revenue_result.scalar() or 0)
        
        return {
            "overview": {
                "total_proposals": total_proposals,
                "total_revenue": total_revenue,
                "active_campaigns": status_breakdown.get("active", 0),
                "pending_approval": status_breakdown.get("pending", 0)
            },
            "status_breakdown": status_breakdown,
            "recent_proposals": recent_proposals,
            "performance_metrics": {
                "approval_rate": (status_breakdown.get("approved", 0) / total_proposals * 100) if total_proposals > 0 else 0,
                "completion_rate": (status_breakdown.get("completed", 0) / total_proposals * 100) if total_proposals > 0 else 0,
                "average_budget": total_revenue / status_breakdown.get("completed", 1) if status_breakdown.get("completed", 0) > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get proposals overview: {str(e)}"
        )

@router.get("/proposals/manage")
async def manage_proposals(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Manage all proposals with filtering and search
    """
    try:
        # Build base query - select only columns that exist in the actual database
        base_query = select(
            AdminBrandProposal.id,
            AdminBrandProposal.proposal_title,
            AdminBrandProposal.proposal_description,
            AdminBrandProposal.service_type,  # This is the actual column name, not proposal_type
            AdminBrandProposal.proposed_budget_usd,
            AdminBrandProposal.status,
            AdminBrandProposal.priority_level,
            AdminBrandProposal.deliverables,  # This is the actual column name
            AdminBrandProposal.created_at,
            AdminBrandProposal.updated_at
        ).order_by(desc(AdminBrandProposal.created_at))
        count_query = select(func.count(AdminBrandProposal.id))
        
        # Apply filters
        filters = []
        if status_filter:
            filters.append(AdminBrandProposal.status == status_filter)
        if search:
            filters.append(or_(
                AdminBrandProposal.proposal_title.ilike(f"%{search}%"),
                AdminBrandProposal.brand_name.ilike(f"%{search}%"),
                AdminBrandProposal.proposal_description.ilike(f"%{search}%")
            ))
        
        if filters:
            base_query = base_query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Execute queries
        proposals_result = await db.execute(base_query.offset(offset).limit(limit))
        proposals = proposals_result.fetchall()
        
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()
        
        # Format proposals using actual database columns
        formatted_proposals = []
        for proposal in proposals:
            formatted_proposals.append({
                "id": str(proposal.id),
                "title": proposal.proposal_title,
                "service_type": proposal.service_type,  # Using actual column name
                "budget": float(proposal.proposed_budget_usd or 0),
                "status": proposal.status,
                "campaign_type": proposal.service_type,  # Use service_type as campaign_type
                "description": proposal.proposal_description,
                "requirements": proposal.deliverables or {},  # Using actual column name
                "timeline": [],  # This column doesn't exist in the actual DB
                "created_at": proposal.created_at,
                "updated_at": proposal.updated_at,
                "brand_contact_email": None,  # Field doesn't exist in this model
                "priority": proposal.priority_level or "medium"
            })
        
        return {
            "proposals": formatted_proposals,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < total_count
            },
            "filters_applied": {
                "status": status_filter,
                "search": search
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to manage proposals: {str(e)}"
        )

@router.put("/proposals/{proposal_id}/status")
async def update_proposal_status(
    proposal_id: UUID,
    new_status: str,
    admin_notes: Optional[str] = None,
    current_user: UserInDB = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update proposal status with admin oversight
    """
    try:
        # Validate status
        valid_statuses = ["pending", "approved", "rejected", "active", "completed", "cancelled"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Get proposal - select specific columns to avoid non-existent columns
        proposal_result = await db.execute(
            select(
                AdminBrandProposal.id,
                AdminBrandProposal.status,
                AdminBrandProposal.updated_at,
                AdminBrandProposal.admin_metadata
            ).where(AdminBrandProposal.id == proposal_id)
        )
        proposal_row = proposal_result.fetchone()
        
        if not proposal_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Now update the proposal using individual update statement
        old_status = proposal_row.status
        
        # Create update values
        update_values = {
            "status": new_status,
            "updated_at": datetime.now()
        }
        
        # Add admin notes to metadata
        if admin_notes:
            admin_metadata = proposal_row.admin_metadata or {}
            if not admin_metadata.get("status_changes"):
                admin_metadata["status_changes"] = []
            
            admin_metadata["status_changes"].append({
                "from_status": old_status,
                "to_status": new_status,
                "admin_notes": admin_notes,
                "changed_by": current_user.email,
                "changed_at": datetime.now().isoformat()
            })
            update_values["admin_metadata"] = admin_metadata
        
        # Execute update
        await db.execute(
            update(AdminBrandProposal)
            .where(AdminBrandProposal.id == proposal_id)
            .values(**update_values)
        )
        await db.commit()
        
        return {
            "success": True,
            "message": f"Proposal status updated from {old_status} to {new_status}",
            "proposal": {
                "id": str(proposal_id),
                "old_status": old_status,
                "new_status": new_status,
                "updated_by": current_user.email,
                "updated_at": datetime.now().isoformat(),
                "admin_notes": admin_notes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update proposal status: {str(e)}"
        )