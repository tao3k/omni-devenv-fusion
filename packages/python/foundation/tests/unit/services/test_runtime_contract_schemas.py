"""Validation tests for newly introduced runtime contract schemas."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _schemas_dir() -> Path:
    return Path(__file__).resolve().parents[6] / "packages" / "shared" / "schemas"


def _load_schema(name: str) -> dict:
    path = _schemas_dir() / name
    assert path.exists(), f"schema missing: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema_name: str, payload: dict) -> None:
    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert not errors, "; ".join(error.message for error in errors)


def test_discover_match_schema_accepts_contract_payload() -> None:
    payload = {
        "tool": "skill.discover",
        "usage": '@omni("skill.discover", {"intent": "<intent: string>"})',
        "score": 0.67,
        "final_score": 0.82,
        "confidence": "high",
        "ranking_reason": "vector=0.91 | keyword=0.11 | final=0.82",
        "input_schema_digest": "sha256:abc123def456",
        "documentation_path": "/tmp/SKILL.md",
    }
    _validate("omni.discover.match.v1.schema.json", payload)


def test_memory_gate_event_schema_accepts_contract_payload() -> None:
    payload = {
        "session_id": "telegram:group-1:user-9",
        "turn_id": 42,
        "memory_id": "mem:9c2",
        "state_before": "active",
        "state_after": "promoted",
        "ttl_score": 0.91,
        "decision": {
            "verdict": "promote",
            "confidence": 0.89,
            "react_evidence_refs": ["react:fix_retry:12"],
            "graph_evidence_refs": ["graph:path:resolve->verify"],
            "omega_factors": ["utility_trend=up"],
            "reason": "High utility and repeated revalidation success",
            "next_action": "promote",
        },
    }
    _validate("omni.memory.gate_event.v1.schema.json", payload)


def test_route_trace_schema_accepts_contract_payload() -> None:
    payload = {
        "session_id": "telegram:group-1:user-9",
        "turn_id": 43,
        "selected_route": "graph",
        "confidence": 0.84,
        "risk_level": "medium",
        "tool_trust_class": "evidence",
        "fallback_applied": False,
        "fallback_policy": "retry_react",
        "tool_chain": ["skill.discover", "knowledge.search"],
        "latency_ms": 327.1,
        "failure_taxonomy": [],
        "injection": {
            "blocks_used": 6,
            "chars_injected": 3120,
            "dropped_by_budget": 1,
        },
    }
    _validate("omni.agent.route_trace.v1.schema.json", payload)


def test_skills_monitor_signals_schema_accepts_contract_payload() -> None:
    payload = {
        "schema": "omni.skills_monitor.signals.v1",
        "retrieval_signals": {
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
        },
        "link_graph_signals": {
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
            }
        },
    }
    _validate("omni.skills_monitor.signals.v1.schema.json", payload)
