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
            # logger.debug(f"[SEARCH] DEBUG: Analyzing args={len(args)} kwargs={len(kwargs)}")
            # logger.debug(f"[SEARCH] DEBUG: kwargs keys: {list(kwargs.keys())}")
            
            # Check args first
            for i, arg in enumerate(args):
                logger.info(f"[SEARCH] DEBUG: arg[{i}] type={type(arg)} value={str(arg)[:100]}")
                if hasattr(arg, 'method') and hasattr(arg, 'url'):  # FastAPI Request
                    request = arg
                    logger.info(f"[SEARCH] DEBUG: Found Request object in args")
                # Check for User object with id attribute (FastAPI dependency injection)
                if hasattr(arg, 'id') and hasattr(arg, 'email'):  # User object
                    try:
                        user_id = UUID(str(arg.id))
                        logger.info(f"[SEARCH] DEBUG: Found User object in args with id={user_id}")
                    except Exception as e:
                        logger.error(f"[SEARCH] DEBUG: Failed to extract user_id from User object in args: {e}")
                elif isinstance(arg, str) and len(arg) == 36:  # UUID string
                    try:
                        user_id = UUID(arg)
                        logger.info(f"[SEARCH] DEBUG: Found UUID string in args {user_id}")
                    except:
                        pass
            
            # Check kwargs for User object and Database session (FastAPI dependency injection)
            db_session = None
            for key, value in kwargs.items():
                logger.info(f"[SEARCH] DEBUG: kwarg[{key}] type={type(value)} value={str(value)[:100]}")
                if hasattr(value, 'id') and hasattr(value, 'email'):  # User object
                    try:
                        user_id = UUID(str(value.id))
                        # logger.debug(f"[SEARCH] DEBUG: Found User object in kwargs[{key}] with id={user_id}")
                    except Exception as e:
                        logger.error(f"[SEARCH] DEBUG: Failed to extract user_id from User object in kwargs: {e}")
                elif hasattr(value, 'method') and hasattr(value, 'url'):  # FastAPI Request
                    request = value
                    logger.info(f"[SEARCH] DEBUG: Found Request object in kwargs[{key}]")
                elif str(type(value)).find('AsyncSession') != -1:  # Database session
                    db_session = value
                    logger.info(f"[SEARCH] DEBUG: Found Database session in kwargs[{key}]")

            # Also check args for database session (when called from another route)
            if not db_session:
                for i, arg in enumerate(args):
                    if str(type(arg)).find('AsyncSession') != -1:  # Database session
                        db_session = arg
                        logger.info(f"[SEARCH] DEBUG: Found Database session in args[{i}]")
                        break
            
            # Extract reference_id from URL path, kwargs, or function args
            reference_id = None

            # First check kwargs
            if 'username' in kwargs:
                reference_id = kwargs['username']
                logger.info(f"[SEARCH] DEBUG: Found username in kwargs: {reference_id}")

            # Then check function args (first string argument is usually username)
            elif args and len(args) > 0 and isinstance(args[0], str) and len(args[0]) > 0:
                reference_id = args[0]
                logger.info(f"[SEARCH] DEBUG: Using args[0] as username: {reference_id}")

            # Finally check request path params
            elif request and hasattr(request, 'path_params'):
                reference_id = request.path_params.get('username')
                logger.info(f"[SEARCH] DEBUG: Found username in request path_params: {reference_id}")
            
            # logger.debug(f"[SEARCH] DEBUG: Final values - user_id={user_id}, reference_id={reference_id}, db_session={bool(db_session)}")
            
            if not user_id or not reference_id:
                logger.error(f"[SEARCH] DEBUG: Missing required values - user_id={user_id}, reference_id={reference_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unable to extract user_id or reference_id for credit gate. user_id={bool(user_id)}, reference_id={bool(reference_id)}"
                )
            
            if not db_session:
                logger.error(f"[SEARCH] DEBUG: Database session not found in function arguments")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available for atomic transaction"
                )
                
            logger.info(f"[SECURE] ATOMIC CREDIT GATE: {action_type} for user {user_id}, reference {reference_id}")
            
            # BEGIN ATOMIC TRANSACTION (using existing session)
            db = db_session
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
                already_unlocked = permission_check.get("already_unlocked", False)

                # FAST PATH: Skip all credit operations for already unlocked profiles
                if already_unlocked and credits_required == 0:
                    logger.info(f"[FAST-PATH] Profile {reference_id} already unlocked - executing function directly")

                    # Execute function immediately without credit operations
                    try:
                        result = await func(*args, **kwargs)
                        logger.info(f"[FAST-PATH] Function executed successfully for {reference_id}")

                        # Add credit information to response if requested
                        if return_detailed_response and isinstance(result, dict):
                            result["credit_info"] = {
                                "credits_spent": 0,
                                "used_free_allowance": False,
                                "remaining_balance": "N/A - Already unlocked",
                                "transaction_id": None,
                                "access_granted": True
                            }

                        return result

                    except Exception as e:
                        logger.error(f"[FAST-PATH] Function execution failed for {reference_id}: {e}")
                        raise

                # Step 2: Execute BULLETPROOF credit transaction
                transaction_result = None
                if credits_required > 0:
                    from app.services.bulletproof_transaction_service import bulletproof_transaction_service

                    # Collect metadata for audit trail
                    transaction_metadata = {
                        "action_type": action_type,
                        "reference_id": reference_id,
                        "user_agent": getattr(request, "headers", {}).get("user-agent", "unknown"),
                        "ip_address": getattr(request, "client", {}).host if hasattr(request, "client") else "unknown",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }

                    try:
                        transaction_result = await bulletproof_transaction_service.execute_credit_transaction(
                            db=db,
                            user_id=user_id,
                            action_type=action_type,
                            reference_id=reference_id,
                            credits_amount=credits_required,
                            metadata=transaction_metadata
                        )

                        if not transaction_result.success:
                            raise AtomicTransactionError(
                                transaction_result.error_message or "Credit transaction failed",
                                "bulletproof_transaction"
                            )

                        logger.info(f"💳 BULLETPROOF PAYMENT: {credits_required} credits for user {user_id} | Intent: {transaction_result.intent_id}")
                    except Exception as e:
                        raise AtomicTransactionError(str(e), "spend_credits")
                
                # Step 3: Execute the wrapped function (may create profile for profile_analysis)
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"[SUCCESS] Function executed successfully for {reference_id}")
                except Exception as e:
                    raise AtomicTransactionError(str(e), "execute_function")
                
                # Step 4: Access records handled by bulletproof transaction service
                access_records_created = False
                if credits_required > 0 and transaction_result:
                    # Access records already created by bulletproof service
                    access_records_created = transaction_result.access_record_id is not None
                    logger.info(f"✅ BULLETPROOF ACCESS RECORDS: Created={access_records_created} | ID={transaction_result.access_record_id}")
                elif credits_required == 0:
                    # Admin user - no access tracking needed
                    access_records_created = True
                    logger.info(f"📋 Skipping access records for admin user {user_id} -> {reference_id}")

                # Step 5: Commit only the main function transaction (credits already committed)
                await db.commit()
                logger.info(f"✅ FUNCTION TRANSACTION COMPLETED for {user_id} -> {reference_id}")
                
                # Add bulletproof credit information to response if requested
                if return_detailed_response and isinstance(result, dict):
                    result["credit_info"] = {
                        "credits_spent": credits_required,
                        "used_free_allowance": used_free_allowance,
                        "remaining_balance": transaction_result.final_balance if transaction_result else 0,
                        "transaction_id": str(transaction_result.transaction_id) if transaction_result and transaction_result.transaction_id else None,
                        "transaction_intent_id": transaction_result.intent_id if transaction_result else None,
                        "access_granted": access_records_created or permission_check["already_unlocked"],
                        "bulletproof_verified": True if transaction_result and transaction_result.success else False
                    }
                
                return result
                    
            except HTTPException as http_exc:
                # CRITICAL: HTTPException from wrapped function - rollback but preserve user-friendly response
                await db.rollback()
                logger.error(f"[ALERT] HTTPException in atomic transaction: {http_exc.detail}")
                logger.error(f"[SYNC] ROLLBACK COMPLETED - User {user_id} was NOT charged")

                # Re-raise the HTTPException with rollback completed
                raise http_exc

            except AtomicTransactionError as e:
                # Rollback the entire transaction
                await db.rollback()
                logger.error(f"[ALERT] ATOMIC TRANSACTION FAILED at {e.step}: {e.message}")
                logger.error(f"[SYNC] ROLLBACK COMPLETED - User {user_id} was NOT charged")

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Transaction failed at {e.step}: {e.message}"
                )

            except Exception as e:
                # Unexpected error - rollback
                await db.rollback()
                logger.error(f"[ALERT] UNEXPECTED ERROR in atomic transaction: {e}")
                logger.error(f"[SYNC] ROLLBACK COMPLETED - User {user_id} was NOT charged")

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
                logger.info(f"[FAST-PATH] Profile {reference_id} already unlocked for user {user_id} - skipping ALL credit checks")
                return {
                    "allowed": True,
                    "credits_required": 0,
                    "used_free_allowance": False,
                    "already_unlocked": True,
                    "message": "Profile already unlocked - fast path"
                }
        
        # Get pricing information with comprehensive error handling
        try:
            # logger.debug(f"[SEARCH] DEBUG: Getting pricing info for user {user_id}, action {action_type}")
            pricing_info = await credit_wallet_service.can_perform_action(user_id, action_type)
            # logger.debug(f"[SEARCH] DEBUG: Pricing info - can_perform={pricing_info.can_perform}, reason='{pricing_info.reason}', credits_required={pricing_info.credits_required}")
        except Exception as pricing_error:
            logger.error(f"[ERROR] CRITICAL: Credit pricing service failed: {pricing_error}")
            return {
                "allowed": False,
                "error": f"Credit service temporarily unavailable: {str(pricing_error)}",
                "credits_required": 0,
                "used_free_allowance": False,
                "already_unlocked": already_unlocked
            }
        
        if not pricing_info.can_perform:
            error_msg = pricing_info.reason or f"Cannot perform action {action_type} - insufficient credits or permissions"
            logger.error(f"[BLOCKED] Permission denied: {error_msg}")
            return {
                "allowed": False,
                "error": error_msg,
                "credits_required": pricing_info.credits_required,
                "used_free_allowance": False,
                "already_unlocked": already_unlocked
            }
        
        return {
            "allowed": True,
            "credits_required": pricing_info.credits_required,
            "used_free_allowance": pricing_info.free_remaining > 0,
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

# OLD FLAWED TRANSACTION LOGIC REMOVED
# Now handled by bulletproof_transaction_service for enterprise-grade consistency