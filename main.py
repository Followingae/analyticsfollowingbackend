from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.routes import router


@asynccontextmanager  
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    print("Starting Analytics Following Backend...")
    yield
    # Shutdown
    print("Shutting down Analytics Following Backend...")


app = FastAPI(
    title="Analytics Following Backend",
    description="SmartProxy Instagram Analytics API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Analytics Following Backend API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )