from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import io
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn
import asyncio
import os

# Suppress TensorFlow verbose startup messages
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Suppress PyTorch/Transformers deprecation warnings
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*encoder_attention_mask.*")
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.cleaned_auth_routes import router as auth_router
from app.api.settings_routes import router as settings_router
# NOTE: Removed cleaned_routes and engagement_routes - functionality moved to robust creator search
from app.api.credit_routes import router as credit_router
from app.middleware.frontend_headers import FrontendHeadersMiddleware
from app.database import init_database, close_database, create_tables
from app.database.comprehensive_service import comprehensive_service
from app.services.supabase_auth_service import supabase_auth_service as auth_service
# Cache cleanup moved to Redis cache manager
# Removed automatic AI refresh scheduler - using manual refresh only


@asynccontextmanager  
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    print("Starting Analytics Following Backend...")
    
    # MANDATORY DATABASE INITIALIZATION - App cannot start without database
    try:
        print("Initializing database connection...")
        await init_database()
        # await create_tables()  # Temporary: Skip table creation during startup
        print("Connected to Supabase - Database ready")
    except Exception as e:
        print(f"CRITICAL: Database initialization failed: {e}")
        print("APPLICATION CANNOT START WITHOUT DATABASE")
        raise SystemExit(f"Database initialization failed: {e}")
    
    # Initialize auth service (independent of database)
    try:
        auth_init_success = await auth_service.initialize()
        print(f"Auth service initialized: {auth_init_success}")
    except Exception as e:
        print(f"Auth service failed: {e}")
    
    # Initialize comprehensive service (may depend on database) 
    try:
        await asyncio.wait_for(comprehensive_service.init_pool(), timeout=15.0)  # Increased timeout
        print("Comprehensive service initialized")
    except asyncio.TimeoutError:
        print("Comprehensive service initialization timed out - will operate without connection pool")
    except Exception as e:
        print(f"Comprehensive service failed: {e}")
        # Don't fail startup - the service can operate without the pool
    
    # Cache cleanup now handled by Redis cache manager
    print("Cache management integrated into Redis cache system")
    
    # MANDATORY SYSTEM INITIALIZATION - ROBUST CREATOR SEARCH
    try:
        print("MANDATORY: Initializing Robust Creator Search System...")
        from app.services.startup_initialization import startup_service
        
        # Initialize all critical services
        initialization_result = await startup_service.initialize_all_services()
        
        if not initialization_result["success"]:
            raise SystemExit(f"System initialization failed: {initialization_result}")
        
        print(f"SUCCESS: System initialization completed in {initialization_result['initialization_time']:.2f}s")
        print("READY: Robust Creator Search System is READY")
        
    except Exception as e:
        print(f"FATAL ERROR: System initialization failed: {e}")
        print("APPLICATION CANNOT START - Critical services failed")
        raise SystemExit(f"System initialization failed: {e}")
    
    # Validate Redis connection is available for background processing
    try:
        print("Checking Redis connection for AI background processing...")
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print("Redis connection successful - Background AI processing available")
    except Exception as e:
        print(f"WARNING: Redis not available: {e}")
        print("Background AI processing will not be available")
        # Don't fail startup - Redis is needed for background processing but not critical for startup
    
    yield
    # Shutdown
    print("Shutting down Analytics Following Backend...")
    try:
        await close_database()
        await comprehensive_service.close_pool()
    except Exception as e:
        print(f"Cleanup failed: {e}")


