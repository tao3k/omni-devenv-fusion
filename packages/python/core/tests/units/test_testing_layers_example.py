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
    assert response.error is None


@unit
def test_tool_response_error() -> None:
    """Unit test: Verify error response creation."""
    response = ToolResponse.error(message="Not found", code="3001", metadata={"tool": "git.status"})
    assert response.status == ResponseStatus.ERROR
    assert response.error == "Not found"
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
async def test_kernel_initialization(kernel) -> None:
    """Integration test: Verify kernel initializes correctly."""
    # This test uses the kernel fixture which requires real initialization
    assert kernel is not None


@integration
async def test_skill_loader_integration(skills_path) -> None:
    """Integration test: Verify skill loading works with real files."""
    from omni.core.skills.loader import SkillLoader

    loader = SkillLoader(skills_dir=str(skills_path))
    skills = await loader.discover()
    assert len(skills) > 0


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
def test_response_creation_benchmark(benchmark) -> None:
    """Benchmark: Measure ToolResponse creation overhead."""
    benchmark(list, [ToolResponse.success({"data": i}) for i in range(100)])


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
