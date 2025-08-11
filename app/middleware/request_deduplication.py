"""
Request Deduplication Middleware - Prevents redundant simultaneous requests
Handles multiple identical requests by returning cached responses and preventing API abuse
"""
import logging
import asyncio
import hashlib
import json
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import weakref

logger = logging.getLogger(__name__)

class RequestDeduplicationMiddleware:
    """
    Middleware that prevents redundant simultaneous requests to expensive endpoints
    Uses in-memory tracking with automatic cleanup
    """
    
    def __init__(self):
        # Track active requests by request signature
        self.active_requests: Dict[str, asyncio.Future] = {}
        
        # Track request metadata for monitoring
        self.request_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Cleanup old entries periodically
        self.last_cleanup = datetime.now(timezone.utc)
        self.cleanup_interval = timedelta(minutes=5)
        
        # Configure which endpoints to deduplicate
        self.DEDUPLICATED_ENDPOINTS = {
            "/api/v1/instagram/profile/": {
                "method": "GET",
                "ttl_seconds": 300,  # 5 minutes
                "include_user": True  # Include user ID in deduplication key
            },
            "/api/v1/instagram/profile/{username}/analytics": {
                "method": "GET", 
                "ttl_seconds": 180,  # 3 minutes
                "include_user": True
            },
            "/api/v1/instagram/profile/{username}/posts": {
                "method": "GET",
                "ttl_seconds": 120,  # 2 minutes
                "include_user": False,  # Posts data is the same for all users
                "include_params": ["limit", "offset"]  # Include specific query params
            },
            "/api/v1/instagram/profile/{username}/refresh": {
                "method": "POST",
                "ttl_seconds": 600,  # 10 minutes - longer for expensive refresh operations
                "include_user": True
            }
        }
    
    def _generate_request_key(self, request: Request, endpoint_config: Dict[str, Any]) -> str:
        """Generate unique key for request deduplication"""
        key_components = [
            request.method,
            str(request.url.path)
        ]
        
        # Include user ID if configured
        if endpoint_config.get("include_user") and hasattr(request.state, "current_user"):
            user_id = getattr(request.state.current_user, "id", "anonymous")
            key_components.append(f"user:{user_id}")
        
        # Include specific query parameters if configured
        if endpoint_config.get("include_params"):
            params = {}
            for param in endpoint_config["include_params"]:
                value = request.query_params.get(param)
                if value is not None:
                    params[param] = value
            
            if params:
                params_str = json.dumps(params, sort_keys=True)
                key_components.append(f"params:{params_str}")
        
        # Include request body for POST requests
        if request.method == "POST" and hasattr(request.state, "body_hash"):
            key_components.append(f"body:{request.state.body_hash}")
        
        # Create hash of all components
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _should_deduplicate_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Check if request should be deduplicated"""
        path = request.url.path
        method = request.method
        
        # Check exact path matches first
        for endpoint_pattern, config in self.DEDUPLICATED_ENDPOINTS.items():
            if config["method"] != method:
                continue
            
            # Handle exact matches
            if path == endpoint_pattern:
                return config
            
            # Handle parameterized paths (simple pattern matching)
            if "{" in endpoint_pattern:
                # Convert pattern to regex-like matching
                pattern_parts = endpoint_pattern.split("/")
                path_parts = path.split("/")
                
                if len(pattern_parts) == len(path_parts):
                    match = True
                    for pattern_part, path_part in zip(pattern_parts, path_parts):
                        if pattern_part.startswith("{") and pattern_part.endswith("}"):
                            # This is a parameter, it matches anything
                            continue
                        elif pattern_part != path_part:
                            match = False
                            break
                    
                    if match:
                        return config
        
        return None
    
    def _cleanup_old_requests(self):
        """Clean up completed and expired requests"""
        try:
            current_time = datetime.now(timezone.utc)
            
            if current_time - self.last_cleanup < self.cleanup_interval:
                return
            
            # Clean up completed requests
            completed_keys = []
            for request_key, future in self.active_requests.items():
                if future.done():
                    completed_keys.append(request_key)
            
            for key in completed_keys:
                self.active_requests.pop(key, None)
                self.request_metadata.pop(key, None)
            
            # Clean up old metadata
            old_metadata_keys = []
            for key, metadata in self.request_metadata.items():
                if current_time - metadata["started_at"] > timedelta(hours=1):
                    old_metadata_keys.append(key)
            
            for key in old_metadata_keys:
                self.request_metadata.pop(key, None)
            
            self.last_cleanup = current_time
            
            if completed_keys or old_metadata_keys:
                logger.debug(f"Cleaned up {len(completed_keys)} active requests and {len(old_metadata_keys)} old metadata entries")
                
        except Exception as e:
            logger.error(f"Error during request deduplication cleanup: {e}")
    
    async def __call__(self, request: Request, call_next):
        """Main middleware function"""
        # Clean up old requests periodically
        self._cleanup_old_requests()
        
        # Check if this request should be deduplicated
        endpoint_config = self._should_deduplicate_request(request)
        
        if not endpoint_config:
            # Not a deduplicated endpoint, proceed normally
            return await call_next(request)
        
        # Generate request key for deduplication
        request_key = self._generate_request_key(request, endpoint_config)
        
        # Check if same request is already in progress
        if request_key in self.active_requests:
            existing_future = self.active_requests[request_key]
            
            if not existing_future.done():
                logger.info(f"Deduplicating request: {request.url.path} (key: {request_key[:12]}...)")
                
                # Update metadata
                if request_key in self.request_metadata:
                    self.request_metadata[request_key]["duplicate_count"] += 1
                
                try:
                    # Wait for the existing request to complete
                    response_data = await existing_future
                    
                    # Return the cached response
                    return JSONResponse(
                        content=response_data["content"],
                        status_code=response_data["status_code"],
                        headers={
                            **response_data.get("headers", {}),
                            "X-Request-Deduplicated": "true",
                            "X-Original-Request-Time": self.request_metadata[request_key]["started_at"].isoformat()
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error waiting for deduplicated request: {e}")
                    # If the original request failed, process this one normally
        
        # Create future for this request
        future = asyncio.Future()
        self.active_requests[request_key] = future
        
        # Track metadata
        self.request_metadata[request_key] = {
            "started_at": datetime.now(timezone.utc),
            "path": request.url.path,
            "method": request.method,
            "duplicate_count": 0,
            "endpoint_config": endpoint_config
        }
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Read response content for caching
            response_content = None
            response_headers = dict(response.headers)
            
            if hasattr(response, 'body'):
                try:
                    # For JSONResponse and similar
                    if isinstance(response, JSONResponse):
                        response_content = response.body.decode() if hasattr(response.body, 'decode') else response.body
                        if isinstance(response_content, str):
                            response_content = json.loads(response_content)
                    else:
                        # Read body for other response types
                        body = b""
                        async for chunk in response.body_iterator:
                            body += chunk
                        response_content = body.decode() if body else None
                        
                        # Recreate response with body
                        response = Response(
                            content=body,
                            status_code=response.status_code,
                            headers=response_headers
                        )
                        
                except Exception as e:
                    logger.warning(f"Failed to cache response content: {e}")
                    response_content = None
            
            # Cache the response for deduplication
            cached_response = {
                "content": response_content,
                "status_code": response.status_code,
                "headers": response_headers
            }
            
            # Set the future result
            if not future.done():
                future.set_result(cached_response)
            
            # Add headers to indicate this was the original request
            response.headers["X-Request-Original"] = "true"
            response.headers["X-Deduplication-Key"] = request_key[:12] + "..."
            
            if self.request_metadata[request_key]["duplicate_count"] > 0:
                response.headers["X-Duplicates-Prevented"] = str(self.request_metadata[request_key]["duplicate_count"])
            
            return response
            
        except Exception as e:
            # Handle errors by setting exception on future
            if not future.done():
                future.set_exception(e)
            
            # Clean up this request key
            self.active_requests.pop(request_key, None)
            self.request_metadata.pop(request_key, None)
            
            raise e
        
        finally:
            # Schedule cleanup of this request after TTL
            ttl = endpoint_config.get("ttl_seconds", 300)
            
            async def cleanup_after_ttl():
                await asyncio.sleep(ttl)
                self.active_requests.pop(request_key, None)
                # Keep metadata longer for monitoring
            
            asyncio.create_task(cleanup_after_ttl())
    
    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get statistics about request deduplication"""
        try:
            current_time = datetime.now(timezone.utc)
            
            stats = {
                "active_requests": len(self.active_requests),
                "total_tracked_requests": len(self.request_metadata),
                "deduplication_stats": {},
                "endpoint_config": self.DEDUPLICATED_ENDPOINTS,
                "last_cleanup": self.last_cleanup.isoformat(),
                "timestamp": current_time.isoformat()
            }
            
            # Calculate stats by endpoint
            endpoint_stats = {}
            total_duplicates_prevented = 0
            
            for request_key, metadata in self.request_metadata.items():
                path = metadata["path"]
                duplicates = metadata["duplicate_count"]
                
                if path not in endpoint_stats:
                    endpoint_stats[path] = {
                        "total_requests": 0,
                        "duplicates_prevented": 0,
                        "active_requests": 0
                    }
                
                endpoint_stats[path]["total_requests"] += 1
                endpoint_stats[path]["duplicates_prevented"] += duplicates
                total_duplicates_prevented += duplicates
                
                if request_key in self.active_requests and not self.active_requests[request_key].done():
                    endpoint_stats[path]["active_requests"] += 1
            
            stats["deduplication_stats"] = endpoint_stats
            stats["total_duplicates_prevented"] = total_duplicates_prevented
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting deduplication stats: {e}")
            return {"error": str(e)}

# Global middleware instance
request_deduplication_middleware = RequestDeduplicationMiddleware()