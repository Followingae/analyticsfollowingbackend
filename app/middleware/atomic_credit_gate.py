"""
ATOMIC CREDIT GATE - Bulletproof Transaction Management
Ensures all-or-nothing transactions: credits are only charged if ALL operations succeed
"""
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from uuid import UUID
from datetime import datetime, timezone

from fastapi import HTTPException, status, Request
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.services.credit_wallet_service import credit_wallet_service
from app.services.credit_transaction_service import credit_transaction_service
from app.database.connection import get_session
from app.database.unified_models import Profile, User, UnlockedInfluencer, UserProfileAccess, CreditTransaction

logger = logging.getLogger(__name__)

class AtomicTransactionError(Exception):
    """Raised when atomic transaction fails and needs rollback"""
    def __init__(self, message: str, step: str):
        self.message = message
        self.step = step
        super().__init__(f"Atomic transaction failed at {step}: {message}")

def atomic_requires_credits(
    action_type: str, 
    credits_required: Optional[int] = None,
    check_unlock_status: bool = False,
    unlock_key_param: str = "username",
    return_detailed_response: bool = False
):
    """
    BULLETPROOF ATOMIC CREDIT GATE
    
    All operations are performed in a single database transaction:
    1. Check credit requirements
    2. Create access records (if profile unlock)
    3. Spend credits
    4. Execute the wrapped function
    
    If ANY step fails, EVERYTHING is rolled back and user is not charged.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user info from FastAPI dependency injection
            request = None
            user_id = None
            
            # Find request and user_id in the arguments
            for arg in args:
                if hasattr(arg, 'method') and hasattr(arg, 'url'):  # FastAPI Request
                    request = arg
                if isinstance(arg, str) and len(arg) == 36:  # UUID string
                    try:
                        user_id = UUID(arg)
                    except:
                        pass
            
            # Extract reference_id from URL path or kwargs
            reference_id = None
            if 'username' in kwargs:
                reference_id = kwargs['username']
            elif request and hasattr(request, 'path_params'):
                reference_id = request.path_params.get('username')
            
            if not user_id or not reference_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to extract user_id or reference_id for credit gate"
                )
                
            logger.info(f"🔒 ATOMIC CREDIT GATE: {action_type} for user {user_id}, reference {reference_id}")
            
            # BEGIN ATOMIC TRANSACTION
            async with get_session() as db:
                try:
                    # Step 1: Check credit requirements and existing access
                    permission_check = await _atomic_check_permissions(
                        db, user_id, action_type, reference_id
                    )
                    
                    if not permission_check["allowed"]:
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail=permission_check["error"]
                        )
                    
                    credits_required = permission_check["credits_required"]
                    used_free_allowance = permission_check["used_free_allowance"]
                    
                    # Step 2: Create access records BEFORE charging (for profile unlocks)
                    access_records_created = False
                    if action_type == "profile_analysis" and not permission_check["already_unlocked"]:
                        try:
                            await _atomic_create_access_records(
                                db, user_id, reference_id, credits_required
                            )
                            access_records_created = True
                            logger.info(f"✅ Access records created for {user_id} -> {reference_id}")
                        except Exception as e:
                            raise AtomicTransactionError(str(e), "create_access_records")
                    
                    # Step 3: Spend credits (only if required)
                    transaction = None
                    if credits_required > 0:
                        try:
                            transaction = await credit_wallet_service.spend_credits_atomic(
                                db=db,  # Use same transaction
                                user_id=user_id,
                                action_type=action_type,
                                credits_amount=credits_required,
                                reference_id=reference_id,
                                reference_type="profile" if action_type == "profile_analysis" else "action"
                            )
                            logger.info(f"💳 Credits spent: {credits_required} for user {user_id}")
                        except Exception as e:
                            raise AtomicTransactionError(str(e), "spend_credits")
                    
                    # Step 4: Execute the wrapped function
                    try:
                        result = await func(*args, **kwargs)
                        logger.info(f"✅ Function executed successfully for {reference_id}")
                    except Exception as e:
                        raise AtomicTransactionError(str(e), "execute_function")
                    
                    # Step 5: Commit the entire transaction
                    await db.commit()
                    logger.info(f"🎉 ATOMIC TRANSACTION COMPLETED for {user_id} -> {reference_id}")
                    
                    # Add credit information to response if requested
                    if return_detailed_response and isinstance(result, dict):
                        wallet_info = await credit_wallet_service.get_wallet_summary(user_id)
                        result["credit_info"] = {
                            "credits_spent": credits_required,
                            "used_free_allowance": used_free_allowance,
                            "remaining_balance": wallet_info.get("current_balance", 0),
                            "transaction_id": transaction.id if transaction else None,
                            "access_granted": access_records_created or permission_check["already_unlocked"]
                        }
                    
                    return result
                    
                except AtomicTransactionError as e:
                    # Rollback the entire transaction
                    await db.rollback()
                    logger.error(f"🚨 ATOMIC TRANSACTION FAILED at {e.step}: {e.message}")
                    logger.error(f"🔄 ROLLBACK COMPLETED - User {user_id} was NOT charged")
                    
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Transaction failed at {e.step}: {e.message}"
                    )
                    
                except Exception as e:
                    # Unexpected error - rollback
                    await db.rollback()
                    logger.error(f"🚨 UNEXPECTED ERROR in atomic transaction: {e}")
                    logger.error(f"🔄 ROLLBACK COMPLETED - User {user_id} was NOT charged")
                    
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Transaction failed unexpectedly: {str(e)}"
                    )
        
        return wrapper
    return decorator

async def _atomic_check_permissions(db, user_id: UUID, action_type: str, reference_id: str) -> Dict[str, Any]:
    """Check if user can perform action and calculate credits required"""
    try:
        # Check if profile is already unlocked (for profile_analysis actions)
        already_unlocked = False
        if action_type == "profile_analysis":
            # Check both unlocked_influencers and user_profile_access
            unlock_check = select(UnlockedInfluencer).where(
                UnlockedInfluencer.user_id == user_id,
                UnlockedInfluencer.username == reference_id
            )
            unlock_result = await db.execute(unlock_check)
            already_unlocked = unlock_result.scalar_one_or_none() is not None
            
            if already_unlocked:
                logger.info(f"Profile {reference_id} already unlocked for user {user_id}")
                return {
                    "allowed": True,
                    "credits_required": 0,
                    "used_free_allowance": False,
                    "already_unlocked": True,
                    "message": "Profile already unlocked"
                }
        
        # Get pricing information
        pricing_info = await credit_wallet_service.can_perform_action(user_id, action_type)
        
        if not pricing_info["allowed"]:
            return {
                "allowed": False,
                "error": pricing_info.get("error", "Insufficient credits"),
                "credits_required": pricing_info.get("credits_required", 0),
                "used_free_allowance": False,
                "already_unlocked": already_unlocked
            }
        
        return {
            "allowed": True,
            "credits_required": pricing_info.get("credits_required", 0),
            "used_free_allowance": pricing_info.get("used_free_allowance", False),
            "already_unlocked": already_unlocked,
            "message": "Permission granted"
        }
        
    except Exception as e:
        logger.error(f"Permission check failed for {user_id}/{action_type}: {e}")
        return {
            "allowed": False,
            "error": f"Permission check failed: {str(e)}",
            "credits_required": 0,
            "used_free_allowance": False,
            "already_unlocked": False
        }

async def _atomic_create_access_records(db, user_id: UUID, username: str, credits_spent: int):
    """Create access records in the same transaction"""
    try:
        # Get profile information
        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        if not profile:
            raise Exception(f"Profile not found: {username}")
        
        # Get database user ID for user_profile_access table
        user_query = select(User.id).where(User.supabase_user_id == str(user_id))
        user_result = await db.execute(user_query)
        database_user_id = user_result.scalar_one_or_none()
        
        if not database_user_id:
            raise Exception(f"Database user not found for Supabase ID: {user_id}")
        
        # Create unlocked_influencers record (uses Supabase user ID)
        unlocked_influencer = UnlockedInfluencer(
            user_id=user_id,  # Supabase UUID
            profile_id=profile.id,
            username=username,
            unlocked_at=datetime.now(timezone.utc),
            credits_spent=credits_spent
        )
        db.add(unlocked_influencer)
        
        # Create user_profile_access record (uses database user ID)
        profile_access = UserProfileAccess(
            user_id=database_user_id,  # Database UUID
            profile_id=profile.id,
            access_level='full',
            accessed_at=datetime.now(timezone.utc),
            credits_spent=credits_spent
        )
        db.add(profile_access)
        
        # Don't commit here - let the main transaction handle it
        logger.info(f"Access records prepared for {user_id} -> {username}")
        
    except Exception as e:
        logger.error(f"Failed to create access records for {user_id}/{username}: {e}")
        raise e