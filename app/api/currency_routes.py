"""
Currency Management API Routes
Provides superadmin endpoints for managing team currencies
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.currency_service import currency_service
from app.models.auth import UserInDB

def require_superadmin(current_user: UserInDB = Depends(get_current_active_user)):
    """Enforce superadmin role requirement"""
    if current_user.role not in ['admin', 'superadmin', 'super_admin']:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Requires superadmin role, user has '{current_user.role}' role"
        )
    return current_user

router = APIRouter(prefix="/api/v1/currency", tags=["Currency Management"])

class CurrencySettingsResponse(BaseModel):
    """Response model for currency settings"""
    team_id: str
    currency_code: str = Field(..., description="3-letter currency code (e.g., USD, EUR)")
    currency_symbol: str = Field(..., description="Currency symbol (e.g., $, €)")
    decimal_places: int = Field(..., description="Number of decimal places")

class UpdateCurrencyRequest(BaseModel):
    """Request model for updating team currency"""
    currency_code: str = Field(..., min_length=3, max_length=3, description="3-letter currency code")
    currency_symbol: Optional[str] = Field(None, description="Currency symbol (auto-detected if not provided)")
    decimal_places: int = Field(2, ge=0, le=4, description="Number of decimal places (0-4)")

class CurrencyFormatRequest(BaseModel):
    """Request model for formatting currency amounts"""
    amount_cents: int = Field(..., description="Amount in cents/smallest currency unit")
    team_id: Optional[str] = Field(None, description="Team ID to get currency for")

class CurrencyFormatResponse(BaseModel):
    """Response model for formatted currency"""
    formatted_amount: str = Field(..., description="Formatted currency string")
    currency_info: dict = Field(..., description="Currency information used")

@router.get("/team/{team_id}", response_model=CurrencySettingsResponse)
async def get_team_currency(
    team_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get currency settings for a specific team.
    Available to team members and superadmins.
    """
    try:
        # Get currency settings
        currency_info = await currency_service.get_team_currency(team_id, db)

        return CurrencySettingsResponse(
            team_id=team_id,
            currency_code=currency_info["code"],
            currency_symbol=currency_info["symbol"],
            decimal_places=currency_info["decimal_places"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get team currency: {str(e)}"
        )

@router.get("/user/current", response_model=CurrencySettingsResponse)
async def get_current_user_currency(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get currency settings for the current user's team.
    """
    try:
        # Get currency settings for current user
        currency_info = await currency_service.get_user_currency(str(current_user.id), db)

        return {
            "team_id": current_user.id,  # Using user ID as fallback
            "currency_code": currency_info["code"],
            "currency_symbol": currency_info["symbol"],
            "decimal_places": currency_info["decimal_places"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user currency: {str(e)}"
        )

@router.put("/team/{team_id}", response_model=CurrencySettingsResponse)
async def update_team_currency(
    team_id: str,
    request: UpdateCurrencyRequest,
    current_user: UserInDB = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update currency settings for a team.
    Only available to superadmins.
    """
    try:
        # Update currency settings
        currency_info = await currency_service.update_team_currency(
            team_id=team_id,
            currency_code=request.currency_code.upper(),
            currency_symbol=request.currency_symbol,
            decimal_places=request.decimal_places,
            db=db
        )

        return CurrencySettingsResponse(
            team_id=team_id,
            currency_code=currency_info["code"],
            currency_symbol=currency_info["symbol"],
            decimal_places=currency_info["decimal_places"]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update team currency: {str(e)}"
        )

@router.post("/format", response_model=CurrencyFormatResponse)
async def format_currency_amount(
    request: CurrencyFormatRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Format a currency amount using team/user currency settings.
    """
    try:
        # Get currency info
        if request.team_id:
            currency_info = await currency_service.get_team_currency(request.team_id, db)
        else:
            currency_info = await currency_service.get_user_currency(str(current_user.id), db)

        # Format the amount
        formatted_amount = await currency_service.format_amount(
            amount_cents=request.amount_cents,
            currency_info=currency_info
        )

        return CurrencyFormatResponse(
            formatted_amount=formatted_amount,
            currency_info=currency_info
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to format currency: {str(e)}"
        )

@router.get("/supported", response_model=List[dict])
async def get_supported_currencies(
    current_user: UserInDB = Depends(require_superadmin)
):
    """
    Get list of supported currencies.
    Only available to superadmins.
    """
    supported_currencies = [
        {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
        {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
        {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_places": 2},
        {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "decimal_places": 2},
        {"code": "SAR", "name": "Saudi Riyal", "symbol": "ر.س", "decimal_places": 2},
        {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_places": 0},
        {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "decimal_places": 2},
        {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimal_places": 2},
        {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "decimal_places": 2},
        {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "decimal_places": 2},
    ]

    return supported_currencies

@router.get("/health")
async def currency_service_health():
    """
    Health check for currency service.
    """
    return {
        "status": "healthy",
        "service": "currency_service",
        "default_currency": currency_service.default_currency,
        "cache_ttl": currency_service.cache_ttl
    }