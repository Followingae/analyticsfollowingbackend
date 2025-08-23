"""
Admin System Monitoring & Dashboard API Routes
Comprehensive system health and platform analytics for super admins
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
import psutil
import asyncio
from pydantic import BaseModel, Field

from app.middleware.role_based_auth import (
    get_current_user_with_permissions,
    requires_permission,
    requires_role_level,
    RoleLevel,
    auth_service,
    audit_action
)
from app.database.connection import get_db, async_engine
from app.database.unified_models import (
    Users, UserActivityLogs, AdminActionsLog, SystemHealthMetrics,
    PlatformMetrics, CreditTransactions, AdminBrandProposals
)

router = APIRouter(prefix="/admin/system", tags=["Admin - System Monitoring"])

# Pydantic Models
class SystemHealthResponse(BaseModel):
    overall_status: str
    uptime_hours: float
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    active_connections: int
    database_status: str
    redis_status: str
    api_response_time_ms: float
    error_rate_percent: float
    last_check: datetime

class PlatformAnalyticsResponse(BaseModel):
    total_users: int
    active_users_today: int
    active_users_this_week: int
    active_users_this_month: int
    new_registrations_today: int
    new_registrations_this_week: int
    new_registrations_this_month: int
    total_api_calls_today: int
    average_session_duration_minutes: float
    top_features_used: List[Dict[str, Any]]

class UserActivityStatsResponse(BaseModel):
    login_activity: Dict[str, int]
    feature_usage: Dict[str, int]
    geographic_distribution: Dict[str, int]
    device_types: Dict[str, int]
    peak_usage_hours: List[Dict[str, Any]]

class AdminActionsSummaryResponse(BaseModel):
    total_admin_actions: int
    actions_by_type: Dict[str, int]
    actions_by_admin: List[Dict[str, Any]]
    recent_critical_actions: List[Dict[str, Any]]
    security_incidents: int

class SystemPerformanceResponse(BaseModel):
    api_performance: Dict[str, Any]
    database_performance: Dict[str, Any]
    cache_performance: Dict[str, Any]
    background_jobs: Dict[str, Any]
    error_rates: Dict[str, Any]

@router.get("/health", response_model=SystemHealthResponse)
@requires_permission("can_view_system_logs")
@audit_action("view_system_health")
async def get_system_health(
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive system health status"""
    
    try:
        # System resource usage
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        # Database health check
        database_status = "healthy"
        active_connections = 0
        
        try:
            if async_engine:
                active_connections = async_engine.pool.checkedout()
                # Test query
                test_query = select(func.count(Users.id))
                await db.execute(test_query)
            else:
                database_status = "disconnected"
        except Exception as e:
            database_status = "unhealthy"
        
        # Redis health check
        redis_status = "healthy"
        try:
            from app.middleware.role_based_auth import redis_client
            if redis_client:
                redis_client.ping()
            else:
                redis_status = "disconnected"
        except Exception:
            redis_status = "unhealthy"
        
        # Get latest system metrics
        latest_metrics_query = select(SystemHealthMetrics).order_by(
            desc(SystemHealthMetrics.metric_timestamp)
        ).limit(1)
        
        metrics_result = await db.execute(latest_metrics_query)
        latest_metrics = metrics_result.scalar()
        
        api_response_time = latest_metrics.response_time_ms if latest_metrics else 0
        error_rate = latest_metrics.error_rate_percent if latest_metrics else 0
        uptime_hours = latest_metrics.uptime_hours if latest_metrics else 0
        
        # Determine overall status
        overall_status = "healthy"
        if (cpu_usage > 80 or memory_usage > 80 or disk_usage > 90 or 
            database_status != "healthy" or error_rate > 5):
            overall_status = "warning"
        
        if (cpu_usage > 95 or memory_usage > 95 or disk_usage > 95 or 
            database_status == "unhealthy" or error_rate > 10):
            overall_status = "critical"
        
        # Store current metrics
        current_metrics = SystemHealthMetrics(
            cpu_usage_percent=cpu_usage,
            memory_usage_percent=memory_usage,
            disk_usage_percent=disk_usage,
            active_connections=active_connections,
            response_time_ms=api_response_time,
            error_rate_percent=error_rate,
            uptime_hours=uptime_hours
        )
        
        db.add(current_metrics)
        await db.commit()
        
        return SystemHealthResponse(
            overall_status=overall_status,
            uptime_hours=uptime_hours,
            cpu_usage_percent=cpu_usage,
            memory_usage_percent=memory_usage,
            disk_usage_percent=disk_usage,
            active_connections=active_connections,
            database_status=database_status,
            redis_status=redis_status,
            api_response_time_ms=api_response_time,
            error_rate_percent=error_rate,
            last_check=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )

