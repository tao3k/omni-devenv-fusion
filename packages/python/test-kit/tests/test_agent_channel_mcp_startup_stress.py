"""Tests for scripts/channel/test_omni_agent_mcp_startup_stress.py."""

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
    script_path = root / "scripts" / "channel" / "test_omni_agent_mcp_startup_stress.py"
    spec = importlib.util.spec_from_file_location("omni_agent_mcp_startup_stress", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "rounds": 6,
        "parallel": 3,
        "startup_timeout_secs": 45,
        "cooldown_secs": 0.2,
        "executable": "target/debug/omni-agent",
        "mcp_config": ".mcp.json",
        "project_root": ".",
        "bind_addr": "127.0.0.1:0",
        "rust_log": "omni_agent::mcp_pool=debug",
        "output_json": ".run/reports/omni-agent-mcp-startup-stress.json",
        "output_markdown": ".run/reports/omni-agent-mcp-startup-stress.md",
        "restart_mcp_cmd": "",
        "restart_mcp_settle_secs": 2.0,
        "health_url": "http://127.0.0.1:3002/health",
        "strict_health_check": False,
        "health_probe_interval_secs": 0.2,
        "health_probe_timeout_secs": 1.0,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_classify_reason_priority() -> None:
    module = _load_module()
    assert (
        module.classify_reason(
            ready_seen=True,
            handshake_timeout_seen=True,
            connect_failed_seen=True,
            process_exited=True,
            timed_out=True,
        )
        == "ok"
    )
    assert (
        module.classify_reason(
            ready_seen=False,
            handshake_timeout_seen=True,
            connect_failed_seen=True,
            process_exited=True,
            timed_out=False,
        )
        == "handshake_timeout"
    )
    assert (
        module.classify_reason(
            ready_seen=False,
            handshake_timeout_seen=False,
            connect_failed_seen=True,
            process_exited=True,
            timed_out=False,
        )
        == "connect_failed"
    )


def test_summarize_counts_and_stats() -> None:
    module = _load_module()
    rows = [
        module.ProbeResult(1, 1, True, "ok", 1200, 0, 4, 0, False, False, True, ""),
        module.ProbeResult(
            1,
            2,
            False,
            "handshake_timeout",
            45000,
            1,
            0,
            1,
            True,
            False,
            False,
            "timeout",
        ),
        module.ProbeResult(
            2,
            1,
            False,
            "connect_failed",
            3200,
            1,
            0,
            1,
            False,
            True,
            False,
            "failed",
        ),
    ]
    health_rows = [
        module.HealthSample(ok=True, latency_ms=30.0, detail="status=200"),
        module.HealthSample(ok=False, latency_ms=200.0, detail="error=timeout"),
    ]
    summary = module.summarize(rows, health_rows)
    assert summary["total"] == 3
    assert summary["passed"] == 1
    assert summary["failed"] == 2
    assert summary["reason_counts"]["ok"] == 1
    assert summary["reason_counts"]["handshake_timeout"] == 1
    assert summary["reason_counts"]["connect_failed"] == 1
    assert summary["success_avg_startup_ms"] == 1200.0
    assert summary["health_samples_total"] == 2
    assert summary["health_samples_failed"] == 1
    assert summary["health_failure_rate"] == 0.5


def test_render_markdown_includes_failures() -> None:
    module = _load_module()
    report = {
        "started_at": "2026-02-18T00:00:00+00:00",
        "finished_at": "2026-02-18T00:00:10+00:00",
        "duration_ms": 10000,
        "summary": {
            "total": 2,
            "passed": 1,
            "failed": 1,
            "pass_rate": 0.5,
            "reason_counts": {"ok": 1, "handshake_timeout": 1},
            "success_avg_startup_ms": 100.0,
            "success_p95_startup_ms": 100.0,
            "failure_avg_startup_ms": 40000.0,
            "health_samples_total": 10,
            "health_samples_ok": 9,
            "health_samples_failed": 1,
            "health_failure_rate": 0.1,
            "health_avg_latency_ms": 28.0,
            "health_p95_latency_ms": 40.0,
            "health_max_latency_ms": 72.0,
            "health_error_top": [{"detail": "error=timeout", "count": 1}],
        },
        "results": [
            {
                "round_index": 1,
                "worker_index": 1,
                "success": True,
                "reason": "ok",
                "startup_duration_ms": 100,
                "mcp_connect_succeeded": 4,
                "mcp_connect_failed": 0,
                "tail": "",
            },
            {
                "round_index": 1,
                "worker_index": 2,
                "success": False,
                "reason": "handshake_timeout",
                "startup_duration_ms": 40000,
                "mcp_connect_succeeded": 0,
                "mcp_connect_failed": 1,
                "tail": "MCP handshake timeout",
            },
        ],
    }
    markdown = module.render_markdown(report)
    assert "MCP Startup Stress Report" in markdown
    assert "Health Monitor" in markdown
    assert "handshake_timeout" in markdown
    assert "MCP handshake timeout" in markdown


def test_build_config_resolves_paths(tmp_path) -> None:
    module = _load_module()
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True)
    executable = project_root / "target" / "debug" / "omni-agent"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    mcp_config = project_root / ".mcp.json"
    mcp_config.write_text('{"mcpServers":{}}', encoding="utf-8")

    args = _make_args(
        project_root=str(project_root),
        executable="target/debug/omni-agent",
        mcp_config=".mcp.json",
        output_json=".run/reports/a.json",
        output_markdown=".run/reports/a.md",
    )
    config = module.build_config(args)
    assert config.executable == executable.resolve()
    assert config.mcp_config == mcp_config.resolve()
    assert config.output_json.name == "a.json"
    assert config.output_markdown.name == "a.md"
