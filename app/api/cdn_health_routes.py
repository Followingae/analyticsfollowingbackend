"""
CDN Health Check Routes
Comprehensive health monitoring for CDN system
"""
from fastapi import APIRouter, Depends, status
from typing import Dict, Any, List
import logging
from datetime import datetime
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.infrastructure.r2_storage_client import R2StorageClient
from app.services.cdn_image_service import cdn_image_service
from app.services.image_transcoder_service import ImageTranscoderService
from app.middleware.auth_middleware import get_current_active_user
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["CDN Health"])

# Service instances
_r2_client = None
_transcoder_service = None

def get_r2_client() -> R2StorageClient:
    """Get R2 storage client singleton"""
    global _r2_client
    if _r2_client is None:
        _r2_client = R2StorageClient(
            account_id=settings.CF_ACCOUNT_ID,
            access_key=settings.R2_ACCESS_KEY_ID,
            secret_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME
        )
    return _r2_client

def get_transcoder_service() -> ImageTranscoderService:
    """Get image transcoder service singleton"""
    global _transcoder_service
    if _transcoder_service is None:
        _transcoder_service = ImageTranscoderService(get_r2_client())
    return _transcoder_service

@router.get("/health/cdn")
async def cdn_health_check(db: AsyncSession = Depends(get_db)):
    """CDN system health check"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "overall_score": 100
    }
    
    score_deductions = 0
    
    try:
        # Run all health checks concurrently
        check_tasks = [
            _check_database_connectivity(db),
            _check_r2_storage(),
            _check_transcoder_service(),
            _check_processing_queue(db),
            _check_worker_availability()
        ]
        
        check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # Process results
        check_names = [
            "database_connection",
            "r2_storage", 
            "transcoder_service",
            "processing_queue",
            "worker_availability"
        ]
        
        for i, result in enumerate(check_results):
            check_name = check_names[i]
            
            if isinstance(result, Exception):
                health_status["checks"][check_name] = {
                    "status": "unhealthy",
                    "error": str(result),
                    "score_impact": -30
                }
                score_deductions += 30
            else:
                health_status["checks"][check_name] = result
                if result["status"] == "unhealthy":
                    score_deductions += result.get("score_impact", 30)
                elif result["status"] == "degraded":
                    score_deductions += result.get("score_impact", 15)
        
        # Calculate overall status and score
        health_status["overall_score"] = max(0, 100 - score_deductions)
        
        if score_deductions >= 50:
            health_status["status"] = "unhealthy"
        elif score_deductions >= 20:
            health_status["status"] = "degraded"
        
        # Add system information
        health_status["system_info"] = {
            "version": "1.0.0",
            "environment": "production",
            "cdn_base_url": settings.CDN_BASE_URL,
            "bucket_name": settings.R2_BUCKET_NAME,
            "max_posts_per_profile": settings.IMG_MAX_POSTS_PER_PROFILE,
            "supported_formats": ["webp"],
            "supported_sizes": [256, 512]
        }
        
        logger.debug(f"🏥 CDN health check completed: {health_status['status']} (score: {health_status['overall_score']})")
        return health_status
        
    except Exception as e:
        logger.error(f"❌ CDN health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "overall_score": 0
        }

async def _check_database_connectivity(db: AsyncSession) -> Dict[str, Any]:
    """Check database connectivity and CDN tables"""
    try:
        # Test basic connectivity
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        
        # Check CDN tables exist
        tables_to_check = ['cdn_image_assets', 'cdn_image_jobs', 'cdn_processing_stats']
        table_results = {}
        
        for table in tables_to_check:
            try:
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                table_results[table] = {"exists": True, "count": count}
            except Exception as e:
                table_results[table] = {"exists": False, "error": str(e)}
        
        # Check for missing tables
        missing_tables = [t for t, r in table_results.items() if not r["exists"]]
        
        if missing_tables:
            return {
                "status": "unhealthy",
                "connectivity": True,
                "tables": table_results,
                "missing_tables": missing_tables,
                "error": f"Missing CDN tables: {missing_tables}",
                "score_impact": 40
            }
        
        return {
            "status": "healthy",
            "connectivity": True,
            "tables": table_results,
            "latency_ms": 0,  # Could measure actual latency
            "score_impact": 0
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "connectivity": False,
            "error": str(e),
            "score_impact": 40
        }

async def _check_r2_storage() -> Dict[str, Any]:
    """Check R2 storage connectivity and performance"""
    try:
        r2_client = get_r2_client()
        
        # Run comprehensive R2 health check
        health_result = await r2_client.health_check()
        
        # Get storage statistics
        storage_stats = r2_client.get_storage_stats()
        
        if health_result["status"] == "healthy":
            return {
                "status": "healthy",
                "bucket_accessible": health_result["bucket_accessible"],
                "upload_test": health_result["upload_test"],
                "download_test": health_result["download_test"],
                "latency_ms": health_result["latency_ms"],
                "storage_stats": {
                    "object_count": storage_stats.get("object_count", 0),
                    "total_size_gb": storage_stats.get("total_size_gb", 0),
                    "bucket_name": storage_stats.get("bucket_name")
                },
                "score_impact": 0
            }
        else:
            return {
                "status": "unhealthy" if health_result["status"] == "unhealthy" else "degraded",
                "error": health_result.get("error", "R2 health check failed"),
                "details": health_result,
                "score_impact": 35 if health_result["status"] == "unhealthy" else 15
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "score_impact": 35
        }

async def _check_transcoder_service() -> Dict[str, Any]:
    """Check image transcoder service health"""
    try:
        transcoder = get_transcoder_service()
        
        # Run transcoder health check
        health_result = await transcoder.health_check()
        
        # Get processing statistics
        processing_stats = transcoder.get_processing_stats()
        
        if health_result["status"] == "healthy":
            return {
                "status": "healthy",
                "http_client_ready": health_result["http_client_ready"],
                "pil_available": health_result["pil_available"],
                "processing_stats": {
                    "jobs_processed": processing_stats.get("jobs_processed", 0),
                    "success_rate": processing_stats.get("success_rate", 0),
                    "avg_processing_time_ms": processing_stats.get("avg_processing_time_ms", 0)
                },
                "score_impact": 0
            }
        else:
            return {
                "status": "unhealthy" if health_result["status"] == "unhealthy" else "degraded",
                "error": health_result.get("error", "Transcoder health check failed"),
                "details": health_result,
                "score_impact": 25 if health_result["status"] == "unhealthy" else 10
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "score_impact": 25
        }

async def _check_processing_queue(db: AsyncSession) -> Dict[str, Any]:
    """Check processing queue health"""
    try:
        from sqlalchemy import text
        
        # Get queue statistics
        queue_stats_sql = """
            SELECT 
                COUNT(CASE WHEN status = 'queued' THEN 1 END) as queued,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(*) as total
            FROM cdn_image_jobs
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """
        
        result = await db.execute(text(queue_stats_sql))
        stats = result.fetchone()
        
        queued = stats.queued or 0
        processing = stats.processing or 0
        failed = stats.failed or 0
        total = stats.total or 0
        
        # Determine status based on queue metrics
        if queued > 2000:
            status = "unhealthy"
            score_impact = 20
            message = "Queue severely backed up"
        elif queued > 1000:
            status = "degraded"
            score_impact = 10
            message = "Queue backed up"
        elif failed > total * 0.1 and total > 10:  # More than 10% failed
            status = "degraded"
            score_impact = 15
            message = "High failure rate"
        else:
            status = "healthy"
            score_impact = 0
            message = "Queue processing normally"
        
        return {
            "status": status,
            "queue_depth": queued,
            "jobs_processing": processing,
            "jobs_failed_24h": failed,
            "total_jobs_24h": total,
            "message": message,
            "score_impact": score_impact
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "score_impact": 20
        }

async def _check_worker_availability() -> Dict[str, Any]:
    """Check worker availability (simplified check)"""
    try:
        # This is a simplified check - in production you might check:
        # - Celery worker status
        # - Worker process health
        # - Recent job completion rates
        
        # For now, we assume workers are available if Redis is accessible
        import redis
        redis_client = redis.from_url(settings.REDIS_URL)
        
        # Test Redis connection
        redis_client.ping()
        
        # Check if there are active workers (simplified)
        # In production, you'd query Celery inspect APIs
        
        return {
            "status": "healthy",
            "redis_available": True,
            "estimated_workers": settings.INGEST_CONCURRENCY,
            "message": "Workers appear to be available",
            "score_impact": 0
        }
        
    except Exception as e:
        return {
            "status": "degraded",
            "redis_available": False,
            "error": str(e),
            "message": "Cannot verify worker status",
            "score_impact": 10
        }

@router.get("/health/cdn/detailed")
async def cdn_detailed_health_check(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Detailed CDN health check with comprehensive diagnostics (admin only)"""
    try:
        # Check if user has admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required for detailed health check"
            )
        
        logger.info("🏥 Running detailed CDN health check")
        
        # Run comprehensive diagnostics
        diagnostics = {
            "timestamp": datetime.utcnow().isoformat(),
            "system_overview": await _get_system_overview(db),
            "component_health": await _get_component_health_details(),
            "performance_metrics": await _get_performance_metrics(db),
            "error_analysis": await _get_error_analysis(db),
            "recommendations": []
        }
        
        # Generate recommendations based on health status
        diagnostics["recommendations"] = _generate_health_recommendations(diagnostics)
        
        logger.info("✅ Detailed health check completed")
        return diagnostics
        
    except Exception as e:
        logger.error(f"❌ Detailed health check failed: {e}")
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detailed health check failed"
        )

