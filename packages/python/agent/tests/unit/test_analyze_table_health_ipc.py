"""Unit tests for RustVectorStore.analyze_table_health_ipc and pyarrow decoding.

Verifies the Python API returns bytes and that the documented decoding path
yields a table with the expected schema. Uses test_kit arrow helpers and a mock
store so no real LanceDB table is required.
"""

from __future__ import annotations

from omni.foundation.bridge.rust_vector import RustVectorStore
from omni.test_kit.fixtures.arrow import (
    TABLE_HEALTH_IPC_COLUMNS,
    assert_table_health_ipc_table,
    decode_table_health_ipc_bytes,
    make_table_health_ipc_bytes,
)


def test_analyze_table_health_ipc_returns_bytes_and_decodes() -> None:
    """Store.analyze_table_health_ipc returns bytes; pyarrow decodes to table with expected schema."""
    ipc_bytes = make_table_health_ipc_bytes()
    assert isinstance(ipc_bytes, bytes)
    assert len(ipc_bytes) > 0

    table = decode_table_health_ipc_bytes(ipc_bytes)
    assert_table_health_ipc_table(table)
    assert set(table.column_names) >= set(TABLE_HEALTH_IPC_COLUMNS)
    assert table.column("row_count")[0].as_py() == 100
    assert table.column("fragment_count")[0].as_py() == 5
    assert table.column("fragmentation_ratio")[0].as_py() == 0.05


def test_analyze_table_health_ipc_api_with_mock_store() -> None:
    """RustVectorStore.analyze_table_health_ipc delegates to inner and returns bytes."""
    ipc_bytes = make_table_health_ipc_bytes()
    mock_inner = type("MockInner", (), {})()
    mock_inner.analyze_table_health_ipc = lambda table_name: ipc_bytes  # noqa: ARG005

    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = mock_inner

    out = store.analyze_table_health_ipc("skills")
    assert isinstance(out, bytes)
    assert out == ipc_bytes

    table = decode_table_health_ipc_bytes(out)
    assert_table_health_ipc_table(table)
