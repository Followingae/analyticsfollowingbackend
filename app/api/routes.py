from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from app.core.config import settings
from app.models.instagram import ProfileAnalysisResponse
from app.scrapers.smartproxy_client import SmartProxyClient, SmartProxyAPIError
from app.scrapers.instagram_analyzer import InstagramAnalyzer
from app.scrapers.inhouse_scraper import InHouseInstagramScraper

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/instagram/profile/{username}", response_model=ProfileAnalysisResponse)
async def analyze_instagram_profile(
    username: str,
    detailed: bool = Query(True, description="Include detailed post analysis")
):
    """
    Comprehensive Instagram profile analysis using SmartProxy
    
    - **username**: Instagram username (without @)
    - **detailed**: Include detailed post and hashtag analysis
    """
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="SmartProxy credentials not configured"
        )
    
    try:
        async with SmartProxyClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            analyzer = InstagramAnalyzer(client)
            analysis = await analyzer.analyze_profile_comprehensive(username)
            
            return analysis
            
    except SmartProxyAPIError as e:
        logger.error(f"SmartProxy API error for user {username}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error analyzing {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Analysis failed")


@router.get("/instagram/profile/{username}/basic")
async def get_basic_profile_info(username: str):
    """
    Get basic Instagram profile information without detailed analysis
    """
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="SmartProxy credentials not configured"
        )
    
    try:
        async with SmartProxyClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            analyzer = InstagramAnalyzer(client)
            
            # Get profile data only
            profile_raw = await client.scrape_instagram_profile(username)
            profile = analyzer._parse_profile_data(profile_raw)
            
            return {"profile": profile}
            
    except SmartProxyAPIError as e:
        logger.error(f"SmartProxy API error for user {username}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting basic info for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get profile info")


@router.get("/instagram/hashtag/{hashtag}")
async def analyze_hashtag(hashtag: str):
    """
    Analyze Instagram hashtag performance and metrics
    """
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="SmartProxy credentials not configured"
        )
    
    try:
        # Remove # if provided
        hashtag = hashtag.lstrip('#')
        
        async with SmartProxyClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            hashtag_raw = await client.scrape_hashtag_data(hashtag)
            
            # Basic hashtag info extraction (simplified)
            results = hashtag_raw.get('results', [])
            if not results:
                raise HTTPException(status_code=404, detail="Hashtag not found")
            
            hashtag_data = results[0].get('content', {})
            
            return {
                "hashtag": hashtag,
                "data": hashtag_data,
                "analysis_timestamp": "2024-01-01T00:00:00Z"  # Placeholder
            }
            
    except SmartProxyAPIError as e:
        logger.error(f"SmartProxy API error for hashtag {hashtag}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error analyzing hashtag {hashtag}: {str(e)}")
        raise HTTPException(status_code=500, detail="Hashtag analysis failed")


@router.get("/health")
async def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "message": "Analytics Following Backend is running",
        "smartproxy_configured": bool(settings.SMARTPROXY_USERNAME and settings.SMARTPROXY_PASSWORD)
    }


@router.get("/test-connection")
async def test_smartproxy_connection():
    """Test SmartProxy API connection"""
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="SmartProxy credentials not configured"
        )
    
    try:
        async with SmartProxyClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            # Test with a simple call
            result = await client.scrape_instagram_profile("instagram")
            
            return {
                "status": "success",
                "message": "SmartProxy connection working",
                "response_type": type(result).__name__,
                "has_data": bool(result)
            }
            
    except SmartProxyAPIError as e:
        logger.error(f"SmartProxy connection test failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Connection test failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in connection test: {str(e)}")
        raise HTTPException(status_code=500, detail="Connection test failed")


# NEW IN-HOUSE SCRAPER ENDPOINTS

@router.get("/inhouse/instagram/profile/{username}", response_model=ProfileAnalysisResponse)
async def analyze_instagram_profile_inhouse(
    username: str,
    detailed: bool = Query(True, description="Include detailed analysis")
):
    """
    In-house Instagram profile analysis using web scraping
    
    - **username**: Instagram username (without @)
    - **detailed**: Include detailed analysis (currently basic only)
    """
    
    try:
        async with InHouseInstagramScraper() as scraper:
            analysis = await scraper.analyze_profile_comprehensive(username)
            return analysis
            
    except Exception as e:
        logger.error(f"In-house scraper error for user {username}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inhouse/instagram/profile/{username}/basic")
async def get_basic_profile_info_inhouse(username: str):
    """
    Get basic Instagram profile information using in-house scraper
    """
    
    try:
        async with InHouseInstagramScraper() as scraper:
            raw_data = await scraper.scrape_profile(username)
            profile = scraper._parse_profile_data(raw_data, username)
            
            return {"profile": profile}
            
    except Exception as e:
        logger.error(f"In-house basic scraper error for user {username}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inhouse/test")
async def test_inhouse_scraper():
    """Test in-house scraper functionality"""
    
    try:
        async with InHouseInstagramScraper() as scraper:
            # Test with Instagram's official account
            result = await scraper.scrape_profile("instagram")
            
            return {
                "status": "success",
                "message": "In-house scraper working",
                "data_keys": list(result.keys()) if result else [],
                "has_username": bool(result.get('username')),
                "has_followers": bool(result.get('followers') or result.get('edge_followed_by'))
            }
            
    except Exception as e:
        logger.error(f"In-house scraper test failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Test failed: {str(e)}")