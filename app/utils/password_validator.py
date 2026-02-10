"""
Password validation utility for ensuring strong passwords BEFORE payment processing
"""
import re
from typing import Tuple

# List of common passwords that should be rejected
COMMON_PASSWORDS = [
    'password', 'password123', '123456', '123456789', 'qwerty', 'abc123',
    'password1', '12345678', '111111', '1234567', 'sunshine', 'qwerty123',
    'iloveyou', 'princess', 'admin', 'welcome', 'monkey', '1234567890',
    'letmein', 'dragon', 'password123!', 'test123', 'testpassword'
]

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength with comprehensive checks.

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """

    # Check minimum length
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    # Check for digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"

    # Check for special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"

    # Check if password is too common (case-insensitive)
    password_lower = password.lower()

    # Check exact match with common passwords
    if password_lower in [p.lower() for p in COMMON_PASSWORDS]:
        return False, "This password is too common. Please choose a more unique password"

    # Check if password contains common patterns
    for common in COMMON_PASSWORDS:
        if common.lower() in password_lower:
            return False, f"Password contains a common pattern ({common}). Please choose a more unique password"

    # Check for sequential patterns
    if has_sequential_pattern(password):
        return False, "Password contains sequential characters (e.g., 'abc', '123'). Please choose a more complex password"

    # Check for repeated characters
    if has_excessive_repetition(password):
        return False, "Password contains too many repeated characters. Please choose a more varied password"

    # Additional Supabase-specific checks (matching their requirements)
    # Supabase seems to reject passwords that are variations of common words
    if is_dictionary_based(password):
        return False, "Password appears to be based on a common word. Please choose a more complex password"

    return True, "Password is strong"


def has_sequential_pattern(password: str) -> bool:
    """Check if password has sequential characters"""
    password_lower = password.lower()

    # Check for alphabetic sequences
    for i in range(len(password_lower) - 2):
        if (ord(password_lower[i+1]) == ord(password_lower[i]) + 1 and
            ord(password_lower[i+2]) == ord(password_lower[i]) + 2):
            return True

    # Check for numeric sequences
    for i in range(len(password) - 2):
        if password[i:i+3].isdigit():
            if int(password[i+1]) == int(password[i]) + 1 and int(password[i+2]) == int(password[i]) + 2:
                return True

    return False


def has_excessive_repetition(password: str) -> bool:
    """Check if password has too many repeated characters"""
    # Check for same character repeated 3+ times
    for i in range(len(password) - 2):
        if password[i] == password[i+1] == password[i+2]:
            return True
    return False


def is_dictionary_based(password: str) -> bool:
    """Check if password is based on dictionary words"""
    # Remove numbers and special characters to check the base
    base = re.sub(r'[0-9!@#$%^&*(),.?":{}|<>]', '', password.lower())

    # Common dictionary words that shouldn't be password bases
    dictionary_words = [
        'password', 'admin', 'user', 'login', 'test', 'demo', 'hello',
        'welcome', 'love', 'monkey', 'dragon', 'master', 'shadow'
    ]

    for word in dictionary_words:
        if len(word) >= 4 and word in base:
            return True

    return False


def generate_password_requirements_message() -> str:
    """Get a user-friendly message about password requirements"""
    return """Password must meet ALL of these requirements:
• At least 8 characters long
• Include at least one uppercase letter (A-Z)
• Include at least one lowercase letter (a-z)
• Include at least one number (0-9)
• Include at least one special character (!@#$%^&*(),.?":{}|<>)
• Cannot be a common password (e.g., 'password123')
• Cannot contain sequential patterns (e.g., 'abc', '123')
• Cannot have excessive character repetition

Example of a strong password: SecurePass2024#Strong!"""