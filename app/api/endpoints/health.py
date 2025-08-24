from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import psutil
import time
from typing import Dict, Any

from app.database.connection import get_db
from app.cache.redis_cache_manager import redis_cache_manager as cache_manager

router = APIRouter()

@router.get("/health", response_model=Dict[str, Any])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Comprehensive system health check endpoint
    Returns overall health status and component diagnostics
    """
    start_time = time.time()
    health_data = {
        "status": "healthy",
        "timestamp": int(time.time()),
        "version": "1.0.0",
        "components": {},
        "performance": {}
    }
    
    # Database health check
    try:
        await db.execute(text("SELECT 1"))
        health_data["components"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["components"]["database"] = {
            "status": "unhealthy", 
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Redis/Cache health check
    try:
        if cache_manager.initialized:
            await cache_manager.redis_client.ping()
            health_data["components"]["redis"] = {
                "status": "healthy",
                "message": "Redis connection successful"
            }
        else:
            health_data["components"]["redis"] = {
                "status": "warning",
                "message": "Redis not initialized"
            }
    except Exception as e:
        health_data["components"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }
    
    # System resource check
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_data["components"]["system"] = {
            "status": "healthy" if cpu_percent < 80 and memory.percent < 85 else "warning",
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent
        }
    except Exception as e:
        health_data["components"]["system"] = {
            "status": "warning",
            "message": f"System metrics unavailable: {str(e)}"
        }
    
    # Calculate overall health
    component_statuses = [comp["status"] for comp in health_data["components"].values()]
    if "unhealthy" in component_statuses:
        health_data["status"] = "unhealthy"
    elif "warning" in component_statuses:
        health_data["status"] = "degraded"
    
    # Performance metrics
    health_data["performance"] = {
        "response_time_ms": round((time.time() - start_time) * 1000, 2)
    }
    
    return health_data


@router.get("/metrics", response_model=Dict[str, Any])
async def system_metrics(db: AsyncSession = Depends(get_db)):
    """
    Detailed system metrics and performance data
    """
    try:
        # Database metrics
        db_metrics = {}
        try:
            # Get connection pool stats
            if hasattr(db.bind, 'pool'):
                pool = db.bind.pool
                db_metrics = {
                    "pool_size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow()
                }
        except Exception as e:
            db_metrics = {"error": f"Could not get DB metrics: {str(e)}"}
        
        # System metrics
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent,
                "used": psutil.virtual_memory().used
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            }
        }
        
        # Redis metrics
        redis_metrics = {}
        try:
            if cache_manager.initialized:
                info = await cache_manager.redis_client.info()
                redis_metrics = {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0)
                }
        except Exception as e:
            redis_metrics = {"error": f"Redis metrics unavailable: {str(e)}"}
        
        return {
            "timestamp": int(time.time()),
            "database": db_metrics,
            "system": system_metrics,
            "redis": redis_metrics,
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/database/schema-check", response_model=Dict[str, Any])
async def database_schema_check(db: AsyncSession = Depends(get_db)):
    """
    TEMPORARY: Check database schema for missing columns and fix if needed
    """
    try:
        results = {
            "status": "checking",
            "tables_checked": [],
            "issues_found": [],
            "fixes_applied": [],
            "timestamp": int(time.time())
        }
        
        # Check monthly_usage_tracking table structure
        table_check = await db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'monthly_usage_tracking' 
            ORDER BY ordinal_position;
        """))
        columns = [dict(row._mapping) for row in table_check]
        
        results["tables_checked"].append({
            "table": "monthly_usage_tracking",
            "columns": columns
        })
        
        # Check for missing timestamp columns
        has_created_at = any(col['column_name'] == 'created_at' for col in columns)
        has_updated_at = any(col['column_name'] == 'updated_at' for col in columns)
        
        if not has_created_at:
            results["issues_found"].append("monthly_usage_tracking missing created_at column")
            # Attempt to fix
            try:
                await db.execute(text("""
                    ALTER TABLE monthly_usage_tracking 
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
                """))
                results["fixes_applied"].append("Added created_at column to monthly_usage_tracking")
            except Exception as fix_error:
                results["issues_found"].append(f"Failed to add created_at: {str(fix_error)}")
        
        if not has_updated_at:
            results["issues_found"].append("monthly_usage_tracking missing updated_at column")
            # Attempt to fix
            try:
                await db.execute(text("""
                    ALTER TABLE monthly_usage_tracking 
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
                """))
                results["fixes_applied"].append("Added updated_at column to monthly_usage_tracking")
            except Exception as fix_error:
                results["issues_found"].append(f"Failed to add updated_at: {str(fix_error)}")
        
        # Try to create trigger if columns were added
        if results["fixes_applied"]:
            try:
                await db.execute(text("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                    
                    DROP TRIGGER IF EXISTS update_monthly_usage_tracking_updated_at ON monthly_usage_tracking;
                    CREATE TRIGGER update_monthly_usage_tracking_updated_at
                        BEFORE UPDATE ON monthly_usage_tracking
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                """))
                results["fixes_applied"].append("Created updated_at trigger for monthly_usage_tracking")
            except Exception as trigger_error:
                results["issues_found"].append(f"Failed to create trigger: {str(trigger_error)}")
        
        await db.commit()
        
        results["status"] = "completed" if not results["issues_found"] or results["fixes_applied"] else "issues_found"
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema check failed: {str(e)}")