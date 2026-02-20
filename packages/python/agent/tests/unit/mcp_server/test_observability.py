"""Unit tests for MCP request observability."""

from __future__ import annotations

from omni.agent.mcp_server.observability import MCPRequestObservability


class _Logger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str, *args: object) -> None:
        rendered = message % args if args else message
        self.messages.append(rendered)


def test_observability_tracks_in_flight_and_latency_percentiles() -> None:
    logger = _Logger()
    metrics = MCPRequestObservability(
        logger=logger,
        log_interval_secs=9999.0,
        latency_window_size=16,
    )

    first = metrics.start("mcp:/")
    second = metrics.start("mcp:/")
    summary = metrics.health_summary()
    assert summary["in_flight"] == 2
    assert summary["max_in_flight"] == 2

    metrics.finish("mcp:/", first, ok=True, status_code=200, elapsed_ms=10.0)
    metrics.finish("mcp:/", second, ok=True, status_code=200, elapsed_ms=50.0)

    endpoint = metrics.endpoint_snapshot("mcp:/")
    assert endpoint["requests_total"] == 2
    assert endpoint["errors_total"] == 0
    assert endpoint["in_flight"] == 0
    assert endpoint["max_in_flight"] == 2
    assert endpoint["latency_p95_ms"] == 50.0
    assert endpoint["latency_p99_ms"] == 50.0


def test_observability_tracks_error_and_status_buckets() -> None:
    logger = _Logger()
    metrics = MCPRequestObservability(
        logger=logger,
        log_interval_secs=9999.0,
        latency_window_size=16,
    )

    first = metrics.start("mcp:/")
    metrics.finish("mcp:/", first, ok=False, status_code=404, elapsed_ms=12.0)
    second = metrics.start("mcp:/")
    metrics.finish("mcp:/", second, ok=False, status_code=503, elapsed_ms=22.0)

    endpoint = metrics.endpoint_snapshot("mcp:/")
    assert endpoint["errors_total"] == 2
    assert endpoint["status_4xx_total"] == 1
    assert endpoint["status_5xx_total"] == 1
    assert endpoint["error_rate_pct"] == 100.0

    summary = metrics.health_summary()
    assert summary["total_requests"] == 2
    assert summary["total_errors"] == 2


def test_observability_emits_periodic_pressure_log() -> None:
    logger = _Logger()
    metrics = MCPRequestObservability(
        logger=logger,
        log_interval_secs=1.0,
        latency_window_size=16,
    )

    started = metrics.start("http:/embed/batch")
    metrics.finish("http:/embed/batch", started, ok=False, status_code=503, elapsed_ms=25.0)

    assert logger.messages
    assert "request pressure" in logger.messages[0]
    assert "http:/embed/batch" in logger.messages[0]
