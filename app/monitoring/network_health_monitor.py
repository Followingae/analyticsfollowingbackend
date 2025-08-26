"""
Network Health Monitoring Service
Monitors network connectivity and provides system health information
"""
import asyncio
import logging
import time
import socket
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)

@dataclass
class NetworkStatus:
    """Network connectivity status"""
    dns_working: bool = False
    http_working: bool = False
    database_reachable: bool = False
    supabase_reachable: bool = False
    last_check: datetime = None
    check_duration_ms: float = 0
    errors: List[str] = None

class NetworkHealthMonitor:
    """
    Monitors network connectivity and service health
    """
    
    def __init__(self):
        self.check_interval = 30  # seconds
        self.timeout = 5  # seconds for each check
        self.monitoring_active = False
        self.current_status = NetworkStatus(errors=[])
        self.history = []  # Keep last 10 checks
        self.max_history = 10
        
        # Test endpoints
        self.dns_servers = ['8.8.8.8', '1.1.1.1']
        self.http_endpoints = [
            'https://httpbin.org/status/200',
            'https://google.com',
        ]
        
    async def check_dns_connectivity(self) -> bool:
        """Check if DNS resolution is working"""
        try:
            for dns_server in self.dns_servers:
                socket.inet_aton(dns_server)  # Validate IP
                
            # Try to resolve common domains
            test_domains = ['google.com', 'cloudflare.com']
            for domain in test_domains:
                try:
                    socket.gethostbyname(domain)
                    return True
                except socket.gaierror:
                    continue
                    
            return False
        except Exception as e:
            logger.debug(f"DNS check failed: {e}")
            return False
    
    async def check_http_connectivity(self) -> bool:
        """Check if HTTP requests are working"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for endpoint in self.http_endpoints:
                    try:
                        response = await client.get(endpoint)
                        if response.status_code < 400:
                            return True
                    except Exception:
                        continue
            return False
        except Exception as e:
            logger.debug(f"HTTP check failed: {e}")
            return False
    
    async def check_database_connectivity(self) -> bool:
        """Check if database is reachable"""
        try:
            from app.core.config import settings
            
            # Parse database URL to get host and port
            if not settings.DATABASE_URL:
                return False
                
            # Extract host from DATABASE_URL
            # postgresql://user:pass@host:port/db
            if '://' in settings.DATABASE_URL:
                parts = settings.DATABASE_URL.split('://')[1]
                if '@' in parts:
                    host_part = parts.split('@')[1]
                    host = host_part.split('/')[0]
                    if ':' in host:
                        host = host.split(':')[0]
                    
                    # Try to connect to database host
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.timeout)
                    result = sock.connect_ex((host, 5432))  # PostgreSQL port
                    sock.close()
                    return result == 0
                    
            return False
        except Exception as e:
            logger.debug(f"Database connectivity check failed: {e}")
            return False
    
    async def check_supabase_connectivity(self) -> bool:
        """Check if Supabase is reachable"""
        try:
            from app.core.config import settings
            
            if not settings.SUPABASE_URL:
                return False
                
            # Try to reach Supabase health endpoint
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                health_url = f"{settings.SUPABASE_URL}/rest/v1/"
                response = await client.get(health_url)
                return response.status_code < 500
                
        except Exception as e:
            logger.debug(f"Supabase connectivity check failed: {e}")
            return False
    
    async def perform_health_check(self) -> NetworkStatus:
        """Perform comprehensive network health check"""
        start_time = time.time()
        errors = []
        
        try:
            # Run all checks concurrently
            dns_task = self.check_dns_connectivity()
            http_task = self.check_http_connectivity()
            db_task = self.check_database_connectivity()
            supabase_task = self.check_supabase_connectivity()
            
            # Wait for all checks with timeout
            dns_ok, http_ok, db_ok, supabase_ok = await asyncio.gather(
                dns_task, http_task, db_task, supabase_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(dns_ok, Exception):
                dns_ok = False
                errors.append(f"DNS check failed: {dns_ok}")
            
            if isinstance(http_ok, Exception):
                http_ok = False
                errors.append(f"HTTP check failed: {http_ok}")
                
            if isinstance(db_ok, Exception):
                db_ok = False
                errors.append(f"Database check failed: {db_ok}")
                
            if isinstance(supabase_ok, Exception):
                supabase_ok = False
                errors.append(f"Supabase check failed: {supabase_ok}")
            
            check_duration = (time.time() - start_time) * 1000  # milliseconds
            
            status = NetworkStatus(
                dns_working=bool(dns_ok),
                http_working=bool(http_ok),
                database_reachable=bool(db_ok),
                supabase_reachable=bool(supabase_ok),
                last_check=datetime.now(timezone.utc),
                check_duration_ms=check_duration,
                errors=errors
            )
            
            return status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return NetworkStatus(
                dns_working=False,
                http_working=False,
                database_reachable=False,
                supabase_reachable=False,
                last_check=datetime.now(timezone.utc),
                check_duration_ms=(time.time() - start_time) * 1000,
                errors=[f"Health check exception: {e}"]
            )
    
    async def start_monitoring(self):
        """Start continuous network monitoring"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        logger.info("NETWORK MONITOR: Starting network health monitoring")
        
        while self.monitoring_active:
            try:
                status = await self.perform_health_check()
                self.current_status = status
                
                # Add to history
                self.history.append(status)
                if len(self.history) > self.max_history:
                    self.history.pop(0)
                
                # Log status changes
                if not status.dns_working:
                    logger.warning("NETWORK MONITOR: DNS connectivity issues detected")
                if not status.database_reachable:
                    logger.warning("NETWORK MONITOR: Database connectivity issues detected")
                if not status.supabase_reachable:
                    logger.warning("NETWORK MONITOR: Supabase connectivity issues detected")
                    
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"NETWORK MONITOR: Monitoring loop error: {e}")
                await asyncio.sleep(5)  # Short wait on error
    
    def stop_monitoring(self):
        """Stop network monitoring"""
        self.monitoring_active = False
        logger.info("NETWORK MONITOR: Stopped network health monitoring")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current network status"""
        status = self.current_status
        return {
            'overall_healthy': (
                status.dns_working and 
                (status.database_reachable or status.supabase_reachable)
            ),
            'dns_working': status.dns_working,
            'http_working': status.http_working,
            'database_reachable': status.database_reachable,
            'supabase_reachable': status.supabase_reachable,
            'last_check': status.last_check.isoformat() if status.last_check else None,
            'check_duration_ms': status.check_duration_ms,
            'errors': status.errors or [],
            'monitoring_active': self.monitoring_active
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary with history"""
        if not self.history:
            return self.get_current_status()
        
        # Calculate success rates over last checks
        recent_checks = self.history[-5:]  # Last 5 checks
        dns_success_rate = sum(1 for s in recent_checks if s.dns_working) / len(recent_checks)
        db_success_rate = sum(1 for s in recent_checks if s.database_reachable) / len(recent_checks)
        
        current = self.get_current_status()
        current.update({
            'recent_dns_success_rate': dns_success_rate,
            'recent_db_success_rate': db_success_rate,
            'total_checks': len(self.history),
            'connectivity_stable': dns_success_rate > 0.6 and db_success_rate > 0.6
        })
        
        return current

# Global instance
network_health_monitor = NetworkHealthMonitor()