"""监测 Python 端是否拥抱 Rust 新 Schema（v2：独立字典列，无 metadata 列）.

Rust 使用新 schema 后，此处测试用于验证 Python 侧：
- list_all_tools / list_all_arrow 读取的是新 schema 的扁平字段；
- 不依赖旧版单一 metadata 列；
- 返回结构为 skill_name, category, tool_name, content, file_path 等独立字段。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore

# 新 schema 下 list_all_tools 返回的每条记录必须包含的字段（Rust 从字典列读出）
V2_TOOL_ROW_KEYS = frozenset({"id", "content", "skill_name", "category", "tool_name", "file_path"})


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
async def test_list_all_tools_returns_v2_native_columns() -> None:
    """Python 端拥抱新 Schema：list_all_tools 返回的是独立列，不依赖 metadata 列。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "skills.lance")
        store = RustVectorStore(
            index_path=path,
            dimension=8,
            enable_keyword_index=False,
        )
        table_name = "skills"
        ids = ["git.commit", "knowledge.recall"]
        vectors = [[0.1] * 8, [0.2] * 8]
        contents = ["Commit changes", "Recall from knowledge"]
        metadatas = [
            json.dumps(
                {
                    "skill_name": "git",
                    "category": "vcs",
                    "tool_name": "commit",
                    "file_path": "git/scripts/commit.py",
                }
            ),
            json.dumps(
                {
                    "skill_name": "knowledge",
                    "category": "rag",
                    "tool_name": "recall",
                    "file_path": "knowledge/recall.py",
                }
            ),
        ]
        await store.add_documents(table_name, ids, vectors, contents, metadatas)

        tools = store.list_all_tools()
        assert len(tools) == 2

        # 新 schema：每条记录必须有这些独立字段（由 Rust 从字典列读出，非从 metadata 列解析）
        for t in tools:
            keys = set(t.keys())
            assert V2_TOOL_ROW_KEYS.issubset(keys), (
                f"Python 端应使用新 schema 返回的扁平字段，缺少 {V2_TOOL_ROW_KEYS - keys}"
            )
            # 不依赖单一 metadata 字段（旧 schema）
            assert "metadata" not in keys or t.get("metadata") is None, (
                "新 schema 下不应依赖顶层 metadata 字段"
            )
        skill_names = {t["skill_name"] for t in tools}
        assert skill_names == {"git", "knowledge"}
        assert tools[0]["content"] == "Commit changes"
        assert tools[0]["tool_name"] == "git.commit"
        assert tools[0]["file_path"] == "git/scripts/commit.py"

        # list_all_tools_arrow 基于 list_all_tools，列名应一致
        table = store.list_all_tools_arrow()
        assert table.num_rows == 2
        for col in V2_TOOL_ROW_KEYS:
            assert col in table.column_names, f"Arrow 表应包含新 schema 列 {col}"

        entries = store.list_all_arrow(table_name)
        assert entries.num_rows == 2


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
async def test_search_tools_ipc_path_returns_parseable_results() -> None:
    """search_tools() IPC path: results are parseable as ToolSearchPayload and have expected shape."""
    from omni.foundation.services.vector_schema import (
        parse_tool_search_payload,
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "skills.lance")
        store = RustVectorStore(
            index_path=path,
            dimension=8,
            enable_keyword_index=False,
        )
        table_name = "skills"
        ids = ["git.commit", "knowledge.recall"]
        vectors = [[0.1] * 8, [0.2] * 8]
        contents = ["Commit changes", "Recall from knowledge"]
        metadatas = [
            json.dumps(
                {
                    "skill_name": "git",
                    "category": "vcs",
                    "tool_name": "commit",
                    "file_path": "git/scripts/commit.py",
                }
            ),
            json.dumps(
                {
                    "skill_name": "knowledge",
                    "category": "rag",
                    "tool_name": "recall",
                    "file_path": "knowledge/recall.py",
                }
            ),
        ]
        await store.add_documents(table_name, ids, vectors, contents, metadatas)
        await store.create_index(table_name, 8)

        # search_tools (IPC or JSON path) returns list[dict]; each must be parseable as ToolSearchPayload
        results = await store.search_tools(
            table_name,
            [0.11] * 8,
            query_text=None,
            limit=5,
            threshold=0.0,
        )
        # Every result (IPC or JSON path) must be parseable as ToolSearchPayload
        for d in results:
            payload = parse_tool_search_payload(d)
            assert payload.name
            assert payload.description is not None
            assert payload.skill_name is not None
            assert payload.tool_name
            assert 0 <= payload.score <= 1.0
