"""
Cloudflare MCP API Routes
FastAPI endpoints for Cloudflare MCP integration
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from app.integrations.cloudflare_mcp_client import CloudflareMCPContext, create_cloudflare_client
from app.middleware.role_based_auth import get_current_active_user

router = APIRouter(prefix="/api/v1/cloudflare", tags=["cloudflare-mcp"])
logger = logging.getLogger(__name__)

@router.get("/dashboard")
async def get_cloudflare_dashboard(
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get comprehensive Cloudflare dashboard data
    Includes Workers, CDN analytics, AI Gateway, R2 storage, and cache performance
    """
    try:
        async with CloudflareMCPContext() as client:
            dashboard = await client.get_comprehensive_dashboard()
            
            logger.info(f"Cloudflare dashboard accessed by user: {current_user.get('email', 'unknown')}")
            return {
                "success": True,
                "data": dashboard,
                "timestamp": datetime.now().isoformat()
            }
    
    except Exception as e:
        logger.error(f"Failed to get Cloudflare dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard: {str(e)}")

@router.get("/workers")
async def list_workers(
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """List all Cloudflare Workers"""
    try:
        async with CloudflareMCPContext() as client:
            workers = await client.list_workers()
            
            return {
                "success": True,
                "data": workers,
                "count": len(workers)
            }
    
    except Exception as e:
        logger.error(f"Failed to list workers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list workers: {str(e)}")

@router.get("/workers/{script_name}/analytics")
async def get_worker_analytics(
    script_name: str,
    days: int = 7,
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get analytics for a specific Cloudflare Worker"""
    try:
        async with CloudflareMCPContext() as client:
            analytics = await client.get_worker_analytics(script_name, days)
            
            return {
                "success": True,
                "data": analytics,
                "script_name": script_name,
                "days": days
            }
    
    except Exception as e:
        logger.error(f"Failed to get worker analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@router.get("/zone/analytics")
async def get_zone_analytics(
    days: int = 7,
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get zone analytics and performance metrics"""
    try:
        async with CloudflareMCPContext() as client:
            analytics = await client.get_zone_analytics(days)
            
            return {
                "success": True,
                "data": analytics,
                "days": days
            }
    
    except Exception as e:
        logger.error(f"Failed to get zone analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get zone analytics: {str(e)}")

@router.get("/cache/analytics")
async def get_cache_analytics(
    days: int = 7,
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get cache performance analytics"""
    try:
        async with CloudflareMCPContext() as client:
            analytics = await client.get_cache_analytics(days)
            
            return {
                "success": True,
                "data": analytics,
                "days": days
            }
    
    except Exception as e:
        logger.error(f"Failed to get cache analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache analytics: {str(e)}")

@router.get("/ai-gateway")
async def list_ai_gateways(
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """List all AI Gateway applications"""
    try:
        async with CloudflareMCPContext() as client:
            gateways = await client.list_ai_gateways()
            
            return {
                "success": True,
                "data": gateways,
                "count": len(gateways)
            }
    
    except Exception as e:
        logger.error(f"Failed to list AI gateways: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list AI gateways: {str(e)}")

@router.get("/ai-gateway/{gateway_id}/analytics")
async def get_ai_gateway_analytics(
    gateway_id: str,
    days: int = 7,
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get analytics for a specific AI Gateway"""
    try:
        async with CloudflareMCPContext() as client:
            analytics = await client.get_ai_gateway_analytics(gateway_id, days)
            
            return {
                "success": True,
                "data": analytics,
                "gateway_id": gateway_id,
                "days": days
            }
    
    except Exception as e:
        logger.error(f"Failed to get AI gateway analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI gateway analytics: {str(e)}")

@router.get("/r2/buckets")
async def list_r2_buckets(
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """List all R2 storage buckets"""
    try:
        async with CloudflareMCPContext() as client:
            buckets = await client.list_r2_buckets()
            
            return {
                "success": True,
                "data": buckets,
                "count": len(buckets)
            }
    
    except Exception as e:
        logger.error(f"Failed to list R2 buckets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list R2 buckets: {str(e)}")

@router.get("/r2/buckets/{bucket_name}/usage")
async def get_r2_bucket_usage(
    bucket_name: str,
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get R2 bucket usage statistics"""
    try:
        async with CloudflareMCPContext() as client:
            usage = await client.get_r2_bucket_usage(bucket_name)
            
            return {
                "success": True,
                "data": usage,
                "bucket_name": bucket_name
            }
    
    except Exception as e:
        logger.error(f"Failed to get R2 bucket usage: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get R2 bucket usage: {str(e)}")

@router.get("/page-rules")
async def list_page_rules(
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """List all page rules for the zone"""
    try:
        async with CloudflareMCPContext() as client:
            rules = await client.list_page_rules()
            
            return {
                "success": True,
                "data": rules,
                "count": len(rules)
            }
    
    except Exception as e:
        logger.error(f"Failed to list page rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list page rules: {str(e)}")

@router.post("/cache/rules")
async def create_cache_rule(
    url_pattern: str,
    cache_level: str = "cache_everything",
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Create a new cache rule"""
    try:
        async with CloudflareMCPContext() as client:
            rule = await client.create_cache_rule(url_pattern, cache_level)
            
            logger.info(f"Cache rule created by {current_user.get('email')}: {url_pattern}")
            return {
                "success": True,
                "data": rule,
                "url_pattern": url_pattern,
                "cache_level": cache_level
            }
    
    except Exception as e:
        logger.error(f"Failed to create cache rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create cache rule: {str(e)}")

@router.get("/health")
async def cloudflare_health_check() -> Dict[str, Any]:
    """Health check for Cloudflare MCP integration"""
    try:
        client = create_cloudflare_client()
        
        # Simple check - just verify client creation
        return {
            "success": True,
            "status": "healthy",
            "account_id": client.account_id[:8] + "...",  # Truncated for security
            "zone_id": client.zone_id[:8] + "..." if client.zone_id else None,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Cloudflare MCP health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# CDN-specific endpoints for your image processing
@router.get("/cdn/performance")
async def get_cdn_performance(
    days: int = 7,
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get CDN performance metrics specifically for image processing"""
    try:
        async with CloudflareMCPContext() as client:
            # Get both zone and cache analytics
            zone_analytics = await client.get_zone_analytics(days)
            cache_analytics = await client.get_cache_analytics(days)
            
            # Combine and focus on CDN metrics
            cdn_performance = {
                "zone_analytics": zone_analytics,
                "cache_analytics": cache_analytics,
                "period_days": days,
                "focus": "CDN performance for Instagram image processing"
            }
            
            return {
                "success": True,
                "data": cdn_performance,
                "optimized_for": "image_processing"
            }
    
    except Exception as e:
        logger.error(f"Failed to get CDN performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get CDN performance: {str(e)}")