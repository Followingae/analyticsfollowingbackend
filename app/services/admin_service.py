"""
SUPERADMIN DASHBOARD SERVICE - Complete Platform Management
Comprehensive service layer for admin dashboard with analytics, user management, and system controls
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, timedelta
from sqlalchemy import func, select, text, desc, asc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert
import json
import uuid
from decimal import Decimal

from ..database.unified_models import (
    AdminUser, SystemAnalytics, SystemConfiguration, AdminNotification,
    SystemAuditLog, SystemMaintenanceJob, FeatureFlag, AdminUserAction,
    User, AuthUser, Profile, Campaign, CreditTransaction,
    UserProfile, AiAnalysisJob, UserProfileAccess
)


class AdminService:
    """
    Comprehensive admin service for platform management
    Handles system analytics, user management, configurations, and monitoring
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    # ==========================================
    # ADMIN USER MANAGEMENT
    # ==========================================
    
    async def create_admin_user(
        self, 
        user_id: str, 
        admin_role: str, 
        permissions: Dict[str, Any] = None,
        created_by_user_id: Optional[str] = None
    ) -> AdminUser:
        """Create a new admin user with specified role and permissions"""
        try:
            admin_user = AdminUser(
                user_id=user_id,
                admin_role=admin_role,
                permissions=permissions or {},
                created_by=created_by_user_id
            )
            
            self.db.add(admin_user)
            await self.db.flush()
            
            # Log the admin creation
            await self._log_admin_action(
                admin_user_id=created_by_user_id,
                action="create_admin_user",
                resource_type="admin_user",
                resource_id=str(admin_user.id),
                new_values={
                    "user_id": user_id,
                    "admin_role": admin_role,
                    "permissions": permissions
                }
            )
            
            return admin_user
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create admin user: {str(e)}")
    
    async def get_admin_user(self, user_id: str) -> Optional[AdminUser]:
        """Get admin user by user_id"""
        result = await self.db.execute(
            select(AdminUser)
            .options(selectinload(AdminUser.auth_user))
            .where(AdminUser.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_admin_user(
        self, 
        admin_user_id: int, 
        admin_role: Optional[str] = None,
        permissions: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
        updated_by_user_id: Optional[str] = None
    ) -> AdminUser:
        """Update admin user details"""
        try:
            # Get current admin user
            result = await self.db.execute(
                select(AdminUser).where(AdminUser.id == admin_user_id)
            )
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                raise ValueError(f"Admin user with ID {admin_user_id} not found")
            
            # Store old values for audit
            old_values = {
                "admin_role": admin_user.admin_role,
                "permissions": admin_user.permissions,
                "is_active": admin_user.is_active
            }
            
            # Update fields
            if admin_role is not None:
                admin_user.admin_role = admin_role
            if permissions is not None:
                admin_user.permissions = permissions
            if is_active is not None:
                admin_user.is_active = is_active
            
            admin_user.updated_at = datetime.utcnow()
            
            # Log the update
            await self._log_admin_action(
                admin_user_id=updated_by_user_id,
                action="update_admin_user",
                resource_type="admin_user",
                resource_id=str(admin_user.id),
                old_values=old_values,
                new_values={
                    "admin_role": admin_user.admin_role,
                    "permissions": admin_user.permissions,
                    "is_active": admin_user.is_active
                }
            )
            
            return admin_user
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update admin user: {str(e)}")
    
    async def get_all_admin_users(
        self, 
        active_only: bool = True,
        role_filter: Optional[str] = None
    ) -> List[AdminUser]:
        """Get all admin users with optional filtering"""
        query = select(AdminUser).options(selectinload(AdminUser.auth_user))
        
        if active_only:
            query = query.where(AdminUser.is_active == True)
        
        if role_filter:
            query = query.where(AdminUser.admin_role == role_filter)
        
        query = query.order_by(desc(AdminUser.created_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def check_admin_permissions(
        self, 
        user_id: str, 
        required_permission: str
    ) -> bool:
        """Check if admin user has required permission"""
        admin_user = await self.get_admin_user(user_id)
        
        if not admin_user or not admin_user.is_active:
            return False
        
        # Superadmin has all permissions
        if admin_user.admin_role == 'superadmin':
            return True
        
        # Check specific permissions
        permissions = admin_user.permissions or {}
        return permissions.get(required_permission, False) or permissions.get('all', False)
    
    # ==========================================
    # SYSTEM ANALYTICS
    # ==========================================
    
    async def get_system_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive system dashboard data"""
        try:
            # Get platform summary using database function
            platform_summary_result = await self.db.execute(
                text("SELECT get_platform_summary()")
            )
            platform_summary = platform_summary_result.scalar()
            
            # Get recent system analytics
            analytics_result = await self.db.execute(
                select(SystemAnalytics)
                .order_by(desc(SystemAnalytics.date))
                .limit(7)
            )
            recent_analytics = analytics_result.scalars().all()
            
            # Get performance metrics using database function
            performance_result = await self.db.execute(
                text("SELECT get_system_performance_metrics()")
            )
            performance_metrics = performance_result.scalar()
            
            # Get recent notifications
            notifications_result = await self.db.execute(
                select(AdminNotification)
                .where(AdminNotification.is_dismissed == False)
                .order_by(desc(AdminNotification.created_at))
                .limit(5)
            )
            recent_notifications = notifications_result.scalars().all()
            
            # Calculate trends
            trends = await self._calculate_trends(recent_analytics)
            
            return {
                "platform_summary": platform_summary,
                "performance_metrics": performance_metrics,
                "recent_analytics": [
                    {
                        "date": str(analytics.date),
                        "total_users": analytics.total_users,
                        "active_users": analytics.active_users,
                        "new_users": analytics.new_users,
                        "api_requests": analytics.api_requests,
                        "credits_consumed": analytics.credits_consumed,
                        "system_uptime": float(analytics.system_uptime_percentage),
                        "error_rate": float(analytics.error_rate_percentage),
                        "cache_hit_rate": float(analytics.cache_hit_rate_percentage)
                    }
                    for analytics in recent_analytics
                ],
                "trends": trends,
                "recent_notifications": [
                    {
                        "id": notification.id,
                        "type": notification.notification_type,
                        "title": notification.title,
                        "message": notification.message,
                        "severity": notification.severity,
                        "created_at": notification.created_at.isoformat()
                    }
                    for notification in recent_notifications
                ],
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to get system dashboard: {str(e)}")
    
    async def update_daily_analytics(self) -> SystemAnalytics:
        """Update today's system analytics"""
        try:
            # Use database function to update analytics
            await self.db.execute(
                text("SELECT update_daily_system_analytics()")
            )
            await self.db.commit()
            
            # Get the updated record
            result = await self.db.execute(
                select(SystemAnalytics)
                .where(SystemAnalytics.date == date.today())
            )
            return result.scalar_one()
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update daily analytics: {str(e)}")
    
    async def get_user_activity_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get user activity summary using database function"""
        try:
            result = await self.db.execute(
                text("SELECT get_user_activity_summary(:days)"),
                {"days": days}
            )
            return result.scalar()
            
        except Exception as e:
            raise Exception(f"Failed to get user activity summary: {str(e)}")
    
    async def get_analytics_by_date_range(
        self, 
        start_date: date, 
        end_date: date
    ) -> List[SystemAnalytics]:
        """Get system analytics for a date range"""
        result = await self.db.execute(
            select(SystemAnalytics)
            .where(and_(
                SystemAnalytics.date >= start_date,
                SystemAnalytics.date <= end_date
            ))
            .order_by(SystemAnalytics.date)
        )
        return result.scalars().all()
    
    # ==========================================
    # SYSTEM CONFIGURATIONS
    # ==========================================
    
    async def get_system_config(self, config_key: str) -> Optional[SystemConfiguration]:
        """Get system configuration by key"""
        result = await self.db.execute(
            select(SystemConfiguration)
            .where(and_(
                SystemConfiguration.config_key == config_key,
                SystemConfiguration.is_active == True
            ))
        )
        return result.scalar_one_or_none()
    
    async def update_system_config(
        self, 
        config_key: str, 
        config_value: Any,
        config_type: Optional[str] = None,
        description: Optional[str] = None,
        requires_restart: bool = False,
        updated_by_user_id: Optional[str] = None
    ) -> SystemConfiguration:
        """Update or create system configuration"""
        try:
            # Get existing config
            existing_config = await self.get_system_config(config_key)
            
            if existing_config:
                # Store old value for audit
                old_values = {
                    "config_value": existing_config.config_value,
                    "config_type": existing_config.config_type,
                    "description": existing_config.description,
                    "requires_restart": existing_config.requires_restart
                }
                
                # Update existing config
                existing_config.config_value = config_value
                if config_type:
                    existing_config.config_type = config_type
                if description:
                    existing_config.description = description
                existing_config.requires_restart = requires_restart
                existing_config.updated_by = updated_by_user_id
                existing_config.updated_at = datetime.utcnow()
                
                config_record = existing_config
                action = "update_system_config"
            else:
                # Create new config
                config_record = SystemConfiguration(
                    config_key=config_key,
                    config_value=config_value,
                    config_type=config_type or 'general',
                    description=description,
                    requires_restart=requires_restart,
                    created_by=updated_by_user_id,
                    updated_by=updated_by_user_id
                )
                self.db.add(config_record)
                old_values = None
                action = "create_system_config"
            
            await self.db.flush()
            
            # Log the configuration change
            await self._log_admin_action(
                admin_user_id=updated_by_user_id,
                action=action,
                resource_type="system_config",
                resource_id=config_key,
                old_values=old_values,
                new_values={
                    "config_value": config_value,
                    "config_type": config_type,
                    "description": description,
                    "requires_restart": requires_restart
                }
            )
            
            return config_record
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update system config: {str(e)}")
    
    async def get_all_system_configs(
        self, 
        config_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[SystemConfiguration]:
        """Get all system configurations"""
        query = select(SystemConfiguration)
        
        if active_only:
            query = query.where(SystemConfiguration.is_active == True)
        
        if config_type:
            query = query.where(SystemConfiguration.config_type == config_type)
        
        query = query.order_by(SystemConfiguration.config_key)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    # ==========================================
    # ADMIN NOTIFICATIONS
    # ==========================================
    
    async def create_admin_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        severity: str = 'info',
        data: Optional[Dict[str, Any]] = None,
        target_admin_role: Optional[str] = None
    ) -> AdminNotification:
        """Create a new admin notification"""
        try:
            notification = AdminNotification(
                notification_type=notification_type,
                title=title,
                message=message,
                severity=severity,
                data=data or {},
                target_admin_role=target_admin_role
            )
            
            self.db.add(notification)
            await self.db.flush()
            
            return notification
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create admin notification: {str(e)}")
    
    async def get_admin_notifications(
        self,
        admin_role: Optional[str] = None,
        notification_type: Optional[str] = None,
        severity: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[AdminNotification]:
        """Get admin notifications with filtering"""
        query = select(AdminNotification)
        
        if admin_role:
            query = query.where(or_(
                AdminNotification.target_admin_role.is_(None),
                AdminNotification.target_admin_role == admin_role
            ))
        
        if notification_type:
            query = query.where(AdminNotification.notification_type == notification_type)
        
        if severity:
            query = query.where(AdminNotification.severity == severity)
        
        if unread_only:
            query = query.where(AdminNotification.is_read == False)
        
        query = query.where(AdminNotification.is_dismissed == False)
        query = query.order_by(desc(AdminNotification.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def mark_notification_read(self, notification_id: int) -> AdminNotification:
        """Mark notification as read"""
        result = await self.db.execute(
            select(AdminNotification).where(AdminNotification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise ValueError(f"Notification with ID {notification_id} not found")
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        
        return notification
    
    async def dismiss_notification(self, notification_id: int) -> AdminNotification:
        """Dismiss notification"""
        result = await self.db.execute(
            select(AdminNotification).where(AdminNotification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise ValueError(f"Notification with ID {notification_id} not found")
        
        notification.is_dismissed = True
        notification.dismissed_at = datetime.utcnow()
        
        return notification
    
    # ==========================================
    # USER MANAGEMENT
    # ==========================================
    
    async def get_user_list(
        self,
        page: int = 1,
        limit: int = 50,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc'
    ) -> Dict[str, Any]:
        """Get paginated user list with search and filtering"""
        try:
            offset = (page - 1) * limit
            
            # Base query joining auth users with user profiles
            base_query = (
                select(AuthUser, UserProfile)
                .outerjoin(UserProfile, AuthUser.id == UserProfile.user_id)
            )
            
            # Apply search filter
            if search:
                base_query = base_query.where(or_(
                    AuthUser.email.ilike(f'%{search}%'),
                    UserProfile.full_name.ilike(f'%{search}%'),
                    UserProfile.company.ilike(f'%{search}%')
                ))
            
            # Apply sorting
            sort_column = getattr(AuthUser, sort_by) if hasattr(AuthUser, sort_by) else AuthUser.created_at
            order_func = desc if sort_order.lower() == 'desc' else asc
            query = base_query.order_by(order_func(sort_column))
            
            # Get total count
            count_query = select(func.count()).select_from(base_query.subquery())
            total_result = await self.db.execute(count_query)
            total_users = total_result.scalar()
            
            # Get paginated results
            paginated_query = query.offset(offset).limit(limit)
            result = await self.db.execute(paginated_query)
            users_data = result.all()
            
            # Process user data
            users = []
            for auth_user, user_profile in users_data:
                # Get user credits
                credits_result = await self.db.execute(
                    select(func.coalesce(func.sum(CreditTransaction.amount), 0))
                    .where(and_(
                        CreditTransaction.user_id == auth_user.id,
                        CreditTransaction.type == 'credit'
                    ))
                )
                total_credits = credits_result.scalar() or 0
                
                used_credits_result = await self.db.execute(
                    select(func.coalesce(func.sum(CreditTransaction.amount), 0))
                    .where(and_(
                        CreditTransaction.user_id == auth_user.id,
                        CreditTransaction.type == 'debit'
                    ))
                )
                used_credits = used_credits_result.scalar() or 0
                
                # Get profile access count
                profile_access_result = await self.db.execute(
                    select(func.count(UserProfileAccess.id))
                    .where(UserProfileAccess.user_id == auth_user.id)
                )
                profile_access_count = profile_access_result.scalar() or 0
                
                users.append({
                    "id": str(auth_user.id),
                    "email": auth_user.email,
                    "created_at": auth_user.created_at.isoformat() if auth_user.created_at else None,
                    "full_name": user_profile.full_name if user_profile else None,
                    "company": user_profile.company if user_profile else None,
                    "total_credits": int(total_credits),
                    "available_credits": int(total_credits - used_credits),
                    "used_credits": int(used_credits),
                    "profile_access_count": profile_access_count,
                    "last_active": None  # Would need to track this separately
                })
            
            return {
                "users": users,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_users": total_users,
                    "total_pages": (total_users + limit - 1) // limit,
                    "has_next": page * limit < total_users,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            raise Exception(f"Failed to get user list: {str(e)}")
    
    async def update_user_credits(
        self,
        user_id: str,
        credit_amount: int,
        admin_user_id: str,
        reason: str = "Admin credit adjustment"
    ) -> Dict[str, Any]:
        """Update user credits (add or subtract)"""
        try:
            # Create credit transaction
            transaction = CreditTransaction(
                user_id=user_id,
                amount=abs(credit_amount),
                type='credit' if credit_amount > 0 else 'debit',
                description=reason,
                transaction_type='admin_adjustment',
                metadata={'admin_user_id': admin_user_id, 'reason': reason}
            )
            
            self.db.add(transaction)
            await self.db.flush()
            
            # Record admin action
            await self.db.execute(
                insert(AdminUserAction).values(
                    admin_user_id=admin_user_id,
                    target_user_id=user_id,
                    action='update_credits',
                    reason=reason,
                    action_data={
                        'credit_amount': credit_amount,
                        'transaction_id': str(transaction.id)
                    }
                )
            )
            
            # Log admin action
            await self._log_admin_action(
                admin_user_id=admin_user_id,
                action="update_user_credits",
                resource_type="user",
                resource_id=user_id,
                new_values={
                    "credit_amount": credit_amount,
                    "reason": reason,
                    "transaction_id": str(transaction.id)
                }
            )
            
            # Get updated credit balance
            balance_result = await self.db.execute(
                select(func.coalesce(func.sum(
                    func.case(
                        (CreditTransaction.type == 'credit', CreditTransaction.amount),
                        else_=-CreditTransaction.amount
                    )
                ), 0))
                .where(CreditTransaction.user_id == user_id)
            )
            new_balance = balance_result.scalar()
            
            return {
                "transaction_id": str(transaction.id),
                "credit_amount": credit_amount,
                "new_balance": int(new_balance),
                "reason": reason
            }
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update user credits: {str(e)}")
    
    # ==========================================
    # FEATURE FLAGS
    # ==========================================
    
    async def create_feature_flag(
        self,
        flag_name: str,
        flag_description: Optional[str] = None,
        is_enabled: bool = False,
        rollout_percentage: int = 0,
        target_users: Optional[List[str]] = None,
        conditions: Optional[Dict[str, Any]] = None,
        created_by_user_id: Optional[str] = None
    ) -> FeatureFlag:
        """Create a new feature flag"""
        try:
            feature_flag = FeatureFlag(
                flag_name=flag_name,
                flag_description=flag_description,
                is_enabled=is_enabled,
                rollout_percentage=rollout_percentage,
                target_users=target_users or [],
                conditions=conditions or {},
                created_by=created_by_user_id,
                updated_by=created_by_user_id
            )
            
            self.db.add(feature_flag)
            await self.db.flush()
            
            # Log the creation
            await self._log_admin_action(
                admin_user_id=created_by_user_id,
                action="create_feature_flag",
                resource_type="feature_flag",
                resource_id=str(feature_flag.id),
                new_values={
                    "flag_name": flag_name,
                    "is_enabled": is_enabled,
                    "rollout_percentage": rollout_percentage
                }
            )
            
            return feature_flag
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create feature flag: {str(e)}")
    
    async def update_feature_flag(
        self,
        flag_id: int,
        is_enabled: Optional[bool] = None,
        rollout_percentage: Optional[int] = None,
        target_users: Optional[List[str]] = None,
        conditions: Optional[Dict[str, Any]] = None,
        updated_by_user_id: Optional[str] = None
    ) -> FeatureFlag:
        """Update feature flag settings"""
        try:
            result = await self.db.execute(
                select(FeatureFlag).where(FeatureFlag.id == flag_id)
            )
            feature_flag = result.scalar_one_or_none()
            
            if not feature_flag:
                raise ValueError(f"Feature flag with ID {flag_id} not found")
            
            # Store old values
            old_values = {
                "is_enabled": feature_flag.is_enabled,
                "rollout_percentage": feature_flag.rollout_percentage,
                "target_users": feature_flag.target_users,
                "conditions": feature_flag.conditions
            }
            
            # Update fields
            if is_enabled is not None:
                feature_flag.is_enabled = is_enabled
            if rollout_percentage is not None:
                feature_flag.rollout_percentage = rollout_percentage
            if target_users is not None:
                feature_flag.target_users = target_users
            if conditions is not None:
                feature_flag.conditions = conditions
            
            feature_flag.updated_by = updated_by_user_id
            feature_flag.updated_at = datetime.utcnow()
            
            # Log the update
            await self._log_admin_action(
                admin_user_id=updated_by_user_id,
                action="update_feature_flag",
                resource_type="feature_flag",
                resource_id=str(feature_flag.id),
                old_values=old_values,
                new_values={
                    "is_enabled": feature_flag.is_enabled,
                    "rollout_percentage": feature_flag.rollout_percentage,
                    "target_users": feature_flag.target_users,
                    "conditions": feature_flag.conditions
                }
            )
            
            return feature_flag
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update feature flag: {str(e)}")
    
    async def get_all_feature_flags(self) -> List[FeatureFlag]:
        """Get all feature flags"""
        result = await self.db.execute(
            select(FeatureFlag)
            .order_by(FeatureFlag.flag_name)
        )
        return result.scalars().all()
    
    async def is_feature_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """Check if feature flag is enabled for user"""
        try:
            result = await self.db.execute(
                select(FeatureFlag).where(FeatureFlag.flag_name == flag_name)
            )
            feature_flag = result.scalar_one_or_none()
            
            if not feature_flag or not feature_flag.is_enabled:
                return False
            
            # Check if user is specifically targeted
            if user_id and user_id in (feature_flag.target_users or []):
                return True
            
            # Check rollout percentage (simplified random check)
            if feature_flag.rollout_percentage >= 100:
                return True
            elif feature_flag.rollout_percentage <= 0:
                return False
            
            # Simple hash-based consistent rollout
            if user_id:
                user_hash = hash(f"{flag_name}_{user_id}") % 100
                return user_hash < feature_flag.rollout_percentage
            
            return False
            
        except Exception as e:
            return False
    
    # ==========================================
    # SYSTEM AUDIT AND MAINTENANCE
    # ==========================================
    
    async def get_audit_logs(
        self,
        admin_user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get system audit logs with filtering and pagination"""
        try:
            offset = (page - 1) * limit
            
            query = select(SystemAuditLog).options(selectinload(SystemAuditLog.admin_user))
            
            if admin_user_id:
                query = query.where(SystemAuditLog.admin_user_id == admin_user_id)
            if resource_type:
                query = query.where(SystemAuditLog.resource_type == resource_type)
            if action:
                query = query.where(SystemAuditLog.action == action)
            if start_date:
                query = query.where(SystemAuditLog.created_at >= start_date)
            if end_date:
                query = query.where(SystemAuditLog.created_at <= end_date)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total_logs = total_result.scalar()
            
            # Get paginated results
            paginated_query = query.order_by(desc(SystemAuditLog.created_at)).offset(offset).limit(limit)
            result = await self.db.execute(paginated_query)
            audit_logs = result.scalars().all()
            
            return {
                "audit_logs": [
                    {
                        "id": log.id,
                        "admin_user_id": str(log.admin_user_id) if log.admin_user_id else None,
                        "action": log.action,
                        "resource_type": log.resource_type,
                        "resource_id": log.resource_id,
                        "old_values": log.old_values,
                        "new_values": log.new_values,
                        "ip_address": log.ip_address,
                        "result": log.result,
                        "error_message": log.error_message,
                        "created_at": log.created_at.isoformat()
                    }
                    for log in audit_logs
                ],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_logs": total_logs,
                    "total_pages": (total_logs + limit - 1) // limit,
                    "has_next": page * limit < total_logs,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            raise Exception(f"Failed to get audit logs: {str(e)}")
    
    async def create_maintenance_job(
        self,
        job_name: str,
        job_type: str,
        scheduled_at: datetime,
        job_config: Optional[Dict[str, Any]] = None,
        created_by_user_id: Optional[str] = None
    ) -> SystemMaintenanceJob:
        """Create a new maintenance job"""
        try:
            maintenance_job = SystemMaintenanceJob(
                job_name=job_name,
                job_type=job_type,
                scheduled_at=scheduled_at,
                job_config=job_config or {},
                created_by=created_by_user_id
            )
            
            self.db.add(maintenance_job)
            await self.db.flush()
            
            # Log the creation
            await self._log_admin_action(
                admin_user_id=created_by_user_id,
                action="create_maintenance_job",
                resource_type="maintenance_job",
                resource_id=str(maintenance_job.id),
                new_values={
                    "job_name": job_name,
                    "job_type": job_type,
                    "scheduled_at": scheduled_at.isoformat(),
                    "job_config": job_config
                }
            )
            
            return maintenance_job
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create maintenance job: {str(e)}")
    
    async def get_maintenance_jobs(
        self,
        job_status: Optional[str] = None,
        job_type: Optional[str] = None
    ) -> List[SystemMaintenanceJob]:
        """Get maintenance jobs with optional filtering"""
        query = select(SystemMaintenanceJob)
        
        if job_status:
            query = query.where(SystemMaintenanceJob.job_status == job_status)
        if job_type:
            query = query.where(SystemMaintenanceJob.job_type == job_type)
        
        query = query.order_by(desc(SystemMaintenanceJob.scheduled_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    # ==========================================
    # PRIVATE HELPER METHODS
    # ==========================================
    
    async def _log_admin_action(
        self,
        admin_user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        result: str = 'success',
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log admin action to audit trail"""
        try:
            audit_log = SystemAuditLog(
                admin_user_id=admin_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                result=result,
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.db.add(audit_log)
            await self.db.flush()
            
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            pass
    
    async def _calculate_trends(self, recent_analytics: List[SystemAnalytics]) -> Dict[str, Any]:
        """Calculate trends from recent analytics data"""
        if len(recent_analytics) < 2:
            return {}
        
        # Get current and previous values
        current = recent_analytics[0]
        previous = recent_analytics[1]
        
        def calculate_percentage_change(current_val, previous_val):
            if previous_val == 0:
                return 100.0 if current_val > 0 else 0.0
            return ((current_val - previous_val) / previous_val) * 100
        
        return {
            "users_growth": calculate_percentage_change(current.total_users, previous.total_users),
            "active_users_change": calculate_percentage_change(current.active_users, previous.active_users),
            "api_requests_change": calculate_percentage_change(current.api_requests, previous.api_requests),
            "credits_consumption_change": calculate_percentage_change(
                current.credits_consumed, previous.credits_consumed
            ),
            "error_rate_change": float(current.error_rate_percentage) - float(previous.error_rate_percentage),
            "cache_hit_rate_change": float(current.cache_hit_rate_percentage) - float(previous.cache_hit_rate_percentage)
        }