@router.get("/analytics", response_model=PlatformAnalyticsResponse)
@requires_permission("can_view_system_logs")
@audit_action("view_platform_analytics")
async def get_platform_analytics(
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive platform usage analytics"""
    
    now = datetime.utcnow()
    today = now.date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Total users
    total_users_query = select(func.count(Users.id))
    total_users_result = await db.execute(total_users_query)
    total_users = total_users_result.scalar()
    
    # Active users by period (based on last login)
    active_today_query = select(func.count(Users.id)).where(
        Users.last_login_at >= datetime.combine(today, datetime.min.time())
    )
    active_today_result = await db.execute(active_today_query)
    active_today = active_today_result.scalar()
    
    active_week_query = select(func.count(Users.id)).where(
        Users.last_login_at >= datetime.combine(week_ago, datetime.min.time())
    )
    active_week_result = await db.execute(active_week_query)
    active_week = active_week_result.scalar()
    
    active_month_query = select(func.count(Users.id)).where(
        Users.last_login_at >= datetime.combine(month_ago, datetime.min.time())
    )
    active_month_result = await db.execute(active_month_query)
    active_month = active_month_result.scalar()
    
    # New registrations by period
    new_today_query = select(func.count(Users.id)).where(
        Users.created_at >= datetime.combine(today, datetime.min.time())
    )
    new_today_result = await db.execute(new_today_query)
    new_today = new_today_result.scalar()
    
    new_week_query = select(func.count(Users.id)).where(
        Users.created_at >= datetime.combine(week_ago, datetime.min.time())
    )
    new_week_result = await db.execute(new_week_query)
    new_week = new_week_result.scalar()
    
    new_month_query = select(func.count(Users.id)).where(
        Users.created_at >= datetime.combine(month_ago, datetime.min.time())
    )
    new_month_result = await db.execute(new_month_query)
    new_month = new_month_result.scalar()
    
    # API calls today (from activity logs)
    api_calls_query = select(func.count(UserActivityLogs.id)).where(
        and_(
            UserActivityLogs.created_at >= datetime.combine(today, datetime.min.time()),
            UserActivityLogs.action_type.in_(['api_call', 'profile_view', 'export_data'])
        )
    )
    api_calls_result = await db.execute(api_calls_query)
    api_calls_today = api_calls_result.scalar()
    
    # Average session duration (estimated from activity logs)
    session_duration_query = select(
        UserActivityLogs.user_id,
        func.min(UserActivityLogs.created_at).label('session_start'),
        func.max(UserActivityLogs.created_at).label('session_end')
    ).where(
        UserActivityLogs.created_at >= datetime.combine(today, datetime.min.time())
    ).group_by(
        UserActivityLogs.user_id,
        func.date_trunc('hour', UserActivityLogs.created_at)
    )
    
    session_result = await db.execute(session_duration_query)
    sessions = session_result.all()
    
    total_session_minutes = 0
    valid_sessions = 0
    
    for session in sessions:
        if session.session_end and session.session_start:
            duration = (session.session_end - session.session_start).total_seconds() / 60
            if 0 < duration < 480:  # Valid sessions between 0 and 8 hours
                total_session_minutes += duration
                valid_sessions += 1
    
    avg_session_duration = total_session_minutes / valid_sessions if valid_sessions > 0 else 0
    
    # Top features used (from activity logs)
    feature_usage_query = select(
        UserActivityLogs.action_type,
        func.count(UserActivityLogs.id).label('usage_count')
    ).where(
        UserActivityLogs.created_at >= datetime.combine(week_ago, datetime.min.time())
    ).group_by(
        UserActivityLogs.action_type
    ).order_by(desc('usage_count')).limit(10)
    
    feature_result = await db.execute(feature_usage_query)
    top_features = [
        {
            "feature": row.action_type,
            "usage_count": row.usage_count,
            "percentage": (row.usage_count / api_calls_today * 100) if api_calls_today > 0 else 0
        }
        for row in feature_result.all()
    ]
    
    return PlatformAnalyticsResponse(
        total_users=total_users,
        active_users_today=active_today,
        active_users_this_week=active_week,
        active_users_this_month=active_month,
        new_registrations_today=new_today,
        new_registrations_this_week=new_week,
        new_registrations_this_month=new_month,
        total_api_calls_today=api_calls_today,
        average_session_duration_minutes=avg_session_duration,
        top_features_used=top_features
    )

@router.get("/user-activity", response_model=UserActivityStatsResponse)
@requires_permission("can_view_user_activity")
@audit_action("view_user_activity_stats")
async def get_user_activity_stats(
    days_back: int = Query(7, ge=1, le=30),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed user activity statistics"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    
    # Login activity by day
    login_activity_query = select(
        func.date(UserActivityLogs.created_at).label('date'),
        func.count(UserActivityLogs.id).label('logins')
    ).where(
        and_(
            UserActivityLogs.action_type == 'login',
            UserActivityLogs.created_at >= cutoff_date,
            UserActivityLogs.success == True
        )
    ).group_by('date').order_by('date')
    
    login_result = await db.execute(login_activity_query)
    login_activity = {
        str(row.date): row.logins 
        for row in login_result.all()
    }
    
    # Feature usage statistics
    feature_usage_query = select(
        UserActivityLogs.action_type,
        func.count(UserActivityLogs.id).label('usage_count')
    ).where(
        UserActivityLogs.created_at >= cutoff_date
    ).group_by(UserActivityLogs.action_type).order_by(desc('usage_count'))
    
    feature_result = await db.execute(feature_usage_query)
    feature_usage = {
        row.action_type: row.usage_count 
        for row in feature_result.all()
    }
    
    # Geographic distribution (based on IP addresses - simplified)
    # This would require IP geolocation service integration
    geographic_distribution = {"Unknown": 100}  # Placeholder
    
    # Device types (based on user agents - simplified)
    device_query = select(
        func.case(
            [(UserActivityLogs.user_agent.ilike('%Mobile%'), 'Mobile')],
            else_='Desktop'
        ).label('device_type'),
        func.count(UserActivityLogs.id).label('count')
    ).where(
        and_(
            UserActivityLogs.created_at >= cutoff_date,
            UserActivityLogs.user_agent.isnot(None)
        )
    ).group_by('device_type')
    
    device_result = await db.execute(device_query)
    device_types = {
        row.device_type: row.count 
        for row in device_result.all()
    }
    
    # Peak usage hours
    hourly_usage_query = select(
        func.extract('hour', UserActivityLogs.created_at).label('hour'),
        func.count(UserActivityLogs.id).label('activity_count')
    ).where(
        UserActivityLogs.created_at >= cutoff_date
    ).group_by('hour').order_by('hour')
    
    hourly_result = await db.execute(hourly_usage_query)
    peak_usage_hours = [
        {
            "hour": int(row.hour),
            "activity_count": row.activity_count,
            "formatted_hour": f"{int(row.hour):02d}:00"
        }
        for row in hourly_result.all()
    ]
    
    return UserActivityStatsResponse(
        login_activity=login_activity,
        feature_usage=feature_usage,
        geographic_distribution=geographic_distribution,
        device_types=device_types,
        peak_usage_hours=peak_usage_hours
    )

@router.get("/admin-actions", response_model=AdminActionsSummaryResponse)
@requires_permission("can_view_system_logs")
@audit_action("view_admin_actions_summary")
async def get_admin_actions_summary(
    days_back: int = Query(30, ge=1, le=90),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get summary of admin actions and security events"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    
    # Total admin actions
    total_actions_query = select(func.count(AdminActionsLog.id)).where(
        AdminActionsLog.created_at >= cutoff_date
    )
    total_actions_result = await db.execute(total_actions_query)
    total_admin_actions = total_actions_result.scalar()
    
    # Actions by type
    actions_by_type_query = select(
        AdminActionsLog.action_type,
        func.count(AdminActionsLog.id).label('count')
    ).where(
        AdminActionsLog.created_at >= cutoff_date
    ).group_by(AdminActionsLog.action_type).order_by(desc('count'))
    
    actions_type_result = await db.execute(actions_by_type_query)
    actions_by_type = {
        row.action_type: row.count 
        for row in actions_type_result.all()
    }
    
    # Actions by admin user
    actions_by_admin_query = select(
        Users.email,
        func.count(AdminActionsLog.id).label('action_count')
    ).join(
        Users, AdminActionsLog.admin_user_id == Users.id
    ).where(
        AdminActionsLog.created_at >= cutoff_date
    ).group_by(Users.email).order_by(desc('action_count')).limit(10)
    
    actions_admin_result = await db.execute(actions_by_admin_query)
    actions_by_admin = [
        {
            "admin_email": row.email,
            "action_count": row.action_count
        }
        for row in actions_admin_result.all()
    ]
    
    # Recent critical actions
    critical_actions_query = select(
        AdminActionsLog.action_type,
        AdminActionsLog.created_at,
        AdminActionsLog.reason,
        Users.email.label('admin_email')
    ).join(
        Users, AdminActionsLog.admin_user_id == Users.id
    ).where(
        and_(
            AdminActionsLog.created_at >= cutoff_date,
            AdminActionsLog.severity.in_(['warning', 'critical'])
        )
    ).order_by(desc(AdminActionsLog.created_at)).limit(20)
    
    critical_result = await db.execute(critical_actions_query)
    recent_critical_actions = [
        {
            "action_type": row.action_type,
            "created_at": row.created_at,
            "reason": row.reason,
            "admin_email": row.admin_email
        }
        for row in critical_result.all()
    ]
    
    # Security incidents (failed logins, account lockouts, etc.)
    security_incidents_query = select(func.count(UserActivityLogs.id)).where(
        and_(
            UserActivityLogs.created_at >= cutoff_date,
            UserActivityLogs.success == False,
            UserActivityLogs.action_type.in_(['login', 'api_call', 'password_reset'])
        )
    )
    
    security_result = await db.execute(security_incidents_query)
    security_incidents = security_result.scalar()
    
    return AdminActionsSummaryResponse(
        total_admin_actions=total_admin_actions,
        actions_by_type=actions_by_type,
        actions_by_admin=actions_by_admin,
        recent_critical_actions=recent_critical_actions,
        security_incidents=security_incidents
    )

@router.get("/performance", response_model=SystemPerformanceResponse)
@requires_permission("can_view_system_logs")
@audit_action("view_system_performance")
async def get_system_performance(
    hours_back: int = Query(24, ge=1, le=168),  # Max 1 week
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed system performance metrics"""
    
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
    
    # API Performance
    api_performance_query = select(
        func.avg(UserActivityLogs.response_time_ms).label('avg_response_time'),
        func.max(UserActivityLogs.response_time_ms).label('max_response_time'),
        func.count(UserActivityLogs.id).label('total_requests'),
        func.sum(func.case([(UserActivityLogs.success == False, 1)], else_=0)).label('failed_requests')
    ).where(
        and_(
            UserActivityLogs.created_at >= cutoff_time,
            UserActivityLogs.response_time_ms.isnot(None)
        )
    )
    
    api_result = await db.execute(api_performance_query)
    api_stats = api_result.first()
    
    api_performance = {
        "average_response_time_ms": float(api_stats.avg_response_time or 0),
        "max_response_time_ms": float(api_stats.max_response_time or 0),
        "total_requests": api_stats.total_requests,
        "failed_requests": api_stats.failed_requests,
        "success_rate_percent": (
            ((api_stats.total_requests - api_stats.failed_requests) / api_stats.total_requests * 100)
            if api_stats.total_requests > 0 else 100
        )
    }
    
    # Database Performance
    db_performance_query = select(
        func.avg(SystemHealthMetrics.response_time_ms).label('avg_db_time'),
        func.avg(SystemHealthMetrics.active_connections).label('avg_connections'),
        func.max(SystemHealthMetrics.active_connections).label('max_connections')
    ).where(
        SystemHealthMetrics.metric_timestamp >= cutoff_time
    )
    
    db_result = await db.execute(db_performance_query)
    db_stats = db_result.first()
    
    database_performance = {
        "average_query_time_ms": float(db_stats.avg_db_time or 0),
        "average_connections": int(db_stats.avg_connections or 0),
        "max_connections": int(db_stats.max_connections or 0),
        "connection_pool_utilization": (
            (db_stats.avg_connections / 100 * 100) if db_stats.avg_connections else 0
        )
    }
    
    # Cache Performance (Redis)
    cache_performance = {
        "hit_rate_percent": 85.0,  # Would need Redis monitoring
        "memory_usage_mb": 256,    # Would need Redis monitoring
        "connected_clients": 5,    # Would need Redis monitoring
        "operations_per_second": 1000  # Would need Redis monitoring
    }
    
    # Background Jobs (would integrate with Celery monitoring)
    background_jobs = {
        "active_jobs": 3,
        "pending_jobs": 12,
        "completed_jobs_24h": 145,
        "failed_jobs_24h": 2,
        "average_job_duration_seconds": 45.2
    }
    
    # Error Rates by endpoint/feature
    error_rates_query = select(
        UserActivityLogs.action_type,
        func.count(UserActivityLogs.id).label('total'),
        func.sum(func.case([(UserActivityLogs.success == False, 1)], else_=0)).label('errors')
    ).where(
        UserActivityLogs.created_at >= cutoff_time
    ).group_by(UserActivityLogs.action_type).having(
        func.count(UserActivityLogs.id) > 10  # Only show endpoints with significant traffic
    )
    
    error_result = await db.execute(error_rates_query)
    error_rates = {}
    
    for row in error_result.all():
        error_rate = (row.errors / row.total * 100) if row.total > 0 else 0
        error_rates[row.action_type] = {
            "total_requests": row.total,
            "error_count": row.errors,
            "error_rate_percent": round(error_rate, 2)
        }
    
    return SystemPerformanceResponse(
        api_performance=api_performance,
        database_performance=database_performance,
        cache_performance=cache_performance,
        background_jobs=background_jobs,
        error_rates=error_rates
    )

@router.post("/maintenance-mode")
@requires_role_level(RoleLevel.SUPER_ADMIN)
@audit_action("toggle_maintenance_mode")
async def toggle_maintenance_mode(
    enabled: bool = Query(..., description="Enable or disable maintenance mode"),
    message: Optional[str] = Query(None, description="Maintenance message for users"),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Toggle system maintenance mode (Super Admin only)"""
    
    try:
        # Store maintenance mode status in platform metrics
        maintenance_metric = PlatformMetrics(
            metric_name="maintenance_mode",
            metric_value=1 if enabled else 0,
            metric_date=datetime.utcnow().date(),
            metric_category="system",
            additional_data={
                "enabled": enabled,
                "message": message,
                "enabled_by": current_user["email"]
            }
        )
        
        db.add(maintenance_metric)
        await db.commit()
        
        # Log critical admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="maintenance_mode_toggle",
            new_values={
                "enabled": enabled,
                "message": message
            },
            reason=f"Maintenance mode {'enabled' if enabled else 'disabled'}",
            severity="critical",
            db=db
        )
        
        return {
            "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}",
            "enabled": enabled,
            "maintenance_message": message,
            "updated_by": current_user["email"],
            "updated_at": datetime.utcnow()
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle maintenance mode: {str(e)}"
        )