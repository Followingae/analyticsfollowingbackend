"""
Credit Management API Routes
Comprehensive credit system endpoints for wallet, transaction, and pricing management
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body
from fastapi.responses import JSONResponse

from app.middleware.auth_middleware import get_current_user as get_current_active_user
from app.models.auth import UserInDB
from app.models.credits import (
    CreditBalance, CreditWalletSummary, CreditDashboard,
    CreditTransactionSummary, MonthlyUsageSummary,
    CreditPricingRule, CanPerformActionResponse,
    CreditActionRequest, CreditActionResponse, TotalPlanCredits
)
from app.services.credit_wallet_service import credit_wallet_service
from app.services.credit_transaction_service import credit_transaction_service
from app.services.credit_pricing_service import credit_pricing_service
from app.services.currency_service import currency_service
from app.middleware.credit_gate import check_credits_only

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/credits", tags=["Credits"])


# =============================================================================
# CREDIT BALANCE & WALLET ENDPOINTS
# =============================================================================

@router.get("/balance", response_model=CreditBalance)
async def get_credit_balance(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get user's current credit balance"""
    user_id = UUID(str(current_user.id))
    
    try:
        balance = await credit_wallet_service.get_wallet_balance(user_id)
        return balance
    except Exception as e:
        logger.error(f"Error getting balance for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving credit balance")


