"""
Operations OS Authentication & Authorization Middleware
Role-based access control for Campaign Operations
"""
from fastapi import HTTPException, status, Depends
from typing import Optional, Dict, Any, List
from app.middleware.auth_middleware import get_current_active_user
from app.models.operations_models import OperationsPermissions, OperationsAccess
import logging

logger = logging.getLogger(__name__)


class OperationsPermissionError(HTTPException):
    """Custom exception for operations permission errors"""
    def __init__(self, detail: str, required_role: str = None, user_role: str = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Insufficient permissions",
                "message": detail,
                "required_role": required_role,
                "user_role": user_role
            }
        )


def get_operations_permissions(role: str) -> OperationsPermissions:
    """
    Get operations permissions based on user role

    Role Mapping:
    - super_admin: Full access to everything
    - standard/premium: Client access (limited view)
    - free: Most limited client access
    - Others: No access
    """

    # Superadmin permissions - FULL ACCESS
    if role in ['super_admin', 'superadmin']:
        return OperationsPermissions(
            view_internal_notes=True,
            view_finance=True,
            view_banking=True,
            create_workstreams=True,
            create_deliverables=True,
            approve_concepts=True,
            manage_production=True,
            manage_events=True,
            export_data=True,
            bulk_operations=True,
            access_settings=True,
            bypass_approvals=True
        )

    # Premium tier - Client with export
    elif role == 'premium':
        return OperationsPermissions(
            view_internal_notes=False,
            view_finance=False,
            view_banking=False,
            create_workstreams=False,
            create_deliverables=False,
            approve_concepts=True,  # Can approve their own concepts
            manage_production=False,
            manage_events=False,
            export_data=True,  # Premium feature
            bulk_operations=False,
            access_settings=False,
            bypass_approvals=False
        )

    # Standard tier - Client basic
    elif role == 'standard':
        return OperationsPermissions(
            view_internal_notes=False,
            view_finance=False,
            view_banking=False,
            create_workstreams=False,
            create_deliverables=False,
            approve_concepts=True,  # Can approve their own concepts
            manage_production=False,
            manage_events=False,
            export_data=True,  # Standard can export
            bulk_operations=False,
            access_settings=False,
            bypass_approvals=False
        )

    # Free tier - Most limited
    elif role == 'free':
        return OperationsPermissions(
            view_internal_notes=False,
            view_finance=False,
            view_banking=False,
            create_workstreams=False,
            create_deliverables=False,
            approve_concepts=True,  # Can still approve
            manage_production=False,
            manage_events=False,
            export_data=False,  # Cannot export
            bulk_operations=False,
            access_settings=False,
            bypass_approvals=False
        )

    # No access for other roles
    else:
        return OperationsPermissions()  # All False by default


async def get_operations_access(
    current_user = Depends(get_current_active_user)
) -> OperationsAccess:
    """
    Get complete operations access for current user
    """
    permissions = get_operations_permissions(current_user.role)

    # Build campaign access list (would query database for actual campaigns)
    campaign_access = []
    # TODO: Query database for campaigns user has access to

    return OperationsAccess(
        user_id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        subscription_tier=current_user.subscription_tier or current_user.role,
        operations_access=permissions,
        campaign_access=campaign_access,
        team_id=str(current_user.team_id) if hasattr(current_user, 'team_id') else None,
        is_team_admin=getattr(current_user, 'is_team_admin', False)
    )


