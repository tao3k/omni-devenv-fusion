"""Tests for common response payload builders."""

from __future__ import annotations

from omni.foundation.api.response_payloads import (
    build_error_response,
    build_status_error_response,
    build_status_message_response,
    build_success_error_response,
)


def test_build_status_message_response_with_extra() -> None:
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


def test_build_status_error_response_default_status() -> None:
    payload = build_status_error_response(
        error="boom",
        extra={"collection": "knowledge_chunks"},
    )
    assert payload == {
        "status": "error",
        "error": "boom",
        "collection": "knowledge_chunks",
    }


def test_build_success_error_response_shapes_payload() -> None:
    payload = build_success_error_response(
        error="boom",
        extra={"query": "x"},
    )
    assert payload == {
        "success": False,
        "error": "boom",
        "query": "x",
    }


def test_build_error_response_shapes_payload() -> None:
    payload = build_error_response(
        error="boom",
        extra={"source": "resource"},
    )
    assert payload == {
        "error": "boom",
        "source": "resource",
    }
