"""Tests for omni.rag.retrieval.response helpers."""

from __future__ import annotations

from omni.rag.retrieval import (
    build_recall_chunked_response,
    build_recall_error_response,
    build_recall_search_response,
    build_status_error_response,
    build_status_message_response,
    extract_graph_confidence,
    override_retrieval_plan_mode,
)


def test_build_recall_search_response_shapes_payload() -> None:
    payload = build_recall_search_response(
        query="architecture",
        keywords=["graph"],
        collection="knowledge_chunks",
        preview=True,
        retrieval_mode="hybrid",
        retrieval_path="graph_only",
        retrieval_reason="graph_sufficient",
        graph_backend="wendao",
        graph_hit_count=2,
        graph_confidence_score=0.88,
        graph_confidence_level="high",
        retrieval_plan_schema_id="https://schemas.omni.dev/plan.schema.json",
        retrieval_plan={"selected_mode": "graph_only"},
        results=[{"content": "x"}],
    )
    assert payload["status"] == "success"
    assert payload["query"] == "architecture"
    assert payload["keywords"] == ["graph"]
    assert payload["found"] == 1
    assert payload["retrieval_path"] == "graph_only"
    assert payload["graph_confidence_level"] == "high"
    assert payload["retrieval_plan_schema_id"] == "https://schemas.omni.dev/plan.schema.json"


def test_build_recall_search_response_handles_empty_inputs() -> None:
    payload = build_recall_search_response(
        query="q",
        keywords=None,
        collection="knowledge_chunks",
        preview=False,
        retrieval_mode="vector_only",
        retrieval_path="vector_only",
        retrieval_reason="vector_default",
        graph_backend="",
        graph_hit_count=0,
        graph_confidence_score=0.0,
        graph_confidence_level="none",
        retrieval_plan_schema_id="",
        retrieval_plan=None,
        results=None,
    )
    assert payload["keywords"] == []
    assert payload["found"] == 0
    assert payload["retrieval_plan_schema_id"] is None


def test_build_recall_error_response_shapes_payload() -> None:
    payload = build_recall_error_response(query="q", error="boom")
    assert payload == {
        "query": "q",
        "status": "error",
        "error": "boom",
        "results": [],
    }


def test_build_recall_chunked_response_shapes_payload() -> None:
    payload = build_recall_chunked_response(
        query="q",
        status="success",
        error=None,
        preview_results=[{"source": "doc.md"}],
        batches=[[{"id": 1}], [{"id": 2}]],
        results=[{"id": 1}, {"id": 2}],
    )
    assert payload == {
        "query": "q",
        "status": "success",
        "error": None,
        "preview_results": [{"source": "doc.md"}],
        "batches": [[{"id": 1}], [{"id": 2}]],
        "all_chunks_count": 2,
        "results": [{"id": 1}, {"id": 2}],
    }


def test_build_status_message_response_shapes_payload() -> None:
    payload = build_status_message_response(
        status="unavailable",
        message="Vector store not initialized.",
        extra={"collection": "knowledge_chunks"},
    )
    assert payload == {
        "status": "unavailable",
        "message": "Vector store not initialized.",
        "collection": "knowledge_chunks",
    }


def test_build_status_error_response_shapes_payload() -> None:
    payload = build_status_error_response(
        error="boom",
        extra={"collection": "knowledge_chunks"},
    )
    assert payload == {
        "status": "error",
        "error": "boom",
        "collection": "knowledge_chunks",
    }


def test_extract_graph_confidence_defaults_and_mapping() -> None:
    score, level = extract_graph_confidence(None)
    assert score == 0.0
    assert level == "none"

    score2, level2 = extract_graph_confidence(
        {
            "graph_confidence_score": "0.42",
            "graph_confidence_level": "medium",
        }
    )
    assert score2 == 0.42
    assert level2 == "medium"


def test_override_retrieval_plan_mode_copies_and_overrides() -> None:
    original = {"schema": "x", "selected_mode": "graph_only", "reason": "graph_sufficient"}
    updated = override_retrieval_plan_mode(
        original,
        selected_mode="vector_only",
        reason="graph_empty_fallback_vector",
    )
    assert updated is not None
    assert original["selected_mode"] == "graph_only"
    assert updated["selected_mode"] == "vector_only"
    assert updated["reason"] == "graph_empty_fallback_vector"
    assert override_retrieval_plan_mode(None, selected_mode="v", reason="r") is None
