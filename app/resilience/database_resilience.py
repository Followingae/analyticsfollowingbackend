"""
Database Resilience Manager - Bulletproof Database Connectivity
Handles network failures, connection pooling, and automatic recovery
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import socket

logger = logging.getLogger(__name__)

class DatabaseResilience:
    """
    Bulletproof database connectivity with automatic recovery
    """
    
    def __init__(self):
        self.connection_failures = 0
        self.last_failure_time = None
        self.circuit_breaker_open = False
        self.circuit_breaker_threshold = 15  # Higher threshold for production
        self.circuit_breaker_timeout = 30  # Shorter timeout for faster recovery
        self.retry_delays = [0.5, 1, 2, 4, 8]  # Faster initial retries
        self.max_retries = 3  # Fewer retries per operation
        
        # Connection pool health
        self.pool_health_check_interval = 30  # seconds
        self.last_pool_check = None
        
        # Operation-specific failure tracking (more granular than global circuit breaking)
        self.operation_failures = {}  # Track failures per operation type
        self.operation_threshold = 10  # Per-operation failure threshold
        
    def is_network_available(self) -> bool:
        """Check if basic network connectivity is available"""
        try:
            # Try to resolve a reliable DNS name
            socket.gethostbyname('google.com')
            return True
        except socket.gaierror:
            try:
                # Fallback: try another DNS server
                socket.gethostbyname('cloudflare.com')
                return True
            except socket.gaierror:
                return False
    
    def should_circuit_break(self) -> bool:
        """Check if circuit breaker should prevent attempts"""
        if not self.circuit_breaker_open:
            return False
            
        if self.last_failure_time is None:
            return False
            
        # Check if timeout has passed
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure > self.circuit_breaker_timeout:
            logger.info("CIRCUIT BREAKER: Recovery timeout passed, attempting gradual reconnection")
            self.circuit_breaker_open = False
            # Reset failure count partially for gradual recovery
            self.connection_failures = max(0, self.connection_failures - 5)
            return False
            
        return True
    
    def record_failure(self):
        """Record a connection failure"""
        self.connection_failures += 1
        self.last_failure_time = time.time()
        
        if self.connection_failures >= self.circuit_breaker_threshold:
            if not self.circuit_breaker_open:
                logger.warning(f"CIRCUIT BREAKER: Opening circuit after {self.connection_failures} consecutive failures - allowing graceful degradation")
                self.circuit_breaker_open = True
    
    def record_success(self):
        """Record a successful connection"""
        if self.connection_failures > 0 or self.circuit_breaker_open:
            logger.info("CIRCUIT BREAKER: Connection restored, resetting failures")
        
        self.connection_failures = 0
        self.last_failure_time = None
        self.circuit_breaker_open = False
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker - for admin recovery operations"""
        logger.info("CIRCUIT BREAKER: Manual reset triggered")
        self.connection_failures = 0
        self.last_failure_time = None
        self.circuit_breaker_open = False
    
    @property
    def failure_count(self) -> int:
        """Get current failure count"""
        return self.connection_failures
    
    def should_skip_operation(self, operation_name: str) -> bool:
        """Check if specific operation should be skipped due to repeated failures"""
        if operation_name not in self.operation_failures:
            return False
        
        failure_info = self.operation_failures[operation_name]
        failure_count = failure_info.get('count', 0)
        last_failure = failure_info.get('last_failure', 0)
        
        # Only skip if operation has failed repeatedly AND recently
        if failure_count >= self.operation_threshold:
            time_since_failure = time.time() - last_failure
            if time_since_failure < self.circuit_breaker_timeout:
                logger.warning(f"OPERATION THROTTLE: Skipping {operation_name} due to {failure_count} recent failures")
                return True
            else:
                # Reset operation failures after timeout
                self.operation_failures[operation_name]['count'] = max(0, failure_count - 3)
                
        return False
    
    def record_operation_failure(self, operation_name: str):
        """Record a failure for specific operation type"""
        if operation_name not in self.operation_failures:
            self.operation_failures[operation_name] = {'count': 0, 'last_failure': 0}
        
        self.operation_failures[operation_name]['count'] += 1
        self.operation_failures[operation_name]['last_failure'] = time.time()
    
    def record_operation_success(self, operation_name: str):
        """Record success for specific operation type"""
        if operation_name in self.operation_failures:
            # Reduce failure count on success
            current_count = self.operation_failures[operation_name]['count']
            self.operation_failures[operation_name]['count'] = max(0, current_count - 2)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current resilience status"""
        return {
            "circuit_breaker_open": self.circuit_breaker_open,
            "failure_count": self.connection_failures,
            "last_failure_time": self.last_failure_time,
            "network_available": self.is_network_available(),
            "status": "open" if self.circuit_breaker_open else "closed",
            "operation_failures": self.operation_failures
        }
    
    async def execute_with_resilience(
        self,
        db: AsyncSession,
        operation: Callable,
        operation_name: str = "database_operation",
        *args,
        **kwargs
    ):
        """
        Execute database operation with comprehensive resilience
        """
        # Check operation-specific throttling first
        if self.should_skip_operation(operation_name):
            logger.warning(f"OPERATION THROTTLE: Temporarily skipping {operation_name} due to repeated failures")
            raise ConnectionError(f"Operation {operation_name} temporarily throttled due to repeated failures")
        
        # Check global circuit breaker for severe system issues
        if self.should_circuit_break():
            logger.warning(f"CIRCUIT BREAKER: Blocking {operation_name} - circuit open for severe system issues")
            raise ConnectionError(f"Circuit breaker open for {operation_name}")
        
        # Check network connectivity first
        if not self.is_network_available():
            logger.error(f"NETWORK: No network connectivity for {operation_name}")
            self.record_failure()
            self.record_operation_failure(operation_name)
            raise ConnectionError(f"No network connectivity for {operation_name}")
        
        # Attempt operation with retries
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"RESILIENCE: Attempting {operation_name} (attempt {attempt + 1}/{self.max_retries})")
                
                # Execute the operation
                result = await operation(db, *args, **kwargs)
                
                # Success!
                self.record_success()
                self.record_operation_success(operation_name)
                return result
                
            except (asyncpg.PostgresConnectionError, 
                   ConnectionError, 
                   socket.gaierror,
                   OSError) as e:
                last_exception = e
                logger.warning(f"RESILIENCE: {operation_name} attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.info(f"RESILIENCE: Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    
                    # Check if network came back
                    if not self.is_network_available():
                        logger.warning(f"RESILIENCE: Network still unavailable, continuing retries...")
                        continue
                else:
                    # Final attempt failed
                    logger.error(f"RESILIENCE: All {self.max_retries} attempts failed for {operation_name}")
                    self.record_failure()
                    self.record_operation_failure(operation_name)
            
            except Exception as e:
                # Non-network error, don't retry
                logger.error(f"RESILIENCE: Non-retryable error in {operation_name}: {e}")
                raise e
        
        # If we get here, all retries failed
        raise last_exception
    
    async def health_check_connection(self, db: AsyncSession) -> bool:
        """Perform a lightweight health check on database connection"""
        try:
            await db.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"DB HEALTH: Connection health check failed: {e}")
            return False
    
    @asynccontextmanager
    async def resilient_session(self, db: AsyncSession):
        """Context manager for resilient database sessions"""
        try:
            # Health check before use
            if not await self.health_check_connection(db):
                logger.warning("DB HEALTH: Connection failed health check")
                
            yield db
            
        except Exception as e:
            logger.error(f"RESILIENT SESSION: Error in database session: {e}")
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(f"RESILIENT SESSION: Rollback failed: {rollback_error}")
            raise
        finally:
            try:
                await db.close()
            except Exception as close_error:
                logger.warning(f"RESILIENT SESSION: Session close warning: {close_error}")

# Global instance
database_resilience = DatabaseResilience()