app = FastAPI(
    title="Analytics Following Backend",
    description="SmartProxy Instagram Analytics API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - Configured for production and development
import os
from typing import List

def get_allowed_origins() -> List[str]:
    """Get allowed origins based on environment"""
    if settings.DEBUG:
        # Development origins
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000", 
            "http://localhost:3001",
            "https://localhost:3000",
            # Add production URLs even in debug mode for testing
            "https://analyticsfollowingfrontend.vercel.app",
            "https://analytics.following.ae",
            "https://analyticsfollowingfrontend-followingaes-projects.vercel.app",
            "*"  # Allow all in development
        ]
    else:
        # Production origins
        allowed = os.getenv("ALLOWED_ORIGINS", "").split(",")
        base_origins = [origin.strip() for origin in allowed if origin.strip()]
        
        # Add default production domains
        default_origins = [
            "https://following.ae",
            "https://www.following.ae", 
            "https://app.following.ae",
            "https://analytics.following.ae"
        ]
        
        # Add your specific frontend URLs
        vercel_origins = [
            "https://analyticsfollowingfrontend.vercel.app",
            "https://analytics.following.ae",
            "https://analyticsfollowingfrontend-followingaes-projects.vercel.app",
            "https://analytics-following-frontend.vercel.app",
            "https://barakat-frontend.vercel.app", 
            "https://following-frontend.vercel.app",
            "https://analytics-frontend.vercel.app",
            # Add wildcard patterns for common naming
            "https://*.vercel.app"
        ]
        
        return base_origins + default_origins + vercel_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add custom middleware for frontend integration
app.add_middleware(FrontendHeadersMiddleware)

# Configure static file serving for uploads
uploads_dir = "uploads"
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir, exist_ok=True)
    os.makedirs(os.path.join(uploads_dir, "avatars"), exist_ok=True)
    print(f"Created upload directories: {uploads_dir}/avatars")

app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include Core API routes (NON-INSTAGRAM)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(credit_router, prefix="/api/v1")
# NOTE: Removed old router (cleaned_routes.py) - replaced by robust creator search system

# Include My Lists routes
from app.api.lists_routes import router as lists_router
app.include_router(lists_router, prefix="/api/v1")

# Include Discovery routes
from app.api.discovery_routes import router as discovery_router
app.include_router(discovery_router, prefix="/api/v1")

# Include Campaigns routes - WORKING VERSION (No auth until dependency issue resolved)
from app.api.campaigns_routes import router as campaigns_router
app.include_router(campaigns_router, prefix="/api/v1")

# Include Health and Metrics endpoints
from app.api.endpoints.health import router as health_router
app.include_router(health_router, prefix="/api")

# Include Brand Proposals routes
from app.api.brand_proposals_routes import router as brand_proposals_router
# NOTE: Removed team_instagram_routes - replaced by robust creator search system
from app.api.team_management_routes import router as team_management_router
from app.api.stripe_subscription_routes import router as stripe_router
app.include_router(brand_proposals_router, prefix="/api")

# NOTE: Removed team_router (team_instagram_routes.py) - replaced by robust creator search system

# Include Team Management routes - Team member management
app.include_router(team_management_router, prefix="/api/v1")

# Include Stripe Subscription routes - Billing and subscription management
app.include_router(stripe_router, prefix="/api/v1")

# Include Robust Creator Search routes - BULLETPROOF CREATOR SEARCH SYSTEM
from app.api.robust_creator_search_routes import router as robust_creator_router
app.include_router(robust_creator_router, prefix="/api/v1")

# System status and recovery routes
from app.api.system_status_routes import router as system_status_router  
app.include_router(system_status_router, prefix="/api/v1")

# Include Admin Proposals Routes - SECURITY ENABLED
from app.api.admin_secure.proposals_routes import router as admin_proposals_router
app.include_router(admin_proposals_router, prefix="/api")

# Include CDN Media and Health routes
from app.api.cdn_media_routes import router as cdn_media_router
from app.api.cdn_health_routes import router as cdn_health_router
app.include_router(cdn_media_router, prefix="/api/v1")
app.include_router(cdn_health_router, prefix="/api/v1")

# TEMPORARY FIX: Add credit routes with double prefix to fix frontend calling wrong URL
# This should be removed once frontend is updated to use correct /api/v1/credits/* paths
app.include_router(credit_router, prefix="/api/v1/api", tags=["Credits (Legacy)"])

# Direct AI routes temporarily removed - will be restored if needed


@app.get("/")
async def root():
    return {"message": "Analytics Following Backend API", "status": "running"}


