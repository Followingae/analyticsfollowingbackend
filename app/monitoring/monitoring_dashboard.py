"""
Monitoring Dashboard Service - Centralized monitoring and health checking
Provides comprehensive system health status and monitoring endpoints
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import asyncio

# Import all monitoring components
from .performance_monitor import performance_monitor
from ..cache.redis_cache_manager import redis_cache_manager
from ..services.ai_background_task_manager import ai_background_task_manager
from ..services.ai.ai_manager_singleton import ai_manager
from ..resilience.circuit_breaker import circuit_breaker_manager
from ..resilience.fallback_handlers import fallback_service
from ..middleware.request_deduplication import request_deduplication_middleware

logger = logging.getLogger(__name__)

class MonitoringDashboard:
    """
    Centralized monitoring dashboard that aggregates health status from all system components
    """
    
    def __init__(self):
        self.service_health_checks = {
            "performance_monitor": self._check_performance_monitor_health,
            "redis_cache": self._check_redis_health,
            "ai_background_processing": self._check_ai_background_health,
            "ai_models": self._check_ai_models_health,
            "circuit_breakers": self._check_circuit_breakers_health,
            "fallback_system": self._check_fallback_system_health,
            "request_deduplication": self._check_deduplication_health
        }
        
        # Alert configuration
        self.alert_subscribers: List[callable] = []
        self.last_health_check = None
        self.health_check_interval = 60  # seconds
        self.auto_health_check_task: Optional[asyncio.Task] = None
        
        # System status cache
        self._cached_system_status = None
        self._cache_timestamp = None
        self._cache_ttl = 30  # seconds
    
    async def start_monitoring(self):
        """Start all monitoring services"""
        try:
            logger.info("🚀 Starting comprehensive monitoring system...")
            
            # Start performance monitoring
            await performance_monitor.start_system_monitoring()
            
            # Initialize cache manager
            await redis_cache_manager.initialize()
            
            # Add performance monitor alert callback
            performance_monitor.add_alert_callback(self._handle_performance_alert)
            
            # Start auto health check
            self.auto_health_check_task = asyncio.create_task(self._auto_health_check_loop())
            
            logger.info("[SUCCESS] Monitoring system started successfully")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to start monitoring system: {e}")
            raise
    
    async def stop_monitoring(self):
        """Stop all monitoring services"""
        try:
            logger.info("Stopping monitoring system...")
            
            # Stop performance monitoring
            await performance_monitor.stop_system_monitoring()
            
            # Stop auto health check
            if self.auto_health_check_task:
                self.auto_health_check_task.cancel()
                try:
                    await self.auto_health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Close cache connections
            await redis_cache_manager.close()
            
            logger.info("Monitoring system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring system: {e}")
    
    async def _auto_health_check_loop(self):
        """Background loop for periodic health checks"""
        try:
            while True:
                await self.get_comprehensive_health_status()
                await asyncio.sleep(self.health_check_interval)
        except asyncio.CancelledError:
            logger.info("Auto health check loop cancelled")
        except Exception as e:
            logger.error(f"Auto health check loop failed: {e}")
    
    async def get_comprehensive_health_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive health status of all system components
        
        Args:
            force_refresh: Skip cache and force fresh health check
            
        Returns:
            Comprehensive system health status
        """
        current_time = datetime.now(timezone.utc)
        
        # Check cache first (unless forced refresh)
        if not force_refresh and self._cached_system_status and self._cache_timestamp:
            cache_age = (current_time - self._cache_timestamp).total_seconds()
            if cache_age < self._cache_ttl:
                return self._cached_system_status
        
        logger.info("Performing comprehensive health check...")
        
        # Run all health checks in parallel
        health_results = {}
        health_check_tasks = []
        
        for service_name, health_check_func in self.service_health_checks.items():
            task = asyncio.create_task(self._safe_health_check(service_name, health_check_func))
            health_check_tasks.append((service_name, task))
        
        # Collect results
        for service_name, task in health_check_tasks:
            try:
                health_results[service_name] = await task
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
                health_results[service_name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": current_time.isoformat()
                }
        
        # Calculate overall system health
        overall_status = self._calculate_overall_health(health_results)
        
        # Create comprehensive status
        system_status = {
            "overall_status": overall_status["status"],
            "overall_health_score": overall_status["health_score"],
            "critical_issues": overall_status["critical_issues"],
            "warnings": overall_status["warnings"],
            "services": health_results,
            "summary": {
                "healthy_services": sum(1 for s in health_results.values() if s.get("status") == "healthy"),
                "degraded_services": sum(1 for s in health_results.values() if s.get("status") == "degraded"),
                "unhealthy_services": sum(1 for s in health_results.values() if s.get("status") == "unhealthy"),
                "total_services": len(health_results)
            },
            "last_check": current_time.isoformat(),
            "check_duration_ms": 0  # Will be updated below
        }
        
        # Cache the result
        self._cached_system_status = system_status
        self._cache_timestamp = current_time
        self.last_health_check = current_time
        
        # Calculate check duration
        check_end_time = datetime.now(timezone.utc)
        check_duration = (check_end_time - current_time).total_seconds() * 1000
        system_status["check_duration_ms"] = round(check_duration, 2)
        
        logger.info(f"Health check completed in {check_duration:.2f}ms - Status: {overall_status['status']}")
        
        return system_status
    
    async def _safe_health_check(self, service_name: str, health_check_func: callable) -> Dict[str, Any]:
        """Safely execute health check with timeout"""
        try:
            # Add timeout to prevent hanging health checks
            result = await asyncio.wait_for(health_check_func(), timeout=10.0)
            return result
        except asyncio.TimeoutError:
            return {
                "status": "unhealthy",
                "error": "Health check timed out",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _calculate_overall_health(self, health_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall system health from individual service health"""
        critical_issues = []
        warnings = []
        health_scores = []
        
        # Service priority weights
        service_weights = {
            "performance_monitor": 0.2,
            "redis_cache": 0.15,
            "ai_background_processing": 0.2,
            "ai_models": 0.15,
            "circuit_breakers": 0.1,
            "fallback_system": 0.1,
            "request_deduplication": 0.1
        }
        
        total_weight = 0
        weighted_score = 0
        
        for service_name, health_data in health_results.items():
            status = health_data.get("status", "unknown")
            weight = service_weights.get(service_name, 0.1)
            total_weight += weight
            
            # Convert status to numeric score
            if status == "healthy":
                score = 100
            elif status == "degraded":
                score = 60
                warnings.append(f"{service_name} is degraded")
            elif status == "unhealthy":
                score = 20
                critical_issues.append(f"{service_name} is unhealthy")
            else:
                score = 0
                critical_issues.append(f"{service_name} status unknown")
            
            weighted_score += score * weight
            health_scores.append(score)
        
        # Calculate overall health score
        overall_health_score = weighted_score / total_weight if total_weight > 0 else 0
        
        # Determine overall status
        if overall_health_score >= 90:
            overall_status = "healthy"
        elif overall_health_score >= 70:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "health_score": round(overall_health_score, 1),
            "critical_issues": critical_issues,
            "warnings": warnings
        }
    
    # Individual health check methods
    async def _check_performance_monitor_health(self) -> Dict[str, Any]:
        """Check performance monitor health"""
        try:
            system_status = performance_monitor.get_system_status()
            active_alerts = performance_monitor.get_active_alerts()
            
            # Determine health based on system metrics
            if system_status["status"] == "healthy" and len(active_alerts) == 0:
                status = "healthy"
            elif system_status["status"] == "degraded" or len(active_alerts) <= 2:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "system_metrics": system_status,
                "active_alerts": len(active_alerts),
                "monitoring_active": performance_monitor.system_monitor_active,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis cache health"""
        try:
            health_check = await redis_cache_manager.health_check()
            cache_stats = await redis_cache_manager.get_cache_stats()
            
            if health_check["status"] == "healthy":
                status = "healthy"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "health_check": health_check,
                "cache_stats": cache_stats,
                "initialized": redis_cache_manager.initialized,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _check_ai_background_health(self) -> Dict[str, Any]:
        """Check AI background processing health"""
        try:
            system_stats = ai_background_task_manager.get_system_stats()
            
            if system_stats.get("system_healthy", False):
                status = "healthy"
            elif system_stats.get("active_workers", 0) > 0:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "system_stats": system_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _check_ai_models_health(self) -> Dict[str, Any]:
        """Check AI models health"""
        try:
            model_stats = ai_manager.get_system_stats()
            health_status = ai_manager.health_check()
            
            models_loaded = len(model_stats.get("models_loaded", []))
            total_models = model_stats.get("total_models_available", 0)
            
            if models_loaded >= 2:  # At least sentiment and language models
                status = "healthy"
            elif models_loaded >= 1:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "models_loaded": models_loaded,
                "total_models_available": total_models,
                "model_stats": model_stats,
                "health_check": health_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _check_circuit_breakers_health(self) -> Dict[str, Any]:
        """Check circuit breakers health"""
        try:
            all_states = circuit_breaker_manager.get_all_states()
            health_summary = circuit_breaker_manager.get_health_summary()
            
            health_percentage = health_summary.get("overall_health_percentage", 0)
            
            if health_percentage >= 90:
                status = "healthy"
            elif health_percentage >= 70:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "health_percentage": health_percentage,
                "healthy_services": health_summary.get("healthy_services", 0),
                "unhealthy_services": health_summary.get("unhealthy_services", 0),
                "circuit_states": all_states,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _check_fallback_system_health(self) -> Dict[str, Any]:
        """Check fallback system health"""
        try:
            health_status = fallback_service.get_health_status()
            fallback_stats = fallback_service.get_fallback_statistics()
            
            system_status = health_status.get("status", "unknown")
            success_rate = health_status.get("overall_success_rate", 0)
            
            if system_status == "healthy" and success_rate > 80:
                status = "healthy"
            elif success_rate > 60:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "health_status": health_status,
                "statistics": fallback_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _check_deduplication_health(self) -> Dict[str, Any]:
        """Check request deduplication health"""
        try:
            dedup_stats = request_deduplication_middleware.get_deduplication_stats()
            
            active_requests = dedup_stats.get("active_requests", 0)
            duplicates_prevented = dedup_stats.get("total_duplicates_prevented", 0)
            
            # Simple health check based on reasonable activity
            if active_requests < 100:  # Not overwhelmed
                status = "healthy"
            elif active_requests < 200:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "deduplication_stats": dedup_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _handle_performance_alert(self, alert: Dict[str, Any]):
        """Handle performance alerts from performance monitor"""
        logger.warning(f"Performance alert: {alert}")
        
        # Notify all subscribers
        for subscriber in self.alert_subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(alert)
                else:
                    subscriber(alert)
            except Exception as e:
                logger.error(f"Alert subscriber failed: {e}")
    
    def add_alert_subscriber(self, callback: callable):
        """Add alert subscriber callback"""
        self.alert_subscribers.append(callback)
        logger.info(f"Added alert subscriber: {callback.__name__}")
    
    async def get_performance_dashboard(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get performance dashboard data"""
        try:
            performance_summary = performance_monitor.get_performance_summary(time_window_minutes)
            operation_statistics = performance_monitor.get_operation_statistics()
            active_alerts = performance_monitor.get_active_alerts()
            
            return {
                "performance_summary": performance_summary,
                "operation_statistics": operation_statistics,
                "active_alerts": active_alerts,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance dashboard: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_system_metrics_history(self, hours: int = 24) -> Dict[str, Any]:
        """Get system metrics history"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            # Get system metrics from performance monitor
            system_metrics = []
            for metric in performance_monitor.system_metrics_history:
                if metric.timestamp >= cutoff_time:
                    system_metrics.append({
                        "timestamp": metric.timestamp.isoformat(),
                        "cpu_percent": metric.cpu_percent,
                        "memory_percent": metric.memory_percent,
                        "disk_usage_percent": metric.disk_usage_percent,
                        "active_connections": metric.active_connections
                    })
            
            return {
                "time_window_hours": hours,
                "metrics_count": len(system_metrics),
                "metrics": system_metrics,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system metrics history: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# Global monitoring dashboard instance
monitoring_dashboard = MonitoringDashboard()