# app/core/metrics_middleware.py

"""
In-memory request latency metrics.

Keeps the last `window` latencies per route template in a ring buffer. This is
process-local and resets on restart; it exists to power the admin health page,
not to replace real observability.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

import numpy as np
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class LatencyStore:
    def __init__(self, window: int = 500) -> None:
        self.window = window
        self._data: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window))
        self._counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record(self, key: str, ms: float) -> None:
        with self._lock:
            self._data[key].append(ms)
            self._counts[key] += 1

    def snapshot(self) -> list[dict]:
        with self._lock:
            items = [(k, list(v), self._counts[k]) for k, v in self._data.items()]
        out = []
        for key, values, count in items:
            arr = np.asarray(values, dtype=float)
            out.append(
                {
                    "endpoint": key,
                    "count": count,
                    "window": len(values),
                    "avg_ms": round(float(arr.mean()), 1),
                    "p50_ms": round(float(np.percentile(arr, 50)), 1),
                    "p95_ms": round(float(np.percentile(arr, 95)), 1),
                    "min_ms": round(float(arr.min()), 1),
                    "max_ms": round(float(arr.max()), 1),
                }
            )
        return sorted(out, key=lambda m: m["endpoint"])

    def reset(self) -> None:
        with self._lock:
            self._data.clear()
            self._counts.clear()


latency_store = LatencyStore()


class LatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        # Use the route template ("/occupations/{occupationUri:path}/skill-gap")
        # so per-URI calls aggregate; skip unmatched paths (404s, static).
        if route is not None and getattr(route, "path", None):
            key = f"{request.method} {route.path}"
            if "/admin/diagnostics/metrics" not in key:
                latency_store.record(key, (time.perf_counter() - start) * 1000)
        return response
