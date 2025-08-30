from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import time
import logging
from typing import Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)

class FrontendHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add helpful headers for frontend integration
    """
    
    def __init__(self, app):
        super().__init__(app)
        self._request_times: Dict[str, List[float]] = defaultdict(list)
        self._rate_limit_window = 10  # seconds
        self._rate_limit_count = 100  # requests per window
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client has exceeded rate limit"""
        current_time = time.time()
        client_requests = self._request_times[client_ip]
        
        # Remove old requests outside the window
        cutoff_time = current_time - self._rate_limit_window
        client_requests[:] = [t for t in client_requests if t > cutoff_time]
        
        # Check if within limit
        if len(client_requests) >= self._rate_limit_count:
            return False
        
        # Add current request
        client_requests.append(current_time)
        return True
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log incoming requests for debugging
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"GLOBAL: {request.method} {request.url.path} from {client_ip}")
        
        # Check rate limit (but be lenient for localhost development)
        if not client_ip.startswith("127.0.0.1") and not self._check_rate_limit(client_ip):
            logger.warning(f"   RATE_LIMIT: Client {client_ip} exceeded {self._rate_limit_count} requests per {self._rate_limit_window}s")
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Log request headers for CORS debugging
        origin = request.headers.get("origin", "none")
        user_agent = request.headers.get("user-agent", "unknown")[:100]
        auth_header = request.headers.get("authorization", "none")
        
        # Enhanced auth header debugging for malformed token issues
        if auth_header != "none":
            if auth_header.startswith("Bearer "):
                token_part = auth_header[7:].strip()  # Remove "Bearer " prefix
                if token_part:
                    token_segments = len(token_part.split('.'))
                    logger.debug(f"   Auth: Bearer token present (segments: {token_segments}, length: {len(token_part)})")
                    if token_segments != 3:
                        logger.warning(f"   AUTH WARNING: Malformed token detected - {token_segments} segments instead of 3")
                        logger.warning(f"   AUTH WARNING: Token preview: '{token_part[:30]}...'")
                else:
                    logger.warning("   AUTH WARNING: Bearer header present but token is empty")
            else:
                logger.warning(f"   AUTH WARNING: Authorization header doesn't start with 'Bearer ': '{auth_header[:50]}...'")
        
        logger.debug(f"   Origin: {origin}, User-Agent: {user_agent}")
        
        # Process request with error handling
        try:
            response = await call_next(request)
        except Exception as e:
            # Log any unhandled exceptions that cause 500 errors
            logger.error(f"EXPLOSION: UNHANDLED EXCEPTION in {request.url.path}: {str(e)}")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Client: {client_ip}")
            raise
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response status with different emojis for errors
        if response.status_code >= 500:
            logger.error(f"   ERROR Response: {response.status_code} in {process_time:.3f}s")
        elif response.status_code >= 400:
            logger.warning(f"   WARNING Response: {response.status_code} in {process_time:.3f}s")
        else:
            logger.info(f"   SUCCESS Response: {response.status_code} in {process_time:.3f}s")
        
        # Add custom headers for frontend
        response.headers["X-API-Version"] = "2.0.0"
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        response.headers["X-Backend-Status"] = "operational"
        response.headers["X-Data-Source"] = "decodo-primary"
        response.headers["X-Timestamp"] = datetime.now().isoformat()
        
        # Add rate limiting info (helpful for frontend)
        client_requests = len(self._request_times.get(client_ip, []))
        remaining = max(0, self._rate_limit_count - client_requests)
        response.headers["X-Rate-Limit-Remaining"] = str(remaining)
        response.headers["X-Rate-Limit-Limit"] = str(self._rate_limit_count)
        response.headers["X-Rate-Limit-Window"] = str(self._rate_limit_window)
        response.headers["X-Retry-Mechanism"] = "enabled"
        
        return response