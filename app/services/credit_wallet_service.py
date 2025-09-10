"""
Credit Wallet Service - Core wallet management functionality
Handles wallet creation, balance management, and billing cycles
"""
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.database.connection import get_session
from app.database.unified_models import (
    CreditWallet, CreditPackage, CreditTransaction, 
    CreditUsageTracking, UnlockedInfluencer
)
from app.models.credits import (
    CreditWalletCreate, CreditWalletUpdate, CreditWalletSummary,
    CreditBalance, CanPerformActionResponse, TotalPlanCredits
)
from app.core.exceptions import ValidationError
from app.cache.redis_cache_manager import cache_manager

logger = logging.getLogger(__name__)


class CreditWalletService:
    """
    Comprehensive credit wallet management service
    Handles all wallet operations with bulletproof reliability
    """
    
    def __init__(self):
        self.cache_prefix = "credit_wallet"
        self.balance_cache_ttl = 300  # 5 minutes
        self.wallet_cache_ttl = 1800  # 30 minutes
    
    # =========================================================================
    # WALLET CREATION & MANAGEMENT
    # =========================================================================
    
    async def create_wallet(
        self, 
        user_id: UUID, 
        package_id: Optional[int] = None,
        initial_balance: int = 0
    ) -> CreditWallet:
        """
        Create a new credit wallet for a user
        
        Args:
            user_id: User UUID
            package_id: Optional credit package ID
            initial_balance: Starting credit balance
            
        Returns:
            Created CreditWallet instance
            
        Raises:
            ValidationError: If user already has a wallet or invalid package
        """
        try:
            async with get_session() as session:
                # Check if user already has a wallet
                existing_wallet = await session.execute(
                    select(CreditWallet).where(CreditWallet.user_id == user_id)
                )
                if existing_wallet.scalar_one_or_none():
                    raise ValidationError(f"User {user_id} already has a credit wallet")
                
                # Validate package if provided
                if package_id:
                    package = await session.execute(
                        select(CreditPackage).where(
                            and_(
                                CreditPackage.id == package_id,
                                CreditPackage.is_active == True
                            )
                        )
                    )
                    if not package.scalar_one_or_none():
                        raise ValidationError(f"Invalid or inactive package ID: {package_id}")
                
                # Create new wallet
                wallet = CreditWallet(
                    user_id=user_id,
                    package_id=package_id,
                    current_balance=initial_balance,
                    total_earned_this_cycle=initial_balance if initial_balance > 0 else 0,
                    billing_cycle_start=date.today(),
                    next_reset_date=date.today() + timedelta(days=30)
                )
                
                session.add(wallet)
                await session.commit()
                await session.refresh(wallet)
                
                # Clear cache for user
                await self._clear_user_cache(user_id)
                
                logger.info(f"Created credit wallet for user {user_id} with balance {initial_balance}")
                return wallet
                
        except IntegrityError as e:
            logger.error(f"Database integrity error creating wallet for user {user_id}: {e}")
            raise ValidationError(f"Failed to create wallet: database constraint violation")
        except Exception as e:
            logger.error(f"Unexpected error creating wallet for user {user_id}: {e}")
            raise
    
    async def get_wallet(self, user_id: UUID) -> Optional[CreditWallet]:
        """Get user's credit wallet with caching"""
        cache_key = f"{self.cache_prefix}:wallet:{user_id}"
        
        # Try cache first - use direct Redis for wallet cache
        try:
            if cache_manager.initialized:
                cached_data = await cache_manager.redis_client.get(cache_key)
                if cached_data:
                    import json
                    # For wallet objects, we'll skip caching complex SQLAlchemy objects for now
                    # and just fetch from database each time for simplicity
                    pass
        except Exception as cache_error:
            logger.debug(f"Cache miss for wallet {user_id}: {cache_error}")
        
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CreditWallet)
                    .options(selectinload(CreditWallet.package))
                    .where(CreditWallet.user_id == user_id)
                )
                wallet = result.scalar_one_or_none()
                
                if wallet:
                    # Cache the wallet - use direct Redis 
                    try:
                        if cache_manager.initialized:
                            import json
                            # Convert wallet to dict for JSON serialization
                            wallet_dict = {
                                "id": wallet.id,
                                "user_id": str(wallet.user_id),
                                "current_balance": wallet.current_balance,
                                "is_locked": wallet.is_locked,
                                "next_reset_date": wallet.next_reset_date.isoformat() if wallet.next_reset_date else None
                            }
                            await cache_manager.redis_client.setex(
                                cache_key, 
                                self.wallet_cache_ttl, 
                                json.dumps(wallet_dict, default=str)
                            )
                    except Exception as cache_error:
                        logger.debug(f"Failed to cache wallet {user_id}: {cache_error}")
                
                return wallet
                
        except Exception as e:
            logger.error(f"Error retrieving wallet for user {user_id}: {e}")
            return None
    
    async def get_wallet_balance(self, user_id: UUID) -> CreditBalance:
        """Get user's current credit balance with high-performance caching"""
        cache_key = f"{self.cache_prefix}:balance:{user_id}"
        
        # Try cache first - use direct Redis for wallet cache
        try:
            if cache_manager.initialized:
                cached_data = await cache_manager.redis_client.get(cache_key)
                if cached_data:
                    import json
                    cached_balance = json.loads(cached_data)
                    return CreditBalance(**cached_balance)
        except Exception as cache_error:
            logger.debug(f"Cache miss for wallet balance {user_id}: {cache_error}")
        
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return CreditBalance(balance=0, is_locked=True, next_reset_date=date.today())
        
        balance_data = {
            "balance": wallet.current_balance,
            "is_locked": wallet.is_locked,
            "next_reset_date": wallet.next_reset_date.isoformat() if wallet.next_reset_date else None
        }
        
        # Cache balance - use direct Redis
        try:
            if cache_manager.initialized:
                import json
                await cache_manager.redis_client.setex(
                    cache_key, 
                    self.balance_cache_ttl, 
                    json.dumps(balance_data)
                )
        except Exception as cache_error:
            logger.debug(f"Failed to cache wallet balance {user_id}: {cache_error}")
        
        return CreditBalance(**balance_data)
    
    async def update_wallet(
        self, 
        user_id: UUID, 
        update_data: CreditWalletUpdate
    ) -> Optional[CreditWallet]:
        """Update wallet settings"""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CreditWallet).where(CreditWallet.user_id == user_id)
                )
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    return None
                
                # Apply updates
                update_dict = update_data.dict(exclude_unset=True)
                for field, value in update_dict.items():
                    setattr(wallet, field, value)
                
                await session.commit()
                await session.refresh(wallet)
                
                # Clear cache
                await self._clear_user_cache(user_id)
                
                logger.info(f"Updated wallet for user {user_id}: {update_dict}")
                return wallet
                
        except Exception as e:
            logger.error(f"Error updating wallet for user {user_id}: {e}")
            raise
    
    # =========================================================================
    # BALANCE OPERATIONS
    # =========================================================================
    
    async def add_credits(
        self, 
        user_id: UUID, 
        amount: int, 
        transaction_type: str = "manual_adjust",
        description: Optional[str] = None,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None
    ) -> Optional[CreditTransaction]:
        """
        Add credits to user's wallet using the database function
        
        Args:
            user_id: User UUID
            amount: Credits to add (positive number)
            transaction_type: Type of transaction
            description: Transaction description
            reference_id: Reference ID for tracking
            reference_type: Type of reference
            
        Returns:
            CreditTransaction if successful, None otherwise
        """
        if amount <= 0:
            raise ValidationError("Amount must be positive when adding credits")
        
        wallet = await self.get_wallet(user_id)
        if not wallet:
            raise ValidationError(f"No wallet found for user {user_id}")
        
        try:
            async with get_session() as session:
                # Use the database function for safe balance updates
                result = await session.execute(
                    text("""
                        SELECT public.update_wallet_balance(
                            :wallet_id, :amount, :transaction_type, 
                            :description, :reference_id, :reference_type, NULL
                        )
                    """),
                    {
                        "wallet_id": wallet.id,
                        "amount": amount,
                        "transaction_type": transaction_type,
                        "description": description,
                        "reference_id": reference_id,
                        "reference_type": reference_type
                    }
                )
                
                transaction_id = result.scalar()
                await session.commit()
                
                # Get the created transaction
                transaction_result = await session.execute(
                    select(CreditTransaction).where(CreditTransaction.id == transaction_id)
                )
                transaction = transaction_result.scalar_one()
                
                # Clear cache
                await self._clear_user_cache(user_id)
                
                logger.info(f"Added {amount} credits to user {user_id}, new balance: {transaction.balance_after}")
                return transaction
                
        except Exception as e:
            logger.error(f"Error adding credits for user {user_id}: {e}")
            raise
    
    async def spend_credits(
        self,
        user_id: UUID,
        amount: int,
        action_type: str,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[CreditTransaction]:
        """
        Spend credits from user's wallet with validation
        
        Args:
            user_id: User UUID
            amount: Credits to spend (positive number, will be made negative)
            action_type: Action type that triggered spending
            reference_id: Reference ID for tracking
            reference_type: Type of reference
            description: Transaction description
            
        Returns:
            CreditTransaction if successful, None otherwise
            
        Raises:
            ValidationError: If insufficient credits or invalid wallet
        """
        if amount <= 0:
            raise ValidationError("Amount must be positive when spending credits")
        
        wallet = await self.get_wallet(user_id)
        if not wallet:
            raise ValidationError(f"No wallet found for user {user_id}")
        
        if wallet.is_locked:
            raise ValidationError("Wallet is locked - cannot spend credits")
        
        if wallet.current_balance < amount:
            raise ValidationError(
                f"Insufficient credits. Required: {amount}, Available: {wallet.current_balance}"
            )
        
        try:
            async with get_session() as session:
                # Use the corrected database function
                result = await session.execute(
                    text("""
                        SELECT public.update_wallet_balance(
                            :wallet_id, :amount, 'spend', 
                            :description, :reference_id, :reference_type, :action_type
                        )
                    """),
                    {
                        "wallet_id": wallet.id,
                        "amount": -amount,  # Negative for spending
                        "description": description,
                        "reference_id": reference_id,
                        "reference_type": reference_type,
                        "action_type": action_type
                    }
                )
                
                transaction_id = result.scalar()
                await session.commit()
                
                # Get the created transaction
                transaction_result = await session.execute(
                    select(CreditTransaction).where(CreditTransaction.id == transaction_id)
                )
                transaction = transaction_result.scalar_one()
                
                # Clear cache
                await self._clear_user_cache(user_id)
                
                logger.info(f"Spent {amount} credits for user {user_id}, new balance: {transaction.balance_after}")
                return transaction
                
        except Exception as e:
            logger.error(f"Error spending credits for user {user_id}: {e}")
            raise
    
    async def spend_credits_atomic(
        self,
        db,  # Existing database session
        user_id: UUID,
        action_type: str,
        credits_amount: int,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[CreditTransaction]:
        """
        ATOMIC spend credits within existing database transaction
        
        This method is designed for atomic operations where multiple database
        operations must succeed or fail together. It uses an existing database
        session instead of creating its own.
        
        Args:
            db: Existing database session (AsyncSession)
            user_id: User UUID
            action_type: Action type that triggered spending
            credits_amount: Credits to spend (positive number)
            reference_id: Reference ID for tracking
            reference_type: Type of reference
            description: Transaction description
            
        Returns:
            CreditTransaction if successful, None otherwise
            
        Raises:
            Exception: If insufficient credits, locked wallet, or database error
        """
        if credits_amount <= 0:
            raise Exception("Amount must be positive when spending credits")
        
        # Get wallet within the existing transaction
        wallet_query = select(CreditWallet).where(CreditWallet.user_id == user_id)
        wallet_result = await db.execute(wallet_query)
        wallet = wallet_result.scalar_one_or_none()
        
        if not wallet:
            raise Exception(f"No wallet found for user {user_id}")
        
        if wallet.is_locked:
            raise Exception("Wallet is locked - cannot spend credits")
        
        if wallet.current_balance < credits_amount:
            raise Exception(
                f"Insufficient credits. Required: {credits_amount}, Available: {wallet.current_balance}"
            )
        
        try:
            # Use the database function within existing transaction
            result = await db.execute(
                text("""
                    SELECT public.update_wallet_balance(
                        :wallet_id, :amount, 'spend', 
                        :description, :reference_id, :reference_type, :action_type
                    )
                """),
                {
                    "wallet_id": wallet.id,
                    "amount": -credits_amount,  # Negative for spending
                    "description": description or f"Credits spent for {action_type}",
                    "reference_id": reference_id,
                    "reference_type": reference_type,
                    "action_type": action_type
                }
            )
            
            transaction_id = result.scalar()
            
            # Get the created transaction within same session
            transaction_result = await db.execute(
                select(CreditTransaction).where(CreditTransaction.id == transaction_id)
            )
            transaction = transaction_result.scalar_one()
            
            # Clear cache (will be called after transaction commits)
            # Note: Cache clearing happens in the calling atomic method
            
            logger.info(f"ATOMIC: Spent {credits_amount} credits for user {user_id}, new balance: {transaction.balance_after}")
            return transaction
            
        except Exception as e:
            logger.error(f"ATOMIC: Error spending credits for user {user_id}: {e}")
            # Don't commit or rollback - let the atomic transaction handler manage this
            raise
    
    # =========================================================================
    # ACTION PERMISSION CHECKING
    # =========================================================================
    
    async def can_perform_action(
        self,
        user_id: UUID,
        action_type: str,
        required_credits: Optional[int] = None
    ) -> CanPerformActionResponse:
        """
        Check if user can perform a credit-gated action using database function
        
        Args:
            user_id: User UUID
            action_type: Action type to check
            required_credits: Override default action cost
            
        Returns:
            CanPerformActionResponse with decision and details
        """
        try:
            async with get_session() as session:
                # ADMIN BYPASS: Check if user is admin first
                admin_check = await session.execute(
                    text("""
                        SELECT raw_user_meta_data->>'role' as role 
                        FROM auth.users 
                        WHERE id = :user_id
                    """),
                    {"user_id": str(user_id)}
                )
                
                user_role = admin_check.scalar()
                
                # Admins bypass all credit checks
                if user_role in ['admin', 'super_admin']:
                    logger.info(f"Admin user {user_id} bypassing credit check for {action_type}")
                    return CanPerformActionResponse(
                        can_perform=True,
                        reason="admin_bypass",
                        credits_required=0,
                        wallet_balance=999999,
                        free_remaining=999999,
                        credits_needed=0,
                        message=f"Admin access granted for {action_type}"
                    )
                result = await session.execute(
                    text("""
                        SELECT public.can_perform_credit_action(:user_id, :action_type, :required_credits)
                    """),
                    {
                        "user_id": str(user_id),
                        "action_type": action_type,
                        "required_credits": required_credits
                    }
                )
                
                response_data = result.scalar()
                
                return CanPerformActionResponse(
                    can_perform=response_data.get("can_perform", False),
                    reason=response_data.get("reason", "unknown"),
                    credits_required=response_data.get("credits_required", 0),
                    wallet_balance=response_data.get("wallet_balance", 0),
                    free_remaining=response_data.get("free_remaining", 0),
                    credits_needed=response_data.get("credits_needed", 0),
                    message=response_data.get("message")
                )
                
        except Exception as e:
            logger.error(f"Error checking action permission for user {user_id}: {e}")
            return CanPerformActionResponse(
                can_perform=False,
                reason="error",
                message=f"Error checking permissions: {str(e)}"
            )
    
    # =========================================================================
    # WALLET STATISTICS & ANALYTICS
    # =========================================================================
    
    async def get_wallet_summary(self, user_id: UUID) -> Optional[CreditWalletSummary]:
        """Get comprehensive wallet summary with total plan credits"""
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return None
        
        # Get total plan credits breakdown
        total_plan_data = await self.get_total_plan_credits(user_id)
        
        return CreditWalletSummary(
            current_balance=wallet.current_balance,
            is_locked=wallet.is_locked,
            subscription_active=wallet.subscription_active,
            next_reset_date=wallet.next_reset_date,
            total_spent_this_cycle=wallet.total_spent_this_cycle,
            # Total plan credits breakdown
            total_plan_credits=total_plan_data.total_plan_credits if total_plan_data else 0,
            package_credits_balance=total_plan_data.package_credits if total_plan_data else 0,
            purchased_credits_balance=total_plan_data.purchased_credits if total_plan_data else 0,
            bonus_credits_balance=total_plan_data.bonus_credits if total_plan_data else 0,
            monthly_allowance=total_plan_data.monthly_allowance if total_plan_data else 0,
            package_name=total_plan_data.package_name if total_plan_data else None
        )
    
    async def get_monthly_spending(self, user_id: UUID, month_year: Optional[date] = None) -> int:
        """Get total credits spent in a specific month"""
        if not month_year:
            month_year = date.today().replace(day=1)
        
        try:
            # TEMPORARY FIX: Skip usage tracking due to model mismatch
            # TODO: Fix CreditUsageTracking model schema mismatch
            logger.warning(f"TEMP FIX: Skipping monthly spending calculation for user {user_id}")
            return 0
                
        except Exception as e:
            logger.error(f"Error getting monthly spending for user {user_id}: {e}")
            return 0
    
    async def get_unlocked_influencers_count(self, user_id: UUID) -> int:
        """Get count of influencers unlocked by user"""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(func.count(UnlockedInfluencer.id))
                    .where(UnlockedInfluencer.user_id == user_id)
                )
                
                return result.scalar() or 0
                
        except Exception as e:
            logger.error(f"Error getting unlocked influencers count for user {user_id}: {e}")
            return 0
    
    async def get_total_plan_credits(self, user_id: UUID) -> Optional[TotalPlanCredits]:
        """
        Get comprehensive Total Plan Credits breakdown
        Shows package allowance + purchased credits + bonus credits
        """
        try:
            # Check cache first (skip cache for now due to method availability)
            cache_key = f"{self.cache_prefix}:total_plan:{user_id}"
            # cached = await cache_manager.get_json(cache_key)
            # if cached:
            #     return TotalPlanCredits(**cached)
            
            async with get_session() as session:
                # Use the database function to get total plan credits breakdown
                result = await session.execute(
                    text("SELECT * FROM public.calculate_total_plan_credits(:user_id)"),
                    {"user_id": str(user_id)}
                )
                
                row = result.fetchone()
                if not row:
                    logger.warning(f"No credit wallet found for user {user_id}")
                    return None
                
                # Get current balance from wallet
                wallet = await self.get_wallet(user_id)
                current_balance = wallet.current_balance if wallet else 0
                
                total_plan_credits = TotalPlanCredits(
                    total_plan_credits=row[0],  # total_plan_credits
                    package_credits=row[1],     # package_credits
                    purchased_credits=row[2],   # purchased_credits
                    bonus_credits=row[3],       # bonus_credits
                    monthly_allowance=row[4],   # monthly_allowance
                    package_name=row[5],        # package_name
                    current_balance=current_balance
                )
                
                # Cache for 10 minutes (skip cache for now)
                # await cache_manager.set_json(
                #     cache_key, 
                #     total_plan_credits.dict(), 
                #     ttl=600
                # )
                
                return total_plan_credits
                
        except Exception as e:
            logger.error(f"Error getting total plan credits for user {user_id}: {e}")
            return None
    
    async def update_credits_breakdown(
        self,
        user_id: UUID,
        package_credits: Optional[int] = None,
        purchased_credits: Optional[int] = None,
        bonus_credits: Optional[int] = None
    ) -> bool:
        """
        Update wallet credits breakdown maintaining consistency
        Uses database function to ensure total balance matches breakdown
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT public.update_wallet_credits_breakdown(
                            :user_id, :package_credits, :purchased_credits, :bonus_credits
                        )
                    """),
                    {
                        "user_id": str(user_id),
                        "package_credits": package_credits,
                        "purchased_credits": purchased_credits,
                        "bonus_credits": bonus_credits
                    }
                )
                
                success = result.scalar()
                await session.commit()
                
                if success:
                    # Clear cache
                    await self._clear_user_cache(user_id)
                    logger.info(f"Updated credits breakdown for user {user_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Error updating credits breakdown for user {user_id}: {e}")
            return False
    
    # =========================================================================
    # BILLING CYCLE MANAGEMENT
    # =========================================================================
    
    async def reset_monthly_credits(self, user_id: UUID) -> bool:
        """
        Reset user's monthly credit allowance
        Called by background job on billing cycle
        """
        try:
            wallet = await self.get_wallet(user_id)
            if not wallet or not wallet.package:
                logger.warning(f"Cannot reset credits for user {user_id}: no wallet or package")
                return False
            
            async with get_session() as session:
                # Calculate rollover credits
                rollover_amount = 0
                if wallet.rollover_months_allowed > 0:
                    # Implement rollover logic based on business rules
                    pass
                
                # Add monthly allowance
                monthly_credits = wallet.package.monthly_credits
                total_credits = monthly_credits + rollover_amount
                
                # Use database function to add credits
                await session.execute(
                    text("""
                        SELECT public.update_wallet_balance(
                            :wallet_id, :amount, 'reset', 
                            'Monthly credit reset', NULL, 'billing_cycle', NULL
                        )
                    """),
                    {
                        "wallet_id": wallet.id,
                        "amount": total_credits
                    }
                )
                
                # Update billing cycle dates
                await session.execute(
                    text("""
                        UPDATE public.credit_wallets 
                        SET 
                            billing_cycle_start = CURRENT_DATE,
                            next_reset_date = CURRENT_DATE + INTERVAL '1 month',
                            total_earned_this_cycle = 0,
                            total_purchased_this_cycle = 0,
                            total_spent_this_cycle = 0,
                            updated_at = NOW()
                        WHERE id = :wallet_id
                    """),
                    {"wallet_id": wallet.id}
                )
                
                await session.commit()
                
                # Clear cache
                await self._clear_user_cache(user_id)
                
                logger.info(f"Reset monthly credits for user {user_id}: {total_credits} credits")
                return True
                
        except Exception as e:
            logger.error(f"Error resetting monthly credits for user {user_id}: {e}")
            return False
    
    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================
    
    async def _clear_user_cache(self, user_id: UUID) -> None:
        """Clear all cache entries for a user"""
        cache_keys = [
            f"{self.cache_prefix}:wallet:{user_id}",
            f"{self.cache_prefix}:balance:{user_id}",
            f"{self.cache_prefix}:total_plan:{user_id}"
        ]
        
        # Use direct Redis client to delete cache keys
        try:
            if cache_manager.initialized:
                for key in cache_keys:
                    await cache_manager.redis_client.delete(key)
        except Exception as e:
            logger.debug(f"Failed to clear cache for user {user_id}: {e}")
    
    async def warm_cache(self, user_id: UUID) -> None:
        """Warm cache with user's wallet data"""
        wallet = await self.get_wallet(user_id)
        balance = await self.get_wallet_balance(user_id)
        logger.debug(f"Warmed cache for user {user_id}")

    async def is_profile_unlocked(self, user_id: UUID, profile_identifier: str, identifier_type: str = "username") -> bool:
        """
        Check if a user has unlocked a specific profile
        
        Args:
            user_id: User UUID
            profile_identifier: Profile username or UUID
            identifier_type: Either "username" or "profile_id"
            
        Returns:
            True if profile is unlocked, False otherwise
        """
        try:
            from app.database.unified_models import UnlockedProfile, Profile
            from sqlalchemy import select, and_
            
            async with get_session() as session:
                if identifier_type == "username":
                    # Check by username (join with profiles table)
                    query = select(UnlockedProfile).join(Profile).where(
                        and_(
                            UnlockedProfile.user_id == user_id,
                            Profile.username == profile_identifier
                        )
                    )
                else:
                    # Check by profile_id directly  
                    query = select(UnlockedProfile).where(
                        and_(
                            UnlockedProfile.user_id == user_id,
                            UnlockedProfile.profile_id == UUID(str(profile_identifier))
                        )
                    )
                
                result = await session.execute(query)
                unlock_record = result.scalar_one_or_none()
                
                return unlock_record is not None
                
        except Exception as e:
            logger.error(f"Error checking if profile {profile_identifier} is unlocked for user {user_id}: {e}")
            return False


# Global service instance
credit_wallet_service = CreditWalletService()