"""
Database Health Monitoring Middleware
Proactive database connection health monitoring and recovery
"""

import asyncio
import logging
import time
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class DatabaseHealthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor database health and automatically recover from connection issues
    """
    
    def __init__(self, app, check_interval: int = 30):
        super().__init__(app)
        self.check_interval = check_interval
        self.last_health_check = 0
        self.health_status = "unknown"
        self.consecutive_failures = 0
        self.max_failures = 3
        
    async def dispatch(self, request: Request, call_next):
        """
        Monitor database health on each request and proactively recover
        """
        # Perform health check if needed
        current_time = time.time()
        if current_time - self.last_health_check > self.check_interval:
            await self._check_database_health()
            self.last_health_check = current_time
        
        # Proceed with request
        try:
            response = await call_next(request)
            
            # Reset failure counter on successful database operations
            if hasattr(response, 'status_code') and response.status_code < 500:
                self.consecutive_failures = 0
                
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Detect database connection errors
            if any(db_error in error_str for db_error in [
                "database", "connection", "timeout", "circuit breaker"
            ]):
                logger.warning(f"DATABASE HEALTH: Connection error detected: {e}")
                self.consecutive_failures += 1
                
                # Trigger recovery if too many failures
                if self.consecutive_failures >= self.max_failures:
                    await self._trigger_database_recovery()
                    
            raise e
    
    async def _check_database_health(self):
        """
        Proactive database health check
        """
        try:
            from app.database.connection import SessionLocal, async_engine
            from sqlalchemy import text
            
            if not SessionLocal or not async_engine:
                self.health_status = "not_initialized"
                return
            
            # Quick health check
            async with SessionLocal() as session:
                result = await asyncio.wait_for(
                    session.execute(text("SELECT 1 as health_check")), 
                    timeout=5.0
                )
                health_value = result.scalar()
                
                if health_value == 1:
                    self.health_status = "healthy"
                    self.consecutive_failures = 0
                    logger.debug("DATABASE HEALTH: Connection healthy")
                else:
                    self.health_status = "degraded"
                    logger.warning("DATABASE HEALTH: Unexpected health check result")
                    
        except asyncio.TimeoutError:
            self.health_status = "timeout"
            self.consecutive_failures += 1
            logger.warning("DATABASE HEALTH: Health check timed out")
            
        except Exception as e:
            self.health_status = "unhealthy"
            self.consecutive_failures += 1
            logger.warning(f"DATABASE HEALTH: Health check failed: {e}")
    
    async def _trigger_database_recovery(self):
        """
        Trigger automatic database recovery procedures
        """
        logger.error(f"DATABASE RECOVERY: Triggering recovery after {self.consecutive_failures} consecutive failures")
        
        try:
            # Reset circuit breaker
            from app.resilience.database_resilience import database_resilience
            database_resilience.reset_circuit_breaker()
            logger.info("DATABASE RECOVERY: Circuit breaker reset")
            
            # Test connection recovery
            await self._check_database_health()
            
            if self.health_status == "healthy":
                logger.info("DATABASE RECOVERY: Connection restored successfully")
                self.consecutive_failures = 0
            else:
                logger.warning("DATABASE RECOVERY: Connection still unhealthy after recovery attempt")
                
        except Exception as e:
            logger.error(f"DATABASE RECOVERY: Recovery procedure failed: {e}")
    
    def get_health_status(self) -> dict:
        """
        Get current database health status
        """
        return {
            "status": self.health_status,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_health_check,
            "max_failures": self.max_failures
        }