from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)

class FrontendHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add helpful headers for frontend integration
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log incoming requests for debugging
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"GLOBAL: {request.method} {request.url.path} from {client_ip}")
        
        # Log request headers for CORS debugging
        origin = request.headers.get("origin", "none")
        user_agent = request.headers.get("user-agent", "unknown")[:100]
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
        response.headers["X-Rate-Limit-Remaining"] = "unlimited"
        response.headers["X-Retry-Mechanism"] = "enabled"
        
        return response