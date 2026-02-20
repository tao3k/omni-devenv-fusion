"""Request observability primitives for MCP SSE transport."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


def _nearest_rank_percentile(samples: list[float], p: float) -> float:
    """Return percentile using nearest-rank method."""
    if not samples:
        return 0.0
    sorted_samples = sorted(samples)
    rank = max(1, math.ceil(p * len(sorted_samples)))
    index = min(len(sorted_samples) - 1, rank - 1)
    return sorted_samples[index]


@dataclass(slots=True)
class _EndpointStats:
    """In-memory counters and latency window for one endpoint."""

    requests_total: int
    errors_total: int
    status_4xx_total: int
    status_5xx_total: int
    in_flight: int
    max_in_flight: int
    latency_total_ms: float
    latency_max_ms: float
    latencies_ms: deque[float]


class MCPRequestObservability:
    """Tracks per-endpoint request pressure and latency with periodic log emission."""

    def __init__(
        self,
        *,
        logger: Any,
        log_interval_secs: float = 30.0,
        latency_window_size: int = 1024,
    ) -> None:
        self._logger = logger
        self._log_interval_secs = max(1.0, float(log_interval_secs))
        self._latency_window_size = max(32, int(latency_window_size))
        self._last_log_at_monotonic = 0.0
        self._endpoints: dict[str, _EndpointStats] = {}
        self._total_requests = 0
        self._total_errors = 0
        self._in_flight_total = 0
        self._max_in_flight_total = 0

    def _get_endpoint(self, endpoint: str) -> _EndpointStats:
        stats = self._endpoints.get(endpoint)
        if stats is not None:
            return stats
        stats = _EndpointStats(
            requests_total=0,
            errors_total=0,
            status_4xx_total=0,
            status_5xx_total=0,
            in_flight=0,
            max_in_flight=0,
            latency_total_ms=0.0,
            latency_max_ms=0.0,
            latencies_ms=deque(maxlen=self._latency_window_size),
        )
        self._endpoints[endpoint] = stats
        return stats

    def start(self, endpoint: str) -> float:
        """Mark request start and return perf-counter timestamp."""
        stats = self._get_endpoint(endpoint)
        stats.requests_total += 1
        stats.in_flight += 1
        stats.max_in_flight = max(stats.max_in_flight, stats.in_flight)

        self._total_requests += 1
        self._in_flight_total += 1
        self._max_in_flight_total = max(self._max_in_flight_total, self._in_flight_total)
        return time.perf_counter()

    def finish(
        self,
        endpoint: str,
        started_at: float,
        *,
        ok: bool,
        status_code: int,
        elapsed_ms: float | None = None,
    ) -> None:
        """Mark request completion, update stats, and emit periodic aggregate logs."""
        stats = self._get_endpoint(endpoint)
        elapsed = (
            float(elapsed_ms)
            if elapsed_ms is not None
            else (time.perf_counter() - started_at) * 1000.0
        )

        if stats.in_flight > 0:
            stats.in_flight -= 1
        if self._in_flight_total > 0:
            self._in_flight_total -= 1

        if not ok:
            stats.errors_total += 1
            self._total_errors += 1

        if 400 <= status_code < 500:
            stats.status_4xx_total += 1
        elif status_code >= 500:
            stats.status_5xx_total += 1

        stats.latency_total_ms += elapsed
        stats.latency_max_ms = max(stats.latency_max_ms, elapsed)
        stats.latencies_ms.append(elapsed)
        self._maybe_log()

    def _endpoint_snapshot(self, endpoint: str, stats: _EndpointStats) -> dict[str, Any]:
        sample_count = len(stats.latencies_ms)
        avg_ms = stats.latency_total_ms / stats.requests_total if stats.requests_total else 0.0
        p95_ms = _nearest_rank_percentile(list(stats.latencies_ms), 0.95)
        p99_ms = _nearest_rank_percentile(list(stats.latencies_ms), 0.99)
        err_rate = (
            (stats.errors_total / stats.requests_total * 100.0) if stats.requests_total else 0.0
        )
        return {
            "endpoint": endpoint,
            "requests_total": stats.requests_total,
            "errors_total": stats.errors_total,
            "status_4xx_total": stats.status_4xx_total,
            "status_5xx_total": stats.status_5xx_total,
            "error_rate_pct": round(err_rate, 2),
            "in_flight": stats.in_flight,
            "max_in_flight": stats.max_in_flight,
            "latency_sample_count": sample_count,
            "latency_avg_ms": round(avg_ms, 2),
            "latency_p95_ms": round(p95_ms, 2),
            "latency_p99_ms": round(p99_ms, 2),
            "latency_max_ms": round(stats.latency_max_ms, 2),
        }

    def endpoint_snapshot(self, endpoint: str) -> dict[str, Any]:
        """Public endpoint snapshot for tests and debug endpoints."""
        return self._endpoint_snapshot(endpoint, self._get_endpoint(endpoint))

    def health_summary(self, *, top_n: int = 5) -> dict[str, Any]:
        """Small health payload for runtime pressure inspection."""
        top_endpoints = sorted(
            self._endpoints.items(),
            key=lambda pair: pair[1].requests_total,
            reverse=True,
        )[: max(1, int(top_n))]
        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "in_flight": self._in_flight_total,
            "max_in_flight": self._max_in_flight_total,
            "top_endpoints": [
                self._endpoint_snapshot(name, stats) for name, stats in top_endpoints
            ],
        }

    def _maybe_log(self) -> None:
        now = time.monotonic()
        if now - self._last_log_at_monotonic < self._log_interval_secs:
            return
        self._last_log_at_monotonic = now

        summary = self.health_summary(top_n=4)
        endpoint_parts = []
        for item in summary["top_endpoints"]:
            endpoint_parts.append(
                f"{item['endpoint']} req={item['requests_total']} err={item['errors_total']} "
                f"in={item['in_flight']}/{item['max_in_flight']} "
                f"p95={item['latency_p95_ms']:.2f}ms p99={item['latency_p99_ms']:.2f}ms"
            )

        self._logger.info(
            "[MCP] request pressure total_req=%d total_err=%d in_flight=%d max_in_flight=%d "
            "endpoints=[%s]",
            summary["total_requests"],
            summary["total_errors"],
            summary["in_flight"],
            summary["max_in_flight"],
            "; ".join(endpoint_parts) if endpoint_parts else "none",
        )


__all__ = ["MCPRequestObservability"]
