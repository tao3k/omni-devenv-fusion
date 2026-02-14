"""Integration tests for vector search IPC path (Arrow zero-copy).

Verifies the full flow: RustVectorStore.search_optimized_ipc → IPC bytes
→ pyarrow.Table → VectorPayload.from_arrow_table, against a real indexed table.

Tests either use the project's synced store (after `omni sync`) or a temp store
with index_skill_tools from repo assets/skills.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pyarrow.ipc
import pytest

from omni.foundation.utils.asyncio import run_async_blocking


@pytest.fixture
def repo_root() -> Path:
    """Repository root (integration -> tests -> agent -> packages -> repo)."""
    return Path(__file__).resolve().parents[5]


def _parse_vector_dim_from_error(err: Exception) -> int | None:
    """Extract 'vector dim(NNN)' from LanceDB dimension mismatch message."""
    m = re.search(r"vector dim\((\d+)\)", str(err))
    return int(m.group(1)) if m else None


def _store_and_skills_table(repo_root: Path, tmp_path: Path):
    """Return (store, table_name) using synced cache if available, else tmp + index."""
    from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore
    from omni.foundation.config.database import get_vector_db_path
    from omni.foundation.services.index_dimension import get_embedding_dimension_status

    if not RUST_AVAILABLE:
        return None, None
    # Dimension must match the index (synced store may use 1536 etc.)
    dim_status = get_embedding_dimension_status()
    dim = dim_status.index_dim if dim_status.index_dim is not None else dim_status.current_dim
    # Prefer synced store so that "omni sync" is enough to run these tests
    cache_path = get_vector_db_path()
    if cache_path.is_dir():
        store = RustVectorStore(str(cache_path), dim, True)
        try:
            health = store.analyze_table_health("skills")
            if health.get("row_count", 0) > 0:
                # If search fails with dimension mismatch, retry with dim from error (index may predate signature)
                try:
                    store.search_optimized_ipc("skills", [0.0] * dim, 1, None)
                except RuntimeError as e:
                    actual_dim = _parse_vector_dim_from_error(e)
                    if actual_dim is not None and actual_dim != dim:
                        store = RustVectorStore(str(cache_path), actual_dim, True)
                return store, "skills"
        except Exception:
            pass
    # Fallback: temp store and index from repo
    skills_base = repo_root / "assets" / "skills"
    if not skills_base.is_dir():
        return None, None
    store = RustVectorStore(str(tmp_path), dim, True)
    n = run_async_blocking(store.index_skill_tools(str(repo_root), "skills"))
    if n == 0:
        return None, None
    return store, "skills"


def test_vector_search_ipc_returns_bytes(tmp_path: Path, repo_root: Path):
    """search_optimized_ipc returns non-empty IPC stream bytes when table exists."""
    store, table_name = _store_and_skills_table(repo_root, tmp_path)
    if store is None or table_name is None:
        pytest.skip("no skills table (run omni sync or ensure assets/skills exists)")

    # Store was created with correct dim in _store_and_skills_table; use same for query
    dim = store._dimension
    query_vector = [0.0] * dim
    ipc_bytes = store.search_optimized_ipc(table_name, query_vector, limit=5, options_json=None)
    assert isinstance(ipc_bytes, bytes)
    assert len(ipc_bytes) > 0


def test_vector_search_ipc_decode_and_from_arrow_table(tmp_path: Path, repo_root: Path):
    """IPC bytes decode to Table and VectorPayload.from_arrow_table produces valid payloads."""
    from omni.foundation.services.vector_schema import VectorPayload

    store, table_name = _store_and_skills_table(repo_root, tmp_path)
    if store is None or table_name is None:
        pytest.skip("no skills table (run omni sync or ensure assets/skills exists)")

    dim = store._dimension
    query_vector = [0.0] * dim
    ipc_bytes = store.search_optimized_ipc(table_name, query_vector, limit=10, options_json=None)
    table = pyarrow.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
    assert table.num_rows >= 0
    assert "id" in table.column_names or "content" in table.column_names

    payloads = VectorPayload.from_arrow_table(table)
    # May be 0 if table empty; otherwise check shape
    for p in payloads:
        assert p.id
        assert p.content is not None
        assert hasattr(p, "distance")
        assert hasattr(p, "metadata")
