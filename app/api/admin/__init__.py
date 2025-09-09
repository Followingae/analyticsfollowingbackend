"""
Admin API Module - Industry Standard Administrative Interface
Comprehensive admin dashboard and management capabilities
"""
# Import only the working routes for now
from fastapi import APIRouter

# Create main admin router (minimal for now)
admin_router = APIRouter(prefix="/admin", tags=["Administration"])

# Only include working routes - superadmin_dashboard_routes is imported directly in main.py
# Other routes will be added when their dependencies are fixed

__all__ = ["admin_router"]