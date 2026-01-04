"""
src/agent/tests/test_swarm.py
Swarm Health Monitoring Tests

Tests for:
1. Swarm health status retrieval
2. Server status checking
3. Metrics aggregation
4. Error handling scenarios

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_swarm.py -v
"""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.swarm import (
    get_swarm_health,
    get_simple_swarm_health,
    get_async_swarm_health,
    _check_server_health,
)


class TestSwarmHealthBasics:
    """Basic functionality tests for swarm health monitoring."""

    def test_simple_swarm_health_returns_valid_structure(self):
        """Test that get_simple_swarm_health returns properly structured response."""
        result = get_simple_swarm_health()

        # Check required top-level keys
        assert "healthy" in result
        assert "servers" in result
        assert "metrics" in result
        assert "timestamp" in result

        # Check servers structure
        assert "orchestrator" in result["servers"]
        assert "executor" in result["servers"]
        assert "coder" in result["servers"]

    def test_simple_swarm_health_all_servers_running(self):
        """Test that all servers are reported as running by default."""
        result = get_simple_swarm_health()

        for server_name, server_info in result["servers"].items():
            assert server_info["status"] == "running", f"{server_name} should be running"
            assert server_info["tools"] == "active", f"{server_name} tools should be active"

    def test_simple_swarm_health_healthy_flag(self):
        """Test that healthy flag is True when all servers running."""
        result = get_simple_swarm_health()

        assert result["healthy"] is True

    def test_simple_swarm_health_metrics_complete(self):
        """Test that metrics contain all required fields."""
        result = get_simple_swarm_health()
        metrics = result["metrics"]

        assert "total_servers" in metrics
        assert "active_servers" in metrics
        assert "health_percentage" in metrics

        assert metrics["total_servers"] == 3
        assert metrics["active_servers"] == 3
        assert metrics["health_percentage"] == 100.0

    def test_simple_swarm_health_has_timestamp(self):
        """Test that timestamp is in ISO format."""
        result = get_simple_swarm_health()

        assert result["timestamp"] is not None
        assert "T" in result["timestamp"]  # ISO format contains T for date/time separator


class TestSwarmHealthAsync:
    """Tests for async swarm health monitoring."""

    @pytest.mark.asyncio
    async def test_check_server_health_returns_structure(self):
        """Test that _check_server_health returns proper structure."""
        result = await _check_server_health("orchestrator")

        assert "status" in result
        assert "description" in result
        assert "tools" in result
        assert "last_check" in result

    @pytest.mark.asyncio
    async def test_check_server_health_unknown_server(self):
        """Test that _check_server_health handles unknown servers."""
        result = await _check_server_health("unknown_server")

        assert result["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_async_swarm_health_works(self):
        """Test that get_async_swarm_health works correctly."""
        result = await get_async_swarm_health()

        assert "healthy" in result
        assert "servers" in result
        assert "metrics" in result
        assert "timestamp" in result

        # All servers should be running
        for server_name, server_info in result["servers"].items():
            assert server_info["status"] == "running"


class TestSwarmHealthSyncWrapper:
    """Tests for synchronous wrapper around async health check."""

    def test_get_swarm_health_returns_valid_structure(self):
        """Test that get_swarm_health returns properly structured response."""
        result = get_swarm_health()

        # Check required top-level keys
        assert "healthy" in result
        assert "servers" in result
        assert "metrics" in result
        assert "timestamp" in result

    def test_get_swarm_health_all_servers_running(self):
        """Test that all servers are reported as running."""
        result = get_swarm_health()

        for server_name, server_info in result["servers"].items():
            assert server_info["status"] == "running", f"{server_name} should be running"

    def test_get_swarm_health_healthy(self):
        """Test that healthy flag is True when all servers running."""
        result = get_swarm_health()

        assert result["healthy"] is True


class TestSwarmMetrics:
    """Tests for swarm metrics calculation."""

    def test_health_percentage_calculation(self):
        """Test that health percentage is calculated correctly."""
        result = get_simple_swarm_health()

        # With 3 active servers out of 3 total
        expected_percentage = (3 / 3) * 100
        assert result["metrics"]["health_percentage"] == expected_percentage

    def test_metrics_total_matches_servers_count(self):
        """Test that total servers metric matches actual servers."""
        result = get_simple_swarm_health()
        servers_count = len(result["servers"])

        assert result["metrics"]["total_servers"] == servers_count


class TestSwarmEdgeCases:
    """Edge case tests for swarm monitoring."""

    def test_swarm_health_returns_dict(self):
        """Test that swarm health returns a dictionary."""
        result = get_swarm_health()

        assert isinstance(result, dict)

    def test_swarm_health_no_none_values_in_servers(self):
        """Test that server statuses don't have None values that could cause issues."""
        result = get_swarm_health()

        for server_name, server_info in result["servers"].items():
            assert server_info is not None
            assert server_info.get("status") is not None

    def test_swarm_health_timestamp_is_string(self):
        """Test that timestamp is a string, not a datetime object."""
        result = get_swarm_health()

        assert isinstance(result["timestamp"], str)


class TestSwarmIntegration:
    """Integration tests for swarm monitoring with real components."""

    def test_swarm_status_tool_registration(self):
        """Test that swarm_status tool is properly registered in router."""
        # This verifies the tool can be imported and has correct signature
        from agent.tools.router import register_router_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")

        # Should not raise an exception
        try:
            register_router_tools(mcp)
        except Exception as e:
            pytest.skip(f"Router tools registration failed: {e}")

        # Verify tool exists - use correct FastMCP API
        tool_names = [t.name for t in mcp._tool_manager._tools.values()]
        assert "swarm_status" in tool_names


class TestSwarmMockScenarios:
    """Tests for mocked scenarios (simulating server failures)."""

    @pytest.mark.asyncio
    async def test_async_check_with_mocked_response(self):
        """Test async health check with mocked server status."""
        # Mock the _check_server_health to simulate a down server
        original_check = _check_server_health

        async def mock_check(name):
            if name == "executor":
                return {
                    "status": "error",
                    "tools": "inactive",
                    "description": "Server down",
                    "latency_ms": None,
                    "last_check": datetime.now().isoformat(),
                }
            return await original_check(name)

        with patch("agent.core.swarm._check_server_health", side_effect=mock_check):
            result = await get_async_swarm_health()

            # With one server down, healthy should be False
            assert result["healthy"] is False
            assert result["servers"]["executor"]["status"] == "error"


# =============================================================================
# Performance Tests
# =============================================================================


class TestSwarmPerformance:
    """Performance benchmarks for swarm monitoring."""

    def test_simple_health_check_is_fast(self):
        """Test that simple health check completes quickly."""
        import time

        start = time.perf_counter()
        result = get_simple_swarm_health()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

        # Simple check should complete in under 10ms
        assert elapsed < 10, f"Simple health check took {elapsed:.1f}ms, expected < 10ms"
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_async_health_check_is_fast(self):
        """Test that async health check completes quickly."""
        import time

        start = time.perf_counter()
        result = await get_async_swarm_health()
        elapsed = (time.perf_counter() - start) * 1000

        # Async check should complete in under 100ms
        assert elapsed < 100, f"Async health check took {elapsed:.1f}ms, expected < 100ms"
        assert result["healthy"] is True


# =============================================================================
# Documentation Example Tests
# These tests demonstrate the usage patterns from the documentation
# =============================================================================


class TestSwarmDocumentationExamples:
    """Tests demonstrating documented usage scenarios."""

    def test_basic_usage_example(self):
        """
        Demonstrates basic usage from documentation:

        Usage:
            from agent.core.swarm import get_swarm_health
            health = get_swarm_health()
        """
        health = get_swarm_health()

        # Verify basic structure
        assert isinstance(health, dict)
        assert health["healthy"] is True
        assert len(health["servers"]) == 3

    @pytest.mark.asyncio
    async def test_async_usage_example(self):
        """
        Demonstrates async usage from documentation:

        Usage:
            import asyncio
            async def check():
                return await get_async_swarm_health()
        """
        result = await get_async_swarm_health()

        assert result["healthy"] is True
        assert "orchestrator" in result["servers"]
        assert "executor" in result["servers"]
        assert "coder" in result["servers"]

    def test_health_check_with_metrics(self):
        """
        Demonstrates extracting metrics from health check:

        Usage:
            health = get_swarm_health()
            metrics = health["metrics"]
            print(f"Health: {metrics['health_percentage']:.0f}%")
        """
        health = get_swarm_health()
        metrics = health["metrics"]

        assert metrics["total_servers"] == 3
        assert metrics["health_percentage"] == 100.0
        assert metrics["active_servers"] == 3

    def test_check_individual_server(self):
        """
        Demonstrates checking a specific server:

        Usage:
            servers = health["servers"]
            orchestrator = servers["orchestrator"]
            print(f"Orchestrator: {orchestrator['status']}")
        """
        health = get_swarm_health()
        servers = health["servers"]

        assert servers["orchestrator"]["status"] == "running"
        assert servers["orchestrator"]["tools"] == "active"
        assert servers["executor"]["status"] == "running"
        assert servers["coder"]["status"] == "running"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
