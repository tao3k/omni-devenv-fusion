from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path


def _load_module():
    script_path = Path("scripts/generate_keyword_backend_statistical_report.py")
    spec = importlib.util.spec_from_file_location("keyword_backend_stat_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_statistical_report_builds_for_v4_snapshot() -> None:
    mod = _load_module()
    random.seed(42)
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap"
    )
    data = mod._load_snapshot(snapshot)
    report = mod._build_report(snapshot, data)

    assert "Keyword Backend Statistical Report" in report
    assert "Query count: `120`" in report
    assert "Global Statistics (Tantivy - Lance FTS)" in report
    assert "Default backend: `Tantivy`" in report
    assert "| Scene | Queries |" in report


def test_metric_stats_handles_ties_and_wins() -> None:
    mod = _load_module()
    random.seed(7)
    rows = [
        {"tantivy": {"p_at_5": "0.4"}, "lance_fts": {"p_at_5": "0.2"}},
        {"tantivy": {"p_at_5": "0.2"}, "lance_fts": {"p_at_5": "0.2"}},
        {"tantivy": {"p_at_5": "0.5"}, "lance_fts": {"p_at_5": "0.3"}},
    ]
    stats = mod._metric_stats(rows, "p_at_5")
    assert stats.wins == 2
    assert stats.losses == 0
    assert stats.ties == 1
    assert stats.mean_delta > 0
