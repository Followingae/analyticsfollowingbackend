"""
Discovery System Configuration

Configuration settings for Similar Profiles Discovery and Background Processing
"""

import os
from typing import List, Dict, Any
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings


class DiscoverySettings(BaseSettings):
    """Discovery system configuration"""

    # Similar Profiles Discovery Settings
    DISCOVERY_ENABLED: bool = True  # ✅ ENABLED - Infinite loop prevention fixed
    DISCOVERY_MAX_CONCURRENT_PROFILES: int = 3
    DISCOVERY_BATCH_SIZE: int = 10
    DISCOVERY_RETRY_ATTEMPTS: int = 3
    DISCOVERY_RETRY_DELAY_SECONDS: int = 60

    # Background Processing Settings
    DISCOVERY_QUEUE_NAME: str = "similar_profiles_discovery"
    DISCOVERY_PRIORITY: str = "low"  # low, normal, high
    DISCOVERY_TASK_TIMEOUT_SECONDS: int = 300  # 5 minutes per profile

    # Rate Limiting
    DISCOVERY_RATE_LIMIT_PROFILES_PER_HOUR: int = 100
    DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY: int = 1000

    # Quality Filters
    DISCOVERY_MIN_FOLLOWERS_COUNT: int = 1000  # Skip profiles with < 1k followers
    DISCOVERY_MAX_PROFILES_TO_DISCOVER: int = 500  # Max similar profiles to process per day
    DISCOVERY_SKIP_EXISTING_PROFILES: bool = True  # Skip profiles already in database

    # Logging and Monitoring
    DISCOVERY_LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    DISCOVERY_ENABLE_METRICS: bool = True
    DISCOVERY_METRICS_INTERVAL_SECONDS: int = 300  # Report metrics every 5 minutes

    # Database Settings
    DISCOVERY_DB_BATCH_COMMIT_SIZE: int = 20
    DISCOVERY_DB_CONNECTION_TIMEOUT: int = 30

    # Error Handling
    DISCOVERY_CONTINUE_ON_ERROR: bool = True  # Don't stop entire process if one profile fails
    DISCOVERY_MAX_FAILED_PROFILES_PER_BATCH: int = 5  # Stop batch if too many failures

    # Feature Flags
    DISCOVERY_ENABLE_SIMILAR_PROFILES: bool = True
    DISCOVERY_ENABLE_POST_ANALYTICS_HOOK: bool = True
    DISCOVERY_ENABLE_CREATOR_ANALYTICS_HOOK: bool = True

    class Config:
        env_prefix = "DISCOVERY_"
        case_sensitive = True


# Global discovery settings instance
discovery_settings = DiscoverySettings()


# Discovery System Constants
class DiscoveryConstants:
    """Constants for discovery system"""

    # Profile Quality Thresholds
    MIN_FOLLOWERS_FOR_DISCOVERY = 1000
    MIN_POSTS_FOR_DISCOVERY = 5
    MAX_SIMILAR_PROFILES_PER_SOURCE = 15

    # Processing Priorities
    PRIORITY_HIGH = "high"     # For manual admin requests
    PRIORITY_NORMAL = "normal" # For user-triggered analytics
    PRIORITY_LOW = "low"       # For background discovery

    # Discovery Sources
    SOURCE_CREATOR_ANALYTICS = "creator_analytics"
    SOURCE_POST_ANALYTICS = "post_analytics"
    SOURCE_MANUAL_ADMIN = "manual_admin"
    SOURCE_BATCH_REPAIR = "batch_repair"

    # Profile Status
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"

    # Error Types
    ERROR_PROFILE_NOT_FOUND = "profile_not_found"
    ERROR_APIFY_FAILED = "apify_failed"
    ERROR_AI_ANALYSIS_FAILED = "ai_analysis_failed"
    ERROR_DATABASE_ERROR = "database_error"
    ERROR_RATE_LIMITED = "rate_limited"
    ERROR_TIMEOUT = "timeout"


# Configuration Validation
def validate_discovery_config() -> Dict[str, Any]:
    """Validate discovery configuration and return status"""
    issues = []
    warnings = []

    # Check critical settings
    if not discovery_settings.DISCOVERY_ENABLED:
        warnings.append("Discovery system is disabled")

    if discovery_settings.DISCOVERY_MAX_CONCURRENT_PROFILES > 10:
        warnings.append("High concurrency setting may overload system")

    if discovery_settings.DISCOVERY_MIN_FOLLOWERS_COUNT < 100:
        warnings.append("Very low follower threshold may process low-quality profiles")

    if discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY > 2000:
        warnings.append("High daily rate limit may exceed API quotas")

    # Check dependencies
    try:
        from app.core.config import settings
        if not settings.APIFY_API_TOKEN:
            issues.append("APIFY_API_TOKEN not configured")
    except ImportError:
        issues.append("Cannot import main settings")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "settings": {
            "enabled": discovery_settings.DISCOVERY_ENABLED,
            "max_concurrent": discovery_settings.DISCOVERY_MAX_CONCURRENT_PROFILES,
            "batch_size": discovery_settings.DISCOVERY_BATCH_SIZE,
            "min_followers": discovery_settings.DISCOVERY_MIN_FOLLOWERS_COUNT,
            "daily_limit": discovery_settings.DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY
        }
    }


# Environment Variable Documentation
DISCOVERY_ENV_VARS = {
    "DISCOVERY_ENABLED": "Enable/disable discovery system (default: True)",
    "DISCOVERY_MAX_CONCURRENT_PROFILES": "Max concurrent profile processing (default: 3)",
    "DISCOVERY_BATCH_SIZE": "Batch size for processing (default: 10)",
    "DISCOVERY_MIN_FOLLOWERS_COUNT": "Min followers for discovery (default: 1000)",
    "DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY": "Daily processing limit (default: 1000)",
    "DISCOVERY_LOG_LEVEL": "Logging level (default: INFO)",
    "DISCOVERY_CONTINUE_ON_ERROR": "Continue processing on errors (default: True)"
}