async def _get_system_overview(db: AsyncSession) -> Dict[str, Any]:
    """Get system overview statistics"""
    try:
        from sqlalchemy import text
        
        overview_sql = """
            SELECT 
                COUNT(DISTINCT a.source_id) as unique_profiles,
                COUNT(CASE WHEN a.source_type = 'profile_avatar' THEN 1 END) as avatar_assets,
                COUNT(CASE WHEN a.source_type = 'post_thumbnail' THEN 1 END) as post_assets,
                COUNT(CASE WHEN a.processing_status = 'completed' THEN 1 END) as completed_assets,
                COUNT(CASE WHEN a.processing_status = 'failed' THEN 1 END) as failed_assets,
                AVG(a.total_processing_time_ms) as avg_processing_time,
                SUM(a.file_size_256 + a.file_size_512) as total_bytes_stored
            FROM cdn_image_assets a
        """
        
        result = await db.execute(text(overview_sql))
        stats = result.fetchone()
        
        return {
            "unique_profiles_processed": stats.unique_profiles or 0,
            "avatar_assets": stats.avatar_assets or 0,
            "post_assets": stats.post_assets or 0,
            "completed_assets": stats.completed_assets or 0,
            "failed_assets": stats.failed_assets or 0,
            "avg_processing_time_ms": round(stats.avg_processing_time or 0, 2),
            "total_bytes_stored": stats.total_bytes_stored or 0,
            "completion_rate": round(
                (stats.completed_assets / (stats.completed_assets + stats.failed_assets) * 100)
                if (stats.completed_assets + stats.failed_assets) > 0 else 0, 1
            )
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get system overview: {e}")
        return {"error": str(e)}

async def _get_component_health_details() -> Dict[str, Any]:
    """Get detailed component health information"""
    try:
        # Get R2 client health
        r2_client = get_r2_client()
        r2_health = await r2_client.health_check()
        r2_stats = r2_client.get_storage_stats()
        
        # Get transcoder health
        transcoder = get_transcoder_service()
        transcoder_health = await transcoder.health_check()
        transcoder_stats = transcoder.get_processing_stats()
        
        return {
            "r2_storage": {
                "health": r2_health,
                "statistics": r2_stats
            },
            "image_transcoder": {
                "health": transcoder_health,
                "statistics": transcoder_stats
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get component health: {e}")
        return {"error": str(e)}

async def _get_performance_metrics(db: AsyncSession) -> Dict[str, Any]:
    """Get performance metrics"""
    try:
        from sqlalchemy import text
        
        # Get recent performance data
        perf_sql = """
            SELECT 
                DATE_TRUNC('hour', created_at) as hour,
                COUNT(*) as jobs_completed,
                AVG(processing_duration_ms) as avg_duration,
                MIN(processing_duration_ms) as min_duration,
                MAX(processing_duration_ms) as max_duration
            FROM cdn_image_jobs 
            WHERE status = 'completed' 
            AND created_at > NOW() - INTERVAL '24 hours'
            GROUP BY DATE_TRUNC('hour', created_at)
            ORDER BY hour DESC
        """
        
        result = await db.execute(text(perf_sql))
        hourly_stats = [
            {
                "hour": row.hour.isoformat(),
                "jobs_completed": row.jobs_completed,
                "avg_duration_ms": round(row.avg_duration or 0, 2),
                "min_duration_ms": row.min_duration or 0,
                "max_duration_ms": row.max_duration or 0
            }
            for row in result.fetchall()
        ]
        
        return {
            "hourly_performance": hourly_stats,
            "performance_summary": {
                "total_hours": len(hourly_stats),
                "avg_jobs_per_hour": sum(h["jobs_completed"] for h in hourly_stats) / len(hourly_stats) if hourly_stats else 0,
                "avg_processing_time_ms": sum(h["avg_duration_ms"] for h in hourly_stats) / len(hourly_stats) if hourly_stats else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get performance metrics: {e}")
        return {"error": str(e)}

async def _get_error_analysis(db: AsyncSession) -> Dict[str, Any]:
    """Get error analysis and patterns"""
    try:
        from sqlalchemy import text
        
        # Get common error patterns
        error_sql = """
            SELECT 
                error_message,
                COUNT(*) as occurrence_count,
                MAX(completed_at) as last_occurred
            FROM cdn_image_jobs 
            WHERE status = 'failed' 
            AND completed_at > NOW() - INTERVAL '7 days'
            AND error_message IS NOT NULL
            GROUP BY error_message
            ORDER BY occurrence_count DESC
            LIMIT 10
        """
        
        result = await db.execute(text(error_sql))
        common_errors = [
            {
                "error_message": row.error_message,
                "occurrence_count": row.occurrence_count,
                "last_occurred": row.last_occurred.isoformat() if row.last_occurred else None
            }
            for row in result.fetchall()
        ]
        
        return {
            "common_errors": common_errors,
            "error_summary": {
                "unique_error_types": len(common_errors),
                "total_errors_7d": sum(e["occurrence_count"] for e in common_errors)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get error analysis: {e}")
        return {"error": str(e)}

def _generate_health_recommendations(diagnostics: Dict[str, Any]) -> List[str]:
    """Generate health recommendations based on diagnostics"""
    recommendations = []
    
    try:
        # Check system overview
        system_overview = diagnostics.get("system_overview", {})
        completion_rate = system_overview.get("completion_rate", 100)
        
        if completion_rate < 95:
            recommendations.append(
                f"Low completion rate ({completion_rate}%) - investigate common failure patterns"
            )
        
        # Check performance metrics
        performance = diagnostics.get("performance_metrics", {}).get("performance_summary", {})
        avg_processing_time = performance.get("avg_processing_time_ms", 0)
        
        if avg_processing_time > 5000:  # 5 seconds
            recommendations.append(
                f"High average processing time ({avg_processing_time}ms) - consider optimizing image processing"
            )
        
        # Check error patterns
        error_analysis = diagnostics.get("error_analysis", {})
        total_errors = error_analysis.get("error_summary", {}).get("total_errors_7d", 0)
        
        if total_errors > 100:
            recommendations.append(
                f"High error count ({total_errors} in 7 days) - review error patterns and implement fixes"
            )
        
        # Check component health
        r2_health = diagnostics.get("component_health", {}).get("r2_storage", {}).get("health", {})
        if r2_health.get("status") != "healthy":
            recommendations.append("R2 storage issues detected - check connectivity and permissions")
        
        # Default recommendation if all is well
        if not recommendations:
            recommendations.append("System is operating within normal parameters")
        
    except Exception as e:
        logger.error(f"❌ Failed to generate recommendations: {e}")
        recommendations.append("Unable to generate recommendations due to analysis error")
    
    return recommendations