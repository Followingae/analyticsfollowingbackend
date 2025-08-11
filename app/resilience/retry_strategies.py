"""
Retry Strategies Service - Advanced retry mechanisms with exponential backoff
Provides different retry strategies for different types of operations and failures
"""
import logging
import asyncio
import random
import time
from typing import Dict, Any, Optional, Callable, Union, List, Type
from datetime import datetime, timezone
from enum import Enum
import inspect

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_INTERVAL = "fixed_interval"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    JITTERED_BACKOFF = "jittered_backoff"

class RetryStopCondition(Enum):
    MAX_ATTEMPTS = "max_attempts"
    MAX_TIME = "max_time"
    MAX_ATTEMPTS_AND_TIME = "both"

class RetryableException(Exception):
    """Base exception for retryable errors"""
    pass

class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted"""
    def __init__(self, attempts: int, total_time: float, last_exception: Exception):
        self.attempts = attempts
        self.total_time = total_time
        self.last_exception = last_exception
        super().__init__(f"Retry exhausted after {attempts} attempts in {total_time:.2f}s. Last error: {last_exception}")

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        max_attempts: int = 3,
        max_time: Optional[float] = None,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter_range: tuple = (0.1, 0.2),
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        non_retryable_exceptions: Optional[List[Type[Exception]]] = None,
        stop_condition: RetryStopCondition = RetryStopCondition.MAX_ATTEMPTS,
        on_retry_callback: Optional[Callable] = None
    ):
        self.strategy = strategy
        self.max_attempts = max_attempts
        self.max_time = max_time
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter_range = jitter_range
        self.retryable_exceptions = retryable_exceptions or [Exception]
        self.non_retryable_exceptions = non_retryable_exceptions or []
        self.stop_condition = stop_condition
        self.on_retry_callback = on_retry_callback

class RetryService:
    """
    Advanced retry service with multiple strategies and comprehensive error handling
    """
    
    def __init__(self):
        # Predefined retry configurations for common operations
        self.RETRY_CONFIGS = {
            "database_operations": RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_attempts=3,
                base_delay=0.5,
                max_delay=10.0,
                retryable_exceptions=[ConnectionError, TimeoutError],
                non_retryable_exceptions=[ValueError, TypeError]
            ),
            
            "api_requests": RetryConfig(
                strategy=RetryStrategy.JITTERED_BACKOFF,
                max_attempts=5,
                max_time=120.0,
                base_delay=1.0,
                max_delay=30.0,
                stop_condition=RetryStopCondition.MAX_ATTEMPTS_AND_TIME,
                retryable_exceptions=[ConnectionError, TimeoutError, RetryableException],
                non_retryable_exceptions=[ValueError, TypeError, KeyError]
            ),
            
            "ai_model_requests": RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_attempts=4,
                max_time=300.0,
                base_delay=2.0,
                max_delay=60.0,
                exponential_base=2.5,
                stop_condition=RetryStopCondition.MAX_ATTEMPTS_AND_TIME,
                retryable_exceptions=[RuntimeError, TimeoutError, MemoryError],
                non_retryable_exceptions=[ValueError, TypeError]
            ),
            
            "cache_operations": RetryConfig(
                strategy=RetryStrategy.LINEAR_BACKOFF,
                max_attempts=3,
                base_delay=0.1,
                max_delay=2.0,
                retryable_exceptions=[ConnectionError],
                non_retryable_exceptions=[ValueError]
            ),
            
            "file_operations": RetryConfig(
                strategy=RetryStrategy.FIXED_INTERVAL,
                max_attempts=3,
                base_delay=0.5,
                retryable_exceptions=[OSError, IOError],
                non_retryable_exceptions=[PermissionError]
            )
        }
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay based on retry strategy"""
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.exponential_base ** attempt)
            
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * (attempt + 1)
            
        elif config.strategy == RetryStrategy.FIXED_INTERVAL:
            delay = config.base_delay
            
        elif config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            fib_sequence = [1, 1]
            for i in range(2, attempt + 2):
                fib_sequence.append(fib_sequence[i-1] + fib_sequence[i-2])
            delay = config.base_delay * fib_sequence[attempt]
            
        elif config.strategy == RetryStrategy.JITTERED_BACKOFF:
            base_delay = config.base_delay * (config.exponential_base ** attempt)
            jitter_min, jitter_max = config.jitter_range
            jitter = random.uniform(jitter_min, jitter_max)
            delay = base_delay * (1 + jitter)
        
        else:
            delay = config.base_delay
        
        # Apply maximum delay limit
        return min(delay, config.max_delay)
    
    def _is_retryable_exception(self, exception: Exception, config: RetryConfig) -> bool:
        """Check if exception is retryable based on configuration"""
        # Check non-retryable exceptions first (takes precedence)
        if any(isinstance(exception, exc_type) for exc_type in config.non_retryable_exceptions):
            return False
        
        # Check if it matches any retryable exception
        return any(isinstance(exception, exc_type) for exc_type in config.retryable_exceptions)
    
    def _should_stop_retrying(self, attempt: int, start_time: float, config: RetryConfig) -> bool:
        """Check if we should stop retrying based on stop conditions"""
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        if config.stop_condition == RetryStopCondition.MAX_ATTEMPTS:
            return attempt >= config.max_attempts
        
        elif config.stop_condition == RetryStopCondition.MAX_TIME:
            return config.max_time and elapsed_time >= config.max_time
        
        elif config.stop_condition == RetryStopCondition.MAX_ATTEMPTS_AND_TIME:
            max_attempts_reached = attempt >= config.max_attempts
            max_time_reached = config.max_time and elapsed_time >= config.max_time
            return max_attempts_reached or max_time_reached
        
        return attempt >= config.max_attempts
    
    async def execute_with_retry(
        self, 
        func: Callable,
        config: Union[RetryConfig, str],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic
        
        Args:
            func: Function to execute (sync or async)
            config: RetryConfig object or string key for predefined config
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            RetryExhausted: When all retry attempts are exhausted
        """
        # Get config
        if isinstance(config, str):
            if config not in self.RETRY_CONFIGS:
                raise ValueError(f"Unknown retry config: {config}")
            retry_config = self.RETRY_CONFIGS[config]
        else:
            retry_config = config
        
        start_time = time.time()
        attempt = 0
        last_exception = None
        
        # Determine if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        while not self._should_stop_retrying(attempt, start_time, retry_config):
            try:
                if is_async:
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success! Log if this wasn't the first attempt
                if attempt > 0:
                    elapsed_time = time.time() - start_time
                    logger.info(f"Retry successful after {attempt} attempts in {elapsed_time:.2f}s for {func.__name__}")
                
                return result
                
            except Exception as e:
                last_exception = e
                attempt += 1
                
                # Check if this exception is retryable
                if not self._is_retryable_exception(e, retry_config):
                    logger.error(f"Non-retryable exception for {func.__name__}: {e}")
                    raise e
                
                # Check if we should stop retrying
                if self._should_stop_retrying(attempt, start_time, retry_config):
                    break
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt - 1, retry_config)
                
                logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s...")
                
                # Call retry callback if provided
                if retry_config.on_retry_callback:
                    try:
                        if inspect.iscoroutinefunction(retry_config.on_retry_callback):
                            await retry_config.on_retry_callback(attempt, e, delay)
                        else:
                            retry_config.on_retry_callback(attempt, e, delay)
                    except Exception as callback_error:
                        logger.error(f"Retry callback failed: {callback_error}")
                
                # Wait before next attempt
                await asyncio.sleep(delay)
        
        # All retries exhausted
        total_time = time.time() - start_time
        logger.error(f"Retry exhausted for {func.__name__} after {attempt} attempts in {total_time:.2f}s")
        
        raise RetryExhausted(attempt, total_time, last_exception)
    
    def create_custom_config(
        self,
        name: str,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        max_attempts: int = 3,
        **kwargs
    ) -> str:
        """
        Create and register a custom retry configuration
        
        Args:
            name: Name for the configuration
            strategy: Retry strategy to use
            max_attempts: Maximum number of attempts
            **kwargs: Additional configuration parameters
            
        Returns:
            Name of the created configuration
        """
        config = RetryConfig(
            strategy=strategy,
            max_attempts=max_attempts,
            **kwargs
        )
        
        self.RETRY_CONFIGS[name] = config
        logger.info(f"Created custom retry configuration: {name}")
        
        return name
    
    def get_retry_decorator(self, config_name: str):
        """
        Get a decorator for automatic retry behavior
        
        Args:
            config_name: Name of retry configuration to use
            
        Returns:
            Decorator function
        """
        def decorator(func):
            if inspect.iscoroutinefunction(func):
                async def async_wrapper(*args, **kwargs):
                    return await self.execute_with_retry(func, config_name, *args, **kwargs)
                return async_wrapper
            else:
                def sync_wrapper(*args, **kwargs):
                    # Convert sync function to async for consistent retry handling
                    async def async_func():
                        return func(*args, **kwargs)
                    
                    # Run in event loop
                    try:
                        loop = asyncio.get_event_loop()
                        return loop.run_until_complete(
                            self.execute_with_retry(async_func, config_name)
                        )
                    except RuntimeError:
                        # No event loop running, create new one
                        return asyncio.run(
                            self.execute_with_retry(async_func, config_name)
                        )
                
                return sync_wrapper
        
        return decorator
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get statistics about retry configurations"""
        stats = {
            "total_configurations": len(self.RETRY_CONFIGS),
            "configurations": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        for name, config in self.RETRY_CONFIGS.items():
            stats["configurations"][name] = {
                "strategy": config.strategy.value,
                "max_attempts": config.max_attempts,
                "max_time": config.max_time,
                "base_delay": config.base_delay,
                "max_delay": config.max_delay,
                "stop_condition": config.stop_condition.value,
                "retryable_exceptions": [exc.__name__ for exc in config.retryable_exceptions],
                "non_retryable_exceptions": [exc.__name__ for exc in config.non_retryable_exceptions]
            }
        
        return stats

# Global retry service instance
retry_service = RetryService()