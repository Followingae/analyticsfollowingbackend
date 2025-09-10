"""
Admin Financial Management API Routes
Comprehensive financial oversight for super admins and admins
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
import csv
import io
from pydantic import BaseModel, Field

from app.middleware.role_based_auth import (
    get_current_user_with_permissions,
    requires_permission,
    auth_service,
    audit_action
)
from app.database.connection import get_db
from app.database.unified_models import (
    Users, CreditWallet, CreditTransactions, CreditAdjustments,
    SubscriptionHistory, RevenueAttribution, PlatformMetrics
)

router = APIRouter(prefix="/admin/financial", tags=["Admin - Financial Management"])

# Pydantic Models
class CreditAdjustmentRequest(BaseModel):
    user_id: UUID
    adjustment_type: str = Field(..., pattern="^(grant|deduct|refund|bonus|correction)$")
    amount: int = Field(..., gt=0, description="Amount in credits")
    reason: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[UUID] = None

class BulkCreditAdjustmentRequest(BaseModel):
    user_ids: List[UUID]
    adjustment_type: str = Field(..., pattern="^(grant|deduct|refund|bonus|correction)$")
    amount: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)

class SubscriptionChangeRequest(BaseModel):
    user_id: UUID
    new_tier: str = Field(..., pattern="^(brand_free|brand_standard|brand_premium|brand_enterprise)$")
    effective_date: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reason: str = Field(..., min_length=1, max_length=500)

class FinancialOverviewResponse(BaseModel):
    total_users: int
    active_subscriptions: int
    total_credits_sold: int
    total_revenue_usd: float
    monthly_recurring_revenue: float
    average_revenue_per_user: float
    top_spending_users: List[Dict[str, Any]]
    revenue_by_tier: Dict[str, float]
    credit_usage_stats: Dict[str, Any]

class CreditWalletResponse(BaseModel):
    id: int
    user_id: str
    user_email: str
    balance: int
    total_purchased: int
    total_spent: int
    billing_cycle_start: Optional[datetime]
    billing_cycle_end: Optional[datetime]
    subscription_active: bool
    is_locked: bool
    created_at: datetime

class TransactionResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    transaction_type: str
    amount: int
    description: str
    created_at: datetime
    success: bool

class RevenueMetricsResponse(BaseModel):
    period: str
    total_revenue: float
    subscription_revenue: float
    credit_revenue: float
    user_count: int
    average_transaction_size: float

@router.get("/overview", response_model=FinancialOverviewResponse)
@requires_permission("can_view_revenue_reports")
@audit_action("view_financial_overview")
async def get_financial_overview(
    period_days: int = Query(30, ge=1, le=365, description="Period in days for calculations"),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive financial overview"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Total users count
    total_users_query = select(func.count(Users.id))
    total_users_result = await db.execute(total_users_query)
    total_users = total_users_result.scalar()
    
    # Active subscriptions (non-free tiers)
    active_subs_query = select(func.count(Users.id)).where(
        and_(
            Users.subscription_tier != 'brand_free',
            Users.account_status == 'active'
        )
    )
    active_subs_result = await db.execute(active_subs_query)
    active_subscriptions = active_subs_result.scalar()
    
    # Total credits sold (from credit transactions)
    credits_query = select(func.coalesce(func.sum(CreditTransactions.credits), 0)).where(
        and_(
            CreditTransactions.transaction_type.in_(['purchase', 'grant']),
            CreditTransactions.created_at >= cutoff_date
        )
    )
    credits_result = await db.execute(credits_query)
    total_credits_sold = credits_result.scalar() or 0
    
    # Total revenue
    revenue_query = select(func.coalesce(func.sum(RevenueAttribution.amount_usd), 0)).where(
        RevenueAttribution.attribution_date >= cutoff_date.date()
    )
    revenue_result = await db.execute(revenue_query)
    total_revenue = float(revenue_result.scalar() or 0)
    
    # Monthly Recurring Revenue (MRR) - estimate based on active subscriptions
    mrr_query = select(
        Users.subscription_tier,
        func.count(Users.id).label('user_count')
    ).where(
        and_(
            Users.subscription_tier != 'brand_free',
            Users.account_status == 'active'
        )
    ).group_by(Users.subscription_tier)
    
    mrr_result = await db.execute(mrr_query)
    tier_counts = mrr_result.all()
    
    # Estimated tier pricing (should be configured)
    tier_pricing = {
        'brand_standard': 29.99,
        'brand_premium': 79.99,
        'brand_enterprise': 199.99
    }
    
    mrr = sum(tier_pricing.get(tier, 0) * count for tier, count in tier_counts)
    
    # ARPU calculation
    arpu = total_revenue / total_users if total_users > 0 else 0
    
    # Top spending users
    top_users_query = select(
        Users.id,
        Users.email,
        Users.total_spent_usd
    ).where(
        Users.total_spent_usd > 0
    ).order_by(desc(Users.total_spent_usd)).limit(10)
    
    top_users_result = await db.execute(top_users_query)
    top_users = [
        {
            "user_id": str(user.id),
            "email": user.email,
            "total_spent": float(user.total_spent_usd)
        }
        for user in top_users_result.all()
    ]
    
    # Revenue by tier
    revenue_by_tier_query = select(
        Users.subscription_tier,
        func.coalesce(func.sum(Users.total_spent_usd), 0).label('tier_revenue')
    ).group_by(Users.subscription_tier)
    
    revenue_by_tier_result = await db.execute(revenue_by_tier_query)
    revenue_by_tier = {
        tier: float(revenue)
        for tier, revenue in revenue_by_tier_result.all()
    }
    
    # Credit usage statistics
    credit_stats_query = select(
        func.sum(CreditWallet.current_balance).label('total_balance'),
        func.sum(CreditWallet.total_purchased_this_cycle).label('total_purchased'),
        func.sum(CreditWallet.lifetime_spent).label('total_spent'),
        func.count(CreditWallet.id).label('wallet_count')
    )
    
    credit_stats_result = await db.execute(credit_stats_query)
    credit_stats = credit_stats_result.first()
    
    credit_usage_stats = {
        "total_balance": credit_stats.total_balance or 0,
        "total_purchased": credit_stats.total_purchased or 0,
        "total_spent": credit_stats.total_spent or 0,
        "active_wallets": credit_stats.wallet_count or 0,
        "utilization_rate": (
            (credit_stats.total_spent / credit_stats.total_purchased * 100)
            if credit_stats.total_purchased and credit_stats.total_purchased > 0 else 0
        )
    }
    
    return FinancialOverviewResponse(
        total_users=total_users,
        active_subscriptions=active_subscriptions,
        total_credits_sold=total_credits_sold,
        total_revenue_usd=total_revenue,
        monthly_recurring_revenue=mrr,
        average_revenue_per_user=arpu,
        top_spending_users=top_users,
        revenue_by_tier=revenue_by_tier,
        credit_usage_stats=credit_usage_stats
    )

@router.get("/wallets", response_model=List[CreditWalletResponse])
@requires_permission("can_view_all_transactions")
@audit_action("view_all_credit_wallets")
async def get_all_credit_wallets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    min_balance: Optional[int] = Query(None, description="Minimum credit balance"),
    max_balance: Optional[int] = Query(None, description="Maximum credit balance"),
    subscription_tier: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get all credit wallets with filtering"""
    
    # Build query with join to Users
    query = select(CreditWallet, Users.email).join(
        Users, CreditWallet.user_id == Users.id
    )
    
    # Apply filters
    conditions = []
    
    if user_email:
        conditions.append(Users.email.icontains(user_email))
    
    if min_balance is not None:
        conditions.append(CreditWallet.current_balance >= min_balance)
    
    if max_balance is not None:
        conditions.append(CreditWallet.current_balance <= max_balance)
    
    if subscription_tier:
        conditions.append(Users.subscription_tier == subscription_tier)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(desc(CreditWallet.created_at)).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    wallets_data = result.all()
    
    # Format response
    wallets = []
    for wallet, user_email in wallets_data:
        wallets.append(CreditWalletResponse(
            id=wallet.id,
            user_id=str(wallet.user_id),
            user_email=user_email,
            balance=wallet.balance,
            total_purchased=wallet.total_purchased_this_cycle,
            total_spent=wallet.total_spent_this_cycle,
            billing_cycle_start=wallet.billing_cycle_start,
            billing_cycle_end=wallet.billing_cycle_end,
            subscription_active=wallet.subscription_active,
            is_locked=wallet.is_locked,
            created_at=wallet.created_at
        ))
    
    return wallets