@app.get("/health")
async def health_check():
    """Enhanced health check with comprehensive resilience monitoring"""
    try:
        # Import resilience services
        from app.resilience.database_resilience import database_resilience
        from app.monitoring.network_health_monitor import network_health_monitor
        from app.services.resilient_auth_service import resilient_auth_service
        
        # Get auth service health with resilience fallback
        try:
            auth_health = await auth_service.health_check()
        except Exception as auth_error:
            logger.warning(f"HEALTH: Auth service health check failed: {auth_error}")
            auth_health = {
                "status": "degraded",
                "error": str(auth_error),
                "fallback_active": True
            }
        
        # Get network status
        network_status = network_health_monitor.get_current_status()
        
        # Get database resilience status
        database_status = {
            "circuit_breaker_open": database_resilience.circuit_breaker_open,
            "connection_failures": database_resilience.connection_failures,
            "network_available": database_resilience.is_network_available(),
            "last_failure_time": database_resilience.last_failure_time
        }
        
        # Get resilient auth service status
        resilient_auth_stats = resilient_auth_service.get_cache_stats()
        
        # Calculate overall system health
        overall_healthy = (
            network_status.get('overall_healthy', False) and
            not database_resilience.circuit_breaker_open and
            auth_health.get("status") != "error"
        )
        
        system_operational = (
            network_status.get('connectivity_stable', False) or
            resilient_auth_stats.get('cached_tokens', 0) > 0 or
            not database_resilience.circuit_breaker_open
        )
        
        # Determine overall status
        if overall_healthy:
            overall_status = "healthy"
        elif system_operational:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.2-network-resilient",
            "features": {
                "decodo_integration": True,
                "retry_mechanism": True,
                "enhanced_reliability": True,
                "comprehensive_analytics": True,
                "rls_security": True,
                "complete_datapoint_storage": True,
                "30_day_access_system": True,
                "advanced_user_dashboard": True,
                "image_thumbnail_storage": True,
                "network_resilience": True,
                "circuit_breaker_protection": True,
                "automatic_recovery": True
            },
            "services": {
                "auth": auth_health,
                "network": network_status,
                "database_resilience": database_status,
                "resilient_auth": resilient_auth_stats
            },
            "system_info": {
                "healthy": overall_healthy,
                "operational": system_operational,
                "resilience_active": True,
                "auto_recovery_enabled": True
            },
            "recommendations": _generate_health_recommendations(
                network_status, database_status, auth_health
            )
        }
        
    except Exception as e:
        logger.error(f"HEALTH CHECK FAILED: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.2-network-resilient",
            "error": str(e),
            "emergency_mode": True,
            "message": "Health check system encountered an error - manual investigation required"
        }


def _generate_health_recommendations(network_status, database_status, auth_health):
    """Generate health recommendations based on system status"""
    recommendations = []
    
    if not network_status.get('overall_healthy', True):
        if not network_status.get('dns_working', True):
            recommendations.append("DNS resolution issues detected - check internet connectivity and DNS servers")
        if not network_status.get('database_reachable', True):
            recommendations.append("Database connectivity issues - verify network connection and database server status")
        if not network_status.get('supabase_reachable', True):
            recommendations.append("Supabase API connectivity issues - check external service status")
    
    if database_status.get('circuit_breaker_open', False):
        recommendations.append("Database circuit breaker is OPEN - automatic recovery in progress, or use manual reset endpoint")
    
    if database_status.get('connection_failures', 0) > 3:
        recommendations.append(f"High number of database failures ({database_status['connection_failures']}) - monitor network stability")
    
    if auth_health.get("status") == "degraded":
        recommendations.append("Authentication service degraded - using fallback mechanisms")
    
    if not recommendations:
        recommendations.append("All systems operating normally with full resilience protection active")
    
    return recommendations


