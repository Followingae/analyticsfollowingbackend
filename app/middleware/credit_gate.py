"""
Credit Gate Middleware - Decorators and utilities for credit-gated actions
Provides decorators to protect API endpoints with credit requirements
"""
import logging
from functools import wraps
from typing import Optional, Callable, Any, Dict
from uuid import UUID
from fastapi import HTTPException, Depends, Request
from fastapi.responses import JSONResponse

from app.models.auth import UserInDB
from app.services.credit_wallet_service import credit_wallet_service
from app.services.credit_pricing_service import credit_pricing_service
from app.services.credit_transaction_service import credit_transaction_service
from app.models.credits import CanPerformActionResponse

logger = logging.getLogger(__name__)


class CreditGateException(HTTPException):
    """Custom exception for credit gate issues"""
    def __init__(self, detail: str, status_code: int = 402, headers: Dict[str, str] = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


def requires_credits(
    action_type: str,
    credits_required: Optional[int] = None,
    create_wallet_if_missing: bool = True,
    return_detailed_response: bool = False,
    check_unlock_status: bool = False,
    unlock_key_param: str = "username"
):
    """
    Decorator to protect endpoints with credit requirements
    
    Args:
        action_type: Action type for pricing lookup
        credits_required: Override default action cost
        create_wallet_if_missing: Auto-create wallet for new users
        return_detailed_response: Return detailed credit info in response
        check_unlock_status: For profile actions, check if already unlocked (skips credit check)
        unlock_key_param: Parameter name containing username/identifier for unlock check
    
    Usage:
        @requires_credits("profile_analysis", credits_required=25, check_unlock_status=True)
        async def analyze_profile(username: str, current_user = Depends(get_current_user)):
            # Endpoint logic here - will skip credit check if profile already unlocked
    """
    def decorator(endpoint_func: Callable) -> Callable:
        @wraps(endpoint_func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, UserInDB):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for credit-gated actions"
                )
            
            user_id = UUID(str(current_user.id))
            
            # CRITICAL OPTIMIZATION: Check if profile is already unlocked (skip credit check)
            if check_unlock_status:
                try:
                    from app.database.connection import get_session
                    from app.database.unified_models import UnlockedInfluencer, Profile, User
                    from sqlalchemy import select, and_
                    
                    profile_identifier = None
                    lookup_type = None
                    
                    # Handle different parameter types
                    if unlock_key_param in kwargs:
                        profile_identifier = kwargs.get(unlock_key_param)
                        lookup_type = "username" if unlock_key_param == "username" else "profile_id"
                    # Handle request body with profile_id
                    elif "unlock_request" in kwargs and hasattr(kwargs["unlock_request"], "profile_id"):
                        profile_identifier = kwargs["unlock_request"].profile_id
                        lookup_type = "profile_id"
                    
                    if profile_identifier:
                        async with get_session() as session:
                            # CRITICAL FIX: Get the correct database user ID first
                            user_query = select(User.id).where(User.supabase_user_id == str(user_id))
                            user_result = await session.execute(user_query)
                            database_user_id = user_result.scalar_one_or_none()
                            
                            if database_user_id:
                                # Check if user has already unlocked this profile
                                if lookup_type == "username":
                                    unlock_check_query = select(UnlockedInfluencer).join(Profile).where(
                                        and_(
                                            UnlockedInfluencer.user_id == database_user_id,
                                            Profile.username == profile_identifier
                                        )
                                    )
                                else:  # profile_id
                                    unlock_check_query = select(UnlockedInfluencer).where(
                                        and_(
                                            UnlockedInfluencer.user_id == database_user_id,
                                            UnlockedInfluencer.profile_id == profile_identifier
                                        )
                                    )
                                
                                unlock_result = await session.execute(unlock_check_query)
                                existing_unlock = unlock_result.scalar_one_or_none()
                            else:
                                existing_unlock = None
                            
                            if existing_unlock:
                                logger.info(f"Profile {profile_identifier} ({lookup_type}) already unlocked for user {user_id}, skipping credit check")
                                
                                # Execute endpoint directly without credit validation
                                result = await endpoint_func(*args, **kwargs)
                                
                                # Add unlock info to response if requested
                                if return_detailed_response and isinstance(result, dict):
                                    result["credit_info"] = {
                                        "credits_spent": 0,
                                        "used_free_allowance": False,
                                        "already_unlocked": True,
                                        "unlock_date": existing_unlock.unlocked_at.isoformat(),
                                        "reason": "Profile already unlocked"
                                    }
                                
                                return result
                                
                except Exception as e:
                    logger.warning(f"Failed to check unlock status for {unlock_key_param}={kwargs.get(unlock_key_param)}: {e}")
                    # Continue with normal credit check if unlock check fails
            
            try:
                # Get or create wallet
                wallet = await credit_wallet_service.get_wallet(user_id)
                if not wallet and create_wallet_if_missing:
                    logger.info(f"Creating wallet for new user {user_id}")
                    wallet = await credit_wallet_service.create_wallet(user_id)
                
                if not wallet:
                    raise CreditGateException(
                        "Credit wallet not found. Please contact support.",
                        status_code=402
                    )
                
                # Check if action can be performed
                permission_check = await credit_wallet_service.can_perform_action(
                    user_id, action_type, credits_required
                )
                
                if not permission_check.can_perform:
                    # Handle different rejection reasons
                    if permission_check.reason == "wallet_locked":
                        raise CreditGateException(
                            "Your credit wallet is locked. Please renew your subscription to continue.",
                            status_code=402
                        )
                    elif permission_check.reason == "insufficient_credits":
                        raise CreditGateException(
                            f"Insufficient credits. Required: {permission_check.credits_required}, "
                            f"Available: {permission_check.wallet_balance}. "
                            f"Need {permission_check.credits_needed} more credits.",
                            status_code=402,
                            headers={
                                "X-Credits-Required": str(permission_check.credits_required),
                                "X-Credits-Available": str(permission_check.wallet_balance),
                                "X-Credits-Needed": str(permission_check.credits_needed)
                            }
                        )
                    elif permission_check.reason == "no_wallet":
                        raise CreditGateException(
                            "Credit wallet not found. Please contact support.",
                            status_code=402
                        )
                    else:
                        raise CreditGateException(
                            f"Action not allowed: {permission_check.message or permission_check.reason}",
                            status_code=402
                        )
                
                # Prepare for credit spending
                will_spend_credits = permission_check.credits_required > 0
                used_free_allowance = permission_check.reason == "free_allowance"
                
                # Execute the endpoint
                try:
                    result = await endpoint_func(*args, **kwargs)
                    
                    # Spend credits after successful execution
                    transaction = None
                    if will_spend_credits:
                        # Extract reference information from kwargs if available
                        reference_id = kwargs.get("username") or kwargs.get("profile_id")
                        reference_type = "profile" if reference_id else "action"
                        
                        transaction = await credit_wallet_service.spend_credits(
                            user_id=user_id,
                            amount=permission_check.credits_required,
                            action_type=action_type,
                            reference_id=str(reference_id) if reference_id else None,
                            reference_type=reference_type,
                            description=f"Credits spent for {action_type}"
                        )
                    
                    # CRITICAL FIX: Create access records for profile unlock actions
                    if action_type == "profile_analysis" and transaction and reference_id:
                        try:
                            await _create_profile_access_records(
                                user_id=user_id,
                                username=reference_id,
                                credits_spent=permission_check.credits_required,
                                transaction_id=transaction.id if transaction else None
                            )
                            logger.info(f"Created access records for user {user_id} unlocking {reference_id}")
                        except Exception as access_error:
                            logger.error(f"Failed to create access records for {user_id}/{reference_id}: {access_error}")
                            # Don't fail the entire operation - user already paid
                    
                    # Track usage for analytics
                    await credit_transaction_service.track_action_usage(
                        user_id=user_id,
                        action_type=action_type,
                        used_free_allowance=used_free_allowance,
                        credits_spent=permission_check.credits_required
                    )
                    
                    # Add credit information to response if requested
                    if return_detailed_response:
                        if isinstance(result, dict):
                            result["credit_info"] = {
                                "credits_spent": permission_check.credits_required,
                                "used_free_allowance": used_free_allowance,
                                "remaining_balance": (
                                    permission_check.wallet_balance - permission_check.credits_required
                                ) if will_spend_credits else permission_check.wallet_balance,
                                "transaction_id": transaction.id if transaction else None
                            }
                    
                    return result
                    
                except Exception as e:
                    # If the endpoint failed, don't charge credits
                    logger.error(f"Endpoint failed after credit check for user {user_id}: {e}")
                    raise
                
            except CreditGateException:
                # Re-raise credit gate exceptions
                raise
            except Exception as e:
                logger.error(f"Credit gate error for user {user_id}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Internal error processing credit requirements"
                )
        
        return wrapper
    return decorator


