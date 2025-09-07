import asyncio
import logging
import json
import base64
import random
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from app.core.config import settings
from app.models.instagram import InstagramProfile, ProfileAnalysisResponse

logger = logging.getLogger(__name__)

class DecodoAPIError(Exception):
    """Custom exception for Decodo API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class DecodoInstabilityError(DecodoAPIError):
    """Exception for temporary Decodo API issues that should be retried"""
    pass

class DecodoProfileNotFoundError(DecodoAPIError):
    """Exception for non-existent profiles that should NOT be retried"""
    pass

class EnhancedDecodoClient:
    """Enhanced Decodo client with robust retry mechanism and comprehensive data extraction"""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://scraper-api.decodo.com/v2"
        self.session: Optional[httpx.AsyncClient] = None
        
        # Retry configuration - optimized for Decodo instagram_graphql_profile instability
        self.max_retries = 3  # Increased based on Decodo tech team feedback
        self.initial_wait = 2  # seconds
        self.max_wait = 20     # seconds - allow more time between retries
        self.backoff_multiplier = 1.5
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Enhanced HTTP client with DNS resolution resilience (compatible version)
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=15.0),  # Separate connect timeout for DNS
            limits=httpx.Limits(max_connections=settings.MAX_CONCURRENT_REQUESTS),
            # Enable HTTP/2 for better connection reuse and stability
            http2=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.aclose()
    
    def _get_auth_header(self) -> str:
        """Generate basic auth header"""
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"
    
    async def _make_request_smart_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Smart retry that detects non-existent profiles and fails fast"""
        username = payload.get('query', 'unknown')
        empty_content_count = 0
        last_exception = None
        
        for attempt in range(5):  # Max 5 attempts
            try:
                return await self._make_request_with_retry(payload)
            except DecodoInstabilityError as e:
                last_exception = e
                if "Empty content received" in str(e):
                    empty_content_count += 1
                    logger.warning(f"Empty content attempt {empty_content_count}/5 for {username}")
                    
                    # If we get empty content 3 times in a row, likely profile doesn't exist
                    if empty_content_count >= 3:
                        logger.error(f"Profile {username} likely doesn't exist - got empty content {empty_content_count} times")
                        raise DecodoProfileNotFoundError(f"Profile '{username}' not found on Instagram") from e
                else:
                    # Reset counter for non-empty-content errors
                    empty_content_count = 0
                    
                # Continue retrying for other types of instability errors
                if attempt < 4:  # Don't wait after last attempt
                    wait_time = min(2 * (1.5 ** attempt), 15)
                    logger.warning(f"Retrying {username} in {wait_time}s (attempt {attempt + 1}/5)")
                    await asyncio.sleep(wait_time)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError) as e:
                last_exception = e
                # Enhanced network error handling including DNS resolution failures
                error_msg = str(e).lower()
                if 'getaddrinfo failed' in error_msg or 'name resolution' in error_msg:
                    logger.warning(f"DNS resolution failed for attempt {attempt + 1}: {e}")
                elif 'timeout' in error_msg:
                    logger.warning(f"Connection timeout for attempt {attempt + 1}: {e}")
                else:
                    logger.warning(f"Network error for attempt {attempt + 1}: {e}")
                
                # Network issues - reset empty content counter and retry with exponential backoff
                empty_content_count = 0
                if attempt < 4:
                    wait_time = min(3 * (2 ** attempt), 30)  # More aggressive backoff for network issues
                    logger.info(f"Retrying after network error in {wait_time}s...")
                    await asyncio.sleep(wait_time)
        
        # If we get here, all retries failed
        if empty_content_count >= 3:
            raise DecodoProfileNotFoundError(f"Profile '{username}' not found on Instagram") from last_exception
        else:
            raise last_exception

    @retry(
        stop=stop_after_attempt(5),  # Increased retries as Decodo tech team confirmed retrying is effective
        wait=wait_exponential(multiplier=1.5, min=2, max=15),  # More aggressive retry strategy
        retry=retry_if_exception_type((DecodoInstabilityError, httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.WARNING)
    )
    async def _make_request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request with automatic retry logic"""
        if not self.session:
            raise DecodoAPIError("Client session not initialized")
        
        headers = {
            "Accept": "application/json",
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json",
            "User-Agent": "Analytics-Backend/1.0"
        }
        
        logger.info(f"Making Decodo request: {payload.get('target', 'unknown')} for {payload.get('query', 'unknown')}")
        
        try:
            response = await self.session.post(
                f"{self.base_url}/scrape",
                json=payload,
                headers=headers
            )
            
            # Only log response details for errors
            if response.status_code != 200:
                logger.info(f"Decodo response status: {response.status_code}")
                try:
                    response_text = response.text
                    logger.info(f"Response body: {response_text[:500]}...")  # First 500 chars for errors
                except Exception:
                    pass
            
            # Handle different response statuses
            if response.status_code == 401:
                raise DecodoAPIError("Authentication failed - check Decodo credentials", 401)
            elif response.status_code == 429:
                # Rate limit - this should be retried
                logger.warning("Rate limit hit, will retry...")
                raise DecodoInstabilityError("Rate limit exceeded", 429)
            elif response.status_code == 500:
                # Server error - might be temporary
                logger.warning("Server error, will retry...")
                raise DecodoInstabilityError("Decodo server error", 500)
            elif response.status_code != 200:
                response_text = response.text
                logger.error(f"API request failed with status {response.status_code}: {response_text}")
                raise DecodoAPIError(f"API request failed: {response.status_code} - {response_text}", response.status_code)
            
            # Parse JSON response
            try:
                response_data = response.json()
                
                # Check for API-level errors in the response
                if isinstance(response_data, dict):
                    # Handle different response formats
                    if 'status' in response_data and 'task_id' in response_data:
                        # This is an error/processing status response, not actual data
                        status = response_data.get('status', '')
                        message = response_data.get('message', '')
                        
                        if status.lower() in ['error', 'failed', 'pending']:
                            logger.warning(f"Decodo returned status response, will retry: {status} - {message}")
                            raise DecodoInstabilityError(f"Decodo processing status: {status} - {message}")
                    
                    # Check for error messages that indicate configuration issues
                    if 'results' not in response_data or not response_data.get('results'):
                        # Check for specific error messages
                        error_msg = response_data.get('message', '')
                        status = response_data.get('status', '')
                        
                        if 'failed' in error_msg.lower() or 'error' in status.lower():
                            raise DecodoInstabilityError(f"Decodo API error: {error_msg}")
                    
                    # Check if results contain actual data
                    results = response_data.get('results', [])
                    if results and len(results) > 0:
                        content = results[0].get('content', {})
                        if not content or 'data' not in content:
                            raise DecodoInstabilityError("Empty content received from Decodo")
                
                return response_data
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                raise DecodoAPIError(f"Invalid JSON response: {str(e)}")
                
        except httpx.TimeoutException as e:
            logger.warning(f"Request timeout: {str(e)}")
            raise DecodoInstabilityError("Request timeout - will retry")
        except httpx.ConnectError as e:
            error_msg = str(e).lower()
            if 'getaddrinfo failed' in error_msg or 'name resolution' in error_msg:
                logger.warning(f"DNS resolution failure: {str(e)}")
                raise DecodoInstabilityError(f"DNS resolution error: {str(e)}")
            else:
                logger.warning(f"Connection error: {str(e)}")
                raise DecodoInstabilityError(f"Connection error: {str(e)}")
        except httpx.NetworkError as e:
            logger.warning(f"Network error: {str(e)}")
            raise DecodoInstabilityError(f"Network error: {str(e)}")
        except OSError as e:
            # Catch socket-level errors including getaddrinfo failures
            error_msg = str(e).lower()
            if 'getaddrinfo failed' in error_msg or 'name resolution' in error_msg:
                logger.warning(f"DNS/Socket error: {str(e)}")
                raise DecodoInstabilityError(f"DNS resolution error: {str(e)}")
            else:
                logger.warning(f"Socket error: {str(e)}")
                raise DecodoInstabilityError(f"Socket error: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {str(e)}")
            raise DecodoAPIError(f"Request error: {str(e)}")
    
    async def get_instagram_profile_basic(self, username: str) -> Dict[str, Any]:
        """Get basic Instagram profile data for Phase 1 search (lightweight request)"""
        
        # Use simple configuration for fast basic data retrieval
        basic_config = {
            "url": f"https://www.instagram.com/{username}/",
            "method": "GET",
            "render_javascript": False,  # Faster without JS rendering
            "response_format": "json",
            "include_headers": False,
            "timeout": 10,  # Shorter timeout for basic requests
            "country": "US"
        }
        
        payload = {
            "target": "instagram_graphql_profile",
            "query": username,
            "settings": {
                "include_posts": True,
                "posts_count": 12,
                "include_related": False,
                "timeout": 30000  # 30 seconds for basic profile
            }
        }
        
        try:
            logger.info(f"Fetching BASIC profile data for {username}")
            response_data = await self._make_request_smart_retry(payload)
            logger.info(f"Successfully fetched basic profile data for {username}")
            return response_data
            
        except DecodoProfileNotFoundError:
            logger.warning(f"Profile {username} not found (basic search)")
            raise
        except Exception as e:
            logger.error(f"Basic profile fetch failed for {username}: {str(e)}")
            raise DecodoAPIError(f"Basic profile fetch failed: {str(e)}")
    
    async def get_instagram_profile_comprehensive(self, username: str) -> Dict[str, Any]:
        """Get comprehensive Instagram profile data with posts and analytics"""
        
        # Comprehensive configuration for complete data extraction
        payload = {
            "target": "instagram_graphql_profile",
            "query": username,
            "settings": {
                "include_posts": True,
                "posts_count": 50,  # More posts for comprehensive analysis
                "include_related": True,
                "related_count": 20,
                "include_highlights": True,
                "include_igtv": True,
                "include_reels": True,
                "timeout": 45000  # Longer timeout for comprehensive data
            }
        }
        
        try:
            logger.info(f"Fetching COMPREHENSIVE profile data for {username}")
            response_data = await self._make_request_smart_retry(payload)
            logger.info(f"Successfully fetched comprehensive profile data for {username}")
            return response_data
            
        except DecodoProfileNotFoundError:
            logger.warning(f"Profile {username} not found (comprehensive search)")
            raise
        except Exception as e:
            logger.error(f"Comprehensive profile fetch failed for {username}: {str(e)}")
            raise DecodoAPIError(f"Comprehensive profile fetch failed: {str(e)}")

    async def get_instagram_posts_only(self, username: str, count: int = 24) -> Dict[str, Any]:
        """Get only posts data for existing profiles (faster than full profile fetch)"""
        
        payload = {
            "target": "instagram_graphql_profile", 
            "query": username,
            "settings": {
                "include_posts": True,
                "posts_count": count,
                "include_related": False,  # Skip related profiles for speed
                "include_highlights": False,
                "timeout": 30000
            }
        }
        
        try:
            logger.info(f"Fetching posts only for {username} (count: {count})")
            response_data = await self._make_request_smart_retry(payload)
            logger.info(f"Successfully fetched {count} posts for {username}")
            return response_data
            
        except DecodoProfileNotFoundError:
            logger.warning(f"Profile {username} not found (posts only)")
            raise
        except Exception as e:
            logger.error(f"Posts fetch failed for {username}: {str(e)}")
            raise DecodoAPIError(f"Posts fetch failed: {str(e)}")