async def require_superadmin(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> OperationsAccess:
    """
    Require superadmin role for endpoint
    """
    if operations_access.role not in ['super_admin', 'superadmin']:
        raise OperationsPermissionError(
            detail="This operation requires administrator access",
            required_role="super_admin",
            user_role=operations_access.role
        )
    return operations_access


async def require_operations_access(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> OperationsAccess:
    """
    Require any valid operations access (client or admin)
    """
    # Check if user has any operations access
    if operations_access.role in ['creator', 'user'] or not any([
        operations_access.operations_access.approve_concepts,
        operations_access.operations_access.create_workstreams
    ]):
        raise OperationsPermissionError(
            detail="Operations OS requires brand or administrator access",
            user_role=operations_access.role
        )
    return operations_access


async def require_permission(permission_name: str):
    """
    Factory function to create permission checkers

    Usage:
    @router.post("/workstreams", dependencies=[Depends(require_permission("create_workstreams"))])
    """
    async def permission_checker(
        operations_access: OperationsAccess = Depends(get_operations_access)
    ) -> OperationsAccess:
        if not getattr(operations_access.operations_access, permission_name, False):
            raise OperationsPermissionError(
                detail=f"Permission '{permission_name}' is required for this operation",
                required_role="super_admin" if permission_name in [
                    'create_workstreams', 'create_deliverables', 'manage_production',
                    'manage_events', 'bulk_operations', 'access_settings', 'view_finance'
                ] else None,
                user_role=operations_access.role
            )
        return operations_access

    return permission_checker


def filter_response_by_role(data: Dict[str, Any], role: str) -> Dict[str, Any]:
    """
    Filter response data based on user role
    Removes sensitive fields for non-superadmin users
    """
    if role in ['super_admin', 'superadmin']:
        # Superadmins see everything
        return data

    # Fields to remove for clients
    sensitive_fields = [
        'internal_notes',
        'banking_details',
        'budget_allocated',
        'budget_spent',
        'reliability_score',
        'contact_info',
        'payment_info',
        'bypass_reason',
        'bypassed_by',
        'frame_io_folder',
        'raw_files',
        'call_time',
        'wrap_time',
        'roster',
        'checklist_items',
        'internal_version',
        'barter_inventory',
        'barter_allocated',
        'shortlist'
    ]

    # Recursively remove sensitive fields
    def remove_fields(obj):
        if isinstance(obj, dict):
            return {
                k: remove_fields(v)
                for k, v in obj.items()
                if k not in sensitive_fields
            }
        elif isinstance(obj, list):
            return [remove_fields(item) for item in obj]
        else:
            return obj

    return remove_fields(data)


def add_access_metadata(data: Dict[str, Any], operations_access: OperationsAccess) -> Dict[str, Any]:
    """
    Add _access metadata to response
    """
    if isinstance(data, dict):
        data['_access'] = {
            'user_role': operations_access.role,
            'view_mode': 'superadmin' if operations_access.role in ['super_admin', 'superadmin'] else 'client',
            'can_create': operations_access.operations_access.create_workstreams,
            'can_edit': operations_access.operations_access.create_deliverables,
            'can_delete': operations_access.operations_access.bulk_operations,
            'can_export': operations_access.operations_access.export_data
        }
    return data


def filter_activities_by_visibility(
    activities: List[Dict[str, Any]],
    is_superadmin: bool
) -> List[Dict[str, Any]]:
    """
    Filter activity logs based on visibility
    Clients only see activities where is_client_visible=True
    """
    if is_superadmin:
        return activities

    return [
        activity for activity in activities
        if activity.get('is_client_visible', True)
    ]


def check_campaign_access(
    campaign_id: str,
    operations_access: OperationsAccess,
    required_access: str = "viewer"
) -> bool:
    """
    Check if user has access to a specific campaign

    Access levels:
    - owner: Can do everything
    - collaborator: Can edit/manage
    - viewer: Can only view
    """
    # Superadmins always have access
    if operations_access.role in ['super_admin', 'superadmin']:
        return True

    # Check campaign access list
    for access in operations_access.campaign_access:
        if access.get('campaign_id') == campaign_id:
            user_access = access.get('access_type', 'viewer')

            # Check access hierarchy
            if required_access == 'viewer':
                return True  # Any access level can view
            elif required_access == 'collaborator':
                return user_access in ['owner', 'collaborator']
            elif required_access == 'owner':
                return user_access == 'owner'

    return False


# Export convenience functions for common checks
async def can_create_workstreams(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> bool:
    """Check if user can create workstreams"""
    return operations_access.operations_access.create_workstreams


async def can_view_finance(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> bool:
    """Check if user can view finance data"""
    return operations_access.operations_access.view_finance


async def can_approve_concepts(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> bool:
    """Check if user can approve concepts"""
    return operations_access.operations_access.approve_concepts


async def can_export_data(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> bool:
    """Check if user can export data"""
    return operations_access.operations_access.export_data