@router.post("/credits/adjust")
@requires_permission("can_adjust_credits")
@audit_action("adjust_user_credits")
async def adjust_user_credits(
    adjustment: CreditAdjustmentRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Manually adjust user credits"""
    
    # Verify user exists
    user_query = select(Users).where(Users.id == adjustment.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user's credit wallet
    wallet_query = select(CreditWallet).where(CreditWallet.user_id == adjustment.user_id)
    wallet_result = await db.execute(wallet_query)
    wallet = wallet_result.scalar()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit wallet not found for user"
        )
    
    try:
        # Calculate new balance
        old_balance = wallet.balance
        
        if adjustment.adjustment_type in ['grant', 'bonus', 'refund']:
            new_balance = old_balance + adjustment.amount
        elif adjustment.adjustment_type in ['deduct', 'correction']:
            new_balance = max(0, old_balance - adjustment.amount)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid adjustment type"
            )
        
        # Update wallet balance
        wallet.balance = new_balance
        
        # Create credit adjustment record
        credit_adjustment = CreditAdjustments(
            user_id=adjustment.user_id,
            wallet_id=wallet.id,
            adjustment_type=adjustment.adjustment_type,
            amount=adjustment.amount,
            reason=adjustment.reason,
            adjusted_by=UUID(current_user["id"]),
            reference_id=adjustment.reference_id
        )
        
        db.add(credit_adjustment)
        await db.commit()
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="credit_adjustment",
            target_user_id=adjustment.user_id,
            old_values={"balance": old_balance},
            new_values={"balance": new_balance, "adjustment_amount": adjustment.amount},
            reason=adjustment.reason,
            severity="info" if adjustment.adjustment_type in ['grant', 'bonus'] else "warning",
            db=db
        )
        
        return {
            "message": "Credit adjustment completed successfully",
            "old_balance": old_balance,
            "new_balance": new_balance,
            "adjustment_amount": adjustment.amount,
            "adjustment_type": adjustment.adjustment_type
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust credits: {str(e)}"
        )

@router.post("/credits/bulk-adjust")
@requires_permission("can_adjust_credits")
@audit_action("bulk_adjust_credits")
async def bulk_adjust_credits(
    bulk_adjustment: BulkCreditAdjustmentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Bulk credit adjustment for multiple users"""
    
    if len(bulk_adjustment.user_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot adjust credits for more than 100 users at once"
        )
    
    try:
        # Get all wallets for the users
        wallets_query = select(CreditWallet, Users.email).join(
            Users, CreditWallet.user_id == Users.id
        ).where(CreditWallet.user_id.in_(bulk_adjustment.user_ids))
        
        wallets_result = await db.execute(wallets_query)
        wallets_data = wallets_result.all()
        
        if len(wallets_data) != len(bulk_adjustment.user_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Some users or wallets not found"
            )
        
        # Process each adjustment
        adjustments_made = []
        
        for wallet, user_email in wallets_data:
            old_balance = wallet.balance
            
            if bulk_adjustment.adjustment_type in ['grant', 'bonus', 'refund']:
                new_balance = old_balance + bulk_adjustment.amount
            else:
                new_balance = max(0, old_balance - bulk_adjustment.amount)
            
            wallet.balance = new_balance
            
            # Create adjustment record
            credit_adjustment = CreditAdjustments(
                user_id=wallet.user_id,
                wallet_id=wallet.id,
                adjustment_type=bulk_adjustment.adjustment_type,
                amount=bulk_adjustment.amount,
                reason=bulk_adjustment.reason,
                adjusted_by=UUID(current_user["id"])
            )
            
            db.add(credit_adjustment)
            
            # Log individual admin action
            await auth_service.log_admin_action(
                admin_user_id=UUID(current_user["id"]),
                action_type="bulk_credit_adjustment",
                target_user_id=wallet.user_id,
                old_values={"balance": old_balance},
                new_values={"balance": new_balance},
                reason=f"Bulk adjustment: {bulk_adjustment.reason}",
                db=db
            )
            
            adjustments_made.append({
                "user_id": str(wallet.user_id),
                "user_email": user_email,
                "old_balance": old_balance,
                "new_balance": new_balance
            })
        
        await db.commit()
        
        return {
            "message": f"Successfully adjusted credits for {len(adjustments_made)} users",
            "adjustment_type": bulk_adjustment.adjustment_type,
            "amount": bulk_adjustment.amount,
            "adjustments": adjustments_made
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk adjust credits: {str(e)}"
        )

@router.post("/subscriptions/change")
@requires_permission("can_manage_subscriptions")
@audit_action("change_user_subscription")
async def change_user_subscription(
    subscription_change: SubscriptionChangeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Change user subscription tier"""
    
    # Get user
    user_query = select(Users).where(Users.id == subscription_change.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    old_tier = user.subscription_tier
    
    try:
        # Update user subscription
        user.subscription_tier = subscription_change.new_tier
        
        if subscription_change.effective_date:
            user.created_at = subscription_change.effective_date
        
        if subscription_change.expires_at:
            user.subscription_expires_at = subscription_change.expires_at
        
        # Create subscription history record
        sub_history = SubscriptionHistory(
            user_id=subscription_change.user_id,
            old_tier=old_tier,
            new_tier=subscription_change.new_tier,
            changed_by=UUID(current_user["id"]),
            change_reason=subscription_change.reason,
            effective_date=subscription_change.effective_date or datetime.utcnow(),
            expires_at=subscription_change.expires_at
        )
        
        db.add(sub_history)
        await db.commit()
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="subscription_change",
            target_user_id=subscription_change.user_id,
            old_values={"subscription_tier": old_tier},
            new_values={"subscription_tier": subscription_change.new_tier},
            reason=subscription_change.reason,
            db=db
        )
        
        # Invalidate user cache
        await auth_service.invalidate_user_cache(subscription_change.user_id)
        
        return {
            "message": "Subscription changed successfully",
            "user_id": str(subscription_change.user_id),
            "old_tier": old_tier,
            "new_tier": subscription_change.new_tier,
            "effective_date": subscription_change.effective_date,
            "expires_at": subscription_change.expires_at
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change subscription: {str(e)}"
        )

@router.get("/transactions", response_model=List[TransactionResponse])
@requires_permission("can_view_all_transactions")
@audit_action("view_all_transactions")
async def get_all_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    transaction_type: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get all credit transactions with filtering"""
    
    # Build query
    query = select(CreditTransactions, Users.email).join(
        Users, CreditTransactions.user_id == Users.id
    )
    
    # Apply filters
    conditions = []
    
    if transaction_type:
        conditions.append(CreditTransactions.transaction_type == transaction_type)
    
    if user_email:
        conditions.append(Users.email.icontains(user_email))
    
    if date_from:
        conditions.append(CreditTransactions.created_at >= date_from)
    
    if date_to:
        conditions.append(CreditTransactions.created_at <= date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(desc(CreditTransactions.created_at)).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    transactions_data = result.all()
    
    # Format response
    transactions = []
    for transaction, user_email in transactions_data:
        transactions.append(TransactionResponse(
            id=str(transaction.id),
            user_id=str(transaction.user_id),
            user_email=user_email,
            transaction_type=transaction.transaction_type,
            amount=abs(transaction.credits),  # Show as positive
            description=transaction.description,
            created_at=transaction.created_at,
            success=True  # Assuming stored transactions are successful
        ))
    
    return transactions

@router.get("/revenue/metrics", response_model=List[RevenueMetricsResponse])
@requires_permission("can_view_revenue_reports")
@audit_action("view_revenue_metrics")
async def get_revenue_metrics(
    period: str = Query("monthly", pattern="^(daily|weekly|monthly|yearly)$"),
    months_back: int = Query(12, ge=1, le=24),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get revenue metrics over time"""
    
    # Calculate date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=months_back * 30)
    
    # Group by period
    if period == "daily":
        date_format = "YYYY-MM-DD"
        interval = "1 day"
    elif period == "weekly":
        date_format = "YYYY-WW"
        interval = "1 week"
    elif period == "monthly":
        date_format = "YYYY-MM"
        interval = "1 month"
    else:  # yearly
        date_format = "YYYY"
        interval = "1 year"
    
    # Revenue metrics query
    revenue_query = text(f"""
        SELECT 
            to_char(attribution_date, :date_format) as period,
            SUM(amount_usd) as total_revenue,
            SUM(CASE WHEN revenue_source = 'subscription' THEN amount_usd ELSE 0 END) as subscription_revenue,
            SUM(CASE WHEN revenue_source = 'credits' THEN amount_usd ELSE 0 END) as credit_revenue,
            COUNT(DISTINCT user_id) as user_count,
            AVG(amount_usd) as avg_transaction_size
        FROM revenue_attribution 
        WHERE attribution_date >= :start_date AND attribution_date <= :end_date
        GROUP BY to_char(attribution_date, :date_format)
        ORDER BY period
    """)
    
    result = await db.execute(revenue_query, {
        "date_format": date_format,
        "start_date": start_date,
        "end_date": end_date
    })
    
    metrics = []
    for row in result.all():
        metrics.append(RevenueMetricsResponse(
            period=row.period,
            total_revenue=float(row.total_revenue or 0),
            subscription_revenue=float(row.subscription_revenue or 0),
            credit_revenue=float(row.credit_revenue or 0),
            user_count=int(row.user_count or 0),
            average_transaction_size=float(row.avg_transaction_size or 0)
        ))
    
    return metrics

@router.get("/export/financial-report")
@requires_permission("can_export_platform_data")
@audit_action("export_financial_report")
async def export_financial_report(
    report_type: str = Query("revenue", pattern="^(revenue|transactions|subscriptions|credits)$"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Export comprehensive financial report"""
    
    # Set default date range if not provided
    if not date_to:
        date_to = datetime.utcnow().date()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    
    # Create CSV content based on report type
    output = io.StringIO()
    writer = csv.writer(output)
    
    if report_type == "revenue":
        # Revenue report
        writer.writerow(['Date', 'User Email', 'Revenue Source', 'Amount USD', 'Payment Method'])
        
        revenue_query = select(
            RevenueAttribution.attribution_date,
            Users.email,
            RevenueAttribution.revenue_source,
            RevenueAttribution.amount_usd,
            RevenueAttribution.payment_method
        ).join(
            Users, RevenueAttribution.user_id == Users.id
        ).where(
            and_(
                RevenueAttribution.attribution_date >= date_from,
                RevenueAttribution.attribution_date <= date_to
            )
        ).order_by(desc(RevenueAttribution.attribution_date))
        
        result = await db.execute(revenue_query)
        for row in result.all():
            writer.writerow([
                row.attribution_date,
                row.email,
                row.revenue_source,
                float(row.amount_usd),
                row.payment_method or ''
            ])
    
    elif report_type == "transactions":
        # Transaction report
        writer.writerow(['Date', 'User Email', 'Transaction Type', 'Credits', 'Description'])
        
        trans_query = select(
            CreditTransactions.created_at,
            Users.email,
            CreditTransactions.transaction_type,
            CreditTransactions.credits,
            CreditTransactions.description
        ).join(
            Users, CreditTransactions.user_id == Users.id
        ).where(
            and_(
                CreditTransactions.created_at >= datetime.combine(date_from, datetime.min.time()),
                CreditTransactions.created_at <= datetime.combine(date_to, datetime.max.time())
            )
        ).order_by(desc(CreditTransactions.created_at))
        
        result = await db.execute(trans_query)
        for row in result.all():
            writer.writerow([
                row.created_at,
                row.email,
                row.transaction_type,
                row.credits,
                row.description
            ])
    
    # Create streaming response
    output.seek(0)
    
    def iter_csv():
        yield output.getvalue()
    
    filename = f"{report_type}_report_{date_from}_{date_to}.csv"
    
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )