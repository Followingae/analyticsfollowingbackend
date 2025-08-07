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
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.cleaned_routes import router
from app.api.cleaned_auth_routes import router as auth_router
from app.api.settings_routes import router as settings_router
from app.middleware.frontend_headers import FrontendHeadersMiddleware
from app.database import init_database, close_database, create_tables
from app.database.comprehensive_service import comprehensive_service
from app.services.supabase_auth_service import supabase_auth_service as auth_service
from app.cache import periodic_cache_cleanup


@asynccontextmanager  
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    print("Starting Analytics Following Backend...")
    
    # MANDATORY DATABASE INITIALIZATION - App cannot start without database
    try:
        print("Initializing database connection...")
        await init_database()
        await create_tables()
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
        await asyncio.wait_for(comprehensive_service.init_pool(), timeout=5.0)
        print("Comprehensive service initialized")
    except Exception as e:
        print(f"Comprehensive service failed: {e}")
    
    # Start cache cleanup task
    try:
        asyncio.create_task(periodic_cache_cleanup())
        print("Cache cleanup task started")
    except Exception as e:
        print(f"Cache cleanup task failed: {e}")
    
    yield
    # Shutdown
    print("Shutting down Analytics Following Backend...")
    try:
        await close_database()
        await comprehensive_service.close_pool()
    except Exception as e:
        print(f"Database cleanup failed: {e}")


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

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")

# Include My Lists routes
from app.api.lists_routes import router as lists_router
app.include_router(lists_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Analytics Following Backend API", "status": "running"}


@app.get("/health")
async def health_check():
    """Enhanced health check with system info"""
    auth_health = await auth_service.health_check()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.1-comprehensive",
        "features": {
            "decodo_integration": True,
            "retry_mechanism": True,
            "enhanced_reliability": True,
            "comprehensive_analytics": True,
            "rls_security": True,
            "complete_datapoint_storage": True,
            "30_day_access_system": True,
            "advanced_user_dashboard": True,
            "image_thumbnail_storage": True
        },
        "services": {
            "auth": auth_health
        }
    }


@app.get("/health/db")
async def database_health_check():
    """Database-specific health check endpoint"""
    from app.database.connection import async_engine
    from sqlalchemy import text
    
    try:
        if not async_engine:
            return {"db": "error", "message": "Database engine not initialized"}, 500
            
        # Test database connection with a simple query
        async with async_engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            
            # Test current timestamp
            result = await conn.execute(text("SELECT NOW() as current_time"))
            current_time = result.scalar()
            
        return {
            "db": "ok",
            "test_query": test_value,
            "server_time": current_time.isoformat(),
            "pool_size": async_engine.pool.size(),
            "checked_out": async_engine.pool.checkedout(),
            "overflow": async_engine.pool.overflow(),
            "pool_status": "healthy"
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"db": "error", "message": str(e)}, 500




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