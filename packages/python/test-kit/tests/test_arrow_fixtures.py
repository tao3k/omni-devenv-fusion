"""Test Arrow/LanceDB fixtures (table health IPC) in omni.test_kit."""

from __future__ import annotations

import pytest

from omni.test_kit.fixtures.arrow import (
    TABLE_HEALTH_IPC_COLUMNS,
    assert_table_health_ipc_table,
    decode_table_health_ipc_bytes,
    make_table_health_ipc_bytes,
    table_health_ipc_schema,
)


class TestArrowTableHealthIpc:
    """Table health IPC helpers: schema, build, decode, assert."""

    def test_table_health_ipc_schema_has_expected_columns(self) -> None:
        schema = table_health_ipc_schema()
        names = [f.name for f in schema]
        assert names == list(TABLE_HEALTH_IPC_COLUMNS)

    def test_make_table_health_ipc_bytes_default(self) -> None:
        data = make_table_health_ipc_bytes()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_make_table_health_ipc_bytes_custom(self) -> None:
        data = make_table_health_ipc_bytes(
            row_count=42,
            fragment_count=3,
            fragmentation_ratio=0.1,
            index_names=["a"],
            index_types=["btree"],
            recommendations=["run_compaction"],
        )
        table = decode_table_health_ipc_bytes(data)
        assert table.num_rows == 1
        assert table.column("row_count")[0].as_py() == 42
        assert table.column("fragment_count")[0].as_py() == 3
        assert table.column("fragmentation_ratio")[0].as_py() == 0.1

    def test_decode_table_health_ipc_bytes_roundtrip(self) -> None:
        data = make_table_health_ipc_bytes()
        table = decode_table_health_ipc_bytes(data)
        assert_table_health_ipc_table(table)

    def test_assert_table_health_ipc_table_raises_on_wrong_shape(self) -> None:
        import pyarrow as pa

        # Table with wrong columns
        bad = pa.table({"x": [1]})
        with pytest.raises(AssertionError, match="columns"):
            assert_table_health_ipc_table(bad)

    def test_assert_table_health_ipc_table_raises_on_zero_rows(self) -> None:
        data = make_table_health_ipc_bytes()
        table = decode_table_health_ipc_bytes(data)
        empty = table.slice(0, 0)
        with pytest.raises(AssertionError, match="one row"):
            assert_table_health_ipc_table(empty)