@router.get("/total-plan-credits", response_model=TotalPlanCredits)
async def get_total_plan_credits(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get Total Plan Credits breakdown showing:
    - Package credits from monthly allowance
    - Purchased credits from payments
    - Bonus credits from promotions
    - Total available credits (sum of all)
    """
    user_id = UUID(str(current_user.id))
    
    try:
        total_plan_credits = await credit_wallet_service.get_total_plan_credits(user_id)
        if not total_plan_credits:
            raise HTTPException(status_code=404, detail="Credit wallet not found")
        
        return total_plan_credits
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting total plan credits for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving total plan credits")


@router.get("/wallet/summary", response_model=CreditWalletSummary)
async def get_wallet_summary(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get comprehensive wallet summary"""
    user_id = UUID(str(current_user.id))
    
    try:
        summary = await credit_wallet_service.get_wallet_summary(user_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Credit wallet not found")
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting wallet summary for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving wallet summary")


@router.get("/dashboard", response_model=CreditDashboard)
async def get_credit_dashboard(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get complete credit dashboard data"""
    user_id = UUID(str(current_user.id))
    
    try:
        # Get wallet summary
        wallet_summary = await credit_wallet_service.get_wallet_summary(user_id)
        if not wallet_summary:
            raise HTTPException(status_code=404, detail="Credit wallet not found")
        
        # Get recent transactions
        recent_transactions = await credit_transaction_service.get_transaction_history(
            user_id, limit=20
        )
        
        # Get monthly usage
        monthly_usage = await credit_transaction_service.get_monthly_usage_summary(user_id)
        
        # Get pricing rules
        pricing_rules = await credit_pricing_service.get_all_pricing_rules()
        
        # Get unlocked influencers count
        unlocked_count = await credit_wallet_service.get_unlocked_influencers_count(user_id)
        
        dashboard = CreditDashboard(
            wallet=wallet_summary,
            recent_transactions=recent_transactions,
            monthly_usage=monthly_usage.dict() if monthly_usage else {},
            pricing_rules=pricing_rules or [],
            unlocked_influencers_count=unlocked_count or 0
        )
        
        return dashboard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving credit dashboard")


# =============================================================================
# TRANSACTION HISTORY ENDPOINTS
# =============================================================================

@router.get("/transactions", response_model=List[CreditTransactionSummary])
async def get_transaction_history(
    limit: int = Query(50, ge=1, le=100, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
    transaction_types: Optional[str] = Query(None, description="Comma-separated transaction types"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get paginated transaction history with filters"""
    user_id = UUID(str(current_user.id))
    
    try:
        # Parse transaction types
        type_filter = None
        if transaction_types:
            type_filter = [t.strip() for t in transaction_types.split(",")]
        
        transactions = await credit_transaction_service.get_transaction_history(
            user_id=user_id,
            limit=limit,
            offset=offset,
            transaction_types=type_filter,
            start_date=start_date,
            end_date=end_date
        )
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error getting transaction history for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving transaction history")


@router.get("/transactions/search", response_model=List[CreditTransactionSummary])
async def search_transactions(
    search: Optional[str] = Query(None, description="Search term"),
    action_types: Optional[str] = Query(None, description="Comma-separated action types"),
    min_amount: Optional[int] = Query(None, description="Minimum amount filter"),
    max_amount: Optional[int] = Query(None, description="Maximum amount filter"),
    limit: int = Query(50, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Advanced transaction search"""
    user_id = UUID(str(current_user.id))
    
    try:
        # Parse filters
        action_filter = None
        if action_types:
            action_filter = [t.strip() for t in action_types.split(",")]
        
        amount_range = None
        if min_amount is not None or max_amount is not None:
            amount_range = (min_amount or 0, max_amount or 999999)
        
        transactions = await credit_transaction_service.search_transactions(
            user_id=user_id,
            search_term=search,
            action_types=action_filter,
            amount_range=amount_range,
            limit=limit
        )
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error searching transactions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error searching transactions")


# =============================================================================
# USAGE ANALYTICS ENDPOINTS
# =============================================================================

@router.get("/usage/monthly", response_model=MonthlyUsageSummary)
async def get_monthly_usage(
    month_year: Optional[str] = Query(None, description="Month in YYYY-MM format"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get monthly usage summary"""
    user_id = UUID(str(current_user.id))
    
    try:
        # Parse month_year if provided
        target_month = None
        if month_year:
            try:
                year, month = month_year.split("-")
                target_month = date(int(year), int(month), 1)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
        
        usage_summary = await credit_transaction_service.get_monthly_usage_summary(
            user_id, target_month
        )
        
        if not usage_summary:
            # Return empty usage summary if none found
            return {"user_id": str(user_id), "month": str(target_month or date.today().replace(day=1)), "actions": []}
        
        return usage_summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting monthly usage for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving monthly usage")


@router.get("/analytics/spending")
async def get_spending_analytics(
    months: int = Query(6, ge=1, le=24, description="Number of months to analyze"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get comprehensive spending analytics"""
    user_id = UUID(str(current_user.id))
    
    try:
        analytics = await credit_transaction_service.get_spending_analytics(user_id, months)
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting spending analytics for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving spending analytics")


# =============================================================================
# ACTION PERMISSION & PRICING ENDPOINTS
# =============================================================================

@router.get("/can-perform/{action_type}", response_model=CanPerformActionResponse)
async def check_action_permission(
    action_type: str = Path(..., description="Action type to check"),
    credits_required: Optional[int] = Query(None, description="Override default cost"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Check if user can perform a credit-gated action"""
    user_id = UUID(str(current_user.id))
    
    try:
        permission = await check_credits_only(user_id, action_type, credits_required)
        return permission
        
    except Exception as e:
        logger.error(f"Error checking action permission for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error checking action permission")


@router.get("/pricing", response_model=List[CreditPricingRule])
async def get_pricing_rules(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get all active pricing rules"""
    try:
        rules = await credit_pricing_service.get_all_pricing_rules()
        return rules
        
    except Exception as e:
        logger.error(f"Error getting pricing rules: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving pricing rules")


@router.get("/pricing/{action_type}")
async def get_action_pricing(
    action_type: str = Path(..., description="Action type"),
    quantity: int = Query(1, ge=1, description="Quantity for bulk pricing"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get pricing information for a specific action"""
    try:
        pricing = await credit_pricing_service.get_action_cost(action_type, quantity)
        return pricing
        
    except Exception as e:
        logger.error(f"Error getting pricing for action {action_type}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving action pricing")


@router.post("/pricing/calculate")
async def calculate_bulk_pricing(
    actions: List[Dict[str, Any]] = Body(..., description="List of {action_type, quantity}"),
    user_id_for_allowances: Optional[bool] = Body(False, description="Include user allowances"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Calculate bulk pricing for multiple actions"""
    user_id = UUID(str(current_user.id))
    
    try:
        if user_id_for_allowances:
            # Calculate considering user's free allowances
            total_cost = 0
            detailed_breakdown = []
            
            for action in actions:
                action_type = action.get("action_type")
                quantity = action.get("quantity", 1)
                
                if not action_type:
                    continue
                
                calculation = await credit_pricing_service.calculate_required_credits(
                    user_id, action_type, quantity
                )
                detailed_breakdown.append(calculation)
                total_cost += calculation.get("credits_required", 0)
            
            return {
                "total_cost": total_cost,
                "detailed_breakdown": detailed_breakdown,
                "includes_user_allowances": True
            }
        else:
            # Standard bulk pricing
            bulk_pricing = await credit_pricing_service.get_bulk_pricing(actions)
            return bulk_pricing
            
    except Exception as e:
        logger.error(f"Error calculating bulk pricing for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error calculating pricing")


# =============================================================================
# ALLOWANCE STATUS ENDPOINTS
# =============================================================================

@router.get("/allowances")
async def get_allowance_status(
    month_year: Optional[str] = Query(None, description="Month in YYYY-MM format"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get free allowance status for all actions"""
    user_id = UUID(str(current_user.id))
    
    try:
        # Parse month_year if provided
        target_month = None
        if month_year:
            try:
                year, month = month_year.split("-")
                target_month = date(int(year), int(month), 1)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
        
        status = await credit_pricing_service.get_user_allowance_status(user_id, target_month)
        
        if not status:
            # Return empty allowance status if none found
            return {"user_id": str(user_id), "month": str(target_month or date.today().replace(day=1)), "allowances": []}
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting allowance status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving allowance status")


# =============================================================================
# CREDIT TOP-UP ENDPOINTS (Prepare for Stripe integration)
# =============================================================================

@router.post("/top-up/estimate")
async def estimate_credit_purchase(
    credits_amount: int = Body(..., ge=1, description="Number of credits to purchase"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Estimate cost for credit purchase (prepare for Stripe)"""
    try:
        # TODO: Implement actual pricing logic when Stripe is integrated
        # For now, return placeholder pricing
        price_per_credit = 0.01  # $0.01 per credit
        total_price_usd = credits_amount * price_per_credit
        
        # Get user's currency for proper formatting
        user_currency = await currency_service.get_user_currency(str(current_user.id))
        total_price_cents = int(total_price_usd * 100)  # Convert to cents
        formatted_total = await currency_service.format_amount(
            total_price_cents,
            currency_info=user_currency
        )

        return {
            "credits_amount": credits_amount,
            "price_per_credit_cents": int(price_per_credit * 100),
            "total_price_cents": total_price_cents,
            "total_price_formatted": formatted_total,
            "currency_info": user_currency,
            "estimated": True,
            "message": "Pricing estimation - Stripe integration pending"
        }
        
    except Exception as e:
        logger.error(f"Error estimating credit purchase: {e}")
        raise HTTPException(status_code=500, detail="Error estimating purchase cost")


@router.get("/top-up/history")
async def get_top_up_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get credit purchase history (placeholder for future Stripe integration)"""
    try:
        # TODO: Implement when credit top-up orders are integrated
        return {
            "orders": [],
            "total_orders": 0,
            "message": "Top-up history - Stripe integration pending"
        }
        
    except Exception as e:
        logger.error(f"Error getting top-up history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving purchase history")


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@router.get("/system/stats")
async def get_credit_system_stats(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get system-wide credit statistics (for admin use)"""
    try:
        # Only return basic stats for regular users
        # TODO: Add admin check when admin roles are implemented
        
        pricing_analytics = await credit_pricing_service.get_pricing_analytics()
        
        return {
            "user_accessible_stats": {
                "total_action_types": len(pricing_analytics.get("action_analytics", [])),
                "period": pricing_analytics.get("period"),
                "top_actions": pricing_analytics.get("highest_conversion_actions", [])[:3]
            },
            "message": "Limited stats for regular users"
        }
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving system statistics")


@router.post("/wallet/create")
async def create_wallet(
    package_id: Optional[int] = Body(None, description="Credit package ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Create credit wallet for user (if they don't have one)"""
    user_id = UUID(str(current_user.id))
    
    try:
        # Check if user already has a wallet
        existing_wallet = await credit_wallet_service.get_wallet(user_id)
        if existing_wallet:
            return {
                "message": "Wallet already exists",
                "wallet_id": existing_wallet.id,
                "current_balance": existing_wallet.current_balance
            }
        
        # Create new wallet
        wallet = await credit_wallet_service.create_wallet(
            user_id=user_id,
            package_id=package_id,
            initial_balance=0
        )
        
        return {
            "message": "Wallet created successfully",
            "wallet_id": wallet.id,
            "current_balance": wallet.current_balance,
            "package_id": wallet.package_id
        }
        
    except Exception as e:
        logger.error(f"Error creating wallet for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error creating credit wallet")