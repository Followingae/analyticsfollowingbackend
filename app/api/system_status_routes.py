"""
System Status Routes - Comprehensive System Health and Recovery
Provides detailed system status and recovery actions
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging
from datetime import datetime, timezone

from app.database.connection import get_db
from app.monitoring.network_health_monitor import network_health_monitor
from app.resilience.database_resilience import database_resilience
from app.services.resilient_auth_service import resilient_auth_service
from app.services.startup_initialization import startup_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System Status"])

@router.get("/status/comprehensive")
async def comprehensive_system_status() -> Dict[str, Any]:
    """
    Get comprehensive system status with all components
    """
    try:
        # Get network health
        network_status = network_health_monitor.get_health_summary()
        
        # Get database resilience status
        db_resilience_status = {
            "circuit_breaker_open": database_resilience.circuit_breaker_open,
            "connection_failures": database_resilience.connection_failures,
            "last_failure_time": database_resilience.last_failure_time,
            "circuit_breaker_threshold": database_resilience.circuit_breaker_threshold,
            "circuit_breaker_timeout": database_resilience.circuit_breaker_timeout,
            "network_available": database_resilience.is_network_available()
        }
        
        # Get auth service status
        auth_service_status = resilient_auth_service.get_cache_stats()
        
        # Get startup service status
        startup_status = startup_service.get_initialization_status()
        
        # Calculate overall system health
        system_healthy = (
            network_status.get('overall_healthy', False) and
            not database_resilience.circuit_breaker_open and
            startup_status.get('initialization_complete', False)
        )
        
        system_operational = (
            network_status.get('connectivity_stable', False) or
            auth_service_status.get('cached_tokens', 0) > 0
        )
        
        return {
            "overall_status": "healthy" if system_healthy else ("operational" if system_operational else "degraded"),
            "system_healthy": system_healthy,
            "system_operational": system_operational,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "network": network_status,
                "database_resilience": db_resilience_status,
                "authentication": auth_service_status,
                "startup": startup_status
            },
            "recommendations": generate_system_recommendations(
                network_status, db_resilience_status, auth_service_status
            )
        }
        
    except Exception as e:
        logger.error(f"Failed to get comprehensive system status: {e}")
        return {
            "overall_status": "error",
            "system_healthy": False,
            "system_operational": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "recommendations": ["System status check failed - manual investigation required"]
        }

@router.post("/recovery/circuit-breaker/reset")
async def reset_circuit_breaker() -> Dict[str, Any]:
    """
    Manually reset the database circuit breaker
    """
    try:
        if database_resilience.circuit_breaker_open:
            logger.info("MANUAL RECOVERY: Resetting database circuit breaker")
            database_resilience.record_success()  # This resets the circuit breaker
            
            return {
                "status": "success",
                "message": "Database circuit breaker has been reset",
                "circuit_breaker_open": database_resilience.circuit_breaker_open,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                "status": "info",
                "message": "Circuit breaker was not open",
                "circuit_breaker_open": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}")
        raise HTTPException(status_code=500, detail=f"Circuit breaker reset failed: {str(e)}")

@router.post("/recovery/auth-cache/clear")
async def clear_auth_cache() -> Dict[str, Any]:
    """
    Clear authentication cache to force fresh validation
    """
    try:
        # Get current stats before clearing
        before_stats = resilient_auth_service.get_cache_stats()
        
        # Clear caches
        resilient_auth_service.token_cache.clear()
        resilient_auth_service.failed_tokens.clear()
        
        # Get stats after clearing
        after_stats = resilient_auth_service.get_cache_stats()
        
        logger.info("MANUAL RECOVERY: Authentication cache cleared")
        
        return {
            "status": "success",
            "message": "Authentication cache has been cleared",
            "before": before_stats,
            "after": after_stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear auth cache: {e}")
        raise HTTPException(status_code=500, detail=f"Auth cache clear failed: {str(e)}")

@router.get("/recovery/suggestions")
async def get_recovery_suggestions() -> Dict[str, Any]:
    """
    Get automated recovery suggestions based on current system state
    """
    try:
        network_status = network_health_monitor.get_current_status()
        db_status = {
            "circuit_breaker_open": database_resilience.circuit_breaker_open,
            "connection_failures": database_resilience.connection_failures,
            "network_available": database_resilience.is_network_available()
        }
        auth_stats = resilient_auth_service.get_cache_stats()
        
        suggestions = generate_recovery_suggestions(network_status, db_status, auth_stats)
        
        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_issues": identify_current_issues(network_status, db_status, auth_stats),
            "recovery_suggestions": suggestions,
            "automated_actions": [
                {
                    "action": "Reset Circuit Breaker",
                    "endpoint": "/system/recovery/circuit-breaker/reset",
                    "method": "POST",
                    "condition": "When database circuit breaker is open"
                },
                {
                    "action": "Clear Auth Cache",
                    "endpoint": "/system/recovery/auth-cache/clear", 
                    "method": "POST",
                    "condition": "When authentication is failing"
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to generate recovery suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Recovery suggestions failed: {str(e)}")

def generate_system_recommendations(network_status: Dict, db_status: Dict, auth_status: Dict) -> list:
    """Generate system recommendations based on current status"""
    recommendations = []
    
    if not network_status.get('overall_healthy', True):
        if not network_status.get('dns_working', True):
            recommendations.append("DNS resolution issues detected - check internet connectivity")
        if not network_status.get('database_reachable', True):
            recommendations.append("Database connectivity issues - check network and database server")
        if not network_status.get('supabase_reachable', True):
            recommendations.append("Supabase connectivity issues - check external service status")
    
    if db_status.get('circuit_breaker_open', False):
        recommendations.append("Database circuit breaker is open - consider manual reset if network is stable")
    
    if db_status.get('connection_failures', 0) > 0:
        recommendations.append(f"Database has {db_status['connection_failures']} connection failures - monitor closely")
    
    if not auth_status.get('network_available', True):
        recommendations.append("Authentication service is in offline mode - using cached tokens")
    
    if auth_status.get('failed_tokens', 0) > 10:
        recommendations.append("High number of failed authentication attempts - consider cache clear")
    
    if not recommendations:
        recommendations.append("System is operating normally")
    
    return recommendations

def generate_recovery_suggestions(network_status: Dict, db_status: Dict, auth_status: Dict) -> list:
    """Generate automated recovery suggestions"""
    suggestions = []
    
    if db_status.get('circuit_breaker_open', False):
        if network_status.get('database_reachable', False):
            suggestions.append({
                "issue": "Database circuit breaker is open but database appears reachable",
                "suggestion": "Try resetting the circuit breaker",
                "action": "POST /system/recovery/circuit-breaker/reset",
                "priority": "high"
            })
    
    if auth_status.get('failed_tokens', 0) > 5:
        suggestions.append({
            "issue": "Multiple authentication failures detected",
            "suggestion": "Clear authentication cache to force fresh validation",
            "action": "POST /system/recovery/auth-cache/clear",
            "priority": "medium"
        })
    
    if not network_status.get('overall_healthy', True):
        suggestions.append({
            "issue": "Network connectivity issues detected",
            "suggestion": "Wait for network to stabilize, system will auto-recover",
            "action": "Monitor /system/status/comprehensive",
            "priority": "low"
        })
    
    return suggestions

def identify_current_issues(network_status: Dict, db_status: Dict, auth_status: Dict) -> list:
    """Identify current system issues"""
    issues = []
    
    if db_status.get('circuit_breaker_open', False):
        issues.append("Database circuit breaker is open")
    
    if not network_status.get('dns_working', True):
        issues.append("DNS resolution is not working")
    
    if not network_status.get('database_reachable', True):
        issues.append("Database is not reachable")
    
    if not network_status.get('supabase_reachable', True):
        issues.append("Supabase is not reachable")
    
    if not auth_status.get('network_available', True):
        issues.append("Authentication service is in offline mode")
    
    if auth_status.get('failed_tokens', 0) > 0:
        issues.append(f"{auth_status['failed_tokens']} authentication tokens have failed")
    
    return issues if issues else ["No issues detected"]