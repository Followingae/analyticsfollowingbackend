"""
Fallback Handlers Service - Graceful degradation when services fail
Provides fallback mechanisms for critical operations to ensure system remains functional
"""
import logging
from typing import Dict, Any, Optional, Callable, Union, List
from datetime import datetime, timezone
from enum import Enum
import json

logger = logging.getLogger(__name__)

class FallbackStrategy(Enum):
    CACHED_RESPONSE = "cached_response"          # Return cached/stale data
    DEFAULT_VALUES = "default_values"           # Return predefined defaults  
    SIMPLIFIED_SERVICE = "simplified_service"   # Use simpler fallback service
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Reduce functionality gracefully
    FAIL_FAST = "fail_fast"                     # Fail immediately with clear error
    QUEUE_FOR_RETRY = "queue_for_retry"         # Queue for later processing

class FallbackHandler:
    """
    Individual fallback handler for specific operations
    """
    
    def __init__(
        self,
        name: str,
        strategy: FallbackStrategy,
        fallback_function: Optional[Callable] = None,
        default_values: Optional[Dict[str, Any]] = None,
        cache_ttl: Optional[int] = None,
        max_fallback_age: Optional[int] = None,
        priority: int = 1  # Lower numbers = higher priority
    ):
        self.name = name
        self.strategy = strategy
        self.fallback_function = fallback_function
        self.default_values = default_values or {}
        self.cache_ttl = cache_ttl
        self.max_fallback_age = max_fallback_age
        self.priority = priority
        
        # Metrics
        self.invocation_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_used = None
        self.last_success = None

