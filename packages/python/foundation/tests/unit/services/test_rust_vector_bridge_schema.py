"""Unit tests for RustVectorStore schema/admin bridge methods."""

from __future__ import annotations

import json

import pytest
from omni.test_kit.fixtures.vector import (
    make_tool_search_payload,
    parametrize_input_schema_variants,
    with_removed_key,
)

from omni.foundation.bridge import rust_vector as rust_vector_module
from omni.foundation.bridge.rust_vector import RustVectorStore
from omni.foundation.services.vector_schema import (
    parse_tool_search_payload,
)


class _StubInner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_table_info(self, table_name: str) -> str:
        self.calls.append(("get_table_info", (table_name,), {}))
        return json.dumps({"version_id": 7, "num_rows": 3})

    def list_versions(self, table_name: str) -> str:
        self.calls.append(("list_versions", (table_name,), {}))
        return json.dumps([{"version_id": 6}, {"version_id": 7}])

    def get_fragment_stats(self, table_name: str) -> str:
        self.calls.append(("get_fragment_stats", (table_name,), {}))
        return json.dumps([{"id": 0, "num_rows": 2}, {"id": 1, "num_rows": 1}])

    def add_columns(self, table_name: str, payload_json: str) -> None:
        self.calls.append(("add_columns", (table_name, payload_json), {}))

    def alter_columns(self, table_name: str, payload_json: str) -> None:
        self.calls.append(("alter_columns", (table_name, payload_json), {}))

    def drop_columns(self, table_name: str, columns: list[str]) -> None:
        self.calls.append(("drop_columns", (table_name, columns), {}))

    def search_tools(
        self,
        table_name: str,
        query_vector,
        query_text,
        limit: int,
        threshold: float,
        confidence_profile_json: str | None = None,
        rerank: bool = True,
    ):
        self.calls.append(
            (
                "search_tools",
                (
                    table_name,
                    query_vector,
                    query_text,
                    limit,
                    threshold,
                    confidence_profile_json,
                    rerank,
                ),
                {},
            )
        )
        return []

    def get_skill_index(self, base_path: str) -> str:
        self.calls.append(("get_skill_index", (base_path,), {}))
        return json.dumps(
            [
                {
                    "name": "git",
                    "tools": [{"name": "git.commit"}, {"name": "status"}],
                }
            ]
        )

    def replace_documents(
        self,
        table_name: str,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        metadatas: list[str],
    ) -> None:
        self.calls.append(
            ("replace_documents", (table_name, ids, vectors, contents, metadatas), {})
        )

    def drop_table(self, table_name: str) -> None:
        self.calls.append(("drop_table", (table_name,), {}))

    def add_documents(
        self,
        table_name: str,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        metadatas: list[str],
    ) -> None:
        self.calls.append(("add_documents", (table_name, ids, vectors, contents, metadatas), {}))

    def index_skill_tools_dual(
        self,
        base_path: str,
        skills_table: str,
        router_table: str,
    ) -> tuple[int, int]:
        self.calls.append(("index_skill_tools_dual", (base_path, skills_table, router_table), {}))
        return 11, 11


class _StubInnerToolPayload(_StubInner):
    def __init__(self, payloads: list[dict]) -> None:
        super().__init__()
        self._payloads = payloads

    def search_tools(
        self,
        table_name: str,
        query_vector,
        query_text,
        limit: int,
        threshold: float,
        confidence_profile_json: str | None = None,
        rerank: bool = True,
    ):
        self.calls.append(
            (
                "search_tools",
                (
                    table_name,
                    query_vector,
                    query_text,
                    limit,
                    threshold,
                    confidence_profile_json,
                    rerank,
                ),
                {},
            )
        )
        return list(self._payloads)


@pytest.fixture
def store() -> RustVectorStore:
    # Bypass __init__ to avoid requiring compiled extension during unit tests.
    s = RustVectorStore.__new__(RustVectorStore)
    s._inner = _StubInner()
    return s


