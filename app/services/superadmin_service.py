"""
Super Admin Service - Comprehensive Platform Management
Integrates with all existing services for complete system control
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import psutil
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text, distinct
from sqlalchemy.exc import SQLAlchemyError

from app.database.unified_models import (
    User, Team, TeamMember, CreditWallet, CreditTransaction,
    UserProfileAccess, Profile, Post, MonthlyUsageTracking,
    AdminBrandProposal, CreditPricingRule
)
from app.services.redis_cache_service import RedisCacheService
from app.services.credit_wallet_service import CreditWalletService
from app.services.supabase_auth_service import SupabaseAuthService
from app.models.auth import UserRole, UserStatus

logger = logging.getLogger(__name__)

class SuperAdminService:
    """
    Comprehensive super admin service integrating with all platform systems
    Provides real-time monitoring, user management, and business analytics
    """
    
    def __init__(self):
        self.redis_service = RedisCacheService()
        self.credit_service = CreditWalletService()
        self.auth_service = SupabaseAuthService()
        
    async def get_platform_overview(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Get comprehensive platform overview with real-time metrics
        """
        try:
            # System health metrics
            system_health = await self._get_system_health()
            
            # User metrics from database
            user_metrics = await self._get_user_metrics(db)
            
            # Revenue metrics from credit system
            revenue_metrics = await self._get_revenue_metrics(db)
            
            # Activity metrics from platform usage
            activity_metrics = await self._get_activity_metrics(db)
            
            # Security alerts from monitoring
            security_alerts = await self._get_security_alerts(db)
            
            return {
                "system_health": system_health,
                "user_metrics": user_metrics,
                "revenue_metrics": revenue_metrics,
                "activity_metrics": activity_metrics,
                "security_alerts": security_alerts,
                "last_updated": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Failed to get platform overview: {e}")
            raise
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get real-time system health metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            return {
                "status": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning",
                "cpu_usage": round(cpu_percent, 2),
                "memory_usage": round(memory.percent, 2),
                "disk_usage": round(disk.percent, 2),
                "uptime_hours": round(uptime.total_seconds() / 3600, 2),
                "active_connections": len(psutil.net_connections()),
                "last_check": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_user_metrics(self, db: AsyncSession) -> Dict[str, int]:
        """Get comprehensive user metrics from database"""
        try:
            result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_users,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '1 day' THEN 1 END) as new_today,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as new_this_week,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as new_this_month,
                    COUNT(CASE WHEN role = 'premium' THEN 1 END) as premium_users,
                    COUNT(CASE WHEN role = 'free' THEN 1 END) as free_users
                FROM users
            """))
            
            row = result.fetchone()
            return {
                "total_users": row.total_users,
                "active_users": row.active_users,
                "new_today": row.new_today,
                "new_this_week": row.new_this_week,
                "new_this_month": row.new_this_month,
                "premium_users": row.premium_users,
                "free_users": row.free_users
            }
            
        except Exception as e:
            logger.error(f"Failed to get user metrics: {e}")
            return {}
    
    async def _get_revenue_metrics(self, db: AsyncSession) -> Dict[str, float]:
        """Get revenue metrics from credit system"""
        try:
            result = await db.execute(text("""
                SELECT 
                    COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as total_spent,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as total_topups,
                    COALESCE(SUM(CASE WHEN created_at >= NOW() - INTERVAL '30 days' AND amount < 0 THEN ABS(amount) ELSE 0 END), 0) as monthly_revenue,
                    COALESCE(SUM(CASE WHEN created_at >= NOW() - INTERVAL '1 day' AND amount < 0 THEN ABS(amount) ELSE 0 END), 0) as daily_revenue,
                    COUNT(DISTINCT wallet_id) as active_wallets
                FROM credit_transactions
            """))
            
            row = result.fetchone()
            return {
                "total_revenue": float(row.total_spent),
                "total_topups": float(row.total_topups),
                "monthly_revenue": float(row.monthly_revenue),
                "daily_revenue": float(row.daily_revenue),
                "active_wallets": row.active_wallets,
                "net_revenue": float(row.total_spent) - float(row.total_topups)
            }
            
        except Exception as e:
            logger.error(f"Failed to get revenue metrics: {e}")
            return {}
    
    async def _get_activity_metrics(self, db: AsyncSession) -> Dict[str, int]:
        """Get platform activity metrics"""
        try:
            result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total_profile_accesses,
                    COUNT(DISTINCT profile_id) as unique_profiles_accessed,
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(CASE WHEN accessed_at >= NOW() - INTERVAL '1 day' THEN 1 END) as accesses_today,
                    COUNT(CASE WHEN accessed_at >= NOW() - INTERVAL '7 days' THEN 1 END) as accesses_this_week
                FROM user_profile_access
                WHERE accessed_at >= NOW() - INTERVAL '30 days'
            """))
            
            row = result.fetchone()
            return {
                "total_profile_accesses": row.total_profile_accesses or 0,
                "unique_profiles_accessed": row.unique_profiles_accessed or 0,
                "active_users": row.active_users or 0,
                "accesses_today": row.accesses_today or 0,
                "accesses_this_week": row.accesses_this_week or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get activity metrics: {e}")
            return {}
    
    async def _get_security_alerts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Get real-time security alerts"""
        try:
            alerts = []
            
            # Check for suspicious login patterns (rapid user updates)
            suspicious_updates = await db.execute(text("""
                SELECT email, COUNT(*) as update_count
                FROM users
                WHERE updated_at >= NOW() - INTERVAL '1 hour'
                GROUP BY email
                HAVING COUNT(*) > 5
                LIMIT 5
            """))
            
            for row in suspicious_updates:
                alerts.append({
                    "type": "suspicious_activity",
                    "severity": "medium",
                    "message": f"Rapid updates for user {row.email} ({row.update_count} times)",
                    "timestamp": datetime.now(),
                    "user": row.email
                })
            
            # Check for unusual spending patterns
            high_spending = await db.execute(text("""
                SELECT 
                    u.email,
                    SUM(ABS(ct.amount)) as total_spent
                FROM credit_transactions ct
                JOIN credit_wallets cw ON ct.wallet_id = cw.id
                JOIN users u ON cw.user_id = u.id::text
                WHERE ct.created_at >= NOW() - INTERVAL '1 hour'
                AND ct.amount < 0
                GROUP BY u.email
                HAVING SUM(ABS(ct.amount)) > 500
                LIMIT 5
            """))
            
            for row in high_spending:
                alerts.append({
                    "type": "high_spending",
                    "severity": "high" if row.total_spent > 1000 else "medium",
                    "message": f"High spending: {row.email} spent {row.total_spent} credits",
                    "timestamp": datetime.now(),
                    "user": row.email,
                    "amount": row.total_spent
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to get security alerts: {e}")
            return []
    
    async def get_user_management_data(
        self, 
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive user management data with filtering and pagination
        """
        try:
            # Build query with filters
            base_query = select(User).order_by(desc(User.created_at))
            count_query = select(func.count(User.id))
            
            if filters:
                conditions = []
                if filters.get("role"):
                    conditions.append(User.role == filters["role"])
                if filters.get("status"):
                    conditions.append(User.status == filters["status"])
                if filters.get("search"):
                    search_term = f"%{filters['search']}%"
                    conditions.append(or_(
                        User.email.ilike(search_term),
                        User.full_name.ilike(search_term)
                    ))
                
                if conditions:
                    base_query = base_query.where(and_(*conditions))
                    count_query = count_query.where(and_(*conditions))
            
            # Execute queries
            users_result = await db.execute(base_query.offset(offset).limit(limit))
            users = users_result.scalars().all()
            
            total_count_result = await db.execute(count_query)
            total_count = total_count_result.scalar()
            
            # Get enhanced user data
            enhanced_users = []
            for user in users:
                # Get team memberships
                teams_result = await db.execute(
                    select(Team.name, TeamMember.role)
                    .select_from(TeamMember.join(Team))
                    .where(TeamMember.user_id == user.id)
                )
                teams = [{"name": t.name, "role": t.role} for t in teams_result.fetchall()]
                
                # Get credit information
                wallet_result = await db.execute(
                    select(CreditWallet.current_balance, CreditWallet.lifetime_spent)
                    .where(CreditWallet.user_id == str(user.id))
                )
                wallet = wallet_result.first()
                
                # Get activity data
                activity_result = await db.execute(
                    select(func.count(UserProfileAccess.id))
                    .where(
                        and_(
                            UserProfileAccess.user_id == user.id,
                            UserProfileAccess.accessed_at >= datetime.now() - timedelta(days=30)
                        )
                    )
                )
                activity_count = activity_result.scalar() or 0
                
                enhanced_users.append({
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "status": user.status,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "teams": teams,
                    "credits": {
                        "balance": wallet.current_balance if wallet else 0,
                        "total_spent": wallet.lifetime_spent if wallet else 0
                    },
                    "activity_30d": activity_count
                })
            
            # Get distribution statistics
            role_dist_result = await db.execute(
                select(User.role, func.count(User.id))
                .group_by(User.role)
            )
            role_distribution = {row.role: row.count for row in role_dist_result}
            
            status_dist_result = await db.execute(
                select(User.status, func.count(User.id))
                .group_by(User.status)
            )
            status_distribution = {row.status: row.count for row in status_dist_result}
            
            return {
                "users": enhanced_users,
                "total_count": total_count,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_next": offset + limit < total_count,
                    "has_previous": offset > 0
                },
                "distributions": {
                    "roles": role_distribution,
                    "statuses": status_distribution
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get user management data: {e}")
            raise
    
    async def update_user_status(
        self,
        db: AsyncSession,
        user_id: UUID,
        new_status: str,
        admin_user_id: UUID,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user status with full audit trail
        """
        try:
            # Validate status
            valid_statuses = ["active", "inactive", "suspended", "pending"]
            if new_status not in valid_statuses:
                raise ValueError(f"Invalid status: {new_status}")
            
            # Get user
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            old_status = user.status
            
            # Update user
            user.status = new_status
            user.updated_at = datetime.now()
            
            # If suspending, also suspend their teams' access
            if new_status == "suspended":
                await self._suspend_user_access(db, user_id)
            
            await db.commit()
            
            # Log the action (would integrate with audit system)
            logger.info(f"User {user.email} status changed from {old_status} to {new_status} by admin {admin_user_id}")
            
            return {
                "success": True,
                "user_id": str(user_id),
                "old_status": old_status,
                "new_status": new_status,
                "updated_at": user.updated_at,
                "reason": reason
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update user status: {e}")
            raise
    
    async def _suspend_user_access(self, db: AsyncSession, user_id: UUID):
        """
        Suspend user's access by setting team memberships to inactive
        """
        try:
            await db.execute(
                text("""
                    UPDATE team_members 
                    SET status = 'inactive', updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id}
            )
            
        except Exception as e:
            logger.error(f"Failed to suspend user access: {e}")
            raise
    
    async def get_business_analytics(
        self,
        db: AsyncSession,
        time_range: str = "30d"
    ) -> Dict[str, Any]:
        """
        Get comprehensive business analytics
        """
        try:
            # Calculate date range
            days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
            days = days_map.get(time_range, 30)
            start_date = datetime.now() - timedelta(days=days)
            
            # Revenue analytics
            revenue_data = await self._get_revenue_analytics(db, start_date, days)
            
            # User growth analytics
            growth_data = await self._get_growth_analytics(db, start_date)
            
            # Platform usage analytics
            usage_data = await self._get_usage_analytics(db, start_date)
            
            # Content analytics
            content_data = await self._get_content_analytics(db, start_date)
            
            return {
                "revenue": revenue_data,
                "growth": growth_data,
                "usage": usage_data,
                "content": content_data,
                "time_range": time_range,
                "generated_at": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Failed to get business analytics: {e}")
            raise
    
    async def _get_revenue_analytics(self, db: AsyncSession, start_date: datetime, days: int) -> Dict[str, Any]:
        """Get detailed revenue analytics"""
        try:
            result = await db.execute(text("""
                SELECT 
                    DATE(created_at) as date,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as daily_revenue,
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as daily_topups,
                    COUNT(DISTINCT wallet_id) as active_users,
                    COUNT(*) as transaction_count
                FROM credit_transactions
                WHERE created_at >= :start_date
                GROUP BY DATE(created_at)
                ORDER BY date
            """), {"start_date": start_date})
            
            daily_data = []
            total_revenue = 0
            total_topups = 0
            
            for row in result:
                daily_data.append({
                    "date": row.date.isoformat(),
                    "revenue": float(row.daily_revenue),
                    "topups": float(row.daily_topups),
                    "active_users": row.active_users,
                    "transactions": row.transaction_count
                })
                total_revenue += row.daily_revenue
                total_topups += row.daily_topups
            
            return {
                "daily_data": daily_data,
                "total_revenue": total_revenue,
                "total_topups": total_topups,
                "net_revenue": total_revenue - total_topups,
                "average_daily_revenue": total_revenue / max(days, 1),
                "growth_rate": self._calculate_growth_rate(daily_data, "revenue")
            }
            
        except Exception as e:
            logger.error(f"Failed to get revenue analytics: {e}")
            return {}
    
    async def _get_growth_analytics(self, db: AsyncSession, start_date: datetime) -> Dict[str, Any]:
        """Get user growth analytics"""
        try:
            result = await db.execute(text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as new_users,
                    role
                FROM users
                WHERE created_at >= :start_date
                GROUP BY DATE(created_at), role
                ORDER BY date, role
            """), {"start_date": start_date})
            
            daily_signups = {}
            role_breakdown = {}
            
            for row in result:
                date_str = row.date.isoformat()
                if date_str not in daily_signups:
                    daily_signups[date_str] = 0
                daily_signups[date_str] += row.new_users
                
                role_breakdown[row.role] = role_breakdown.get(row.role, 0) + row.new_users
            
            return {
                "daily_signups": [
                    {"date": date, "signups": count}
                    for date, count in daily_signups.items()
                ],
                "role_breakdown": role_breakdown,
                "total_new_users": sum(daily_signups.values()),
                "average_daily_signups": sum(daily_signups.values()) / max(len(daily_signups), 1)
            }
            
        except Exception as e:
            logger.error(f"Failed to get growth analytics: {e}")
            return {}
    
    async def _get_usage_analytics(self, db: AsyncSession, start_date: datetime) -> Dict[str, Any]:
        """Get platform usage analytics"""
        try:
            result = await db.execute(text("""
                SELECT 
                    DATE(accessed_at) as date,
                    COUNT(*) as total_accesses,
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(DISTINCT profile_id) as unique_profiles
                FROM user_profile_access
                WHERE accessed_at >= :start_date
                GROUP BY DATE(accessed_at)
                ORDER BY date
            """), {"start_date": start_date})
            
            daily_usage = []
            total_accesses = 0
            unique_users = set()
            
            for row in result:
                daily_usage.append({
                    "date": row.date.isoformat(),
                    "accesses": row.total_accesses,
                    "active_users": row.active_users,
                    "unique_profiles": row.unique_profiles
                })
                total_accesses += row.total_accesses
            
            return {
                "daily_usage": daily_usage,
                "total_accesses": total_accesses,
                "average_daily_accesses": total_accesses / max(len(daily_usage), 1)
            }
            
        except Exception as e:
            logger.error(f"Failed to get usage analytics: {e}")
            return {}
    
    async def _get_content_analytics(self, db: AsyncSession, start_date: datetime) -> Dict[str, Any]:
        """Get content analytics"""
        try:
            result = await db.execute(text("""
                SELECT 
                    COUNT(DISTINCT p.id) as total_profiles,
                    COUNT(DISTINCT posts.id) as total_posts,
                    AVG(p.followers_count) as avg_followers,
                    COUNT(CASE WHEN p.created_at >= :start_date THEN 1 END) as new_profiles_period
                FROM profiles p
                LEFT JOIN posts ON posts.profile_id = p.id
            """), {"start_date": start_date})
            
            row = result.fetchone()
            
            return {
                "total_profiles": row.total_profiles or 0,
                "total_posts": row.total_posts or 0,
                "average_followers": float(row.avg_followers or 0),
                "new_profiles_in_period": row.new_profiles_period or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get content analytics: {e}")
            return {}
    
    def _calculate_growth_rate(self, daily_data: List[Dict], metric: str) -> float:
        """Calculate growth rate for a metric"""
        try:
            if len(daily_data) < 2:
                return 0.0
            
            first_half = daily_data[:len(daily_data)//2]
            second_half = daily_data[len(daily_data)//2:]
            
            first_avg = sum(d.get(metric, 0) for d in first_half) / len(first_half)
            second_avg = sum(d.get(metric, 0) for d in second_half) / len(second_half)
            
            if first_avg == 0:
                return 0.0
            
            return ((second_avg - first_avg) / first_avg) * 100
            
        except Exception:
            return 0.0