class FallbackService:
    """
    Service that manages fallback strategies for different operations
    """
    
    def __init__(self):
        self.handlers: Dict[str, List[FallbackHandler]] = {}
        self.fallback_cache: Dict[str, Dict[str, Any]] = {}
        
        # Initialize default fallback handlers
        self._initialize_default_handlers()
    
    def _initialize_default_handlers(self):
        """Initialize fallback handlers for core operations"""
        
        # Profile analysis fallbacks
        self.register_handler(
            operation="profile_analysis",
            handler=FallbackHandler(
                name="cached_profile_data",
                strategy=FallbackStrategy.CACHED_RESPONSE,
                max_fallback_age=3600,  # 1 hour
                priority=1
            )
        )
        
        self.register_handler(
            operation="profile_analysis", 
            handler=FallbackHandler(
                name="basic_profile_defaults",
                strategy=FallbackStrategy.DEFAULT_VALUES,
                default_values={
                    "followers": 0,
                    "following": 0,
                    "posts_count": 0,
                    "engagement_rate": 0.0,
                    "verification_status": False,
                    "analytics": {
                        "avg_likes": 0,
                        "avg_comments": 0,
                        "influence_score": 0.0
                    },
                    "meta": {
                        "data_source": "fallback_defaults",
                        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                        "fallback_reason": "primary_service_unavailable"
                    }
                },
                priority=2
            )
        )
        
        # AI analysis fallbacks
        self.register_handler(
            operation="ai_analysis",
            handler=FallbackHandler(
                name="rule_based_analysis",
                strategy=FallbackStrategy.SIMPLIFIED_SERVICE,
                fallback_function=self._fallback_ai_analysis,
                priority=1
            )
        )
        
        self.register_handler(
            operation="ai_analysis",
            handler=FallbackHandler(
                name="ai_analysis_defaults",
                strategy=FallbackStrategy.DEFAULT_VALUES,
                default_values={
                    "ai_content_category": "General",
                    "ai_category_confidence": 0.3,
                    "ai_sentiment": "neutral",
                    "ai_sentiment_score": 0.0,
                    "ai_sentiment_confidence": 0.3,
                    "ai_language_code": "en",
                    "ai_language_confidence": 0.5,
                    "analysis_metadata": {
                        "method": "fallback",
                        "reason": "ai_service_unavailable"
                    }
                },
                priority=2
            )
        )
        
        # Database operation fallbacks
        self.register_handler(
            operation="database_read",
            handler=FallbackHandler(
                name="cached_database_response",
                strategy=FallbackStrategy.CACHED_RESPONSE,
                max_fallback_age=600,  # 10 minutes
                priority=1
            )
        )
        
        # API request fallbacks
        self.register_handler(
            operation="api_request",
            handler=FallbackHandler(
                name="queue_for_later",
                strategy=FallbackStrategy.QUEUE_FOR_RETRY,
                fallback_function=self._queue_failed_request,
                priority=1
            )
        )
        
        # Cache operation fallbacks
        self.register_handler(
            operation="cache_operation",
            handler=FallbackHandler(
                name="skip_caching",
                strategy=FallbackStrategy.GRACEFUL_DEGRADATION,
                fallback_function=self._skip_cache_operation,
                priority=1
            )
        )
    
    def register_handler(self, operation: str, handler: FallbackHandler):
        """Register a fallback handler for an operation"""
        if operation not in self.handlers:
            self.handlers[operation] = []
        
        self.handlers[operation].append(handler)
        
        # Sort by priority (lower numbers first)
        self.handlers[operation].sort(key=lambda h: h.priority)
        
        logger.info(f"Registered fallback handler '{handler.name}' for operation '{operation}'")
    
    async def execute_with_fallback(
        self,
        operation: str,
        primary_function: Callable,
        context: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute operation with fallback handling
        
        Args:
            operation: Name of the operation
            primary_function: Primary function to execute
            context: Additional context for fallback decisions
            *args, **kwargs: Arguments for primary function
            
        Returns:
            Result from primary function or fallback
        """
        context = context or {}
        
        try:
            # Try primary function first
            result = await primary_function(*args, **kwargs)
            return {
                "success": True,
                "data": result,
                "source": "primary",
                "fallback_used": False
            }
            
        except Exception as e:
            logger.warning(f"Primary function failed for operation '{operation}': {e}")
            
            # Try fallback handlers in priority order
            if operation in self.handlers:
                for handler in self.handlers[operation]:
                    try:
                        fallback_result = await self._execute_fallback_handler(
                            handler, operation, e, context, *args, **kwargs
                        )
                        
                        if fallback_result:
                            handler.invocation_count += 1
                            handler.success_count += 1
                            handler.last_used = datetime.now(timezone.utc)
                            handler.last_success = datetime.now(timezone.utc)
                            
                            return {
                                "success": True,
                                "data": fallback_result,
                                "source": "fallback",
                                "fallback_used": True,
                                "fallback_handler": handler.name,
                                "fallback_strategy": handler.strategy.value,
                                "original_error": str(e)
                            }
                    
                    except Exception as fallback_error:
                        handler.invocation_count += 1
                        handler.failure_count += 1
                        logger.error(f"Fallback handler '{handler.name}' failed: {fallback_error}")
                        continue
            
            # No successful fallback found
            logger.error(f"All fallback handlers failed for operation '{operation}'")
            return {
                "success": False,
                "data": None,
                "source": "none",
                "fallback_used": False,
                "error": str(e),
                "message": "Primary function and all fallback handlers failed"
            }
    
    async def _execute_fallback_handler(
        self,
        handler: FallbackHandler,
        operation: str,
        original_error: Exception,
        context: Dict[str, Any],
        *args,
        **kwargs
    ) -> Any:
        """Execute a specific fallback handler"""
        
        if handler.strategy == FallbackStrategy.CACHED_RESPONSE:
            return await self._handle_cached_response(handler, operation, context)
            
        elif handler.strategy == FallbackStrategy.DEFAULT_VALUES:
            return handler.default_values
            
        elif handler.strategy == FallbackStrategy.SIMPLIFIED_SERVICE:
            if handler.fallback_function:
                return await handler.fallback_function(operation, context, *args, **kwargs)
            else:
                raise ValueError(f"No fallback function defined for handler {handler.name}")
                
        elif handler.strategy == FallbackStrategy.GRACEFUL_DEGRADATION:
            if handler.fallback_function:
                return await handler.fallback_function(operation, context, *args, **kwargs)
            else:
                return {"degraded": True, "message": "Service temporarily degraded"}
                
        elif handler.strategy == FallbackStrategy.FAIL_FAST:
            raise Exception(f"Fail-fast fallback for {operation}: {original_error}")
            
        elif handler.strategy == FallbackStrategy.QUEUE_FOR_RETRY:
            if handler.fallback_function:
                await handler.fallback_function(operation, context, *args, **kwargs)
                return {"queued": True, "message": "Request queued for retry"}
            else:
                raise ValueError(f"No queue function defined for handler {handler.name}")
        
        else:
            raise ValueError(f"Unknown fallback strategy: {handler.strategy}")
    
    async def _handle_cached_response(
        self, 
        handler: FallbackHandler,
        operation: str,
        context: Dict[str, Any]
    ) -> Optional[Any]:
        """Handle cached response fallback"""
        cache_key = f"{operation}:{context.get('cache_key', 'default')}"
        
        if cache_key in self.fallback_cache:
            cached_entry = self.fallback_cache[cache_key]
            cached_time = cached_entry["timestamp"]
            
            # Check if cached data is still valid
            age = (datetime.now(timezone.utc) - cached_time).total_seconds()
            max_age = handler.max_fallback_age or 3600
            
            if age <= max_age:
                logger.info(f"Using cached fallback data for {operation} (age: {age:.0f}s)")
                return cached_entry["data"]
            else:
                logger.warning(f"Cached fallback data too old for {operation} (age: {age:.0f}s)")
                # Remove expired cache entry
                del self.fallback_cache[cache_key]
        
        return None
    
    async def _fallback_ai_analysis(self, operation: str, context: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        """Simplified rule-based AI analysis fallback"""
        text = context.get("text", "")
        hashtags = context.get("hashtags", [])
        
        # Simple sentiment analysis
        positive_words = ["good", "great", "amazing", "love", "beautiful", "perfect", "awesome", "happy"]
        negative_words = ["bad", "terrible", "hate", "ugly", "awful", "worst", "sad", "disappointed"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
            sentiment_score = 0.6
        elif negative_count > positive_count:
            sentiment = "negative"
            sentiment_score = -0.6
        else:
            sentiment = "neutral"
            sentiment_score = 0.0
        
        # Simple category classification
        category_keywords = {
            "Fashion & Beauty": ["fashion", "style", "outfit", "beauty", "makeup"],
            "Food & Drink": ["food", "recipe", "cooking", "delicious", "restaurant"],
            "Travel": ["travel", "vacation", "trip", "destination"],
            "Technology": ["tech", "technology", "app", "digital"],
            "Fitness": ["fitness", "workout", "gym", "health"],
        }
        
        best_category = "General"
        max_matches = 0
        
        combined_text = f"{text} {' '.join(hashtags)}".lower()
        for category, keywords in category_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in combined_text)
            if matches > max_matches:
                max_matches = matches
                best_category = category
        
        return {
            "ai_content_category": best_category,
            "ai_category_confidence": min(0.8, 0.3 + max_matches * 0.1),
            "ai_sentiment": sentiment,
            "ai_sentiment_score": sentiment_score,
            "ai_sentiment_confidence": 0.7,
            "ai_language_code": "en",  # Default to English
            "ai_language_confidence": 0.5,
            "analysis_metadata": {
                "method": "rule_based_fallback",
                "reason": "ai_service_unavailable",
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    
    async def _queue_failed_request(self, operation: str, context: Dict[str, Any], *args, **kwargs):
        """Queue failed request for retry"""
        # This would typically integrate with a message queue system
        logger.info(f"Queuing failed request for operation: {operation}")
        
        # For now, just log the request details
        request_details = {
            "operation": operation,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retry_count": context.get("retry_count", 0)
        }
        
        logger.info(f"Request queued: {json.dumps(request_details, default=str)}")
    
    async def _skip_cache_operation(self, operation: str, context: Dict[str, Any], *args, **kwargs):
        """Gracefully skip cache operations when cache is unavailable"""
        logger.info(f"Skipping cache operation due to cache unavailability: {operation}")
        return {
            "cache_skipped": True,
            "reason": "cache_unavailable",
            "message": "Operation completed without caching"
        }
    
    def cache_response_for_fallback(
        self,
        operation: str,
        cache_key: str,
        data: Any,
        ttl: Optional[int] = None
    ):
        """Cache successful response for potential fallback use"""
        full_cache_key = f"{operation}:{cache_key}"
        
        self.fallback_cache[full_cache_key] = {
            "data": data,
            "timestamp": datetime.now(timezone.utc),
            "ttl": ttl or 3600
        }
        
        # Cleanup old entries (simple approach)
        if len(self.fallback_cache) > 1000:
            old_keys = list(self.fallback_cache.keys())[:100]
            for old_key in old_keys:
                del self.fallback_cache[old_key]
    
    def get_fallback_statistics(self) -> Dict[str, Any]:
        """Get statistics about fallback handlers"""
        stats = {
            "total_operations": len(self.handlers),
            "total_handlers": sum(len(handlers) for handlers in self.handlers.values()),
            "cache_entries": len(self.fallback_cache),
            "operations": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        for operation, handlers in self.handlers.items():
            operation_stats = {
                "handler_count": len(handlers),
                "handlers": []
            }
            
            for handler in handlers:
                handler_stats = {
                    "name": handler.name,
                    "strategy": handler.strategy.value,
                    "priority": handler.priority,
                    "invocation_count": handler.invocation_count,
                    "success_count": handler.success_count,
                    "failure_count": handler.failure_count,
                    "success_rate": (handler.success_count / max(1, handler.invocation_count)) * 100,
                    "last_used": handler.last_used.isoformat() if handler.last_used else None,
                    "last_success": handler.last_success.isoformat() if handler.last_success else None
                }
                
                operation_stats["handlers"].append(handler_stats)
            
            stats["operations"][operation] = operation_stats
        
        return stats
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of fallback system"""
        total_handlers = sum(len(handlers) for handlers in self.handlers.values())
        
        # Calculate success rates
        total_invocations = 0
        total_successes = 0
        
        for handlers in self.handlers.values():
            for handler in handlers:
                total_invocations += handler.invocation_count
                total_successes += handler.success_count
        
        overall_success_rate = (total_successes / max(1, total_invocations)) * 100
        
        return {
            "status": "healthy" if overall_success_rate > 70 else "degraded",
            "total_operations": len(self.handlers),
            "total_handlers": total_handlers,
            "overall_success_rate": round(overall_success_rate, 2),
            "cache_utilization": len(self.fallback_cache),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Global fallback service instance
fallback_service = FallbackService()