@pytest.mark.asyncio
async def test_admin_methods_parse_json(store: RustVectorStore) -> None:
    info = await store.get_table_info("skills")
    versions = await store.list_versions("skills")
    fragments = await store.get_fragment_stats("skills")

    assert info == {"version_id": 7, "num_rows": 3}
    assert versions == [{"version_id": 6}, {"version_id": 7}]
    assert fragments == [{"id": 0, "num_rows": 2}, {"id": 1, "num_rows": 1}]


@pytest.mark.asyncio
async def test_schema_evolution_payload_contract(store: RustVectorStore) -> None:
    ok_add = await store.add_columns(
        "skills",
        columns=[
            {"name": "custom_note", "data_type": "Utf8", "nullable": True},
        ],
    )
    ok_alter = await store.alter_columns(
        "skills",
        alterations=[
            {"Rename": {"path": "custom_note", "new_name": "custom_label"}},
        ],
    )
    ok_drop = await store.drop_columns("skills", ["custom_label"])

    assert ok_add is True
    assert ok_alter is True
    assert ok_drop is True

    calls = store._inner.calls  # type: ignore[attr-defined]
    add_call = next(c for c in calls if c[0] == "add_columns")
    alter_call = next(c for c in calls if c[0] == "alter_columns")
    drop_call = next(c for c in calls if c[0] == "drop_columns")

    add_payload = json.loads(add_call[1][1])
    alter_payload = json.loads(alter_call[1][1])
    assert add_payload == {
        "columns": [{"name": "custom_note", "data_type": "Utf8", "nullable": True}]
    }
    assert alter_payload == {
        "alterations": [{"Rename": {"path": "custom_note", "new_name": "custom_label"}}]
    }
    assert drop_call[1][1] == ["custom_label"]


@pytest.mark.asyncio
async def test_search_tools_rejects_legacy_payload_without_canonical_schema() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload(
        [
            {
                "name": "git.commit",
                "description": "Commit changes",
                "score": 0.91,
                "tool_name": "git.commit",
            }
        ]
    )

    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=5,
        threshold=0.0,
    )

    assert results == []


@pytest.mark.asyncio
async def test_search_tools_accepts_canonical_tool_schema_payload() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload(
        [
            make_tool_search_payload(
                input_schema="{}",
                score=0.92,
                vector_score=0.8,
                keyword_score=0.7,
                final_score=0.94,
            )
        ]
    )

    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=5,
        threshold=0.0,
    )

    assert len(results) == 1
    assert results[0]["schema"] == "omni.vector.tool_search.v1"
    assert results[0]["tool_name"] == "git.commit"
    assert results[0]["vector_score"] == 0.8
    assert results[0]["keyword_score"] == 0.7
    assert isinstance(results[0]["input_schema"], dict)
    assert results[0]["routing_keywords"] == ["git", "commit"]
    assert "keywords" not in results[0]
    assert "description" in results[0]
    assert "description" in results[0]["payload"]


@pytest.mark.asyncio
@parametrize_input_schema_variants()
async def test_search_tools_normalizes_input_schema_object_payload(
    input_schema_value: str | dict[str, object],
) -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload(
        [
            make_tool_search_payload(
                input_schema=input_schema_value,
                score=0.92,
                final_score=0.94,
            )
        ]
    )

    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=5,
        threshold=0.0,
    )
    assert len(results) == 1
    assert results[0]["input_schema"]["type"] == "object"


@pytest.mark.asyncio
async def test_search_tools_accepts_routing_keywords_only_payload() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload(
        [
            make_tool_search_payload(
                name="advanced_tools.smart_find",
                tool_name="advanced_tools.smart_find",
                description="Find files by extension",
                score=0.88,
                final_score=0.89,
                skill_name="advanced_tools",
                file_path="assets/skills/advanced_tools/scripts/search.py",
                routing_keywords=["find", "files", "directory"],
                category="search",
            )
        ]
    )

    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="find python files",
        limit=5,
        threshold=0.0,
    )

    assert len(results) == 1
    assert results[0]["routing_keywords"] == ["find", "files", "directory"]


