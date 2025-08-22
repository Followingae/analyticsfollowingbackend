"""
TEMPORARY Legacy Credit Routes for Frontend Compatibility
These routes provide backward compatibility for frontend calling /api/v1/api/credits/* endpoints
TODO: Remove once frontend is updated to use correct /api/v1/credits/* paths
"""
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.services.credit_wallet_service import credit_wallet_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Credits (Legacy)"])

@router.get("/balance")
async def get_credit_balance_legacy(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Legacy endpoint for /api/v1/api/credits/balance (frontend compatibility)"""
    user_id = UUID(str(current_user.id))
    
    try:
        balance = await credit_wallet_service.get_wallet_balance(user_id)
        return balance
    except Exception as e:
        logger.error(f"Error getting balance for user {user_id}: {e}")
        
        # If wallet doesn't exist, create a basic response
        return {
            "balance": 0,
            "is_locked": True,
            "next_reset_date": "2025-08-21"
        }