"""Tests for omni.foundation.api.skills_monitor_signals_schema."""

from __future__ import annotations

import pytest

import omni.foundation.api.skills_monitor_signals_schema as skills_monitor_signals_schema
from omni.foundation.api.skills_monitor_signals_schema import (
    build_payload,
    get_schema_id,
    validate,
    validate_signals,
)


def _retrieval_signals() -> dict:
    return {
        "row_budget": {
            "count": 2,
            "query_count": 1,
            "backend_count": 1,
            "rows_fetched_sum": 6,
            "rows_parsed_sum": 6,
            "rows_input_sum": 4,
            "rows_returned_sum": 4,
            "rows_capped_sum": 0,
            "rows_parse_dropped_sum": 0,
            "memory": {
                "observed_count": 2,
                "rss_delta_sum": 10.5,
                "rss_peak_delta_sum": 11.0,
                "rss_delta_max": 10.0,
                "rss_peak_delta_max": 10.2,
            },
            "modes": {
                "semantic": {
                    "count": 1,
                    "rows_returned": 4,
                    "rows_capped": 0,
                }
            },
            "latest": {
                "phase": "retrieval.rows.query",
                "mode": "semantic",
                "collection": "knowledge_chunks",
                "fetch_limit": 4,
                "rows_fetched": None,
                "rows_parsed": None,
                "rows_input": 4,
                "rows_returned": 4,
                "rows_capped": 0,
                "rows_parse_dropped": None,
            },
        }
    }


def _link_graph_signals() -> dict:
    return {
        "policy_search": {
            "count": 1,
            "timeouts": 0,
            "buckets": {"short": 1},
            "latest": {
                "timeout_s": 2.55,
                "timeout_bucket": "short",
                "backend": "wendao",
                "timed_out": False,
            },
        },
        "proximity_fetch": {
            "count": 1,
            "skipped": 0,
            "timed_out": 0,
            "reasons": {},
        },
        "index_refresh": {
            "observed": {
                "total": 3,
                "plan": 1,
                "delta_apply": 1,
                "full_rebuild": 1,
            },
            "plan": {
                "count": 1,
                "strategies": {"delta": 1},
                "reasons": {"delta_requested": 1},
                "force_full_true": 0,
                "changed_count_sum": 2,
                "threshold": {"max": 256},
                "latest": {
                    "strategy": "delta",
                    "reason": "delta_requested",
                    "changed_count": 2,
                    "threshold": 256,
                    "force_full": False,
                },
            },
            "delta_apply": {
                "count": 1,
                "success": 1,
                "failed": 0,
                "changed_count_sum": 2,
                "latest": {"success": True, "changed_count": 2},
            },
            "full_rebuild": {
                "count": 1,
                "success": 1,
                "failed": 0,
                "reasons": {"delta_failed_fallback": 1},
                "changed_count_sum": 2,
                "latest": {
                    "success": True,
                    "reason": "delta_failed_fallback",
                    "changed_count": 2,
                },
            },
        },
        "graph_stats": {
            "count": 1,
            "sources": {"probe": 1},
            "cache_hit_true": 0,
            "fresh_true": 1,
            "refresh_scheduled": 0,
            "age_ms": {"avg": 0.0, "max": 0},
            "latest": {
                "source": "probe",
                "cache_hit": False,
                "fresh": True,
                "age_ms": 0,
                "refresh_scheduled": False,
                "total_notes": 337,
            },
        },
    }


def test_build_payload_roundtrip() -> None:
    payload = build_payload(
        retrieval_signals=_retrieval_signals(),
        link_graph_signals=_link_graph_signals(),
    )
    validate(payload)
    assert payload["schema"] == "omni.skills_monitor.signals.v1"


def test_validate_signals_allows_nulls() -> None:
    validate_signals(
        retrieval_signals=None,
        link_graph_signals=None,
    )


def test_get_schema_id() -> None:
    schema_id = get_schema_id()
    assert schema_id.endswith("/omni.skills_monitor.signals.v1.schema.json")


def test_validate_rejects_unknown_retrieval_property() -> None:
    payload = build_payload(
        retrieval_signals=_retrieval_signals(),
        link_graph_signals=None,
    )
    payload["retrieval_signals"]["row_budget"]["unexpected"] = 1
    with pytest.raises(ValueError, match=r"retrieval_signals"):
        validate(payload)


def test_validate_rejects_unknown_link_graph_property() -> None:
    payload = build_payload(
        retrieval_signals=None,
        link_graph_signals=_link_graph_signals(),
    )
    payload["link_graph_signals"]["policy_search"]["unexpected"] = 1
    with pytest.raises(ValueError, match=r"link_graph_signals"):
        validate(payload)


def test_get_validator_raises_when_schema_file_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_monitor_signals_schema.get_validator.cache_clear()
    missing_path = tmp_path / "missing.schema.json"
    monkeypatch.setattr(skills_monitor_signals_schema, "get_schema_path", lambda: missing_path)
    with pytest.raises(FileNotFoundError, match="skills monitor signals schema not found"):
        skills_monitor_signals_schema.get_validator()
    skills_monitor_signals_schema.get_validator.cache_clear()
