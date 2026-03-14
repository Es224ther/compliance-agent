"""Middleware setup for the FastAPI application."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logger import get_logger

logger = get_logger()
RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.endswith("/analyze"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            bucket = RATE_LIMIT_BUCKETS[client_ip]
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded for /analyze"},
                )
            bucket.append(now)
        return await call_next(request)


def add_api_middleware(app) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(RateLimitMiddleware)


def reset_rate_limit_buckets() -> None:
    RATE_LIMIT_BUCKETS.clear()
