import httpx
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
import base64
from app.core.config import settings
from app.models.instagram import SmartProxyRequest, SmartProxyResponse

logger = logging.getLogger(__name__)


class SmartProxyAPIError(Exception):
    pass


class SmartProxyClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = settings.SMARTPROXY_BASE_URL
        self.session: Optional[httpx.AsyncClient] = None
        self.auth_header = self._create_auth_header()
        
    def _create_auth_header(self) -> str:
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),  # Increased timeout to 2 minutes
            limits=httpx.Limits(max_connections=settings.MAX_CONCURRENT_REQUESTS)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.session:
            raise SmartProxyAPIError("Client session not initialized")
        
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json"
        }
        
        try:
            logger.debug(f"Making request to {self.base_url}/scrape with payload: {payload}")
            
            response = await self.session.post(
                f"{self.base_url}/scrape",
                json=payload,
                headers=headers
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code == 401:
                raise SmartProxyAPIError("Authentication failed - check credentials")
            elif response.status_code == 429:
                raise SmartProxyAPIError("Rate limit exceeded")
            elif response.status_code != 200:
                response_text = response.text
                logger.error(f"API request failed with status {response.status_code}: {response_text}")
                raise SmartProxyAPIError(f"API request failed: {response.status_code} - {response_text}")
            
            response_data = response.json()
            logger.debug(f"Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
            
            return response_data
            
        except httpx.TimeoutException:
            raise SmartProxyAPIError("Request timeout")
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {str(e)}")
            raise SmartProxyAPIError(f"Request error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise SmartProxyAPIError(f"Invalid JSON response: {str(e)}")
    
    async def scrape_instagram_profile(self, username: str) -> Dict[str, Any]:
        payload = {
            "target": "instagram_graphql_profile",
            "query": username
        }
        
        response = await self._make_request(payload)
        return response
    
    async def scrape_instagram_posts(self, username: str, count: int = 12) -> Dict[str, Any]:
        payload = {
            "target": "instagram_graphql_posts",
            "query": username,
            "limit": count
        }
        
        response = await self._make_request(payload)
        return response
    
    async def scrape_hashtag_data(self, hashtag: str) -> Dict[str, Any]:
        payload = {
            "target": "instagram_graphql_hashtag",
            "query": hashtag
        }
        
        response = await self._make_request(payload)
        return response