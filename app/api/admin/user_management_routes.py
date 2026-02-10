"""
Comprehensive User Management Routes for Superadmin
Provides full visibility and control over users, subscriptions, and billing
"""
import logging
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.services.user_subscription_service import UserSubscriptionService
from app.services.stripe_subscription_service import StripeSubscriptionService
from app.services.credit_wallet_service import CreditWalletService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/users", tags=["Admin User Management"])


@router.get("/billing/overview")
async def get_billing_overview(
    current_user=Depends(require_admin())
):
    """
    Get comprehensive billing overview for all users

    Returns:
    - Total users by subscription tier
    - Upcoming billing dates for admin-managed users
    - Active Stripe subscriptions
    - Credit usage statistics
    """
    try:
        subscription_service = UserSubscriptionService()
        stripe_service = StripeSubscriptionService()

        # Get all users billing info
        admin_managed = await subscription_service.get_all_users_billing(
            billing_type="admin_managed",
            page_size=100
        )

        online_payment = await subscription_service.get_all_users_billing(
            billing_type="online_payment",
            page_size=100
        )

        # Get upcoming billings (next 30 days)
        upcoming_billings = []
        for user in admin_managed["users"]:
            if user.get("days_until_billing") and 0 <= user["days_until_billing"] <= 30:
                upcoming_billings.append({
                    "email": user["email"],
                    "tier": user["subscription_tier"],
                    "billing_date": user["next_billing_date"],
                    "days_until": user["days_until_billing"]
                })

        # Sort by billing date
        upcoming_billings.sort(key=lambda x: x["billing_date"])

        return {
            "overview": {
                "total_users": admin_managed["total_count"] + online_payment["total_count"],
                "admin_managed_users": admin_managed["total_count"],
                "stripe_users": online_payment["total_count"]
            },
            "tier_distribution": {
                "free": len([u for u in admin_managed["users"] + online_payment["users"] if u["subscription_tier"] == "free"]),
                "standard": len([u for u in admin_managed["users"] + online_payment["users"] if u["subscription_tier"] == "standard"]),
                "premium": len([u for u in admin_managed["users"] + online_payment["users"] if u["subscription_tier"] == "premium"])
            },
            "upcoming_billings": upcoming_billings,
            "admin_managed_summary": {
                "count": admin_managed["total_count"],
                "next_5_billings": upcoming_billings[:5]
            },
            "stripe_summary": {
                "count": online_payment["total_count"],
                "active_subscriptions": len([u for u in online_payment["users"] if u.get("subscription_active")])
            }
        }

    except Exception as e:
        logger.error(f"Failed to get billing overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_all_users(
    billing_type: Optional[str] = Query(None, description="Filter by billing type"),
    subscription_tier: Optional[str] = Query(None, description="Filter by tier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user=Depends(require_admin())
):
    """
    List all users with comprehensive billing and subscription info

    Parameters:
    - billing_type: admin_managed or online_payment
    - subscription_tier: free, standard, or premium
    - page: Page number
    - page_size: Results per page

    Returns paginated list with full user details
    """
    try:
        subscription_service = UserSubscriptionService()

        # Get users with billing info
        result = await subscription_service.get_all_users_billing(
            billing_type=billing_type,
            page=page,
            page_size=page_size
        )

        # Filter by tier if specified
        if subscription_tier:
            result["users"] = [u for u in result["users"] if u["subscription_tier"] == subscription_tier]

        return result

    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/billing")
async def get_user_billing_details(
    user_id: UUID,
    current_user=Depends(require_admin())
):
    """
    Get detailed billing information for a specific user

    Returns:
    - Current subscription details
    - Credit balance and usage
    - Billing cycle information
    - Stripe subscription data (if applicable)
    """
    try:
        subscription_service = UserSubscriptionService()
        stripe_service = StripeSubscriptionService()
        wallet_service = CreditWalletService()

        # Get billing info
        billing_info = await subscription_service.get_user_billing_info(user_id)

        # Get credit balance
        balance = await wallet_service.get_wallet_balance(user_id)

        # Get Stripe data if online payment
        stripe_info = None
        if billing_info["billing_type"] == "online_payment":
            try:
                # Get Stripe subscription details
                stripe_info = await stripe_service.get_user_subscription_details(user_id)
            except:
                stripe_info = {"error": "Could not retrieve Stripe data"}

        return {
            "user_id": str(user_id),
            "email": billing_info["email"],
            "subscription": {
                "tier": billing_info["subscription_tier"],
                "billing_type": billing_info["billing_type"],
                "status": "active" if billing_info["subscription_active"] else "inactive"
            },
            "credits": {
                "current_balance": billing_info["current_balance"],
                "monthly_allowance": billing_info["monthly_allowance"],
                "tier_benefits": billing_info["tier_benefits"]
            },
            "billing_cycle": {
                "start": billing_info["billing_cycle_start"],
                "end": billing_info["billing_cycle_end"],
                "next_billing_date": billing_info["next_billing_date"],
                "days_until_billing": billing_info["days_until_billing"]
            },
            "stripe_data": stripe_info
        }

    except Exception as e:
        logger.error(f"Failed to get user billing details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/billing/update")
async def update_user_billing(
    user_id: UUID,
    subscription_tier: str = Body(..., description="free, standard, or premium"),
    billing_date: Optional[date] = Body(None, description="New billing cycle start date"),
    current_user=Depends(require_admin())
):
    """
    Update user's subscription tier and billing cycle

    Body:
    - subscription_tier: New tier (free, standard, premium)
    - billing_date: New billing cycle start date (optional)

    This will:
    - Update subscription tier
    - Adjust credit allowance
    - Reset billing cycle if date provided
    """
    try:
        subscription_service = UserSubscriptionService()

        # Update subscription
        result = await subscription_service.setup_user_subscription(
            user_id=user_id,
            subscription_tier=subscription_tier,
            billing_type="admin_managed",
            initial_billing_date=billing_date or date.today()
        )

        return {
            "success": True,
            "message": f"Updated user to {subscription_tier} tier",
            "billing_info": result
        }

    except Exception as e:
        logger.error(f"Failed to update user billing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/billing/cycle")
async def update_billing_cycle(
    user_id: UUID,
    new_billing_date: date = Body(..., description="New billing cycle start date"),
    current_user=Depends(require_admin())
):
    """
    Update billing cycle date for admin-managed user

    Body:
    - new_billing_date: New billing cycle start date

    This updates when the user should be invoiced next
    """
    try:
        subscription_service = UserSubscriptionService()

        result = await subscription_service.update_billing_cycle(
            user_id=user_id,
            new_billing_date=new_billing_date
        )

        return {
            "success": True,
            "message": "Billing cycle updated",
            "billing_cycle": result
        }

    except Exception as e:
        logger.error(f"Failed to update billing cycle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stripe/subscriptions")
async def get_all_stripe_subscriptions(
    status: Optional[str] = Query(None, description="active, canceled, past_due, etc."),
    current_user=Depends(require_admin())
):
    """
    Get all Stripe subscriptions with detailed information

    Parameters:
    - status: Filter by subscription status

    Returns list of all Stripe subscriptions with:
    - Customer details
    - Subscription status
    - Current period dates
    - Renewal dates
    - Payment method
    """
    try:
        stripe_service = StripeSubscriptionService()

        # Get all Stripe subscriptions
        subscriptions = await stripe_service.list_all_subscriptions(status=status)

        return {
            "total_count": len(subscriptions),
            "subscriptions": subscriptions
        }

    except Exception as e:
        logger.error(f"Failed to get Stripe subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stripe/{user_id}/subscription")
async def get_user_stripe_subscription(
    user_id: UUID,
    current_user=Depends(require_admin())
):
    """
    Get detailed Stripe subscription for a specific user

    Returns:
    - Subscription ID and status
    - Current period start/end
    - Next billing date
    - Payment method details
    - Invoice history
    """
    try:
        stripe_service = StripeSubscriptionService()

        subscription_details = await stripe_service.get_user_subscription_details(user_id)

        return subscription_details

    except Exception as e:
        logger.error(f"Failed to get user Stripe subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stripe/{user_id}/cancel")
async def cancel_user_stripe_subscription(
    user_id: UUID,
    immediately: bool = Body(False, description="Cancel immediately or at period end"),
    current_user=Depends(require_admin())
):
    """
    Cancel a user's Stripe subscription

    Body:
    - immediately: If true, cancel immediately. If false, cancel at period end
    """
    try:
        stripe_service = StripeSubscriptionService()

        result = await stripe_service.cancel_subscription(
            user_id=user_id,
            immediately=immediately
        )

        return {
            "success": True,
            "message": "Subscription canceled",
            "details": result
        }

    except Exception as e:
        logger.error(f"Failed to cancel Stripe subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/billing-report")
async def export_billing_report(
    month: Optional[int] = Query(None, description="Month (1-12)"),
    year: Optional[int] = Query(None, description="Year"),
    current_user=Depends(require_admin())
):
    """
    Export comprehensive billing report for admin-managed users

    Parameters:
    - month: Specific month (defaults to current)
    - year: Specific year (defaults to current)

    Returns CSV-ready data with:
    - User details
    - Subscription tiers
    - Billing dates
    - Credit usage
    - Invoice amounts
    """
    try:
        subscription_service = UserSubscriptionService()

        # Get all admin-managed users
        admin_users = await subscription_service.get_all_users_billing(
            billing_type="admin_managed",
            page_size=1000
        )

        # Format for export
        export_data = []
        for user in admin_users["users"]:
            export_data.append({
                "Email": user["email"],
                "Name": user["full_name"],
                "Tier": user["subscription_tier"],
                "Status": user["status"],
                "Current Credits": user["current_balance"],
                "Billing Start": user["billing_cycle_start"],
                "Next Billing": user["next_billing_date"],
                "Days Until Billing": user["days_until_billing"],
                "Created": user["created_at"]
            })

        return {
            "report_date": datetime.utcnow().isoformat(),
            "total_users": len(export_data),
            "data": export_data
        }

    except Exception as e:
        logger.error(f"Failed to export billing report: {e}")
        raise HTTPException(status_code=500, detail=str(e))