"""
Credit Transaction Service - Transaction history and analytics
Provides comprehensive transaction tracking, reporting, and analytics
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload

from app.database.connection import get_session
from app.database.unified_models import (
    CreditTransaction, CreditWallet, CreditUsageTracking,
    CreditPricingRule, UnlockedInfluencer
)
from app.models.credits import (
    CreditTransactionSummary, CreditTransaction as CreditTransactionModel,
    MonthlyUsageSummary
)
from app.cache.redis_cache_manager import cache_manager

logger = logging.getLogger(__name__)


class CreditTransactionService:
    """
    Comprehensive credit transaction service
    Handles transaction history, analytics, and usage tracking
    """
    
    def __init__(self):
        self.cache_prefix = "credit_transactions"
        self.history_cache_ttl = 600  # 10 minutes
        self.analytics_cache_ttl = 3600  # 1 hour
    
    # =========================================================================
    # TRANSACTION HISTORY
    # =========================================================================
    
    async def get_transaction_history(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        transaction_types: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[CreditTransactionSummary]:
        """
        Get paginated transaction history for a user
        
        Args:
            user_id: User UUID
            limit: Number of transactions to return
            offset: Number of transactions to skip
            transaction_types: Filter by transaction types
            start_date: Filter transactions from this date
            end_date: Filter transactions to this date
            
        Returns:
            List of transaction summaries
        """
        cache_key = f"{self.cache_prefix}:history:{user_id}:{limit}:{offset}:{hash(str(transaction_types))}"
        
        # Try cache for recent history
        if not start_date and not end_date:
            cached_data = await cache_manager.redis_client.get(cache_key)
            if cached_data:
                import json
                cached_history = json.loads(cached_data)
                return [CreditTransactionSummary(**item) for item in cached_history]
        
        try:
            async with get_session() as session:
                query = (
                    select(CreditTransaction)
                    .where(CreditTransaction.user_id == user_id)
                    .order_by(desc(CreditTransaction.created_at))
                    .limit(limit)
                    .offset(offset)
                )
                
                # Apply filters
                if transaction_types:
                    query = query.where(CreditTransaction.transaction_type.in_(transaction_types))
                
                if start_date:
                    query = query.where(CreditTransaction.created_at >= start_date)
                
                if end_date:
                    query = query.where(CreditTransaction.created_at <= end_date)
                
                result = await session.execute(query)
                transactions = result.scalars().all()
                
                # Convert to summary format
                summaries = [
                    CreditTransactionSummary(
                        id=t.id,
                        transaction_type=t.transaction_type,
                        action_type=t.action_type,
                        amount=t.amount,
                        description=t.description,
                        balance_after=t.balance_after,
                        created_at=t.created_at
                    )
                    for t in transactions
                ]
                
                # Cache recent history
                if not start_date and not end_date:
                    import json
                    cache_data = [summary.dict() for summary in summaries]
                    await cache_manager.redis_client.setex(
                        cache_key, 
                        self.history_cache_ttl, 
                        json.dumps(cache_data, default=str)
                    )
                
                return summaries
                
        except Exception as e:
            logger.error(f"Error getting transaction history for user {user_id}: {e}")
            return []
    
    async def get_transaction_by_id(self, transaction_id: int, user_id: UUID) -> Optional[CreditTransactionModel]:
        """Get detailed transaction by ID with user validation"""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CreditTransaction)
                    .where(
                        and_(
                            CreditTransaction.id == transaction_id,
                            CreditTransaction.user_id == user_id
                        )
                    )
                )
                
                transaction = result.scalar_one_or_none()
                if not transaction:
                    return None
                
                return CreditTransactionModel(
                    id=transaction.id,
                    user_id=transaction.user_id,
                    wallet_id=transaction.wallet_id,
                    transaction_type=transaction.transaction_type,
                    action_type=transaction.action_type,
                    amount=transaction.amount,
                    balance_before=transaction.balance_before,
                    balance_after=transaction.balance_after,
                    description=transaction.description,
                    reference_id=transaction.reference_id,
                    reference_type=transaction.reference_type,
                    billing_cycle_date=transaction.month_year,
                    metadata=transaction.transaction_metadata,
                    created_at=transaction.created_at
                )
                
        except Exception as e:
            logger.error(f"Error getting transaction {transaction_id} for user {user_id}: {e}")
            return None
    
    # =========================================================================
    # USAGE TRACKING & ANALYTICS
    # =========================================================================
    
    async def track_action_usage(
        self,
        user_id: UUID,
        action_type: str,
        used_free_allowance: bool = False,
        credits_spent: int = 0
    ) -> None:
        """
        Track usage of a credit-gated action
        Updates monthly usage tracking for analytics
        
        Args:
            user_id: User UUID
            action_type: Action that was performed
            used_free_allowance: Whether free allowance was used
            credits_spent: Number of credits spent (0 if free)
        """
        current_month = date.today().replace(day=1)
        
        try:
            async with get_session() as session:
                # Use raw SQL to insert using actual database schema
                query = text("""
                    INSERT INTO credit_usage_tracking
                    (user_id, action_type, month_year, free_actions_used, paid_actions_used, total_credits_spent)
                    VALUES (:user_id, :action_type, :month_year, :free_used, :paid_used, :credits_spent)
                    ON CONFLICT (user_id, action_type, month_year)
                    DO UPDATE SET
                        free_actions_used = credit_usage_tracking.free_actions_used + :free_used,
                        paid_actions_used = credit_usage_tracking.paid_actions_used + :paid_used,
                        total_credits_spent = credit_usage_tracking.total_credits_spent + :credits_spent,
                        last_updated = NOW()
                """)

                await session.execute(query, {
                    "user_id": str(user_id),
                    "action_type": action_type,
                    "month_year": current_month,
                    "free_used": 1 if used_free_allowance else 0,
                    "paid_used": 0 if used_free_allowance else 1,
                    "credits_spent": credits_spent
                })
                await session.commit()
                
                # Clear analytics cache
                await self._clear_analytics_cache(user_id, current_month)
                
        except Exception as e:
            logger.error(f"Error tracking usage for user {user_id}, action {action_type}: {e}")
    
    async def get_monthly_usage_summary(
        self, 
        user_id: UUID, 
        month_year: Optional[date] = None
    ) -> MonthlyUsageSummary:
        """
        Get comprehensive monthly usage summary
        
        Args:
            user_id: User UUID
            month_year: Month to analyze (defaults to current month)
            
        Returns:
            MonthlyUsageSummary with detailed usage breakdown
        """
        if not month_year:
            month_year = date.today().replace(day=1)
        
        cache_key = f"{self.cache_prefix}:monthly:{user_id}:{month_year}"
        
        # Try cache first
        cached_data = await cache_manager.redis_client.get(cache_key)
        if cached_data:
            import json
            cached_summary = json.loads(cached_data)
            return MonthlyUsageSummary(**cached_summary)
        
        try:
            async with get_session() as session:
                # Use raw SQL to query the actual database schema
                query = text("""
                    SELECT action_type,
                           SUM(free_actions_used) as free_used,
                           SUM(paid_actions_used) as paid_used,
                           SUM(total_credits_spent) as credits_spent
                    FROM credit_usage_tracking
                    WHERE user_id = :user_id
                      AND month_year = :month_year
                    GROUP BY action_type
                """)

                result = await session.execute(query, {
                    "user_id": str(user_id),
                    "month_year": month_year
                })
                usage_records = result.fetchall()

            # Calculate totals and breakdown using actual database fields
            total_spent = sum(record.credits_spent for record in usage_records)
            actions_breakdown = {}

            # Process records from actual database
            for record in usage_records:
                actions_breakdown[record.action_type] = {
                    "free_used": record.free_used,
                    "paid_used": record.paid_used,
                    "credits_spent": record.credits_spent
                }

            # Get top actions by credits spent (after processing all records)
            top_actions = sorted(
                [
                    {
                        "action_type": action_type,
                        "credits_spent": data["credits_spent"],
                        "total_actions": data["free_used"] + data["paid_used"]
                    }
                    for action_type, data in actions_breakdown.items()
                ],
                key=lambda x: x["credits_spent"],
                reverse=True
            )[:5]  # Top 5 actions

            summary = MonthlyUsageSummary(
                month_year=month_year,
                total_spent=total_spent,
                actions_breakdown=actions_breakdown,
                top_actions=top_actions
            )

            # Cache the summary
            import json
            await cache_manager.redis_client.setex(
                cache_key,
                self.analytics_cache_ttl,
                json.dumps(summary.dict(), default=str)
            )

            return summary
                
        except Exception as e:
            logger.error(f"Error getting monthly usage for user {user_id}: {e}")
            return MonthlyUsageSummary(
                month_year=month_year,
                total_spent=0,
                actions_breakdown={},
                top_actions=[]
            )
    
    async def get_spending_analytics(
        self,
        user_id: UUID,
        months: int = 6
    ) -> Dict[str, Any]:
        """
        Get comprehensive spending analytics for multiple months
        
        Args:
            user_id: User UUID
            months: Number of months to analyze
            
        Returns:
            Dictionary with analytics data
        """
        cache_key = f"{self.cache_prefix}:analytics:{user_id}:{months}"
        
        # Try cache first
        cached_data = await cache_manager.redis_client.get(cache_key)
        if cached_data:
            import json
            cached_analytics = json.loads(cached_data)
            return cached_analytics
        
        try:
            # Generate date range
            current_date = date.today().replace(day=1)
            start_date = current_date - timedelta(days=30 * (months - 1))
            
            async with get_session() as session:
                # Get transaction aggregates by month
                transactions_result = await session.execute(
                    text("""
                        SELECT 
                            DATE_TRUNC('month', created_at)::date as month,
                            transaction_type,
                            COUNT(*) as transaction_count,
                            SUM(ABS(amount)) as total_amount
                        FROM public.credit_transactions
                        WHERE user_id = :user_id 
                          AND created_at >= :start_date
                          AND transaction_type IN ('spend', 'purchase', 'earn')
                        GROUP BY DATE_TRUNC('month', created_at), transaction_type
                        ORDER BY month DESC
                    """),
                    {
                        "user_id": str(user_id),
                        "start_date": start_date
                    }
                )
                
                transactions_data = transactions_result.fetchall()
                
                # Get usage tracking aggregates using actual database schema
                usage_query = (
                    select(
                        CreditUsageTracking.month_year.label('month_year'),
                        CreditUsageTracking.action_type.label('action_type'),
                        func.count().label('total_actions'),
                        func.sum(CreditUsageTracking.total_credits_spent).label('total_spent')
                    )
                    .where(
                        and_(
                            CreditUsageTracking.user_id == user_id,
                            CreditUsageTracking.month_year >= start_date
                        )
                    )
                    .group_by(CreditUsageTracking.month_year, CreditUsageTracking.action_type)
                    .order_by(CreditUsageTracking.month_year.desc(), func.sum(CreditUsageTracking.total_credits_spent).desc())
                )

                usage_result = await session.execute(usage_query)
                
                usage_data = usage_result.fetchall()
                
                # Process data
                monthly_spending = {}
                monthly_transactions = {}
                action_usage = {}
                
                for row in transactions_data:
                    month_key = row.month.strftime('%Y-%m')
                    if month_key not in monthly_spending:
                        monthly_spending[month_key] = {"spend": 0, "purchase": 0, "earn": 0}
                        monthly_transactions[month_key] = {"spend": 0, "purchase": 0, "earn": 0}
                    
                    monthly_spending[month_key][row.transaction_type] = row.total_amount
                    monthly_transactions[month_key][row.transaction_type] = row.transaction_count
                
                for row in usage_data:
                    month_key = row.month_year.strftime('%Y-%m')
                    if month_key not in action_usage:
                        action_usage[month_key] = {}

                    action_usage[month_key][row.action_type] = {
                        "free_actions": 0,  # Not tracked in current schema
                        "paid_actions": row.total_actions,
                        "credits_spent": row.total_spent or 0
                    }
                
                analytics = {
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": current_date.isoformat(),
                        "months": months
                    },
                    "monthly_spending": monthly_spending,
                    "monthly_transactions": monthly_transactions,
                    "action_usage": action_usage,
                    "totals": {
                        "total_spent": sum(
                            month_data.get("spend", 0) 
                            for month_data in monthly_spending.values()
                        ),
                        "total_purchased": sum(
                            month_data.get("purchase", 0) 
                            for month_data in monthly_spending.values()
                        ),
                        "total_earned": sum(
                            month_data.get("earn", 0) 
                            for month_data in monthly_spending.values()
                        )
                    }
                }
                
                # Cache analytics
                import json
                await cache_manager.redis_client.setex(
                    cache_key, 
                    self.analytics_cache_ttl, 
                    json.dumps(analytics, default=str)
                )
                
                return analytics
                
        except Exception as e:
            logger.error(f"Error getting spending analytics for user {user_id}: {e}")
            return {
                "period": {"months": months},
                "monthly_spending": {},
                "monthly_transactions": {},
                "action_usage": {},
                "totals": {"total_spent": 0, "total_purchased": 0, "total_earned": 0}
            }

    # =========================================================================
    # CREDITS IN/OUT SUMMARY
    # =========================================================================

    async def get_credits_in_out_summary(
        self,
        user_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_monthly_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive credits in vs credits out summary

        Args:
            user_id: User UUID
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            include_monthly_breakdown: Whether to include monthly breakdown for charts

        Returns:
            CreditsInOutSummary data with detailed breakdown
        """
        try:
            async with get_session() as session:
                # Base query for user transactions
                base_query = select(CreditTransaction).where(CreditTransaction.user_id == user_id)

                # Apply date filters if provided
                if start_date:
                    base_query = base_query.where(CreditTransaction.created_at >= start_date)
                if end_date:
                    # Include full end date
                    end_datetime = datetime.combine(end_date, datetime.max.time())
                    base_query = base_query.where(CreditTransaction.created_at <= end_datetime)

                # Execute query to get all transactions
                result = await session.execute(base_query.order_by(CreditTransaction.created_at))
                transactions = result.scalars().all()

                # Initialize counters
                credits_in = {
                    'earned': 0,      # Monthly allowances, rewards
                    'purchased': 0,   # Topup purchases
                    'bonus': 0,       # Promotional credits
                    'refunded': 0     # Refunded credits
                }

                credits_out = {
                    'spent': 0,       # Used for actions
                    'expired': 0      # Expired credits
                }

                monthly_data = {}

                # Process each transaction
                for transaction in transactions:
                    amount = abs(transaction.amount)
                    month_key = transaction.created_at.strftime('%Y-%m')

                    # Initialize monthly data if needed
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {
                            'month': month_key,
                            'credits_in': 0,
                            'credits_out': 0,
                            'net': 0
                        }

                    # Categorize transaction based on type
                    if transaction.transaction_type == 'earned':
                        credits_in['earned'] += amount
                        monthly_data[month_key]['credits_in'] += amount

                    elif transaction.transaction_type == 'spent':
                        credits_out['spent'] += amount
                        monthly_data[month_key]['credits_out'] += amount

                    elif transaction.transaction_type == 'refunded':
                        credits_in['refunded'] += amount
                        monthly_data[month_key]['credits_in'] += amount

                    elif transaction.transaction_type == 'expired':
                        credits_out['expired'] += amount
                        monthly_data[month_key]['credits_out'] += amount

                    elif transaction.transaction_type == 'bonus':
                        credits_in['bonus'] += amount
                        monthly_data[month_key]['credits_in'] += amount

                # Calculate monthly net
                for month_data in monthly_data.values():
                    month_data['net'] = month_data['credits_in'] - month_data['credits_out']

                # Calculate totals
                total_credits_in = sum(credits_in.values())
                total_credits_out = sum(credits_out.values())
                net_credits = total_credits_in - total_credits_out

                # Get current balance from wallet
                from app.services.credit_wallet_service import credit_wallet_service
                balance_info = await credit_wallet_service.get_wallet_balance(user_id)
                current_balance = balance_info.balance if balance_info else 0

                # Prepare monthly breakdown for charts
                monthly_breakdown = []
                if include_monthly_breakdown:
                    monthly_breakdown = sorted(monthly_data.values(), key=lambda x: x['month'])

                return {
                    # Credits In (positive transactions)
                    "total_credits_in": total_credits_in,
                    "credits_earned": credits_in['earned'],
                    "credits_purchased": credits_in['purchased'],
                    "credits_bonus": credits_in['bonus'],
                    "credits_refunded": credits_in['refunded'],

                    # Credits Out (negative transactions)
                    "total_credits_out": total_credits_out,
                    "credits_spent": credits_out['spent'],
                    "credits_expired": credits_out['expired'],

                    # Summary
                    "net_credits": net_credits,
                    "current_balance": current_balance,

                    # Time period
                    "period_start": start_date,
                    "period_end": end_date,

                    # Breakdown by month
                    "monthly_breakdown": monthly_breakdown
                }

        except Exception as e:
            logger.error(f"Failed to get credits in/out summary for user {user_id}: {str(e)}")
            # Return empty summary on error
            return {
                "total_credits_in": 0,
                "credits_earned": 0,
                "credits_purchased": 0,
                "credits_bonus": 0,
                "credits_refunded": 0,
                "total_credits_out": 0,
                "credits_spent": 0,
                "credits_expired": 0,
                "net_credits": 0,
                "current_balance": 0,
                "period_start": start_date,
                "period_end": end_date,
                "monthly_breakdown": []
            }

    # =========================================================================
    # TRANSACTION SEARCH & FILTERING
    # =========================================================================
    
    async def search_transactions(
        self,
        user_id: UUID,
        search_term: Optional[str] = None,
        action_types: Optional[List[str]] = None,
        transaction_types: Optional[List[str]] = None,
        amount_range: Optional[Tuple[int, int]] = None,
        date_range: Optional[Tuple[date, date]] = None,
        limit: int = 50
    ) -> List[CreditTransactionSummary]:
        """
        Advanced transaction search with multiple filters
        
        Args:
            user_id: User UUID
            search_term: Search in description and reference fields
            action_types: Filter by action types
            transaction_types: Filter by transaction types
            amount_range: Filter by amount range (min, max)
            date_range: Filter by date range (start, end)
            limit: Maximum results to return
            
        Returns:
            List of matching transaction summaries
        """
        try:
            async with get_session() as session:
                query = (
                    select(CreditTransaction)
                    .where(CreditTransaction.user_id == user_id)
                    .order_by(desc(CreditTransaction.created_at))
                    .limit(limit)
                )
                
                # Apply filters
                if search_term:
                    search_filter = or_(
                        CreditTransaction.description.ilike(f"%{search_term}%"),
                        CreditTransaction.reference_id.ilike(f"%{search_term}%")
                    )
                    query = query.where(search_filter)
                
                if action_types:
                    query = query.where(CreditTransaction.action_type.in_(action_types))
                
                if transaction_types:
                    query = query.where(CreditTransaction.transaction_type.in_(transaction_types))
                
                if amount_range:
                    min_amount, max_amount = amount_range
                    query = query.where(
                        and_(
                            CreditTransaction.amount >= min_amount,
                            CreditTransaction.amount <= max_amount
                        )
                    )
                
                if date_range:
                    start_date, end_date = date_range
                    query = query.where(
                        and_(
                            CreditTransaction.created_at >= start_date,
                            CreditTransaction.created_at <= end_date
                        )
                    )
                
                result = await session.execute(query)
                transactions = result.scalars().all()
                
                return [
                    CreditTransactionSummary(
                        id=t.id,
                        transaction_type=t.transaction_type,
                        action_type=t.action_type,
                        amount=t.amount,
                        description=t.description,
                        balance_after=t.balance_after,
                        created_at=t.created_at
                    )
                    for t in transactions
                ]
                
        except Exception as e:
            logger.error(f"Error searching transactions for user {user_id}: {e}")
            return []
    
    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================
    
    async def _clear_analytics_cache(self, user_id: UUID, month_year: date) -> None:
        """Clear analytics cache for user and month"""
        cache_keys = [
            f"{self.cache_prefix}:monthly:{user_id}:{month_year}",
            f"{self.cache_prefix}:analytics:{user_id}:*"  # Clear all analytics caches
        ]
        
        # Use direct Redis client to delete cache keys
        try:
            if cache_manager.initialized:
                for key in cache_keys:
                    if "*" in key:
                        # Clear pattern-based keys
                        await cache_manager.delete_pattern(key)
                    else:
                        await cache_manager.redis_client.delete(key)
        except Exception as e:
            logger.debug(f"Failed to clear analytics cache for user {user_id}: {e}")
    
    async def clear_user_cache(self, user_id: UUID) -> None:
        """Clear all transaction cache for a user"""
        await cache_manager.delete_pattern(f"{self.cache_prefix}:*:{user_id}:*")


# Global service instance
credit_transaction_service = CreditTransactionService()