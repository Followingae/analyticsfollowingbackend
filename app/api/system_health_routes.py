"""
System Health Monitoring Routes
Comprehensive system health endpoints for monitoring and debugging
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import logging
import asyncio
import time

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user
from app.models.auth import UserInDB

router = APIRouter(prefix="/api/v1/system", tags=["System Health"])
logger = logging.getLogger(__name__)

@router.get("/health/comprehensive")
async def comprehensive_health_check(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Comprehensive system health check including database, services, and dependencies
    """
    start_time = time.time()
    health_report = {
        "timestamp": time.time(),
        "overall_status": "healthy",
        "components": {},
        "performance_metrics": {},
        "recommendations": []
    }
    
    try:
        # Database Health
        db_health = await _check_database_health(db)
        health_report["components"]["database"] = db_health
        
        # Circuit Breaker Status
        circuit_breaker_health = await _check_circuit_breaker_health()
        health_report["components"]["circuit_breaker"] = circuit_breaker_health
        
        # Cache Health (Redis)
        cache_health = await _check_cache_health()
        health_report["components"]["cache"] = cache_health
        
        # AI Services Health
        ai_health = await _check_ai_services_health()
        health_report["components"]["ai_services"] = ai_health
        
        # External API Health
        external_api_health = await _check_external_apis_health()
        health_report["components"]["external_apis"] = external_api_health
        
        # Performance Metrics
        end_time = time.time()
        health_report["performance_metrics"] = {
            "health_check_duration_ms": round((end_time - start_time) * 1000, 2),
            "memory_usage_mb": await _get_memory_usage(),
            "connection_pool_status": await _get_connection_pool_status()
        }
        
        # Determine overall status
        component_statuses = [comp["status"] for comp in health_report["components"].values()]
        if "critical" in component_statuses:
            health_report["overall_status"] = "critical"
        elif "degraded" in component_statuses:
            health_report["overall_status"] = "degraded"
        else:
            health_report["overall_status"] = "healthy"
        
        # Generate recommendations
        health_report["recommendations"] = _generate_health_recommendations(health_report)
        
        return health_report
        
    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}")
        return {
            "timestamp": time.time(),
            "overall_status": "critical",
            "error": str(e),
            "message": "Health check system failure"
        }

