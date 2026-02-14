"""Integration tests for db health and compact against a real LanceDB store.

Uses a temp directory and indexes skills from the repo to create a real table,
then exercises analyze_table_health, compact, get_query_metrics, and
analyze_table_health_ipc (Arrow IPC stream).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omni.foundation.utils.asyncio import run_async_blocking
from omni.test_kit.fixtures.arrow import (
    assert_table_health_ipc_table,
    decode_table_health_ipc_bytes,
)


@pytest.fixture
def repo_root() -> Path:
    """Repository root (integration -> tests -> agent -> python -> packages -> repo)."""
    return Path(__file__).resolve().parents[5]


def test_query_metrics_placeholder_shape(tmp_path: Path):
    """get_query_metrics returns metrics shape (query_count 0 when no search in this process)."""
    from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore

    if not RUST_AVAILABLE:
        pytest.skip("omni_core_rs not available")

    store = RustVectorStore(str(tmp_path), 384, True)
    metrics = store.get_query_metrics("skills")
    assert isinstance(metrics, dict)
    assert "query_count" in metrics
    assert metrics.get("query_count") == 0


def test_db_health_compact_query_metrics_integration(tmp_path: Path, repo_root: Path):
    """Run health, compact, and query-metrics against a real temp LanceDB."""
    from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore

    if not RUST_AVAILABLE:
        pytest.skip("omni_core_rs not available")

    store = RustVectorStore(str(tmp_path), 384, True)
    # Index from repo so we have a real table
    skills_base = repo_root / "assets" / "skills"
    if not skills_base.is_dir():
        pytest.skip("repo assets/skills not found")

    n = run_async_blocking(store.index_skill_tools(str(repo_root), "skills"))
    assert n >= 0, "index_skill_tools should return count"

    if n == 0:
        pytest.skip("index_skill_tools returned 0 (no table created or no skills found)")

    # Health report shape
    health = store.analyze_table_health("skills")
    assert isinstance(health, dict), "health should be dict"
    assert "row_count" in health, f"health should have row_count: {health}"
    assert "fragment_count" in health
    assert "fragmentation_ratio" in health
    assert "recommendations" in health
    assert health["fragment_count"] >= 0
    assert isinstance(health["recommendations"], list)

    # Arrow IPC: analyze_table_health_ipc returns bytes, decode and assert schema
    ipc_bytes = store.analyze_table_health_ipc("skills")
    assert isinstance(ipc_bytes, bytes), "analyze_table_health_ipc should return bytes"
    assert len(ipc_bytes) > 0
    table = decode_table_health_ipc_bytes(ipc_bytes)
    assert_table_health_ipc_table(table)

    # Compact returns stats
    compact = store.compact("skills")
    assert isinstance(compact, dict)
    assert "fragments_before" in compact or "error" in compact
    if "error" not in compact:
        assert "fragments_after" in compact
        assert "duration_ms" in compact

    # Query metrics (in-process: 0 when no agentic_search in this process)
    metrics = store.get_query_metrics("skills")
    assert isinstance(metrics, dict)
    assert "query_count" in metrics
    assert metrics.get("query_count") == 0
