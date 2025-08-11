"""
Circuit Breaker Pattern Implementation - Prevents cascading failures
Protects external services and AI models from being overwhelmed during failures
"""
import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable, Union, List
from datetime import datetime, timezone, timedelta
from enum import Enum
import statistics

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"         # Normal operation
    OPEN = "open"            # Failing - requests rejected immediately
    HALF_OPEN = "half_open"  # Testing if service has recovered

class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open"""
    def __init__(self, service_name: str, failure_rate: float, last_failure: str):
        self.service_name = service_name
        self.failure_rate = failure_rate
        self.last_failure = last_failure
        super().__init__(f"Circuit breaker OPEN for {service_name} (failure rate: {failure_rate:.1%}, last failure: {last_failure})")

class CircuitBreaker:
    """
    Production-ready circuit breaker with configurable thresholds and recovery
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,           # Number of failures before opening
        failure_rate_threshold: float = 0.5,  # Failure rate (0.0-1.0) before opening
        recovery_timeout: int = 60,           # Seconds before trying half-open
        request_volume_threshold: int = 10,   # Minimum requests before considering failure rate
        success_threshold: int = 3,           # Successful requests needed to close from half-open
        timeout: float = 30.0                # Request timeout in seconds
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.failure_rate_threshold = failure_rate_threshold
        self.recovery_timeout = recovery_timeout
        self.request_volume_threshold = request_volume_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_failure_exception = None
        
        # Request tracking (sliding window)
        self.request_history: List[Dict[str, Any]] = []
        self.history_window_seconds = 300  # 5 minutes
        self.max_history_size = 1000
        
        # Performance metrics
        self.total_requests = 0
        self.total_failures = 0
        self.total_success = 0
        self.total_timeouts = 0
        self.avg_response_time = 0.0
        self.response_times: List[float] = []
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerException: When circuit is open
            TimeoutError: When request times out
        """
        async with self._lock:
            # Clean old history
            await self._cleanup_history()
            
            # Check current state
            await self._update_state()
            
            if self.state == CircuitState.OPEN:
                failure_rate = self._calculate_failure_rate()
                last_failure = str(self.last_failure_exception) if self.last_failure_exception else "Unknown"
                raise CircuitBreakerException(self.name, failure_rate, last_failure)
        
        # Execute the function
        start_time = time.time()
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout)
            
            # Record success
            response_time = time.time() - start_time
            await self._record_success(response_time)
            
            return result
            
        except asyncio.TimeoutError as e:
            response_time = time.time() - start_time
            await self._record_timeout(response_time)
            logger.warning(f"Circuit breaker {self.name}: Request timed out after {self.timeout}s")
            raise TimeoutError(f"Request to {self.name} timed out after {self.timeout} seconds")
            
        except Exception as e:
            response_time = time.time() - start_time
            await self._record_failure(e, response_time)
            logger.error(f"Circuit breaker {self.name}: Request failed - {e}")
            raise e
    
    async def _update_state(self):
        """Update circuit breaker state based on current metrics"""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            # Check if we should try half-open
            if (self.last_failure_time and 
                current_time - self.last_failure_time >= self.recovery_timeout):
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name}: Transitioning to HALF_OPEN")
        
        elif self.state == CircuitState.HALF_OPEN:
            # Check if we should close (enough successes) or open (any failure)
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker {self.name}: Transitioning to CLOSED (recovered)")
        
        elif self.state == CircuitState.CLOSED:
            # Check if we should open based on failures
            recent_requests = len([r for r in self.request_history 
                                 if current_time - r['timestamp'] <= self.history_window_seconds])
            
            if recent_requests >= self.request_volume_threshold:
                failure_rate = self._calculate_failure_rate()
                
                if (self.failure_count >= self.failure_threshold or 
                    failure_rate >= self.failure_rate_threshold):
                    self.state = CircuitState.OPEN
                    self.last_failure_time = current_time
                    logger.warning(f"Circuit breaker {self.name}: Transitioning to OPEN (failure_count={self.failure_count}, failure_rate={failure_rate:.1%})")
    
    async def _record_success(self, response_time: float):
        """Record successful request"""
        async with self._lock:
            self.total_requests += 1
            self.total_success += 1
            self.success_count += 1
            
            # Reset failure count on success when closed
            if self.state == CircuitState.CLOSED:
                self.failure_count = 0
            
            # Record in history
            self._add_to_history("success", response_time)
            
            logger.debug(f"Circuit breaker {self.name}: Success recorded (response_time={response_time:.3f}s)")
    
    async def _record_failure(self, exception: Exception, response_time: float):
        """Record failed request"""
        async with self._lock:
            self.total_requests += 1
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_exception = exception
            
            # In half-open state, any failure should open the circuit
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_failure_time = time.time()
                logger.warning(f"Circuit breaker {self.name}: Half-open test failed, reopening circuit")
            
            # Record in history
            self._add_to_history("failure", response_time, str(exception))
    
    async def _record_timeout(self, response_time: float):
        """Record timed out request"""
        async with self._lock:
            self.total_requests += 1
            self.total_timeouts += 1
            self.failure_count += 1  # Timeouts count as failures
            
            # Record in history
            self._add_to_history("timeout", response_time)
    
    def _add_to_history(self, result_type: str, response_time: float, error: str = None):
        """Add request to history"""
        self.request_history.append({
            "timestamp": time.time(),
            "result": result_type,
            "response_time": response_time,
            "error": error
        })
        
        # Update response time statistics
        self.response_times.append(response_time)
        if len(self.response_times) > 100:  # Keep last 100 response times
            self.response_times = self.response_times[-100:]
        
        if self.response_times:
            self.avg_response_time = statistics.mean(self.response_times)
        
        # Limit history size
        if len(self.request_history) > self.max_history_size:
            self.request_history = self.request_history[-self.max_history_size:]
    
    async def _cleanup_history(self):
        """Remove old entries from history"""
        cutoff_time = time.time() - self.history_window_seconds
        self.request_history = [r for r in self.request_history if r["timestamp"] > cutoff_time]
    
    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate"""
        current_time = time.time()
        recent_requests = [r for r in self.request_history 
                          if current_time - r['timestamp'] <= self.history_window_seconds]
        
        if len(recent_requests) < self.request_volume_threshold:
            return 0.0
        
        failures = len([r for r in recent_requests if r['result'] in ['failure', 'timeout']])
        return failures / len(recent_requests)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state and metrics"""
        current_time = time.time()
        failure_rate = self._calculate_failure_rate()
        
        # Calculate uptime
        time_since_last_failure = None
        if self.last_failure_time:
            time_since_last_failure = current_time - self.last_failure_time
        
        return {
            "name": self.name,
            "state": self.state.value,
            "configuration": {
                "failure_threshold": self.failure_threshold,
                "failure_rate_threshold": self.failure_rate_threshold,
                "recovery_timeout": self.recovery_timeout,
                "request_volume_threshold": self.request_volume_threshold,
                "success_threshold": self.success_threshold,
                "timeout": self.timeout
            },
            "metrics": {
                "total_requests": self.total_requests,
                "total_success": self.total_success,
                "total_failures": self.total_failures,
                "total_timeouts": self.total_timeouts,
                "current_failure_rate": failure_rate,
                "avg_response_time": round(self.avg_response_time, 3),
                "failure_count": self.failure_count,
                "success_count": self.success_count
            },
            "status": {
                "is_healthy": self.state == CircuitState.CLOSED,
                "last_failure_time": self.last_failure_time,
                "time_since_last_failure": time_since_last_failure,
                "last_failure": str(self.last_failure_exception) if self.last_failure_exception else None,
                "time_until_retry": max(0, self.recovery_timeout - (current_time - (self.last_failure_time or 0))) if self.state == CircuitState.OPEN else 0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def reset(self):
        """Manually reset circuit breaker to closed state"""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.last_failure_exception = None
            
            logger.info(f"Circuit breaker {self.name}: Manually reset to CLOSED state")
    
    async def force_open(self):
        """Manually force circuit breaker to open state"""
        async with self._lock:
            self.state = CircuitState.OPEN
            self.last_failure_time = time.time()
            
            logger.warning(f"Circuit breaker {self.name}: Manually forced to OPEN state")

class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers with centralized monitoring
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Predefined circuit breakers for common services
        self._initialize_default_breakers()
    
    def _initialize_default_breakers(self):
        """Initialize circuit breakers for known services"""
        # Decodo API circuit breaker (external service)
        self.circuit_breakers["decodo_api"] = CircuitBreaker(
            name="decodo_api",
            failure_threshold=3,
            failure_rate_threshold=0.6,
            recovery_timeout=120,  # 2 minutes
            request_volume_threshold=5,
            timeout=30.0
        )
        
        # AI Analysis circuit breaker
        self.circuit_breakers["ai_analysis"] = CircuitBreaker(
            name="ai_analysis", 
            failure_threshold=5,
            failure_rate_threshold=0.7,
            recovery_timeout=300,  # 5 minutes
            request_volume_threshold=10,
            timeout=60.0  # AI analysis can take longer
        )
        
        # Database circuit breaker
        self.circuit_breakers["database"] = CircuitBreaker(
            name="database",
            failure_threshold=10,
            failure_rate_threshold=0.8,
            recovery_timeout=30,
            request_volume_threshold=20,
            timeout=10.0
        )
        
        # Redis cache circuit breaker
        self.circuit_breakers["redis_cache"] = CircuitBreaker(
            name="redis_cache",
            failure_threshold=5,
            failure_rate_threshold=0.5,
            recovery_timeout=60,
            request_volume_threshold=10,
            timeout=5.0
        )
    
    def get_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            # Create default circuit breaker
            self.circuit_breakers[service_name] = CircuitBreaker(
                name=service_name,
                failure_threshold=5,
                failure_rate_threshold=0.5,
                recovery_timeout=60,
                timeout=30.0
            )
            
            logger.info(f"Created new circuit breaker for service: {service_name}")
        
        return self.circuit_breakers[service_name]
    
    async def execute_with_breaker(self, service_name: str, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        breaker = self.get_breaker(service_name)
        return await breaker.call(func, *args, **kwargs)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all circuit breakers"""
        return {
            name: breaker.get_state() 
            for name, breaker in self.circuit_breakers.items()
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary of all services"""
        all_states = self.get_all_states()
        
        healthy_services = [name for name, state in all_states.items() 
                          if state["status"]["is_healthy"]]
        
        unhealthy_services = [name for name, state in all_states.items() 
                            if not state["status"]["is_healthy"]]
        
        return {
            "total_services": len(all_states),
            "healthy_services": len(healthy_services),
            "unhealthy_services": len(unhealthy_services),
            "healthy_service_names": healthy_services,
            "unhealthy_service_names": unhealthy_services,
            "overall_health_percentage": (len(healthy_services) / len(all_states) * 100) if all_states else 100,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def reset_all_breakers(self):
        """Reset all circuit breakers"""
        for breaker in self.circuit_breakers.values():
            await breaker.reset()
        
        logger.info("All circuit breakers have been reset")
    
    async def reset_breaker(self, service_name: str) -> bool:
        """Reset specific circuit breaker"""
        if service_name in self.circuit_breakers:
            await self.circuit_breakers[service_name].reset()
            return True
        return False

# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()