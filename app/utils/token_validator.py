"""
🔐 Centralized Token Validation Utility
Provides bulletproof JWT token validation with detailed error reporting
"""

import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TokenValidationError(Enum):
    """Token validation error types"""
    EMPTY_TOKEN = "empty_token"
    MALFORMED_TOKEN = "malformed_token"
    INVALID_LENGTH = "invalid_length"
    INVALID_FORMAT = "invalid_format"
    CORRUPTED_TOKEN = "corrupted_token"

@dataclass
class TokenValidationResult:
    """Result of token validation"""
    is_valid: bool
    token: Optional[str] = None
    error_type: Optional[TokenValidationError] = None
    error_message: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
    frontend_actions: Optional[list] = None

class TokenValidator:
    """
    Bulletproof JWT token validator with comprehensive error handling
    """
    
    # Token validation constants
    MIN_TOKEN_LENGTH = 100
    MAX_TOKEN_LENGTH = 2000
    EXPECTED_JWT_SEGMENTS = 3
    
    @staticmethod
    def validate_token(token: Optional[str], context: str = "unknown") -> TokenValidationResult:
        """
        Comprehensive token validation with detailed error reporting
        
        Args:
            token: JWT token to validate
            context: Context for logging (e.g., "auth_middleware", "optional_auth")
        
        Returns:
            TokenValidationResult with validation status and error details
        """
        if not token:
            return TokenValidationResult(
                is_valid=False,
                error_type=TokenValidationError.EMPTY_TOKEN,
                error_message="No authentication token provided",
                frontend_actions=["Include Authorization: Bearer <token> header"]
            )
        
        # Clean token
        cleaned_token = token.strip()
        if not cleaned_token:
            return TokenValidationResult(
                is_valid=False,
                error_type=TokenValidationError.EMPTY_TOKEN,
                error_message="Empty token after cleanup",
                frontend_actions=["Check token storage and retrieval logic"]
            )
        
        # Validate JWT structure (3 segments separated by dots)
        token_parts = cleaned_token.split('.')
        if len(token_parts) != TokenValidator.EXPECTED_JWT_SEGMENTS:
            logger.warning(f"TOKEN_VALIDATOR[{context}]: Malformed token - {len(token_parts)} segments instead of 3")
            return TokenValidationResult(
                is_valid=False,
                token=cleaned_token,
                error_type=TokenValidationError.MALFORMED_TOKEN,
                error_message=f"Invalid JWT format: expected 3 segments, got {len(token_parts)}",
                debug_info={
                    "token_segments": len(token_parts),
                    "token_length": len(cleaned_token),
                    "token_preview": cleaned_token[:30] + "..." if len(cleaned_token) > 30 else cleaned_token,
                    "context": context
                },
                frontend_actions=[
                    "Clear localStorage/sessionStorage auth tokens",
                    "Redirect to login page",
                    "Check token storage/retrieval implementation",
                    "Verify API response handling after login"
                ]
            )
        
        # Validate token length
        if len(cleaned_token) < TokenValidator.MIN_TOKEN_LENGTH:
            logger.warning(f"TOKEN_VALIDATOR[{context}]: Token too short - {len(cleaned_token)} characters")
            return TokenValidationResult(
                is_valid=False,
                token=cleaned_token,
                error_type=TokenValidationError.INVALID_LENGTH,
                error_message=f"Token too short: {len(cleaned_token)} characters (minimum {TokenValidator.MIN_TOKEN_LENGTH})",
                debug_info={
                    "token_length": len(cleaned_token),
                    "min_length": TokenValidator.MIN_TOKEN_LENGTH,
                    "context": context
                },
                frontend_actions=["Check token truncation during storage/transmission"]
            )
        
        if len(cleaned_token) > TokenValidator.MAX_TOKEN_LENGTH:
            logger.warning(f"TOKEN_VALIDATOR[{context}]: Token too long - {len(cleaned_token)} characters")
            return TokenValidationResult(
                is_valid=False,
                token=cleaned_token,
                error_type=TokenValidationError.INVALID_LENGTH,
                error_message=f"Token too long: {len(cleaned_token)} characters (maximum {TokenValidator.MAX_TOKEN_LENGTH})",
                debug_info={
                    "token_length": len(cleaned_token),
                    "max_length": TokenValidator.MAX_TOKEN_LENGTH,
                    "context": context
                },
                frontend_actions=["Check for token corruption or concatenation"]
            )
        
        # Basic format validation (JWT segments should be base64-like)
        for i, part in enumerate(token_parts):
            if not part or not TokenValidator._is_base64_like(part):
                return TokenValidationResult(
                    is_valid=False,
                    token=cleaned_token,
                    error_type=TokenValidationError.INVALID_FORMAT,
                    error_message=f"Invalid JWT segment {i+1}: not valid base64 format",
                    debug_info={
                        "invalid_segment": i+1,
                        "segment_preview": part[:20] + "..." if len(part) > 20 else part,
                        "context": context
                    },
                    frontend_actions=["Check token corruption during transmission"]
                )
        
        # Token passed all validation checks
        logger.debug(f"TOKEN_VALIDATOR[{context}]: Token validation passed - {len(cleaned_token)} chars, 3 segments")
        return TokenValidationResult(
            is_valid=True,
            token=cleaned_token,
            debug_info={
                "token_length": len(cleaned_token),
                "token_segments": len(token_parts),
                "context": context
            }
        )
    
    @staticmethod
    def _is_base64_like(s: str) -> bool:
        """Check if string looks like base64 (contains valid base64 characters)"""
        if not s:
            return False
        # JWT base64 uses URL-safe alphabet and padding is optional
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=')
        return all(c in valid_chars for c in s)
    
    @staticmethod
    def extract_token_from_header(auth_header: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract token from Authorization header
        
        Returns:
            Tuple of (token, error_message)
        """
        if not auth_header:
            return None, "No Authorization header provided"
        
        if not auth_header.startswith("Bearer "):
            return None, f"Authorization header must start with 'Bearer ': got '{auth_header[:50]}...'"
        
        token = auth_header[7:].strip()  # Remove "Bearer " prefix
        if not token:
            return None, "Authorization header contains 'Bearer ' but no token"
        
        return token, None

# Create singleton instance
token_validator = TokenValidator()