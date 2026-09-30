from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Clear contextvars để tránh rò rỉ context giữa các request
        clear_contextvars()

        # 2. Lấy x-request-id từ header hoặc sinh mã mới chuẩn req-<8-char-hex>
        correlation_id = request.headers.get("x-request-id")
        if not correlation_id:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"
        
        # 3. Bind correlation_id vào structlog contextvars
        bind_contextvars(correlation_id=correlation_id)
        
        request.state.correlation_id = correlation_id
        
        start = time.perf_counter()
        response = await call_next(request)
        
        # 4. Tính latency và trả headers chuẩn trong response
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(elapsed_ms)
        
        return response