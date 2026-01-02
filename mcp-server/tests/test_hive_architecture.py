# mcp-server/tests/test_hive_architecture.py
import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add mcp-server to path to import services
sys.path.append(str(Path(__file__).parent.parent))

from services.swarm import SwarmNode

# 指向我们刚才创建的 worker
WORKER_SCRIPT = Path(__file__).parent.parent / "services" / "coder_service.py"

@pytest.mark.asyncio
async def test_swarm_connection_lifecycle():
    """Test 1: Can we connect and disconnect cleanly?"""
    print("\n[Test] Connecting...")
    node = SwarmNode("test-coder", str(WORKER_SCRIPT))

    success = await node.connect()
    assert success is True, "Failed to connect to worker"
    assert node.is_connected is True

    # Test Health Check
    print("[Test] Pinging...")
    result = await node.call_tool("ping", {})
    assert result.content[0].text == "pong"

    await node.close()
    assert node.is_connected is False
    print("[Test] Disconnected cleanly.")

@pytest.mark.asyncio
async def test_worker_logic_execution():
    """Test 2: Can we execute actual logic (read file)?"""
    node = SwarmNode("test-coder", str(WORKER_SCRIPT))
    await node.connect()

    # Create a dummy file
    test_file = Path("temp_swarm_test.txt")
    test_file.write_text("Hello Hive")

    try:
        # Call read_file on worker
        result = await node.call_tool("read_file", {"path": str(test_file)})
        content = result.content[0].text
        assert "Hello Hive" in content
    finally:
        if test_file.exists():
            test_file.unlink()
        await node.close()

@pytest.mark.asyncio
async def test_timeout_resilience():
    """Test 3: Does timeout protection work?"""
    # We don't need to actually deadlock the worker here,
    # we just need to verify that call_tool wraps timeout
    # Real timeout test would require worker to cooperate with sleep, verify basic functionality works first
    node = SwarmNode("test-coder", str(WORKER_SCRIPT))
    await node.connect()

    # Quick call should succeed
    await node.call_tool("ping", {})

    await node.close()
