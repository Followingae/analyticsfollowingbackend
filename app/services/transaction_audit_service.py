"""
TRANSACTION AUDIT & MONITORING SERVICE
Enterprise-grade audit trail and consistency monitoring for SaaS platform
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class InconsistencyReport:
    """Report of transaction inconsistencies found"""
    user_id: str
    issue_type: str
    description: str
    expected_balance: int
    actual_balance: int
    missing_transactions: List[Dict[str, Any]]
    orphaned_access_records: List[str]
    severity: str  # "critical", "high", "medium", "low"
    detected_at: datetime

@dataclass
class SystemHealthReport:
    """Overall system health report"""
    total_users: int
    users_with_inconsistencies: int
    total_transactions_today: int
    total_credits_spent_today: int
    success_rate: float
    average_transaction_time: float
    critical_issues: List[InconsistencyReport]
    last_audit_time: datetime

class TransactionAuditService:
    """
    Comprehensive audit and monitoring service for transaction consistency

    Features:
    1. Real-time consistency checking
    2. Daily audit reports
    3. Automated inconsistency detection
    4. Performance monitoring
    5. Fraud detection alerts
    """

    def __init__(self):
        self.logger = logger

    async def perform_daily_audit(self, db: AsyncSession) -> SystemHealthReport:
        """Perform comprehensive daily audit of all transactions"""

        self.logger.info("🔍 DAILY AUDIT: Starting comprehensive transaction audit")

        try:
            # Get system metrics
            total_users = await self._count_total_users(db)
            transactions_today = await self._count_transactions_today(db)
            credits_spent_today = await self._sum_credits_spent_today(db)

            # Check for inconsistencies
            inconsistencies = await self._detect_all_inconsistencies(db)

            # Calculate health metrics
            users_with_issues = len(set(inc.user_id for inc in inconsistencies))
            critical_issues = [inc for inc in inconsistencies if inc.severity == "critical"]

            # Calculate success rate (transactions without inconsistencies)
            success_rate = ((transactions_today - len(inconsistencies)) / max(transactions_today, 1)) * 100

            report = SystemHealthReport(
                total_users=total_users,
                users_with_inconsistencies=users_with_issues,
                total_transactions_today=transactions_today,
                total_credits_spent_today=credits_spent_today,
                success_rate=success_rate,
                average_transaction_time=0.0,  # Would need timing data
                critical_issues=critical_issues,
                last_audit_time=datetime.now(timezone.utc)
            )

            # Log audit results
            self.logger.info(f"📊 DAILY AUDIT COMPLETE:")
            self.logger.info(f"   Users: {total_users} | With Issues: {users_with_issues}")
            self.logger.info(f"   Transactions Today: {transactions_today} | Credits Spent: {credits_spent_today}")
            self.logger.info(f"   Success Rate: {success_rate:.1f}% | Critical Issues: {len(critical_issues)}")

            if critical_issues:
                self.logger.error(f"🚨 CRITICAL ISSUES DETECTED: {len(critical_issues)} users need immediate attention")
                for issue in critical_issues[:5]:  # Log first 5 critical issues
                    self.logger.error(f"   User {issue.user_id}: {issue.description}")

            return report

        except Exception as e:
            self.logger.error(f"💥 DAILY AUDIT FAILED: {str(e)}")
            raise

    async def check_user_consistency(self, db: AsyncSession, user_id: str) -> Optional[InconsistencyReport]:
        """Check transaction consistency for a specific user"""

        try:
            # Get user's current wallet state
            wallet_query = text("""
                SELECT id, current_balance
                FROM credit_wallets
                WHERE user_id = :user_id
            """)
            wallet_result = await db.execute(wallet_query, {"user_id": user_id})
            wallet_row = wallet_result.fetchone()

            if not wallet_row:
                return InconsistencyReport(
                    user_id=user_id,
                    issue_type="missing_wallet",
                    description="User has no credit wallet",
                    expected_balance=0,
                    actual_balance=0,
                    missing_transactions=[],
                    orphaned_access_records=[],
                    severity="critical",
                    detected_at=datetime.now(timezone.utc)
                )

            wallet_id, current_balance = wallet_row

            # Calculate expected balance from transaction history
            transactions_query = text("""
                SELECT SUM(amount) as total_spent
                FROM credit_transactions
                WHERE user_id = :user_id
            """)
            transactions_result = await db.execute(transactions_query, {"user_id": user_id})
            total_spent = transactions_result.fetchone()[0] or 0

            # Assume starting balance (this could be tracked in user setup)
            # For now, reverse-calculate from first transaction
            first_transaction_query = text("""
                SELECT balance_before
                FROM credit_transactions
                WHERE user_id = :user_id
                ORDER BY created_at ASC
                LIMIT 1
            """)
            first_result = await db.execute(first_transaction_query, {"user_id": user_id})
            first_row = first_result.fetchone()
            starting_balance = first_row[0] if first_row else 5000  # Default assumption

            expected_balance = starting_balance + total_spent  # total_spent is negative

            # Check for discrepancy
            balance_discrepancy = abs(current_balance - expected_balance)

            if balance_discrepancy > 0:
                # Find missing transactions and orphaned records
                missing_transactions = await self._find_missing_transactions(db, user_id)
                orphaned_access = await self._find_orphaned_access_records(db, user_id)

                severity = "critical" if balance_discrepancy > 100 else "high" if balance_discrepancy > 25 else "medium"

                return InconsistencyReport(
                    user_id=user_id,
                    issue_type="balance_mismatch",
                    description=f"Wallet balance mismatch: {balance_discrepancy} credits",
                    expected_balance=expected_balance,
                    actual_balance=current_balance,
                    missing_transactions=missing_transactions,
                    orphaned_access_records=orphaned_access,
                    severity=severity,
                    detected_at=datetime.now(timezone.utc)
                )

            return None  # No inconsistency found

        except Exception as e:
            self.logger.error(f"Error checking consistency for user {user_id}: {str(e)}")
            return InconsistencyReport(
                user_id=user_id,
                issue_type="audit_error",
                description=f"Audit check failed: {str(e)}",
                expected_balance=0,
                actual_balance=0,
                missing_transactions=[],
                orphaned_access_records=[],
                severity="high",
                detected_at=datetime.now(timezone.utc)
            )

    async def _detect_all_inconsistencies(self, db: AsyncSession) -> List[InconsistencyReport]:
        """Detect inconsistencies across all users"""

        # Get all users with wallets
        users_query = text("""
            SELECT DISTINCT user_id
            FROM credit_wallets
        """)
        users_result = await db.execute(users_query)
        user_ids = [row[0] for row in users_result.fetchall()]

        inconsistencies = []

        # Check each user (in production, this should be batched/async)
        for user_id in user_ids:
            inconsistency = await self.check_user_consistency(db, user_id)
            if inconsistency:
                inconsistencies.append(inconsistency)

        return inconsistencies

    async def _count_total_users(self, db: AsyncSession) -> int:
        """Count total users with wallets"""
        query = text("SELECT COUNT(*) FROM credit_wallets")
        result = await db.execute(query)
        return result.fetchone()[0]

    async def _count_transactions_today(self, db: AsyncSession) -> int:
        """Count transactions created today"""
        query = text("""
            SELECT COUNT(*)
            FROM credit_transactions
            WHERE created_at >= CURRENT_DATE
        """)
        result = await db.execute(query)
        return result.fetchone()[0]

    async def _sum_credits_spent_today(self, db: AsyncSession) -> int:
        """Sum credits spent today"""
        query = text("""
            SELECT COALESCE(SUM(ABS(amount)), 0)
            FROM credit_transactions
            WHERE created_at >= CURRENT_DATE
              AND amount < 0
        """)
        result = await db.execute(query)
        return result.fetchone()[0]

    async def _find_missing_transactions(self, db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
        """Find transactions that should exist but don't"""

        # Check for access records without corresponding transactions
        query = text("""
            SELECT upa.id, upa.profile_id, p.username, upa.created_at
            FROM user_profile_access upa
            JOIN profiles p ON p.id = upa.profile_id
            LEFT JOIN credit_transactions ct ON (
                ct.user_id = :user_id
                AND ct.reference_id = p.username
                AND DATE(ct.created_at) = DATE(upa.created_at)
            )
            WHERE upa.user_id = :user_id
              AND ct.id IS NULL
              AND upa.created_at >= CURRENT_DATE - INTERVAL '30 days'
        """)

        result = await db.execute(query, {"user_id": user_id})

        missing = []
        for row in result.fetchall():
            missing.append({
                "access_record_id": str(row[0]),
                "profile_id": str(row[1]),
                "username": row[2],
                "created_at": row[3].isoformat(),
                "expected_amount": -25
            })

        return missing

    async def _find_orphaned_access_records(self, db: AsyncSession, user_id: str) -> List[str]:
        """Find access records that shouldn't exist"""
        # This would check for access records without proper transaction backing
        # Implementation depends on business rules
        return []

    async def monitor_real_time_transactions(self, db: AsyncSession) -> Dict[str, Any]:
        """Real-time monitoring of ongoing transactions"""

        # Check recent transactions (last hour)
        query = text("""
            SELECT
                COUNT(*) as total_transactions,
                COUNT(CASE WHEN amount < 0 THEN 1 END) as spending_transactions,
                COALESCE(AVG(ABS(amount)) FILTER (WHERE amount < 0), 0) as avg_spend,
                MAX(created_at) as last_transaction_time
            FROM credit_transactions
            WHERE created_at >= NOW() - INTERVAL '1 hour'
        """)

        result = await db.execute(query)
        row = result.fetchone()

        return {
            "total_transactions_last_hour": row[0],
            "spending_transactions_last_hour": row[1],
            "average_spend_amount": float(row[2]),
            "last_transaction_time": row[3].isoformat() if row[3] else None,
            "system_status": "healthy" if row[0] > 0 else "low_activity"
        }

# Global audit service
transaction_audit_service = TransactionAuditService()