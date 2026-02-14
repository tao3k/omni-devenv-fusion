"""LanceDB/Arrow test helpers: table health IPC schema, build and decode.

Shared by unit and integration tests for RustVectorStore.analyze_table_health_ipc
and any Arrow IPC stream produced by the Rust bindings (TableHealthReport → RecordBatch).
"""

from __future__ import annotations

import io
import pyarrow as pa
import pyarrow.ipc as ipc

# Column names for the table health IPC stream (must match Rust ipc.rs schema)
TABLE_HEALTH_IPC_COLUMNS = (
    "row_count",
    "fragment_count",
    "fragmentation_ratio",
    "index_names",
    "index_types",
    "recommendations",
)


def table_health_ipc_schema() -> pa.Schema:
    """Arrow schema for one-row table health report (matches Rust TableHealthReport → RecordBatch)."""
    return pa.schema(
        [
            ("row_count", pa.uint32()),
            ("fragment_count", pa.uint64()),
            ("fragmentation_ratio", pa.float64()),
            ("index_names", pa.list_(pa.string())),
            ("index_types", pa.list_(pa.string())),
            ("recommendations", pa.list_(pa.string())),
        ]
    )


def make_table_health_ipc_bytes(
    *,
    row_count: int = 100,
    fragment_count: int = 5,
    fragmentation_ratio: float = 0.05,
    index_names: list[str] | None = None,
    index_types: list[str] | None = None,
    recommendations: list[str] | None = None,
) -> bytes:
    """Build Arrow IPC stream bytes with one row (same schema as Rust table_health_report_to_ipc).

    Use in unit tests to mock store.analyze_table_health_ipc or to assert decode contract.
    """
    if index_names is None:
        index_names = ["vector", "content_fts"]
    if index_types is None:
        index_types = ["IVF_FLAT", "Inverted"]
    if recommendations is None:
        recommendations = ["run_compaction", "none"]

    schema = table_health_ipc_schema()
    table = pa.table(
        {
            "row_count": pa.array([row_count], type=pa.uint32()),
            "fragment_count": pa.array([fragment_count], type=pa.uint64()),
            "fragmentation_ratio": pa.array([fragmentation_ratio], type=pa.float64()),
            "index_names": pa.array([index_names], type=pa.list_(pa.string())),
            "index_types": pa.array([index_types], type=pa.list_(pa.string())),
            "recommendations": pa.array([recommendations], type=pa.list_(pa.string())),
        },
        schema=schema,
    )
    buf = io.BytesIO()
    with ipc.new_stream(buf, schema) as writer:
        writer.write_table(table)
    return buf.getvalue()


def decode_table_health_ipc_bytes(data: bytes) -> pa.Table:
    """Decode Arrow IPC stream bytes to a pyarrow Table (documented API path).

    Use for any IPC bytes returned by RustVectorStore.analyze_table_health_ipc.
    """
    return ipc.open_stream(io.BytesIO(data)).read_all()


def assert_table_health_ipc_table(table: pa.Table) -> None:
    """Assert that a table has the table-health IPC schema (columns and one row)."""
    expected = set(TABLE_HEALTH_IPC_COLUMNS)
    actual = set(table.column_names)
    assert expected.issubset(actual), f"Table should have columns {expected}, got {list(actual)}"
    assert table.num_rows == 1, "Table health IPC should have one row"


__all__ = [
    "TABLE_HEALTH_IPC_COLUMNS",
    "table_health_ipc_schema",
    "make_table_health_ipc_bytes",
    "decode_table_health_ipc_bytes",
    "assert_table_health_ipc_table",
]