async def check_credits_only(
    user_id: UUID,
    action_type: str,
    credits_required: Optional[int] = None
) -> CanPerformActionResponse:
    """
    Utility function to check credits without spending them
    Useful for frontend credit validation
    """
    try:
        wallet = await credit_wallet_service.get_wallet(user_id)
        if not wallet:
            return CanPerformActionResponse(
                can_perform=False,
                reason="no_wallet",
                message="Credit wallet not found"
            )
        
        return await credit_wallet_service.can_perform_action(
            user_id, action_type, credits_required
        )
        
    except Exception as e:
        logger.error(f"Error checking credits for user {user_id}: {e}")
        return CanPerformActionResponse(
            can_perform=False,
            reason="error",
            message="Error checking credit requirements"
        )


def add_credit_headers(response: JSONResponse, credit_info: Dict[str, Any]) -> JSONResponse:
    """Add credit information to response headers"""
    if credit_info:
        response.headers["X-Credits-Spent"] = str(credit_info.get("credits_spent", 0))
        response.headers["X-Used-Free-Allowance"] = str(credit_info.get("used_free_allowance", False))
        response.headers["X-Remaining-Balance"] = str(credit_info.get("remaining_balance", 0))
        if credit_info.get("transaction_id"):
            response.headers["X-Transaction-ID"] = str(credit_info["transaction_id"])
    
    return response


