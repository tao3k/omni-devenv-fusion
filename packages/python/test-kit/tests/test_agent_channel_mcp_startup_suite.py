"""Tests for scripts/channel/test_omni_agent_mcp_startup_suite.py."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from types import ModuleType


def _load_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_mcp_startup_suite.py"
    spec = importlib.util.spec_from_file_location("omni_agent_mcp_startup_suite", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_args(**overrides: object) -> argparse.Namespace:
    root = get_project_root()
    defaults: dict[str, object] = {
        "hot_rounds": 20,
        "hot_parallel": 8,
        "cold_rounds": 8,
        "cold_parallel": 4,
        "startup_timeout_secs": 60,
        "cooldown_secs": 0.2,
        "mcp_host": "127.0.0.1",
        "mcp_port": 3002,
        "mcp_config": ".mcp.json",
        "health_url": "",
        "strict_health_check": False,
        "no_strict_health_check": False,
        "health_probe_interval_secs": 0.2,
        "health_probe_timeout_secs": 1.0,
        "restart_mcp_cmd": "",
        "allow_mcp_restart": False,
        "restart_mcp_settle_secs": 0.2,
        "restart_health_timeout_secs": 30,
        "restart_no_embedding": False,
        "skip_hot": False,
        "skip_cold": False,
        "quality_max_failed_probes": 0,
        "quality_max_hot_p95_ms": 1200.0,
        "quality_max_cold_p95_ms": 1500.0,
        "quality_min_health_samples": 1,
        "quality_max_health_failure_rate": 0.02,
        "quality_max_health_p95_ms": 350.0,
        "quality_baseline_json": "",
        "quality_max_hot_p95_regression_ratio": 0.5,
        "quality_max_cold_p95_regression_ratio": 0.5,
        "project_root": str(root),
        "output_json": ".run/reports/omni-agent-mcp-startup-suite.json",
        "output_markdown": ".run/reports/omni-agent-mcp-startup-suite.md",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_build_mode_specs_defaults_to_hot_only_when_restart_not_allowed() -> None:
    module = _load_module()
    config = module.build_config(_make_args())
    specs = module.build_mode_specs(config)
    assert [spec.name for spec in specs] == ["hot"]


def test_build_mode_specs_honors_skip_flags() -> None:
    module = _load_module()
    cold_only = module.build_mode_specs(
        module.build_config(_make_args(skip_hot=True, allow_mcp_restart=True))
    )
    assert [spec.name for spec in cold_only] == ["cold"]

    hot_only = module.build_mode_specs(module.build_config(_make_args(skip_cold=True)))
    assert [spec.name for spec in hot_only] == ["hot"]


def test_build_mode_specs_includes_cold_when_restart_allowed() -> None:
    module = _load_module()
    config = module.build_config(_make_args(allow_mcp_restart=True))
    specs = module.build_mode_specs(config)
    assert [spec.name for spec in specs] == ["hot", "cold"]
    cold_spec = specs[1]
    assert cold_spec.restart_mcp_cmd is not None
    assert "restart-omni-mcp.sh" in cold_spec.restart_mcp_cmd
    assert "--port 3002" in cold_spec.restart_mcp_cmd


def test_build_config_rejects_cold_only_without_restart_permission() -> None:
    module = _load_module()
    try:
        module.build_config(_make_args(skip_hot=True))
    except ValueError as error:
        assert "cold-only startup suite requires MCP restart permission" in str(error)
    else:
        raise AssertionError("Expected ValueError for cold-only run without restart permission")


def test_build_restart_command_uses_explicit_override() -> None:
    module = _load_module()
    config = module.build_config(_make_args(restart_mcp_cmd="just mcp-restart", skip_hot=True))
    assert module.build_restart_command(config) == "just mcp-restart"


def test_render_markdown_contains_mode_rows() -> None:
    module = _load_module()
    report = {
        "started_at": "2026-02-19T00:00:00+00:00",
        "finished_at": "2026-02-19T00:01:00+00:00",
        "duration_ms": 60000,
        "overall_passed": True,
        "passed_modes": 2,
        "failed_modes": 0,
        "modes": [
            {
                "mode": "hot",
                "passed": True,
                "rounds": 20,
                "parallel": 8,
                "summary": {
                    "success_avg_startup_ms": 300.0,
                    "success_p95_startup_ms": 420.0,
                    "health_failure_rate": 0.01,
                    "health_p95_latency_ms": 120.0,
                },
                "json_report": ".run/reports/hot.json",
            },
            {
                "mode": "cold",
                "passed": True,
                "rounds": 8,
                "parallel": 4,
                "summary": {
                    "success_avg_startup_ms": 500.0,
                    "success_p95_startup_ms": 620.0,
                    "health_failure_rate": 0.00,
                    "health_p95_latency_ms": 140.0,
                },
                "json_report": ".run/reports/cold.json",
            },
        ],
    }
    markdown = module.render_markdown(report)
    assert "MCP Startup Suite Report" in markdown
    assert "| hot | PASS | 20 | 8 | 300.0 | 420.0 | 0 | 1.00% | 120.0 |" in markdown
    assert "| cold | PASS | 8 | 4 | 500.0 | 620.0 | 0 | 0.00% | 140.0 |" in markdown


def test_run_mode_fails_fast_when_pre_restart_command_fails() -> None:
    module = _load_module()
    config = module.build_config(
        _make_args(
            skip_hot=True,
            restart_mcp_cmd="sh -c 'exit 7'",
        )
    )
    mode = module.build_mode_specs(config)[0]
    result = module.run_mode(config, mode)
    assert result["mode"] == "cold"
    assert result["passed"] is False
    assert result["pre_restart_failed"] is True
    assert result["return_code"] == 7


def test_evaluate_quality_gates_fails_when_hot_p95_exceeds_threshold() -> None:
    module = _load_module()
    config = module.build_config(_make_args(quality_max_hot_p95_ms=300.0))
    modes = [
        {
            "mode": "hot",
            "summary": {
                "failed": 0,
                "success_p95_startup_ms": 420.0,
                "health_samples_total": 10,
                "health_failure_rate": 0.0,
                "health_p95_latency_ms": 100.0,
            },
        }
    ]
    quality = module.evaluate_quality_gates(config, modes)
    assert quality["passed"] is False
    assert any("hot: p95" in violation for violation in quality["violations"])


def test_evaluate_quality_gates_fails_when_baseline_regression_exceeds_ratio(tmp_path) -> None:
    module = _load_module()
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        """
{
  "modes": [
    {"mode": "hot", "summary": {"success_p95_startup_ms": 100.0}}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    config = module.build_config(
        _make_args(
            quality_baseline_json=str(baseline_path),
            quality_max_hot_p95_regression_ratio=0.1,
        )
    )
    modes = [
        {
            "mode": "hot",
            "summary": {
                "failed": 0,
                "success_p95_startup_ms": 130.0,
                "health_samples_total": 10,
                "health_failure_rate": 0.0,
                "health_p95_latency_ms": 100.0,
            },
        }
    ]
    quality = module.evaluate_quality_gates(config, modes)
    assert quality["passed"] is False
    assert any("hot: p95 regression" in violation for violation in quality["violations"])


def test_evaluate_quality_gates_fails_when_health_failure_rate_exceeds_threshold() -> None:
    module = _load_module()
    config = module.build_config(_make_args(quality_max_health_failure_rate=0.05))
    modes = [
        {
            "mode": "hot",
            "summary": {
                "failed": 0,
                "success_p95_startup_ms": 100.0,
                "health_samples_total": 20,
                "health_failure_rate": 0.25,
                "health_p95_latency_ms": 120.0,
            },
        }
    ]
    quality = module.evaluate_quality_gates(config, modes)
    assert quality["passed"] is False
    assert any("health failure rate" in violation for violation in quality["violations"])