@app.get("/health/db")
async def database_health_check():
    """Database-specific health check endpoint with network resilience"""
    from app.database.connection import async_engine
    from app.resilience.database_resilience import database_resilience
    from sqlalchemy import text
    import asyncio
    
    try:
        if not async_engine:
            return {
                "db": "error", 
                "message": "Database engine not initialized",
                "timestamp": datetime.now().isoformat(),
                "resilience_active": False
            }
        
        # Check circuit breaker status
        if database_resilience.should_circuit_break():
            return {
                "db": "circuit_breaker_open",
                "message": "Database circuit breaker is currently OPEN",
                "circuit_breaker_open": True,
                "connection_failures": database_resilience.connection_failures,
                "last_failure_time": database_resilience.last_failure_time,
                "timestamp": datetime.now().isoformat(),
                "resilience_active": True,
                "recommendation": "Wait for automatic recovery or use manual reset endpoint"
            }
        
        # Test database connection with resilience and timeout
        try:
            # Fix async context manager usage
            async with async_engine.begin() as conn:
                # Test basic query
                result = await asyncio.wait_for(
                    conn.execute(text("SELECT 1 as test")), 
                    timeout=5
                )
                test_value = result.scalar()
                
                # Test current timestamp
                result = await asyncio.wait_for(
                    conn.execute(text("SELECT NOW() as current_time")), 
                    timeout=5
                )
                current_time = result.scalar()
                
                # Test schema check
                result = await asyncio.wait_for(
                    conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")),
                    timeout=5
                )
                table_count = result.scalar()
                
            # Success - record in resilience system
            database_resilience.record_success()
            
            return {
                "db": "healthy",
                "test_query": test_value,
                "server_time": current_time.isoformat(),
                "table_count": table_count,
                "pool_size": async_engine.pool.size(),
                "checked_out": async_engine.pool.checkedout(),
                "overflow": async_engine.pool.overflow(),
                "pool_status": "healthy",
                "circuit_breaker_open": False,
                "connection_failures": database_resilience.connection_failures,
                "timestamp": datetime.now().isoformat(),
                "resilience_active": True,
                "network_available": database_resilience.is_network_available()
            }
            
        except asyncio.TimeoutError as timeout_error:
            database_resilience.record_failure()
            logger.error(f"Database health check timeout: {timeout_error}")
            return {
                "db": "timeout",
                "message": "Database connection timeout - network issues detected",
                "error": "Connection timed out",
                "circuit_breaker_open": database_resilience.circuit_breaker_open,
                "connection_failures": database_resilience.connection_failures,
                "timestamp": datetime.now().isoformat(),
                "resilience_active": True,
                "recommendation": "Check network connectivity and database server status"
            }
            
        except Exception as conn_error:
            database_resilience.record_failure()
            error_str = str(conn_error).lower()
            
            # Check for network-specific errors
            if any(net_error in error_str for net_error in 
                   ["getaddrinfo failed", "name or service not known", "network is unreachable",
                    "connection refused", "no route to host"]):
                return {
                    "db": "network_error",
                    "message": f"Database connection failed due to network issues: {conn_error}",
                    "error": str(conn_error),
                    "error_type": "network_connectivity",
                    "circuit_breaker_open": database_resilience.circuit_breaker_open,
                    "connection_failures": database_resilience.connection_failures,
                    "timestamp": datetime.now().isoformat(),
                    "resilience_active": True,
                    "recommendation": "Check internet connectivity, DNS resolution, and network routing"
                }
            else:
                return {
                    "db": "error",
                    "message": f"Database connection failed: {conn_error}",
                    "error": str(conn_error),
                    "error_type": "database_error",
                    "circuit_breaker_open": database_resilience.circuit_breaker_open,
                    "connection_failures": database_resilience.connection_failures,
                    "timestamp": datetime.now().isoformat(),
                    "resilience_active": True
                }
        
    except Exception as e:
        logger.error(f"Database health check system error: {e}")
        return {
            "db": "system_error",
            "message": f"Database health check system error: {str(e)}",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "resilience_active": False,
            "recommendation": "Manual investigation required"
        }




@app.get("/api/test")
async def test_endpoint():
    """Test endpoint"""
    return {"message": "Test endpoint working"}



@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "name": "Analytics Following Backend",
        "version": "2.0.0",
        "description": "Instagram Analytics API with Decodo integration",
        "base_url": "/api/v1",
        "documentation": "/docs",
        "health_check": "/health",
        "frontend_port": 3000,
        "backend_port": 8000
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )