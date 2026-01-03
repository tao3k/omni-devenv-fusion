# mcp-server/tests/test_hive_robustness.py
"""
Chaos Engineering Tests for The Hive (Phase 10.5)
Tests for Auto-Healing, Circuit Breaker, and Health Checks.
"""
import pytest
import asyncio
from pathlib import Path

from common.mcp_core.gitops import get_project_root
from common.services.swarm import SwarmNode

WORKER_SCRIPT = get_project_root() / "src" / "common" / "services" / "coder_service.py"


@pytest.mark.asyncio
async def test_auto_healing_on_connection_loss():
    """
    Scenario: Connection is lost, call_tool should auto-reconnect.
    Expectation: The call succeeds after auto-reconnect.
    """
    print("\n[Chaos] Starting Auto-Reconnect Test...")
    node = SwarmNode("chaos-worker", str(WORKER_SCRIPT))
    await node.connect()

    # 1. Ensure it works initially
    res1 = await node.call_tool("ping", {})
    assert res1.content[0].text == "pong"
    print("✅ Initial Ping Success")

    # 2. Close connection but keep session reference (simulating broken pipe)
    print("🔪 Breaking connection...")
    await node.close()
    # Set _connected to True but session to None (simulates connection loss)
    node._connected = True
    node.session = None

    # 3. Call tool -> Should trigger auto-reconnect
    print("🔄 Calling tool after connection loss...")
    try:
        res2 = await node.call_tool("ping", {})
        assert res2.content[0].text == "pong"
        print("✅ Auto-Reconnect Success: Worker reconnected and handled request")
    except Exception as e:
        pytest.fail(f"Auto-Reconnect Failed: {e}")

    await node.close()


@pytest.mark.asyncio
async def test_health_check_metrics():
    """Verify health check and metrics collection."""
    node = SwarmNode("health-worker", str(WORKER_SCRIPT))
    await node.connect()

    # Run some calls
    await node.call_tool("ping", {})
    await node.call_tool("ping", {})

    # Check Health
    health = await node.health_check()
    assert health["healthy"] is True, f"Worker should be healthy: {health}"

    # Check Metrics (latency is in metrics, not directly in health)
    metrics = health.get("metrics", {})
    assert node.metrics.total_calls >= 2, "Should have recorded 2 calls"
    assert node.metrics.success_count >= 2, "Should have 2 successes"
    assert node.metrics.avg_latency_ms > 0, "Latency should be measured"

    print(f"✅ Metrics Verified: total={node.metrics.total_calls}, "
          f"success={node.metrics.success_count}, "
          f"latency={node.metrics.avg_latency_ms:.2f}ms")

    await node.close()


@pytest.mark.asyncio
async def test_metrics_accuracy():
    """Verify metrics are being recorded correctly."""
    node = SwarmNode("metrics-worker", str(WORKER_SCRIPT))
    await node.connect()

    # Initial state
    assert node.metrics.total_calls == 0
    assert node.metrics.success_count == 0
    assert node.metrics.restarts == 0

    # Make 3 successful calls
    for _ in range(3):
        await node.call_tool("ping", {})

    # Verify metrics
    assert node.metrics.total_calls == 3
    assert node.metrics.success_count == 3
    assert node.metrics.avg_latency_ms > 0

    print(f"✅ Metrics accuracy verified: {node.metrics}")

    await node.close()


@pytest.mark.asyncio
async def test_list_tools_with_lazy_connect():
    """Verify list_tools works with lazy connection."""
    node = SwarmNode("list-worker", str(WORKER_SCRIPT))

    # Don't connect explicitly
    tools = await node.list_tools()

    # Should have auto-connected and returned tools
    assert len(tools) > 0, "Should have returned tools"
    assert node.is_connected is True, "Should be connected after list_tools"

    # Verify ping is in the list
    tool_names = [t.name for t in tools]
    assert "ping" in tool_names, "ping tool should be available"

    print(f"✅ Lazy connect verified: {len(tools)} tools available")

    await node.close()


@pytest.mark.asyncio
async def test_circuit_breaker_infrastructure():
    """
    Test that circuit breaker infrastructure is working.
    Verify that the node has circuit breaker state and can report it.
    """
    print("\n[CircuitBreaker] Testing circuit breaker infrastructure...")
    node = SwarmNode("circuit-worker", str(WORKER_SCRIPT))
    await node.connect()

    # Verify circuit breaker state exists
    assert hasattr(node, '_circuit_open_until'), "Node should have circuit breaker"
    assert node._circuit_open_until == 0.0, "Initially closed (0.0)"

    # Verify metrics exist
    assert hasattr(node, 'metrics'), "Node should have metrics"
    assert hasattr(node.metrics, 'failure_count'), "Metrics should track failures"

    # Health check should report circuit state
    health = await node.health_check()
    assert 'circuit' in health, "Health should include circuit state"
    assert health['circuit'] == 'CLOSED', "Initially circuit should be CLOSED"

    print(f"✅ Circuit breaker infrastructure verified: state={health['circuit']}")

    await node.close()


@pytest.mark.asyncio
async def test_swarm_manager_health():
    """Test SwarmManager system health aggregation."""
    from services.swarm import SwarmManager

    manager = SwarmManager()
    manager.register("test-worker", str(WORKER_SCRIPT))

    # Get system health
    health = await manager.get_system_health()

    assert "test-worker" in health
    # First call might not have connected yet
    print(f"✅ SwarmManager health check: {health}")

    # Now connect and check again
    node = await manager.get_node("test-worker")
    assert node is not None

    # Call a tool to warm up
    await node.call_tool("ping", {})

    health = await manager.get_system_health()
    print(f"✅ After warmup: {health}")

    await node.close()
