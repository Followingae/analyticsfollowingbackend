"""
Simple User Management Routes - Direct Database Access
Bypasses PGBouncer issues with prepared statements
"""
import logging
from typing import Optional
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database.connection import get_db
from app.middleware.auth_middleware import require_admin, get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/simple", tags=["Simple Admin"])


@router.get("/user/{user_id}/credits")
async def get_user_credits_simple(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin())
):
    """
    Get user's credit balance - simple and direct

    Returns actual credit balance from database
    """
    try:
        # Get user and their auth ID
        query = text("""
            SELECT
                u.email,
                u.role,
                u.subscription_tier,
                u.billing_type,
                au.id as auth_user_id
            FROM users u
            LEFT JOIN auth.users au ON au.email = u.email
            WHERE u.id = :user_id
        """)

        result = await db.execute(query, {"user_id": str(user_id)})
        user_data = result.fetchone()

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Get credit wallet
        wallet_query = text("""
            SELECT
                current_balance,
                total_earned_this_cycle,
                total_spent_this_cycle,
                current_billing_cycle_start,
                current_billing_cycle_end,
                next_reset_date,
                subscription_status
            FROM credit_wallets
            WHERE user_id = :auth_user_id
        """)

        wallet_result = await db.execute(wallet_query, {"auth_user_id": str(user_data.auth_user_id)})
        wallet = wallet_result.fetchone()

        # Get tier credits
        tier_credits = {
            "free": 125,
            "standard": 12500,
            "premium": 50000
        }.get(user_data.subscription_tier, 125)

        return {
            "user_id": str(user_id),
            "email": user_data.email,
            "subscription_tier": user_data.subscription_tier,
            "current_balance": wallet.current_balance if wallet else 0,
            "monthly_allowance": tier_credits,
            "total_earned": wallet.total_earned_this_cycle if wallet else 0,
            "total_spent": wallet.total_spent_this_cycle if wallet else 0,
            "billing_cycle_start": wallet.current_billing_cycle_start.isoformat() if wallet and wallet.current_billing_cycle_start else None,
            "billing_cycle_end": wallet.current_billing_cycle_end.isoformat() if wallet and wallet.current_billing_cycle_end else None,
            "next_reset_date": wallet.next_reset_date.isoformat() if wallet and wallet.next_reset_date else None,
            "wallet_exists": wallet is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user credits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/{user_id}/fix-wallet")
async def fix_user_wallet(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin())
):
    """
    Fix missing or broken wallet for a user
    Creates wallet with proper tier credits if missing
    """
    try:
        # Get user and their auth ID
        query = text("""
            SELECT
                u.email,
                u.subscription_tier,
                au.id as auth_user_id
            FROM users u
            LEFT JOIN auth.users au ON au.email = u.email
            WHERE u.id = :user_id
        """)

        result = await db.execute(query, {"user_id": str(user_id)})
        user_data = result.fetchone()

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        if not user_data.auth_user_id:
            raise HTTPException(status_code=400, detail="No auth user found")

        # Check if wallet exists
        check_query = text("""
            SELECT id FROM credit_wallets WHERE user_id = :auth_user_id
        """)
        check_result = await db.execute(check_query, {"auth_user_id": str(user_data.auth_user_id)})
        existing = check_result.fetchone()

        if existing:
            return {"message": "Wallet already exists", "wallet_id": existing.id}

        # Get tier credits
        tier_credits = {
            "free": 125,
            "standard": 12500,
            "premium": 50000
        }.get(user_data.subscription_tier, 125)

        # Create wallet
        create_query = text("""
            INSERT INTO credit_wallets (
                user_id,
                current_balance,
                total_earned_this_cycle,
                current_billing_cycle_start,
                current_billing_cycle_end,
                next_reset_date,
                subscription_status,
                auto_refresh_enabled,
                created_at,
                updated_at
            ) VALUES (
                :auth_user_id,
                :credits,
                :credits,
                CURRENT_DATE,
                CURRENT_DATE + INTERVAL '30 days',
                CURRENT_DATE + INTERVAL '30 days',
                'active',
                true,
                NOW(),
                NOW()
            ) RETURNING id
        """)

        result = await db.execute(create_query, {
            "auth_user_id": str(user_data.auth_user_id),
            "credits": tier_credits
        })
        wallet_id = result.fetchone().id

        await db.commit()

        return {
            "success": True,
            "message": f"Wallet created with {tier_credits} credits",
            "wallet_id": wallet_id,
            "credits_added": tier_credits
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fix user wallet: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))