"""
🚨 Frontend Error Handler Utility
Provides standardized error responses for better frontend integration
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorCategory(Enum):
    """Error categories for frontend handling"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    SYSTEM = "system"
    NETWORK = "network"

class FrontendErrorHandler:
    """
    Standardized error handler for better frontend integration
    """
    
    @staticmethod
    def create_auth_error_response(
        error_type: str,
        message: str,
        debug_info: Optional[Dict[str, Any]] = None,
        frontend_actions: Optional[List[str]] = None,
        status_code: int = status.HTTP_401_UNAUTHORIZED
    ) -> HTTPException:
        """
        Create standardized authentication error response
        
        Args:
            error_type: Type of auth error (malformed_token, expired_token, etc.)
            message: Human-readable error message
            debug_info: Debug information for troubleshooting
            frontend_actions: List of suggested frontend actions
            status_code: HTTP status code
        
        Returns:
            HTTPException with standardized error format
        """
        error_detail = {
            "category": ErrorCategory.AUTHENTICATION.value,
            "error": error_type,
            "message": message,
            "action_required": "authentication_required",
            "timestamp": FrontendErrorHandler._get_timestamp()
        }
        
        # Add optional fields
        if debug_info:
            error_detail["debug_info"] = debug_info
        
        if frontend_actions:
            error_detail["frontend_actions"] = frontend_actions
        
        # Standard frontend actions for auth errors
        if not frontend_actions:
            error_detail["frontend_actions"] = [
                "Clear stored authentication tokens",
                "Redirect user to login page",
                "Show authentication required message"
            ]
        
        # Create response headers
        headers = {
            "WWW-Authenticate": "Bearer",
            "X-Error-Category": ErrorCategory.AUTHENTICATION.value,
            "X-Auth-Error": error_type,
            "X-Action-Required": "authentication_required"
        }
        
        # Add debug headers
        if debug_info:
            if "token_segments" in debug_info:
                headers["X-Token-Segments"] = str(debug_info["token_segments"])
            if "token_length" in debug_info:
                headers["X-Token-Length"] = str(debug_info["token_length"])
        
        return HTTPException(
            status_code=status_code,
            detail=error_detail,
            headers=headers
        )
    
    @staticmethod
    def create_validation_error_response(
        field_name: str,
        message: str,
        received_value: Any = None,
        expected_format: str = None
    ) -> HTTPException:
        """Create standardized validation error response"""
        error_detail = {
            "category": ErrorCategory.VALIDATION.value,
            "error": "validation_failed",
            "message": message,
            "field": field_name,
            "timestamp": FrontendErrorHandler._get_timestamp()
        }
        
        if received_value is not None:
            error_detail["received_value"] = str(received_value)
        
        if expected_format:
            error_detail["expected_format"] = expected_format
        
        error_detail["frontend_actions"] = [
            f"Check {field_name} field format",
            "Validate input before sending request",
            "Display field-specific error message"
        ]
        
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail,
            headers={
                "X-Error-Category": ErrorCategory.VALIDATION.value,
                "X-Validation-Field": field_name
            }
        )
    
    @staticmethod
    def create_rate_limit_error_response(
        limit: int,
        window_seconds: int,
        retry_after: int = 60
    ) -> HTTPException:
        """Create standardized rate limit error response"""
        error_detail = {
            "category": ErrorCategory.RATE_LIMIT.value,
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {limit} requests per {window_seconds} seconds",
            "limit": limit,
            "window_seconds": window_seconds,
            "retry_after": retry_after,
            "timestamp": FrontendErrorHandler._get_timestamp(),
            "frontend_actions": [
                f"Wait {retry_after} seconds before retrying",
                "Implement exponential backoff",
                "Show rate limit notification to user",
                "Cache responses to reduce API calls"
            ]
        }
        
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_detail,
            headers={
                "X-Error-Category": ErrorCategory.RATE_LIMIT.value,
                "X-Rate-Limit-Limit": str(limit),
                "X-Rate-Limit-Window": str(window_seconds),
                "Retry-After": str(retry_after)
            }
        )
    
    @staticmethod
    def create_system_error_response(
        error_type: str = "system_error",
        message: str = "An internal system error occurred",
        correlation_id: Optional[str] = None
    ) -> HTTPException:
        """Create standardized system error response"""
        error_detail = {
            "category": ErrorCategory.SYSTEM.value,
            "error": error_type,
            "message": message,
            "timestamp": FrontendErrorHandler._get_timestamp(),
            "frontend_actions": [
                "Retry request after a few seconds",
                "Show user-friendly error message",
                "Report error if problem persists"
            ]
        }
        
        if correlation_id:
            error_detail["correlation_id"] = correlation_id
        
        headers = {
            "X-Error-Category": ErrorCategory.SYSTEM.value,
            "X-System-Error": error_type
        }
        
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
            headers=headers
        )
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current ISO timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    @staticmethod
    def log_error_for_monitoring(
        error_type: str,
        message: str,
        context: str,
        user_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log error for monitoring and alerting"""
        log_data = {
            "error_type": error_type,
            "message": message,
            "context": context,
            "timestamp": FrontendErrorHandler._get_timestamp()
        }
        
        if user_id:
            log_data["user_id"] = user_id
        
        if additional_data:
            log_data["additional_data"] = additional_data
        
        logger.error(f"FRONTEND_ERROR: {log_data}")

# Create singleton instance
frontend_error_handler = FrontendErrorHandler()