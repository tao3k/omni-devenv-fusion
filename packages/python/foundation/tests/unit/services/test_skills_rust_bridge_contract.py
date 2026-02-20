"""Skills ↔ Rust DB Bridge Contract Tests.

CRITICAL: These tests protect the data contract between:
  - Rust omni-vector (LanceDB) → list_all_tools returns {id, content, metadata}
  - Python RustVectorStore._flatten_list_all_entry → flattens to top-level skill_name, tool_name
  - Python SkillDiscoveryService._build_skills_from_tools → expects top-level skill_name, tool_name

If this contract breaks, omni skill list shows 1 skill instead of 17+ (all tools collapse to "unknown").

Run: uv run pytest packages/python/foundation/tests/unit/services/test_skills_rust_bridge_contract.py -v
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore
from omni.foundation.bridge.tool_record_validation import (
    ToolRecordValidationError,
    validate_tool_record,
    validate_tool_records,
)

# Contract: discovery expects these at top level (not nested in metadata)
DISCOVERY_REQUIRED_KEYS = frozenset({"skill_name", "tool_name"})


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
class TestFlattenListAllEntry:
    """Tests that _flatten_list_all_entry produces discovery-compatible output."""

    def test_flatten_promotes_skill_name_tool_name_from_metadata(self):
        """Rust returns {id, content, metadata}; bridge must flatten skill_name, tool_name to top level."""
        store = RustVectorStore(
            index_path=":memory:",
            dimension=8,
            enable_keyword_index=False,
        )
        entry = {
            "id": "git.commit",
            "content": "Commit changes",
            "metadata": {
                "skill_name": "git",
                "tool_name": "commit",
                "file_path": "git/scripts/commit.py",
                "category": "vcs",
            },
        }
        out = store._flatten_list_all_entry(entry)
        assert out["skill_name"] == "git"
        assert out["tool_name"] == "commit"
        assert out["file_path"] == "git/scripts/commit.py"
        assert "metadata" not in out

    def test_flatten_without_metadata_passes_through(self):
        """Entries without metadata dict are returned unchanged."""
        store = RustVectorStore(
            index_path=":memory:",
            dimension=8,
            enable_keyword_index=False,
        )
        entry = {"id": "x", "content": "y", "skill_name": "git", "tool_name": "status"}
        out = store._flatten_list_all_entry(entry)
        assert out == entry

    def test_flatten_uses_content_as_description_when_missing(self):
        """When description is missing, content is used (skills table convention)."""
        store = RustVectorStore(
            index_path=":memory:",
            dimension=8,
            enable_keyword_index=False,
        )
        entry = {
            "id": "knowledge.recall",
            "content": "Recall from knowledge base",
            "metadata": {"skill_name": "knowledge", "tool_name": "recall"},
        }
        out = store._flatten_list_all_entry(entry)
        assert out["description"] == "Recall from knowledge base"

    def test_flatten_is_thin_no_inference(self):
        """Flatten only promotes metadata; no inference. Rust is source of truth."""
        store = RustVectorStore(
            index_path=":memory:",
            dimension=8,
            enable_keyword_index=False,
        )
        entry = {
            "id": "knowledge.ingest_document",
            "content": "Ingest",
            "metadata": {"skill_name": "knowledge", "tool_name": "ingest_document"},
        }
        out = store._flatten_list_all_entry(entry)
        assert out["skill_name"] == "knowledge"
        assert out["tool_name"] == "ingest_document"


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
class TestListAllToolsContract:
    """Tests that list_all_tools returns discovery-compatible format."""

    async def test_list_all_tools_returns_flat_skill_name_tool_name(self):
        """list_all_tools must return tools with skill_name, tool_name at top level."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "skills.lance")
            store = RustVectorStore(
                index_path=path,
                dimension=8,
                enable_keyword_index=False,
            )
            await store.add_documents(
                "skills",
                ["git.commit", "knowledge.recall"],
                [[0.1] * 8, [0.2] * 8],
                ["Commit", "Recall"],
                [
                    json.dumps(
                        {"skill_name": "git", "tool_name": "commit", "file_path": "git/commit.py"}
                    ),
                    json.dumps(
                        {
                            "skill_name": "knowledge",
                            "tool_name": "recall",
                            "file_path": "knowledge/recall.py",
                        }
                    ),
                ],
            )
            tools = store.list_all_tools()
            assert len(tools) == 2
            for t in tools:
                assert DISCOVERY_REQUIRED_KEYS.issubset(t.keys()), (
                    f"Discovery requires {DISCOVERY_REQUIRED_KEYS}; got keys {set(t.keys())}"
                )
                assert t["skill_name"] != "unknown", (
                    f"skill_name must not be 'unknown' (discovery fallback); got {t}"
                )
            skill_names = {t["skill_name"] for t in tools}
            assert skill_names == {"git", "knowledge"}

    async def test_list_all_tools_multiple_skills_not_collapsed(self):
        """Regression: tools from different skills must NOT collapse to one skill."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "skills.lance")
            store = RustVectorStore(
                index_path=path,
                dimension=8,
                enable_keyword_index=False,
            )
            ids = ["git.commit", "git.status", "knowledge.recall", "knowledge.search"]
            vectors = [[0.1] * 8] * 4
            contents = ["Commit", "Status", "Recall", "Search"]
            metadatas = [
                json.dumps(
                    {"skill_name": "git", "tool_name": "commit", "file_path": "git/commit.py"}
                ),
                json.dumps(
                    {"skill_name": "git", "tool_name": "status", "file_path": "git/status.py"}
                ),
                json.dumps(
                    {
                        "skill_name": "knowledge",
                        "tool_name": "recall",
                        "file_path": "knowledge/recall.py",
                    }
                ),
                json.dumps(
                    {
                        "skill_name": "knowledge",
                        "tool_name": "search",
                        "file_path": "knowledge/search.py",
                    }
                ),
            ]
            await store.add_documents("skills", ids, vectors, contents, metadatas)
            tools = store.list_all_tools()
            assert len(tools) == 4
            unique_skills = {t["skill_name"] for t in tools}
            assert len(unique_skills) == 2, (
                f"Expected 2 skills (git, knowledge), got {unique_skills}. "
                "If 1 skill: bridge flatten is broken, discovery would show 1 skill."
            )

    async def test_list_all_tools_filters_non_command_and_path_like_rows(self):
        """Bridge should expose only canonical public command rows."""
        store = RustVectorStore(
            index_path=":memory:",
            dimension=8,
            enable_keyword_index=False,
        )
        store._inner = MagicMock()
        store._inner.list_all_tools.return_value = json.dumps(
            [
                {
                    "id": "knowledge.recall",
                    "content": "Recall docs",
                    "metadata": {
                        "type": "command",
                        "skill_name": "knowledge",
                        "tool_name": "recall",
                        "file_path": "assets/skills/knowledge/scripts/recall.py",
                    },
                },
                {
                    "id": "knowledge",
                    "content": "Skill entry",
                    "metadata": {
                        "type": "skill",
                        "skill_name": "knowledge",
                        "tool_name": "knowledge",
                    },
                },
                {
                    "id": "/Users/me/repo/assets/skills/knowledge/scripts/recall.py:_helper",
                    "content": "Internal helper",
                    "metadata": {
                        "skill_name": "/Users/me/repo",
                        "tool_name": "/Users/me/repo/assets/skills/knowledge/scripts/recall.py:_helper",
                    },
                },
            ]
        )

        tools = store.list_all_tools()
        assert len(tools) == 1
        assert tools[0]["skill_name"] == "knowledge"
        assert tools[0]["tool_name"] == "knowledge.recall"


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
class TestDiscoveryConsumesListAllTools:
    """Tests that SkillDiscoveryService correctly groups tools from list_all_tools output."""

    async def test_discover_all_groups_by_skill_name(self):
        """discover_all must return multiple skills when list_all_tools has multiple skill_names."""
        from omni.core.skills.discovery import SkillDiscoveryService

        # Simulate list_all_tools output (post-flatten)
        tools = [
            {
                "id": "git.commit",
                "content": "Commit",
                "skill_name": "git",
                "tool_name": "commit",
                "file_path": "git/commit.py",
            },
            {
                "id": "git.status",
                "content": "Status",
                "skill_name": "git",
                "tool_name": "status",
                "file_path": "git/status.py",
            },
            {
                "id": "knowledge.recall",
                "content": "Recall",
                "skill_name": "knowledge",
                "tool_name": "recall",
                "file_path": "knowledge/recall.py",
            },
        ]
        discovery = SkillDiscoveryService()
        skills = await discovery._build_skills_from_tools(tools)
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"git", "knowledge"}
        git_skill = next(s for s in skills if s.name == "git")
        assert len(git_skill.metadata.get("tools", [])) == 2

    async def test_discover_all_uses_validated_skill_name(self):
        """Discovery uses skill_name from validated tools (Rust contract)."""
        from omni.core.skills.discovery import SkillDiscoveryService

        tools = [
            {"id": "git.commit", "content": "Commit", "skill_name": "git", "tool_name": "commit"},
        ]
        discovery = SkillDiscoveryService()
        skills = await discovery._build_skills_from_tools(tools)
        assert len(skills) == 1
        assert skills[0].name == "git"

    async def test_validation_fails_when_skill_name_missing(self):
        """Validation raises when skill_name is null/empty - fail fast."""
        tools = [
            {"id": "git.commit", "content": "Commit", "skill_name": None, "tool_name": "commit"},
        ]
        with pytest.raises(ToolRecordValidationError) as exc_info:
            validate_tool_records(tools)
        assert "skill_name" in str(exc_info.value)


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
class TestIndexListDiscoverIntegration:
    """End-to-end: index_skill_tools → list_all_tools → discover_all."""

    async def test_indexed_skills_produce_multiple_skills_via_discovery(self):
        """index_skill_tools on real skills dir → list_all_tools → discover_all must yield > 1 skill."""
        from omni.foundation.config.skills import SKILLS_DIR

        skills_dir = SKILLS_DIR()
        if not skills_dir.exists():
            pytest.skip("SKILLS_DIR not found")
        # Use temp DB to avoid polluting project
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "skills.lance")
            store = RustVectorStore(
                index_path=path,
                dimension=8,
                enable_keyword_index=False,
            )
            count = await store.index_skill_tools(str(skills_dir), "skills")
            if count == 0:
                pytest.skip("No tools indexed (skills dir may be empty)")
            tools = store.list_all_tools()
            assert len(tools) > 0
            unique_skills = {t.get("skill_name") for t in tools}
            unique_skills.discard("unknown")
            assert len(unique_skills) > 1, (
                f"Indexed {count} tools but only {len(unique_skills)} skill(s): {unique_skills}. "
                "Bridge flatten or Rust output may be broken."
            )
            # Discovery path: patch module-level get_vector_store
            from omni.core.skills.discovery import SkillDiscoveryService

            discovery = SkillDiscoveryService()
            with patch("omni.core.skills.discovery.get_vector_store", return_value=store):
                skills = await discovery.discover_all()
            assert len(skills) > 1, (
                f"discover_all returned {len(skills)} skill(s). Expected > 1. "
                "Check list_all_tools returns flat skill_name, tool_name."
            )
