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
    return_detailed_response: bool = False
):
    """
    Decorator to protect endpoints with credit requirements
    
    Args:
        action_type: Action type for pricing lookup
        credits_required: Override default action cost
        create_wallet_if_missing: Auto-create wallet for new users
        return_detailed_response: Return detailed credit info in response
    
    Usage:
        @requires_credits("influencer_unlock", credits_required=25)
        async def unlock_influencer(username: str, current_user = Depends(get_current_user)):
            # Endpoint logic here
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


# Global middleware instance
credit_gate_middleware = CreditGateMiddleware()