class CreditGateMiddleware:
    """
    Middleware class for handling credit requirements at the application level
    Can be used as an alternative to decorators for more complex scenarios
    """
    
    def __init__(self):
        self.protected_paths = {}
    
    def register_protected_path(
        self,
        path: str,
        action_type: str,
        credits_required: Optional[int] = None
    ):
        """Register a path as credit-protected"""
        self.protected_paths[path] = {
            "action_type": action_type,
            "credits_required": credits_required
        }
    
    async def __call__(self, request: Request, call_next):
        """Process request through credit gate"""
        path = request.url.path
        
        if path in self.protected_paths:
            # Handle credit-gated paths
            protection_config = self.protected_paths[path]
            
            # Extract user from request
            # This would need integration with your auth system
            # For now, we'll skip middleware implementation
            pass
        
        response = await call_next(request)
        return response


async def _create_profile_access_records(user_id: UUID, username: str, credits_spent: int, transaction_id: Optional[int] = None):
    """
    Create both unlocked_influencers and user_profile_access records
    when a user unlocks a profile by spending credits
    """
    from app.database.connection import get_session
    from app.database.unified_models import Profile, UnlockedInfluencer, UserProfileAccess
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta
    
    async with get_session() as db:
        try:
            # CRITICAL FIX: Handle mixed user ID requirements
            # unlocked_influencers uses Supabase user ID (auth.users)
            # user_profile_access uses database user ID (users table)
            supabase_user_id = user_id
            
            # Get database user ID for user_profile_access table
            from app.database.unified_models import User
            user_query = select(User.id).where(User.supabase_user_id == str(user_id))
            user_result = await db.execute(user_query)
            database_user_id = user_result.scalar_one_or_none()
            
            if not database_user_id:
                logger.error(f"No database user found for Supabase ID {user_id}")
                return
                
            logger.info(f"Using Supabase ID {supabase_user_id} for unlocked_influencers, Database ID {database_user_id} for user_profile_access")
            
            # Get profile by username
            profile_query = select(Profile).where(Profile.username == username)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()
            
            if not profile:
                logger.error(f"Profile not found for username: {username}")
                return
                
            # Check if unlocked_influencers record already exists
            unlock_query = select(UnlockedInfluencer).where(
                UnlockedInfluencer.user_id == supabase_user_id,
                UnlockedInfluencer.profile_id == profile.id
            )
            unlock_result = await db.execute(unlock_query)
            existing_unlock = unlock_result.scalar_one_or_none()
            
            current_time = datetime.now(timezone.utc)
            
            if not existing_unlock:
                # Create unlocked_influencers record - FIXED: Use Supabase user ID
                unlocked_record = UnlockedInfluencer(
                    user_id=supabase_user_id,
                    profile_id=profile.id,
                    username=username,  # CRITICAL FIX: Include username field
                    unlocked_at=current_time,
                    credits_spent=credits_spent,
                    transaction_id=transaction_id  # Link to credit transaction if available
                )
                db.add(unlocked_record)
                logger.info(f"Created unlocked_influencers record for user {supabase_user_id}, profile {profile.id} ({username})")
            
            # Check if user_profile_access record exists
            access_query = select(UserProfileAccess).where(
                UserProfileAccess.user_id == database_user_id,
                UserProfileAccess.profile_id == profile.id
            )
            access_result = await db.execute(access_query)
            existing_access = access_result.scalar_one_or_none()
            
            if not existing_access:
                # Create user_profile_access record (30 day access)
                expires_at = current_time + timedelta(days=30)
                access_record = UserProfileAccess(
                    user_id=database_user_id,
                    profile_id=profile.id,
                    granted_at=current_time,
                    expires_at=expires_at
                )
                db.add(access_record)
                logger.info(f"Created user_profile_access record for user {database_user_id}, profile {profile.id}")
            
            await db.commit()
            logger.info(f"Successfully created access records for user {database_user_id} -> profile {username}")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create access records: {e}")
            raise


# Global middleware instance
credit_gate_middleware = CreditGateMiddleware()