"""Example tests demonstrating the testing layer markers.

This file shows how to use the test layer markers for categorizing tests.
"""

from __future__ import annotations

import pytest

from omni.core.testing.layers import unit, integration, cloud, benchmark, stress, e2e
from omni.core.responses import ToolResponse, ResponseStatus


# =============================================================================
# Unit Tests (< 100ms, mocked dependencies)
# =============================================================================


@unit
def test_tool_response_success() -> None:
    """Unit test: Verify successful response creation."""
    response = ToolResponse.success(data={"key": "value"})
    assert response.status == ResponseStatus.SUCCESS
    assert response.data == {"key": "value"}
    assert response.error_message is None


@unit
def test_tool_response_error() -> None:
    """Unit test: Verify error response creation."""
    response = ToolResponse.error(message="Not found", code="3001", metadata={"tool": "git.status"})
    assert response.status == ResponseStatus.ERROR
    assert response.error_message == "Not found"
    assert response.error_code == "3001"


@unit
def test_response_to_mcp_format() -> None:
    """Unit test: Verify MCP format conversion."""
    response = ToolResponse.success({"data": 123})
    mcp = response.to_mcp()
    assert len(mcp) == 1
    assert mcp[0]["type"] == "text"
    assert "success" in mcp[0]["text"]


# =============================================================================
# Integration Tests (multiple components, real interactions)
# =============================================================================


@integration
async def test_kernel_initialization() -> None:
    """Integration test: Verify kernel initializes correctly."""
    from omni.core.kernel import get_kernel

    kernel = get_kernel()
    await kernel.initialize()
    assert kernel is not None


@integration
async def test_skill_loader_integration(skills_path) -> None:
    """Integration test: Verify skill loading works with real files."""
    from omni.core.skills.tools_loader import ToolsLoader

    scripts_dir = skills_path / "sample" / "scripts"
    (scripts_dir / "ping.py").write_text(
        "from omni.foundation.api.decorators import skill_command\n"
        '@skill_command(name="ping")\n'
        'def ping(): return "pong"\n'
    )
    loader = ToolsLoader(scripts_dir, "sample")
    loader.load_all()
    assert "sample.ping" in loader.list_commands()


# =============================================================================
# Cloud Tests (require external services, skipped locally)
# =============================================================================


@cloud
async def test_remote_vector_store() -> None:
    """Cloud test: Requires external LanceDB instance."""
    # This test would connect to a remote LanceDB
    # Skipped unless --cloud flag is provided
    pytest.skip("Requires external LanceDB service")


@cloud
def test_external_api_call() -> None:
    """Cloud test: Requires network access to external API."""
    pytest.skip("Requires external API access")


# =============================================================================
# Benchmark Tests (performance measurement)
# =============================================================================


@benchmark
def test_response_creation_benchmark() -> None:
    """Benchmark: Measure ToolResponse creation overhead."""
    import time

    start = time.perf_counter()
    _ = [ToolResponse.success({"data": i}) for i in range(100)]
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.0


# =============================================================================
# Stress Tests (long-running, resource-intensive)
# =============================================================================


@stress
async def test_high_volume_skill_loading() -> None:
    """Stress test: Load thousands of skills."""
    import asyncio
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create many skill directories
        skills_dir = Path(tmpdir)
        for i in range(1000):
            (skills_dir / f"skill_{i}").mkdir()
            (skills_dir / f"skill_{i}" / "SKILL.md").write_text(
                f"---\nname: skill_{i}\nversion: 1.0.0\n---"
            )

        # This would take significant time
        pytest.skip("Long-running stress test")


# =============================================================================
# E2E Tests (complete user workflows)
# =============================================================================


@e2e
async def test_complete_git_workflow() -> None:
    """E2E test: Complete git operation workflow."""
    # Simulate a complete user workflow:
    # 1. Initialize git repo
    # 2. Add files
    # 3. Commit
    # 4. Check status
    pytest.skip("Complete E2E workflow test")
