"""
Admin API Module - Industry Standard Administrative Interface
Comprehensive admin dashboard and management capabilities
"""
from fastapi import APIRouter
from .user_management_routes import router as user_management_router
from .financial_management_routes import router as financial_management_router  
from .proposal_management_routes import router as proposal_management_router
from .system_monitoring_routes import router as system_monitoring_router

# Create main admin router
admin_router = APIRouter(prefix="/admin", tags=["Administration"])

# Include all admin sub-routers
admin_router.include_router(user_management_router)
admin_router.include_router(financial_management_router)
admin_router.include_router(proposal_management_router)
admin_router.include_router(system_monitoring_router)

__all__ = ["admin_router"]