@pytest.mark.asyncio
async def test_search_tools_returns_empty_on_invalid_confidence_label() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload(
        [
            make_tool_search_payload(
                input_schema="{}",
                score=0.92,
                final_score=0.94,
                confidence="unknown",
            )
        ]
    )

    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=5,
        threshold=0.0,
    )

    assert results == []


def test_get_skill_index_sync_parses_payload(store: RustVectorStore) -> None:
    skills = store.get_skill_index_sync("assets/skills")
    assert len(skills) == 1
    assert skills[0]["name"] == "git"
    assert skills[0]["tools"][0]["name"] == "git.commit"


@pytest.mark.asyncio
async def test_get_skill_index_async_delegates_to_sync(store: RustVectorStore) -> None:
    skills = await store.get_skill_index("assets/skills")
    assert len(skills) == 1
    assert skills[0]["name"] == "git"


@pytest.mark.asyncio
async def test_replace_documents_prefers_native_binding_method() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    stub = _StubInner()
    store._inner = stub

    await store.replace_documents(
        "skills",
        ["id1"],
        [[0.1, 0.2]],
        ["content"],
        ["{}"],
    )

    assert any(c[0] == "replace_documents" for c in stub.calls)


@pytest.mark.asyncio
async def test_index_skill_tools_dual_returns_two_counts() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    stub = _StubInner()
    store._inner = stub

    skills_count, router_count = await store.index_skill_tools_dual(
        "assets/skills", "skills", "router"
    )

    assert skills_count == 11
    assert router_count == 11
    assert any(c[0] == "index_skill_tools_dual" for c in stub.calls)


def test_confidence_profile_json_reads_router_search_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "router.search.active_profile": "precision",
        "router.search.profiles": {
            "precision": {
                "high_threshold": 0.81,
                "medium_threshold": 0.57,
                "high_base": 0.91,
                "high_scale": 0.06,
                "high_cap": 0.98,
                "medium_base": 0.61,
                "medium_scale": 0.28,
                "medium_cap": 0.87,
                "low_floor": 0.11,
            }
        },
    }

    def _fake_get_setting(key: str, default=None):
        return values.get(key, default)

    monkeypatch.setattr("omni.foundation.config.settings.get_setting", _fake_get_setting)
    payload = json.loads(rust_vector_module._confidence_profile_json())

    assert payload == {
        "high_threshold": 0.81,
        "medium_threshold": 0.57,
        "high_base": 0.91,
        "high_scale": 0.06,
        "high_cap": 0.98,
        "medium_base": 0.61,
        "medium_scale": 0.28,
        "medium_cap": 0.87,
        "low_floor": 0.11,
    }


def test_rerank_enabled_prefers_router_search(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {"router.search.rerank": False}

    def _fake_get_setting(key: str, default=None):
        return values.get(key, default)

    monkeypatch.setattr("omni.foundation.config.settings.get_setting", _fake_get_setting)
    assert rust_vector_module._rerank_enabled() is False


def test_rerank_enabled_defaults_to_true(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_setting(key: str, default=None):
        return default

    monkeypatch.setattr("omni.foundation.config.settings.get_setting", _fake_get_setting)
    assert rust_vector_module._rerank_enabled() is True


@pytest.mark.asyncio
async def test_search_tools_passes_confidence_profile_json_to_rust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "router.search.active_profile": "precision",
        "router.search.profiles": {
            "precision": {
                "high_threshold": 0.83,
                "medium_threshold": 0.55,
                "high_base": 0.93,
                "high_scale": 0.03,
                "high_cap": 0.99,
                "medium_base": 0.62,
                "medium_scale": 0.25,
                "medium_cap": 0.88,
                "low_floor": 0.12,
            }
        },
    }

    def _fake_get_setting(key: str, default=None):
        return values.get(key, default)

    monkeypatch.setattr("omni.foundation.config.settings.get_setting", _fake_get_setting)

    store = RustVectorStore.__new__(RustVectorStore)
    stub = _StubInnerToolPayload([])
    store._inner = stub

    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=3,
        threshold=0.2,
    )
    assert results == []

    search_call = next(c for c in stub.calls if c[0] == "search_tools")
    confidence_profile_json = search_call[1][5]
    payload = json.loads(confidence_profile_json)
    assert payload["high_threshold"] == 0.83
    assert payload["medium_threshold"] == 0.55
    assert payload["low_floor"] == 0.12
    assert search_call[1][6] is True


