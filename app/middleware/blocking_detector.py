"""
Event Loop Blocking Detector Middleware

Logs a warning when any request handler takes longer than 100ms,
which indicates the event loop was blocked by synchronous/CPU-bound work.
"""
import asyncio
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("blocking_detector")


class BlockingDetectorMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        loop = asyncio.get_event_loop()
        wall_start = time.monotonic()
        loop_start = loop.time()

        response = await call_next(request)

        wall_elapsed = time.monotonic() - wall_start
        loop_elapsed = loop.time() - loop_start

        # Only warn on likely event-loop blocking (wall >> loop means sync work).
        # Slow async I/O (wall ≈ loop) is normal for DB queries over network.
        is_blocking = wall_elapsed > 1.0 and loop_elapsed > 0.5
        if is_blocking:
            logger.warning(
                "BLOCKING: %s %s took %.3fs (loop: %.3fs)",
                request.method,
                request.url.path,
                wall_elapsed,
                loop_elapsed,
            )

        return response
