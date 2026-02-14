"""Integration tests for Knowledge analyzer Arrow path (get_knowledge_dataframe)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
async def test_get_knowledge_dataframe_arrow_path_returns_table() -> None:
    """get_knowledge_dataframe uses list_all_arrow(); returns Table with expected columns."""
    from omni.core.knowledge.analyzer import get_knowledge_dataframe

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "knowledge.lance")
        store = RustVectorStore(
            index_path=path,
            dimension=4,
            enable_keyword_index=False,
        )
        # Populate knowledge table (same shape as librarian)
        ids = ["doc1", "doc2"]
        vectors = [[0.1] * 4, [0.2] * 4]
        contents = ["First chunk", "Second chunk"]
        metadatas = [
            json.dumps({"source": "a.md", "type": "doc"}),
            json.dumps({"source": "b.md", "type": "doc"}),
        ]
        await store.add_documents("knowledge", ids, vectors, contents, metadatas)

        with patch("omni.foundation.config.get_database_path", return_value=path):
            table = get_knowledge_dataframe("knowledge")

        assert table is not None
        assert table.num_rows == 2
        assert "id" in table.column_names
        assert "content" in table.column_names
        # list_all_arrow returns table built from list_all_tools (v2 schema: id, content, skill_name, etc.)
        assert table["content"][0].as_py() in ("First chunk", "Second chunk")