@pytest.mark.asyncio
async def test_search_tools_prefers_explicit_confidence_profile_override() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    stub = _StubInnerToolPayload([])
    store._inner = stub

    override = {
        "high_threshold": 0.9,
        "medium_threshold": 0.6,
        "high_base": 0.95,
        "high_scale": 0.01,
        "high_cap": 0.99,
        "medium_base": 0.7,
        "medium_scale": 0.2,
        "medium_cap": 0.9,
        "low_floor": 0.08,
    }

    await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=3,
        threshold=0.2,
        confidence_profile=override,
    )

    search_call = next(c for c in stub.calls if c[0] == "search_tools")
    confidence_profile_json = search_call[1][5]
    payload = json.loads(confidence_profile_json)
    assert payload == override
    assert search_call[1][6] is True


@pytest.mark.asyncio
async def test_search_tools_passes_explicit_rerank_override() -> None:
    store = RustVectorStore.__new__(RustVectorStore)
    stub = _StubInnerToolPayload([])
    store._inner = stub

    await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=3,
        threshold=0.2,
        rerank=False,
    )

    search_call = next(c for c in stub.calls if c[0] == "search_tools")
    assert search_call[1][6] is False


@pytest.mark.asyncio
async def test_search_tools_and_parser_keep_core_fields_consistent() -> None:
    canonical = make_tool_search_payload(
        name="advanced_tools.smart_find",
        tool_name="advanced_tools.smart_find",
        description="Find files by extension",
        input_schema='{"type":"object"}',
        score=0.88,
        vector_score=0.72,
        keyword_score=0.66,
        final_score=0.89,
        confidence="high",
        skill_name="advanced_tools",
        file_path="assets/skills/advanced_tools/scripts/search.py",
        routing_keywords=["find", "files", "directory"],
        intents=["Locate files"],
        category="search",
    )

    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload([canonical])
    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="find python files",
        limit=5,
        threshold=0.0,
    )

    parsed = parse_tool_search_payload(canonical)
    assert len(results) == 1
    assert results[0]["schema"] == parsed.schema_version
    assert results[0]["tool_name"] == parsed.tool_name
    assert results[0]["description"] == parsed.description
    assert results[0]["routing_keywords"] == parsed.routing_keywords
    expected_router = parsed.to_router_result()
    assert results[0]["payload"]["description"] == expected_router["payload"]["description"]
    assert (
        results[0]["payload"]["metadata"]["tool_name"]
        == expected_router["payload"]["metadata"]["tool_name"]
    )


@pytest.mark.asyncio
async def test_search_tools_rejects_legacy_keywords_field() -> None:
    legacy = with_removed_key(make_tool_search_payload(), "routing_keywords")
    legacy["keywords"] = ["git", "commit"]

    store = RustVectorStore.__new__(RustVectorStore)
    store._inner = _StubInnerToolPayload([legacy])
    results = await store.search_tools(
        table_name="skills",
        query_vector=[0.1, 0.2],
        query_text="git commit",
        limit=5,
        threshold=0.0,
    )
    assert results == []
