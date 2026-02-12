from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    script_path = Path("scripts/generate_keyword_backend_multi_model_report.py")
    spec = importlib.util.spec_from_file_location("keyword_multi_model_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_markdown_multi_model_summary() -> None:
    mod = _load_module()
    payload = {
        "snapshot": "snap-path",
        "models": ["m1", "m2"],
        "evaluated_models": ["m1", "m2"],
        "skipped_models": {},
        "best_model_by_reliability": "m1",
        "reports": {
            "m1": {
                "queries_evaluated": 10,
                "llm_duel_summary": {
                    "tantivy_win_rate": 0.4,
                    "lance_fts_win_rate": 0.1,
                    "reliable_ratio": 0.2,
                    "high_confidence_samples": 3,
                    "fallback_usage_ratio": 0.1,
                },
            },
            "m2": {
                "queries_evaluated": 10,
                "llm_duel_summary": {
                    "tantivy_win_rate": 0.2,
                    "lance_fts_win_rate": 0.2,
                    "reliable_ratio": 0.1,
                    "high_confidence_samples": 1,
                    "fallback_usage_ratio": 0.3,
                },
            },
        },
    }
    md = mod._build_markdown(payload, Path("/tmp/in.json"))
    assert "Keyword Backend Multi-Model Report" in md
    assert "| m1 | 10 | 0.4000 | 0.1000 | 0.2000 | 3 | 0.1000 |" in md
    assert "Best model by reliability: `m1`" in md


def test_build_markdown_with_skipped_models() -> None:
    mod = _load_module()
    payload = {
        "snapshot": "snap-path",
        "models": ["m1", "m2"],
        "evaluated_models": ["m1"],
        "skipped_models": {"m2": "probe_failed_or_empty_response"},
        "best_model_by_reliability": "m1",
        "reports": {
            "m1": {
                "queries_evaluated": 5,
                "llm_duel_summary": {
                    "tantivy_win_rate": 0.2,
                    "lance_fts_win_rate": 0.0,
                    "reliable_ratio": 0.2,
                    "high_confidence_samples": 1,
                    "fallback_usage_ratio": 0.0,
                },
            }
        },
    }
    md = mod._build_markdown(payload, Path("/tmp/in.json"))
    assert "## Recommendation" in md
    assert "- Keep `m1` as primary judge model for now." in md
    assert "## Skipped Models" in md
    assert "`m2`: `probe_failed_or_empty_response`" in md
