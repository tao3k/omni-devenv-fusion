from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("keyword_report_gen", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_keyword_backend_decision_report_helpers() -> None:
    script = Path("scripts/generate_keyword_backend_decision_report.py")
    module = _load_module(script)

    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    data = module._load_snapshot_json(snapshot)
    report = module._compose_report(snapshot, data, None)

    assert "Keyword Backend Decision Report" in report
    assert "Offline Metrics" in report
    assert "Recommendation" in report