@router.get("/health/database")
async def database_health_check(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Detailed database health check
    """
    try:
        return await _check_database_health(db)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "critical",
            "error": str(e),
            "message": "Database health check failed"
        }

@router.post("/recovery/database")
async def trigger_database_recovery(
    current_user: UserInDB = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Manually trigger database recovery procedures
    """
    try:
        logger.info(f"Manual database recovery triggered by {current_user.email}")
        
        # Reset circuit breaker
        from app.resilience.database_resilience import database_resilience
        database_resilience.reset_circuit_breaker()
        
        # Force connection pool refresh
        from app.database.connection import async_engine
        if async_engine:
            # Dispose current connections
            await async_engine.dispose()
            logger.info("Database connection pool disposed")
            
            # Re-initialize database
            from app.database.connection import init_database
            await init_database()
            logger.info("Database re-initialized")
        
        return {
            "success": True,
            "message": "Database recovery procedures completed",
            "actions_taken": [
                "Circuit breaker reset",
                "Connection pool refreshed",
                "Database re-initialized"
            ]
        }
        
    except Exception as e:
        logger.error(f"Database recovery failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Database recovery procedures failed"
        }

@router.get("/monitoring/performance")
async def get_performance_metrics(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed performance metrics
    """
    try:
        from sqlalchemy import text
        
        # Database performance metrics
        db_metrics = {}
        
        # Connection pool metrics
        pool_status = await _get_connection_pool_status()
        db_metrics["connection_pool"] = pool_status
        
        # Query performance sampling
        query_start = time.time()
        await db.execute(text("SELECT COUNT(*) FROM profiles"))
        query_time = (time.time() - query_start) * 1000
        db_metrics["sample_query_ms"] = round(query_time, 2)
        
        # System metrics
        system_metrics = {
            "memory_usage_mb": await _get_memory_usage(),
            "timestamp": time.time()
        }
        
        return {
            "success": True,
            "metrics": {
                "database": db_metrics,
                "system": system_metrics
            }
        }
        
    except Exception as e:
        logger.error(f"Performance metrics collection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Performance metrics unavailable"
        }

# Helper functions

async def _check_database_health(db: AsyncSession) -> Dict[str, Any]:
    """Check database health with detailed diagnostics"""
    try:
        from sqlalchemy import text
        
        # Basic connectivity test
        start_time = time.time()
        result = await asyncio.wait_for(db.execute(text("SELECT 1 as test")), timeout=10)
        response_time = (time.time() - start_time) * 1000
        
        # Table accessibility test
        tables_accessible = 0
        critical_tables = ["profiles", "posts", "users", "credit_wallets"]
        
        for table in critical_tables:
            try:
                await db.execute(text(f"SELECT COUNT(*) FROM {table} LIMIT 1"))
                tables_accessible += 1
            except Exception as e:
                logger.warning(f"Table {table} not accessible: {e}")
        
        # Determine status
        if tables_accessible == len(critical_tables) and response_time < 1000:
            status = "healthy"
        elif tables_accessible >= len(critical_tables) * 0.75:
            status = "degraded"
        else:
            status = "critical"
        
        return {
            "status": status,
            "response_time_ms": round(response_time, 2),
            "tables_accessible": f"{tables_accessible}/{len(critical_tables)}",
            "critical_tables": critical_tables,
            "timestamp": time.time()
        }
        
    except Exception as e:
        return {
            "status": "critical",
            "error": str(e),
            "timestamp": time.time()
        }

async def _check_circuit_breaker_health() -> Dict[str, Any]:
    """Check circuit breaker status"""
    try:
        from app.resilience.database_resilience import database_resilience
        
        is_open = database_resilience.should_circuit_break()
        failure_count = database_resilience.failure_count
        
        if is_open:
            status = "critical"
            message = "Circuit breaker is open"
        elif failure_count > 5:
            status = "degraded" 
            message = f"High failure count: {failure_count}"
        else:
            status = "healthy"
            message = "Circuit breaker operational"
        
        return {
            "status": status,
            "is_open": is_open,
            "failure_count": failure_count,
            "message": message
        }
        
    except Exception as e:
        return {
            "status": "critical",
            "error": str(e)
        }

async def _check_cache_health() -> Dict[str, Any]:
    """Check Redis cache health"""
    try:
        import redis
        import os
        
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        
        start_time = time.time()
        r.ping()
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy" if response_time < 100 else "degraded",
            "response_time_ms": round(response_time, 2),
            "redis_url": redis_url.replace(redis_url.split('@')[0].split('//')[1], '***') if '@' in redis_url else redis_url
        }
        
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "message": "Cache unavailable - system will function with reduced performance"
        }

async def _check_ai_services_health() -> Dict[str, Any]:
    """Check AI services health"""
    try:
        # Test AI model availability
        from app.services.ai.bulletproof_content_intelligence import BulletproofContentIntelligence
        
        ai_service = BulletproofContentIntelligence()
        # Simple test to check if models are loaded
        test_result = await ai_service.analyze_sentiment("test")
        
        if test_result and test_result.get('success'):
            status = "healthy"
        else:
            status = "degraded"
        
        return {
            "status": status,
            "models_loaded": True,
            "test_successful": test_result.get('success', False) if test_result else False
        }
        
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "message": "AI services unavailable - basic functionality will continue"
        }

async def _check_external_apis_health() -> Dict[str, Any]:
    """Check external API health"""
    try:
        # Test network connectivity to key external services
        import httpx
        
        services = {
            "supabase": f"{os.getenv('SUPABASE_URL', '')}/health" if os.getenv('SUPABASE_URL') else None
        }
        
        results = {}
        for service, url in services.items():
            if url:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(url)
                        results[service] = {
                            "status": "healthy" if response.status_code < 400 else "degraded",
                            "response_code": response.status_code
                        }
                except Exception as e:
                    results[service] = {
                        "status": "degraded",
                        "error": str(e)
                    }
            else:
                results[service] = {"status": "not_configured"}
        
        overall_status = "healthy"
        if any(r["status"] == "degraded" for r in results.values()):
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "services": results
        }
        
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }

async def _get_memory_usage() -> float:
    """Get current memory usage in MB"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return round(memory_info.rss / 1024 / 1024, 2)
    except Exception:
        return 0.0

async def _get_connection_pool_status() -> Dict[str, Any]:
    """Get database connection pool status"""
    try:
        from app.database.connection import async_engine
        
        if async_engine and async_engine.pool:
            pool = async_engine.pool
            return {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "status": "healthy" if pool.checkedout() < pool.size() else "degraded"
            }
        else:
            return {"status": "not_available"}
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def _generate_health_recommendations(health_report: Dict[str, Any]) -> List[str]:
    """Generate health recommendations based on current status"""
    recommendations = []
    
    components = health_report.get("components", {})
    
    # Database recommendations
    db_status = components.get("database", {}).get("status")
    if db_status == "critical":
        recommendations.append("CRITICAL: Database connection issues detected. Consider restarting database services.")
    elif db_status == "degraded":
        recommendations.append("WARNING: Database performance is degraded. Monitor connection pool usage.")
    
    # Circuit breaker recommendations
    cb_status = components.get("circuit_breaker", {})
    if cb_status.get("is_open"):
        recommendations.append("URGENT: Circuit breaker is open. System is in protection mode.")
    elif cb_status.get("failure_count", 0) > 5:
        recommendations.append("WARNING: High failure count detected. Monitor system stability.")
    
    # Performance recommendations
    metrics = health_report.get("performance_metrics", {})
    memory_usage = metrics.get("memory_usage_mb", 0)
    if memory_usage > 500:
        recommendations.append("INFO: High memory usage detected. Consider monitoring memory leaks.")
    
    # Cache recommendations
    cache_status = components.get("cache", {}).get("status")
    if cache_status == "degraded":
        recommendations.append("INFO: Cache unavailable. Performance may be reduced.")
    
    if not recommendations:
        recommendations.append("System is operating normally. No immediate action required.")
    
    return recommendations