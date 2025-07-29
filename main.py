from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.middleware.frontend_headers import FrontendHeadersMiddleware
from app.database import init_database, close_database, create_tables
from app.services.auth_service import auth_service


@asynccontextmanager  
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    print("Starting Analytics Following Backend...")
    await init_database()
    await create_tables()
    
    # Initialize auth service
    auth_init_success = await auth_service.initialize()
    print(f"Auth service initialized: {auth_init_success}")
    
    yield
    # Shutdown
    print("Shutting down Analytics Following Backend...")
    await close_database()


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

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Analytics Following Backend API", "status": "running"}


@app.get("/health")
async def health_check():
    """Enhanced health check with system info"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "features": {
            "decodo_integration": True,
            "retry_mechanism": True,
            "enhanced_reliability": True
        }
    }


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