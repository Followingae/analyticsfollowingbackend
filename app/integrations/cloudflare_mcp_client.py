"""
Cloudflare MCP Client Integration
Direct integration with Cloudflare APIs for MCP-style functionality
"""

import os
import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CloudflareMCPClient:
    """
    Cloudflare MCP Client for Analytics Following Backend
    Provides MCP-style integration with Cloudflare services
    """
    
    def __init__(self, api_token: str, account_id: str, zone_id: Optional[str] = None):
        self.api_token = api_token
        self.account_id = account_id
        self.zone_id = zone_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to Cloudflare API"""
        url = f"{self.base_url}/{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=self.headers, **kwargs) as response:
                data = await response.json()
                
                if not data.get('success'):
                    raise Exception(f"Cloudflare API error: {data.get('errors')}")
                
                return data.get('result', {})
    
    # Workers Management
    async def list_workers(self) -> List[Dict[str, Any]]:
        """List all Cloudflare Workers"""
        try:
            result = await self._make_request('GET', f'accounts/{self.account_id}/workers/scripts')
            logger.info(f"Found {len(result)} workers")
            return result
        except Exception as e:
            logger.error(f"Failed to list workers: {e}")
            return []
    
    async def get_worker_analytics(self, script_name: str, days: int = 7) -> Dict[str, Any]:
        """Get analytics for a specific worker"""
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'
            until = datetime.now().isoformat() + 'Z'
            
            endpoint = f'accounts/{self.account_id}/workers/scripts/{script_name}/usage-model'
            result = await self._make_request('GET', endpoint, params={
                'since': since,
                'until': until
            })
            
            logger.info(f"Retrieved analytics for worker: {script_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to get worker analytics: {e}")
            return {}
    
    # CDN & Performance Management
    async def get_zone_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get zone analytics and performance metrics"""
        if not self.zone_id:
            logger.warning("Zone ID not provided, skipping zone analytics")
            return {}
        
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'
            until = datetime.now().isoformat() + 'Z'
            
            endpoint = f'zones/{self.zone_id}/analytics/dashboard'
            result = await self._make_request('GET', endpoint, params={
                'since': since,
                'until': until,
                'continuous': 'true'
            })
            
            logger.info("Retrieved zone analytics")
            return result
        except Exception as e:
            logger.error(f"Failed to get zone analytics: {e}")
            return {}
    
    async def get_cache_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get cache performance analytics"""
        if not self.zone_id:
            return {}
        
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'
            until = datetime.now().isoformat() + 'Z'
            
            endpoint = f'zones/{self.zone_id}/analytics/colos'
            result = await self._make_request('GET', endpoint, params={
                'since': since,
                'until': until
            })
            
            logger.info("Retrieved cache analytics")
            return result
        except Exception as e:
            logger.error(f"Failed to get cache analytics: {e}")
            return {}
    
    # AI Gateway Management
    async def list_ai_gateways(self) -> List[Dict[str, Any]]:
        """List AI Gateway applications"""
        try:
            endpoint = f'accounts/{self.account_id}/ai-gateway/gateways'
            result = await self._make_request('GET', endpoint)
            
            if isinstance(result, list):
                logger.info(f"Found {len(result)} AI gateways")
                return result
            else:
                logger.info("No AI gateways found")
                return []
        except Exception as e:
            logger.error(f"Failed to list AI gateways: {e}")
            return []
    
    async def get_ai_gateway_analytics(self, gateway_id: str, days: int = 7) -> Dict[str, Any]:
        """Get AI Gateway analytics"""
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'
            until = datetime.now().isoformat() + 'Z'
            
            endpoint = f'accounts/{self.account_id}/ai-gateway/gateways/{gateway_id}/logs'
            result = await self._make_request('GET', endpoint, params={
                'since': since,
                'until': until
            })
            
            logger.info(f"Retrieved AI gateway analytics for: {gateway_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to get AI gateway analytics: {e}")
            return {}
    
    # R2 Storage Management
    async def list_r2_buckets(self) -> List[Dict[str, Any]]:
        """List R2 storage buckets"""
        try:
            endpoint = f'accounts/{self.account_id}/r2/buckets'
            result = await self._make_request('GET', endpoint)
            
            buckets = result.get('buckets', [])
            logger.info(f"Found {len(buckets)} R2 buckets")
            return buckets
        except Exception as e:
            logger.error(f"Failed to list R2 buckets: {e}")
            return []
    
    async def get_r2_bucket_usage(self, bucket_name: str) -> Dict[str, Any]:
        """Get R2 bucket usage statistics"""
        try:
            endpoint = f'accounts/{self.account_id}/r2/buckets/{bucket_name}/usage'
            result = await self._make_request('GET', endpoint)
            
            logger.info(f"Retrieved usage for R2 bucket: {bucket_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to get R2 bucket usage: {e}")
            return {}
    
    # Page Rules and Caching
    async def list_page_rules(self) -> List[Dict[str, Any]]:
        """List page rules for the zone"""
        if not self.zone_id:
            return []
        
        try:
            endpoint = f'zones/{self.zone_id}/pagerules'
            result = await self._make_request('GET', endpoint)
            
            logger.info(f"Found {len(result)} page rules")
            return result
        except Exception as e:
            logger.error(f"Failed to list page rules: {e}")
            return []
    
    async def create_cache_rule(self, url_pattern: str, cache_level: str = "cache_everything") -> Dict[str, Any]:
        """Create a new cache rule"""
        if not self.zone_id:
            raise ValueError("Zone ID required for cache rule creation")
        
        try:
            endpoint = f'zones/{self.zone_id}/pagerules'
            data = {
                "targets": [
                    {
                        "target": "url",
                        "constraint": {
                            "operator": "matches",
                            "value": url_pattern
                        }
                    }
                ],
                "actions": [
                    {
                        "id": "cache_level",
                        "value": cache_level
                    }
                ],
                "status": "active"
            }
            
            result = await self._make_request('POST', endpoint, json=data)
            
            logger.info(f"Created cache rule for: {url_pattern}")
            return result
        except Exception as e:
            logger.error(f"Failed to create cache rule: {e}")
            return {}
    
    # Comprehensive Dashboard
    async def get_comprehensive_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive Cloudflare dashboard data"""
        logger.info("Fetching comprehensive Cloudflare dashboard...")
        
        dashboard_data = {
            'account_id': self.account_id,
            'zone_id': self.zone_id,
            'timestamp': datetime.now().isoformat(),
            'workers': [],
            'zone_analytics': {},
            'cache_analytics': {},
            'ai_gateways': [],
            'r2_buckets': [],
            'page_rules': []
        }
        
        # Fetch all data concurrently
        tasks = [
            self.list_workers(),
            self.get_zone_analytics(),
            self.get_cache_analytics(),
            self.list_ai_gateways(),
            self.list_r2_buckets(),
            self.list_page_rules()
        ]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            dashboard_data['workers'] = results[0] if not isinstance(results[0], Exception) else []
            dashboard_data['zone_analytics'] = results[1] if not isinstance(results[1], Exception) else {}
            dashboard_data['cache_analytics'] = results[2] if not isinstance(results[2], Exception) else {}
            dashboard_data['ai_gateways'] = results[3] if not isinstance(results[3], Exception) else []
            dashboard_data['r2_buckets'] = results[4] if not isinstance(results[4], Exception) else []
            dashboard_data['page_rules'] = results[5] if not isinstance(results[5], Exception) else []
            
        except Exception as e:
            logger.error(f"Error fetching dashboard data: {e}")
        
        return dashboard_data

# Factory function for easy initialization
def create_cloudflare_client() -> CloudflareMCPClient:
    """Create Cloudflare MCP client from environment variables"""
    api_token = os.getenv('CF_MCP_API_TOKEN')
    account_id = os.getenv('CF_ACCOUNT_ID')
    zone_id = os.getenv('CF_ZONE_ID')
    
    if not api_token or not account_id:
        raise ValueError("Missing required Cloudflare credentials in environment variables")
    
    return CloudflareMCPClient(api_token, account_id, zone_id)

# Async context manager for easy usage
class CloudflareMCPContext:
    """Context manager for Cloudflare MCP client"""
    
    def __init__(self):
        self.client = None
    
    async def __aenter__(self):
        self.client = create_cloudflare_client()
        return self.client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup if needed
        pass