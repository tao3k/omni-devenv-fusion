from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    script_path = Path("scripts/run_keyword_backend_multi_model_batches.py")
    spec = importlib.util.spec_from_file_location("keyword_multi_model_batches", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_merge_model_reports() -> None:
    mod = _load_module()
    b0 = {
        "snapshot": "snap",
        "models": ["m1", "m2"],
        "skipped_models": {"m2": "probe_failed_or_empty_response"},
        "reports": {
            "m1": {
                "llm_duel_details": [
                    {
                        "winner": "tantivy",
                        "reliable": True,
                        "confidence": 80,
                        "fallback_used": False,
                    },
                    {"winner": "tie", "reliable": False, "confidence": 10, "fallback_used": False},
                ]
            }
        },
    }
    b1 = {
        "snapshot": "snap",
        "models": ["m1", "m2"],
        "skipped_models": {},
        "reports": {
            "m1": {
                "llm_duel_details": [
                    {
                        "winner": "lance_fts",
                        "reliable": True,
                        "confidence": 75,
                        "fallback_used": True,
                    },
                ]
            }
        },
    }
    merged = mod._merge_model_reports([b0, b1])
    assert merged["best_model_by_reliability"] == "m1"
    assert merged["reports"]["m1"]["queries_evaluated"] == 3
    summary = merged["reports"]["m1"]["llm_duel_summary"]
    assert summary["tantivy_wins"] == 1
    assert summary["lance_fts_wins"] == 1
    assert summary["reliable_samples"] == 2
    assert summary["fallback_used_samples"] == 1
