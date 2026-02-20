"""Reusable vector payload fixtures and parametrization helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


def make_tool_search_payload(
    **overrides: Any,
) -> dict[str, Any]:
    """Build a canonical omni.vector.tool_search.v1 payload for tests."""
    payload: dict[str, Any] = {
        "schema": "omni.vector.tool_search.v1",
        "name": "git.commit",
        "description": "Commit changes",
        "input_schema": {"type": "object"},
        "score": 0.91,
        "vector_score": 0.81,
        "keyword_score": 0.74,
        "final_score": 0.93,
        "confidence": "high",
        "skill_name": "git",
        "tool_name": "git.commit",
        "file_path": "assets/skills/git/scripts/commit.py",
        "routing_keywords": ["git", "commit"],
        "intents": [],
        "category": "git",
        "parameters": [],
    }
    payload.update(overrides)
    return payload


def make_vector_payload(**overrides: Any) -> dict[str, Any]:
    """Build a canonical omni.vector.search.v1 payload for tests."""
    payload: dict[str, Any] = {
        "schema": "omni.vector.search.v1",
        "id": "doc-1",
        "content": "hello",
        "metadata": {"k": "v"},
        "distance": 0.2,
        "score": 0.8333,
    }
    payload.update(overrides)
    return payload


def make_hybrid_payload(**overrides: Any) -> dict[str, Any]:
    """Build a canonical omni.vector.hybrid.v1 payload for tests."""
    payload: dict[str, Any] = {
        "schema": "omni.vector.hybrid.v1",
        "id": "doc-1",
        "content": "hello",
        "metadata": {"k": "v"},
        "source": "hybrid",
        "score": 0.8,
        "vector_score": 0.3,
        "keyword_score": 0.6,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def tool_search_payload_factory() -> Callable[..., dict[str, Any]]:
    """Factory fixture to build tool search payloads with overrides."""

    def _factory(**overrides: Any) -> dict[str, Any]:
        return make_tool_search_payload(**overrides)

    return _factory


@pytest.fixture
def vector_payload_factory() -> Callable[..., dict[str, Any]]:
    """Factory fixture to build vector payloads with overrides."""

    def _factory(**overrides: Any) -> dict[str, Any]:
        return make_vector_payload(**overrides)

    return _factory


@pytest.fixture
def hybrid_payload_factory() -> Callable[..., dict[str, Any]]:
    """Factory fixture to build hybrid payloads with overrides."""

    def _factory(**overrides: Any) -> dict[str, Any]:
        return make_hybrid_payload(**overrides)

    return _factory


def parametrize_input_schema_variants(
    arg_name: str = "input_schema_value",
) -> pytest.MarkDecorator:
    """Parametrize a test with the supported input_schema encodings."""
    return pytest.mark.parametrize(
        arg_name,
        [
            '{"type":"object","properties":{"message":{"type":"string"}}}',
            '"{\\"type\\":\\"object\\"}"',
            {"type": "object"},
        ],
        ids=["json-string", "double-encoded-json-string", "json-object"],
    )


def with_removed_key(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a copy of payload without a top-level key."""
    copied = deepcopy(payload)
    copied.pop(key, None)
    return copied


def make_router_result_payload(
    **overrides: Any,
) -> dict[str, Any]:
    """Build a canonical router result payload for CLI/router tests (omni.router.route_test.v1 result item)."""
    payload: dict[str, Any] = {
        "id": "git.commit",
        "name": "git.commit",
        "description": "Commit changes",
        "skill_name": "git",
        "tool_name": "git.commit",
        "command": "commit",
        "score": 0.82,
        "final_score": 0.91,
        "confidence": "high",
        "routing_keywords": ["git", "commit"],
        "input_schema": {"type": "object"},
        "payload": {
            "type": "command",
            "description": "Commit changes",
            "metadata": {
                "tool_name": "git.commit",
                "routing_keywords": ["git", "commit"],
                "input_schema": {"type": "object"},
            },
        },
    }
    payload.update(overrides)
    return payload


def parametrize_route_intent_queries(
    query_name: str = "query",
    expected_tool_name: str = "expected_tool_name",
) -> pytest.MarkDecorator:
    """Parametrize common routing intents across tests (including research/URL intents)."""
    return pytest.mark.parametrize(
        f"{query_name},{expected_tool_name}",
        [
            ("git commit", "git.commit"),
            ("find python files in current directory", "advanced_tools.smart_find"),
            (
                "Help me research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl",
                "researcher.run_research_graph",
            ),
            (
                "帮我研究一下 https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl",
                "researcher.run_research_graph",
            ),
            ("crawl this URL and extract markdown", "crawl4ai.crawl_url"),
        ],
        ids=[
            "git-commit-intent",
            "file-discovery-intent",
            "research-url-en",
            "research-url-zh",
            "crawl-url-intent",
        ],
    )


ROUTE_TEST_SCHEMA_V1 = "omni.router.route_test.v1"


def make_route_test_payload(
    *,
    query: str = "git commit",
    results: list[dict[str, Any]] | None = None,
    stats: dict[str, Any] | None = None,
    threshold: float = 0.4,
    limit: int = 5,
    confidence_profile: dict[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a canonical route test JSON payload (omni route test --json) for contract tests."""
    if results is None:
        results = [make_router_result_payload()]
    if confidence_profile is None:
        confidence_profile = {"name": "balanced", "source": "active-profile"}
    stats_payload: dict[str, Any] = {
        "semantic_weight": None,
        "keyword_weight": None,
        "rrf_k": None,
        "strategy": None,
    }
    if stats:
        stats_payload.update(
            {
                "semantic_weight": stats.get("semantic_weight"),
                "keyword_weight": stats.get("keyword_weight"),
                "rrf_k": stats.get("rrf_k"),
                "strategy": stats.get("strategy"),
            }
        )
    payload: dict[str, Any] = {
        "schema": ROUTE_TEST_SCHEMA_V1,
        "query": query,
        "count": len(results),
        "threshold": threshold,
        "limit": limit,
        "confidence_profile": confidence_profile,
        "stats": stats_payload,
        "results": results,
    }
    payload.update(overrides)
    return payload


def make_db_search_vector_result_list(
    count: int = 1,
    **item_overrides: Any,
) -> list[dict[str, Any]]:
    """Build a canonical list of omni.vector.search.v1 items (db search vector response)."""
    return [make_vector_payload(**item_overrides) for _ in range(count)]


def make_db_search_hybrid_result_list(
    count: int = 1,
    **item_overrides: Any,
) -> list[dict[str, Any]]:
    """Build a canonical list of omni.vector.hybrid.v1 items (db search hybrid response)."""
    default_metadata: dict[str, Any] = {
        "k": "v",
        "debug_scores": {"vector_score": 0.3, "keyword_score": 0.6},
    }
    if "metadata" not in item_overrides:
        item_overrides = {**item_overrides, "metadata": default_metadata}
    return [make_hybrid_payload(**item_overrides) for _ in range(count)]


__all__ = [
    "ROUTE_TEST_SCHEMA_V1",
    "hybrid_payload_factory",
    "make_db_search_hybrid_result_list",
    "make_db_search_vector_result_list",
    "make_hybrid_payload",
    "make_route_test_payload",
    "make_router_result_payload",
    "make_tool_search_payload",
    "make_vector_payload",
    "parametrize_input_schema_variants",
    "parametrize_route_intent_queries",
    "tool_search_payload_factory",
    "vector_payload_factory",
    "with_removed_key",
]
