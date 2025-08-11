"""
Performance Monitoring System - Real-time monitoring of application performance
Tracks response times, throughput, error rates, and system resource usage
"""
import logging
import time
import asyncio
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
import statistics
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Individual performance metric data point"""
    timestamp: datetime
    operation: str
    duration: float
    success: bool
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    endpoint: Optional[str] = None
    user_id: Optional[str] = None
    request_size: Optional[int] = None
    response_size: Optional[int] = None

@dataclass
class SystemMetrics:
    """System resource metrics snapshot"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_connections: int
    process_count: int

class PerformanceMonitor:
    """
    Production-ready performance monitoring with real-time metrics collection
    """
    
    def __init__(self, max_metrics_history: int = 10000):
        self.max_metrics_history = max_metrics_history
        
        # Performance metrics storage
        self.metrics_history: deque = deque(maxlen=max_metrics_history)
        self.system_metrics_history: deque = deque(maxlen=1000)  # Keep 1000 system snapshots
        
        # Real-time aggregations
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_duration": 0.0,
            "success_count": 0,
            "error_count": 0,
            "avg_duration": 0.0,
            "min_duration": float('inf'),
            "max_duration": 0.0,
            "last_updated": None,
            "recent_durations": deque(maxlen=100)  # For percentile calculations
        })
        
        self.endpoint_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_duration": 0.0,
            "success_count": 0,
            "error_count": 0,
            "status_codes": defaultdict(int),
            "avg_duration": 0.0,
            "last_updated": None
        })
        
        # System monitoring
        self.system_monitor_active = False
        self.system_monitor_task: Optional[asyncio.Task] = None
        self.system_monitor_interval = 30  # seconds
        
        # Alert thresholds
        self.alert_thresholds = {
            "response_time_ms": 5000,      # 5 seconds
            "error_rate_percent": 5.0,      # 5%
            "cpu_percent": 80.0,            # 80%
            "memory_percent": 85.0,         # 85%
            "disk_usage_percent": 90.0      # 90%
        }
        
        # Alert state tracking
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        self.alert_callbacks: List[callable] = []
    
    async def start_system_monitoring(self):
        """Start background system metrics collection"""
        if self.system_monitor_active:
            logger.warning("System monitoring is already active")
            return
        
        self.system_monitor_active = True
        self.system_monitor_task = asyncio.create_task(self._system_monitor_loop())
        logger.info(f"Started system monitoring with {self.system_monitor_interval}s interval")
    
    async def stop_system_monitoring(self):
        """Stop background system metrics collection"""
        self.system_monitor_active = False
        
        if self.system_monitor_task:
            self.system_monitor_task.cancel()
            try:
                await self.system_monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped system monitoring")
    
    async def _system_monitor_loop(self):
        """Background loop for collecting system metrics"""
        try:
            while self.system_monitor_active:
                await self._collect_system_metrics()
                await asyncio.sleep(self.system_monitor_interval)
        except asyncio.CancelledError:
            logger.info("System monitoring loop cancelled")
        except Exception as e:
            logger.error(f"System monitoring loop failed: {e}")
    
    async def _collect_system_metrics(self):
        """Collect current system resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / 1024 / 1024
            memory_available_mb = memory.available / 1024 / 1024
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Network stats
            network = psutil.net_io_counters()
            
            # Process stats
            process_count = len(psutil.pids())
            active_connections = len(psutil.net_connections())
            
            # Create metrics object
            system_metrics = SystemMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                active_connections=active_connections,
                process_count=process_count
            )
            
            # Store metrics
            self.system_metrics_history.append(system_metrics)
            
            # Check for alerts
            await self._check_system_alerts(system_metrics)
            
            logger.debug(f"Collected system metrics: CPU={cpu_percent:.1f}%, Memory={memory_percent:.1f}%")
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    @asynccontextmanager
    async def monitor_operation(self, operation: str, **kwargs):
        """Context manager for monitoring operation performance"""
        start_time = time.time()
        success = True
        error_type = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            duration = time.time() - start_time
            
            # Create metric
            metric = PerformanceMetric(
                timestamp=datetime.now(timezone.utc),
                operation=operation,
                duration=duration,
                success=success,
                error_type=error_type,
                **kwargs
            )
            
            # Record metric
            await self.record_metric(metric)
    
    async def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric"""
        try:
            # Add to history
            self.metrics_history.append(metric)
            
            # Update operation statistics
            await self._update_operation_stats(metric)
            
            # Update endpoint statistics if endpoint is provided
            if metric.endpoint:
                await self._update_endpoint_stats(metric)
            
            # Check for performance alerts
            await self._check_performance_alerts(metric)
            
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
    
    async def _update_operation_stats(self, metric: PerformanceMetric):
        """Update aggregated operation statistics"""
        stats = self.operation_stats[metric.operation]
        
        stats["count"] += 1
        stats["total_duration"] += metric.duration
        
        if metric.success:
            stats["success_count"] += 1
        else:
            stats["error_count"] += 1
        
        # Update duration statistics
        stats["min_duration"] = min(stats["min_duration"], metric.duration)
        stats["max_duration"] = max(stats["max_duration"], metric.duration)
        stats["avg_duration"] = stats["total_duration"] / stats["count"]
        stats["recent_durations"].append(metric.duration)
        stats["last_updated"] = metric.timestamp
    
    async def _update_endpoint_stats(self, metric: PerformanceMetric):
        """Update aggregated endpoint statistics"""
        stats = self.endpoint_stats[metric.endpoint]
        
        stats["count"] += 1
        stats["total_duration"] += metric.duration
        
        if metric.success:
            stats["success_count"] += 1
            if metric.status_code:
                stats["status_codes"][metric.status_code] += 1
        else:
            stats["error_count"] += 1
            if metric.status_code:
                stats["status_codes"][metric.status_code] += 1
        
        stats["avg_duration"] = stats["total_duration"] / stats["count"]
        stats["last_updated"] = metric.timestamp
    
    async def _check_performance_alerts(self, metric: PerformanceMetric):
        """Check for performance-based alerts"""
        alerts_triggered = []
        
        # Check response time alert
        if metric.duration > (self.alert_thresholds["response_time_ms"] / 1000):
            alert_key = f"slow_response_{metric.operation}"
            if alert_key not in self.active_alerts:
                alert = {
                    "type": "slow_response",
                    "operation": metric.operation,
                    "threshold_ms": self.alert_thresholds["response_time_ms"],
                    "actual_ms": metric.duration * 1000,
                    "timestamp": metric.timestamp,
                    "severity": "warning"
                }
                self.active_alerts[alert_key] = alert
                alerts_triggered.append(alert)
        
        # Check error rate alert (for operations with enough data)
        operation_stats = self.operation_stats[metric.operation]
        if operation_stats["count"] >= 10:  # Need at least 10 requests
            error_rate = (operation_stats["error_count"] / operation_stats["count"]) * 100
            
            if error_rate > self.alert_thresholds["error_rate_percent"]:
                alert_key = f"high_error_rate_{metric.operation}"
                if alert_key not in self.active_alerts:
                    alert = {
                        "type": "high_error_rate",
                        "operation": metric.operation,
                        "threshold_percent": self.alert_thresholds["error_rate_percent"],
                        "actual_percent": error_rate,
                        "timestamp": metric.timestamp,
                        "severity": "critical"
                    }
                    self.active_alerts[alert_key] = alert
                    alerts_triggered.append(alert)
        
        # Trigger alert callbacks
        for alert in alerts_triggered:
            await self._trigger_alert_callbacks(alert)
    
    async def _check_system_alerts(self, system_metrics: SystemMetrics):
        """Check for system resource alerts"""
        alerts_triggered = []
        
        # CPU usage alert
        if system_metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
            alert_key = "high_cpu_usage"
            if alert_key not in self.active_alerts:
                alert = {
                    "type": "high_cpu_usage",
                    "threshold_percent": self.alert_thresholds["cpu_percent"],
                    "actual_percent": system_metrics.cpu_percent,
                    "timestamp": system_metrics.timestamp,
                    "severity": "critical"
                }
                self.active_alerts[alert_key] = alert
                alerts_triggered.append(alert)
        
        # Memory usage alert
        if system_metrics.memory_percent > self.alert_thresholds["memory_percent"]:
            alert_key = "high_memory_usage"
            if alert_key not in self.active_alerts:
                alert = {
                    "type": "high_memory_usage",
                    "threshold_percent": self.alert_thresholds["memory_percent"],
                    "actual_percent": system_metrics.memory_percent,
                    "timestamp": system_metrics.timestamp,
                    "severity": "critical"
                }
                self.active_alerts[alert_key] = alert
                alerts_triggered.append(alert)
        
        # Disk usage alert
        if system_metrics.disk_usage_percent > self.alert_thresholds["disk_usage_percent"]:
            alert_key = "high_disk_usage"
            if alert_key not in self.active_alerts:
                alert = {
                    "type": "high_disk_usage",
                    "threshold_percent": self.alert_thresholds["disk_usage_percent"],
                    "actual_percent": system_metrics.disk_usage_percent,
                    "timestamp": system_metrics.timestamp,
                    "severity": "critical"
                }
                self.active_alerts[alert_key] = alert
                alerts_triggered.append(alert)
        
        # Clear resolved alerts
        await self._clear_resolved_alerts(system_metrics)
        
        # Trigger alert callbacks
        for alert in alerts_triggered:
            await self._trigger_alert_callbacks(alert)
    
    async def _clear_resolved_alerts(self, system_metrics: SystemMetrics):
        """Clear alerts that have been resolved"""
        alerts_to_clear = []
        
        # Check if system alerts are resolved
        if system_metrics.cpu_percent <= self.alert_thresholds["cpu_percent"]:
            if "high_cpu_usage" in self.active_alerts:
                alerts_to_clear.append("high_cpu_usage")
        
        if system_metrics.memory_percent <= self.alert_thresholds["memory_percent"]:
            if "high_memory_usage" in self.active_alerts:
                alerts_to_clear.append("high_memory_usage")
        
        if system_metrics.disk_usage_percent <= self.alert_thresholds["disk_usage_percent"]:
            if "high_disk_usage" in self.active_alerts:
                alerts_to_clear.append("high_disk_usage")
        
        # Clear resolved alerts
        for alert_key in alerts_to_clear:
            resolved_alert = self.active_alerts.pop(alert_key)
            logger.info(f"Alert resolved: {alert_key}")
            
            # Notify alert callbacks about resolution
            resolution_alert = {
                **resolved_alert,
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc)
            }
            await self._trigger_alert_callbacks(resolution_alert)
    
    async def _trigger_alert_callbacks(self, alert: Dict[str, Any]):
        """Trigger registered alert callbacks"""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def add_alert_callback(self, callback: callable):
        """Add callback function for alert notifications"""
        self.alert_callbacks.append(callback)
        logger.info(f"Added alert callback: {callback.__name__}")
    
    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get performance summary for specified time window"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)
        
        # Filter metrics within time window
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {
                "time_window_minutes": time_window_minutes,
                "total_requests": 0,
                "message": "No metrics available for the specified time window"
            }
        
        # Calculate summary statistics
        total_requests = len(recent_metrics)
        successful_requests = sum(1 for m in recent_metrics if m.success)
        failed_requests = total_requests - successful_requests
        
        durations = [m.duration for m in recent_metrics]
        avg_response_time = statistics.mean(durations)
        
        # Calculate percentiles
        sorted_durations = sorted(durations)
        p50 = statistics.median(sorted_durations)
        p95_index = int(len(sorted_durations) * 0.95)
        p95 = sorted_durations[p95_index] if p95_index < len(sorted_durations) else sorted_durations[-1]
        p99_index = int(len(sorted_durations) * 0.99)
        p99 = sorted_durations[p99_index] if p99_index < len(sorted_durations) else sorted_durations[-1]
        
        # Requests per minute
        requests_per_minute = total_requests / time_window_minutes
        
        # Most common operations
        operation_counts = defaultdict(int)
        for metric in recent_metrics:
            operation_counts[metric.operation] += 1
        
        top_operations = sorted(operation_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "time_window_minutes": time_window_minutes,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate_percent": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "requests_per_minute": round(requests_per_minute, 2),
            "response_times": {
                "avg_ms": round(avg_response_time * 1000, 2),
                "min_ms": round(min(durations) * 1000, 2),
                "max_ms": round(max(durations) * 1000, 2),
                "p50_ms": round(p50 * 1000, 2),
                "p95_ms": round(p95 * 1000, 2),
                "p99_ms": round(p99 * 1000, 2)
            },
            "top_operations": [{"operation": op, "count": count} for op, count in top_operations],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and metrics"""
        if not self.system_metrics_history:
            return {
                "status": "no_data",
                "message": "System monitoring not started or no data collected yet"
            }
        
        latest_metrics = self.system_metrics_history[-1]
        
        # Determine overall system health
        health_issues = []
        if latest_metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
            health_issues.append("high_cpu")
        if latest_metrics.memory_percent > self.alert_thresholds["memory_percent"]:
            health_issues.append("high_memory")
        if latest_metrics.disk_usage_percent > self.alert_thresholds["disk_usage_percent"]:
            health_issues.append("high_disk")
        
        system_health = "healthy" if not health_issues else "degraded"
        
        return {
            "status": system_health,
            "health_issues": health_issues,
            "metrics": asdict(latest_metrics),
            "thresholds": self.alert_thresholds,
            "active_alerts": len(self.active_alerts),
            "monitoring_duration": len(self.system_metrics_history) * self.system_monitor_interval,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics for all monitored operations"""
        stats = {}
        
        for operation, data in self.operation_stats.items():
            # Calculate additional metrics
            success_rate = (data["success_count"] / data["count"] * 100) if data["count"] > 0 else 0
            error_rate = (data["error_count"] / data["count"] * 100) if data["count"] > 0 else 0
            
            # Calculate percentiles if we have recent durations
            percentiles = {}
            if data["recent_durations"]:
                sorted_durations = sorted(data["recent_durations"])
                percentiles = {
                    "p50_ms": round(statistics.median(sorted_durations) * 1000, 2),
                    "p95_ms": round(sorted_durations[int(len(sorted_durations) * 0.95)] * 1000, 2) if len(sorted_durations) > 0 else 0,
                    "p99_ms": round(sorted_durations[int(len(sorted_durations) * 0.99)] * 1000, 2) if len(sorted_durations) > 0 else 0
                }
            
            stats[operation] = {
                "request_count": data["count"],
                "success_count": data["success_count"],
                "error_count": data["error_count"],
                "success_rate_percent": round(success_rate, 2),
                "error_rate_percent": round(error_rate, 2),
                "avg_duration_ms": round(data["avg_duration"] * 1000, 2),
                "min_duration_ms": round(data["min_duration"] * 1000, 2) if data["min_duration"] != float('inf') else 0,
                "max_duration_ms": round(data["max_duration"] * 1000, 2),
                "percentiles": percentiles,
                "last_updated": data["last_updated"].isoformat() if data["last_updated"] else None
            }
        
        return {
            "operations": stats,
            "total_operations": len(stats),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get list of currently active alerts"""
        return [
            {**alert, "alert_key": key} 
            for key, alert in self.active_alerts.items()
        ]

# Global performance monitor instance
performance_monitor = PerformanceMonitor()