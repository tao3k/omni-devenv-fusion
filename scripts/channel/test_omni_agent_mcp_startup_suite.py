#!/usr/bin/env python3
"""
MCP startup regression suite (hot + cold) for omni-agent gateway startup.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class SuiteConfig:
    hot_rounds: int
    hot_parallel: int
    cold_rounds: int
    cold_parallel: int
    startup_timeout_secs: int
    cooldown_secs: float
    mcp_host: str
    mcp_port: int
    mcp_config: Path
    health_url: str
    strict_health_check: bool
    health_probe_interval_secs: float
    health_probe_timeout_secs: float
    restart_mcp_cmd: str | None
    allow_mcp_restart: bool
    restart_mcp_settle_secs: float
    restart_health_timeout_secs: int
    restart_no_embedding: bool
    skip_hot: bool
    skip_cold: bool
    quality_max_failed_probes: int
    quality_max_hot_p95_ms: float
    quality_max_cold_p95_ms: float
    quality_min_health_samples: int
    quality_max_health_failure_rate: float
    quality_max_health_p95_ms: float
    quality_baseline_json: Path | None
    quality_max_hot_p95_regression_ratio: float
    quality_max_cold_p95_regression_ratio: float
    project_root: Path
    stress_script: Path
    restart_script: Path
    output_json: Path
    output_markdown: Path


@dataclass(frozen=True)
class ModeSpec:
    name: str
    rounds: int
    parallel: int
    restart_mcp_cmd: str | None


def default_report_path(filename: str) -> Path:
    runtime_root = Path(os.environ.get("PRJ_RUNTIME_DIR", ".run"))
    if not runtime_root.is_absolute():
        runtime_root = Path.cwd() / runtime_root
    return runtime_root / "reports" / filename


def project_root_from(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def resolve_path(path_str: str, project_root: Path) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run hot/cold MCP startup regression suite for omni-agent gateway."
    )
    parser.add_argument("--hot-rounds", type=int, default=20)
    parser.add_argument("--hot-parallel", type=int, default=8)
    parser.add_argument("--cold-rounds", type=int, default=8)
    parser.add_argument("--cold-parallel", type=int, default=4)
    parser.add_argument("--startup-timeout-secs", type=int, default=60)
    parser.add_argument("--cooldown-secs", type=float, default=0.2)
    parser.add_argument("--mcp-host", default="127.0.0.1")
    parser.add_argument("--mcp-port", type=int, default=3002)
    parser.add_argument("--mcp-config", default=".mcp.json")
    parser.add_argument("--health-url", default="")
    parser.add_argument("--strict-health-check", action="store_true")
    parser.add_argument("--no-strict-health-check", action="store_true")
    parser.add_argument("--health-probe-interval-secs", type=float, default=0.2)
    parser.add_argument("--health-probe-timeout-secs", type=float, default=1.0)
    parser.add_argument("--restart-mcp-cmd", default="")
    parser.add_argument(
        "--allow-mcp-restart",
        action="store_true",
        help=(
            "Allow this suite to restart the shared MCP process for cold-start checks. "
            "By default cold mode is auto-skipped to avoid disrupting a live MCP instance."
        ),
    )
    parser.add_argument("--restart-mcp-settle-secs", type=float, default=0.2)
    parser.add_argument("--restart-health-timeout-secs", type=int, default=30)
    parser.add_argument("--restart-no-embedding", action="store_true")
    parser.add_argument("--skip-hot", action="store_true")
    parser.add_argument("--skip-cold", action="store_true")
    parser.add_argument("--quality-max-failed-probes", type=int, default=0)
    parser.add_argument("--quality-max-hot-p95-ms", type=float, default=1200.0)
    parser.add_argument("--quality-max-cold-p95-ms", type=float, default=1500.0)
    parser.add_argument("--quality-min-health-samples", type=int, default=1)
    parser.add_argument("--quality-max-health-failure-rate", type=float, default=0.02)
    parser.add_argument("--quality-max-health-p95-ms", type=float, default=350.0)
    parser.add_argument("--quality-baseline-json", default="")
    parser.add_argument("--quality-max-hot-p95-regression-ratio", type=float, default=0.5)
    parser.add_argument("--quality-max-cold-p95-regression-ratio", type=float, default=0.5)
    parser.add_argument(
        "--project-root",
        default=str(project_root_from(Path.cwd())),
        help="Project root (default: auto-detect from .git).",
    )
    parser.add_argument(
        "--output-json",
        default=str(default_report_path("omni-agent-mcp-startup-suite.json")),
    )
    parser.add_argument(
        "--output-markdown",
        default=str(default_report_path("omni-agent-mcp-startup-suite.md")),
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> SuiteConfig:
    if args.hot_rounds <= 0 or args.hot_parallel <= 0:
        raise ValueError("--hot-rounds and --hot-parallel must be positive.")
    if args.cold_rounds <= 0 or args.cold_parallel <= 0:
        raise ValueError("--cold-rounds and --cold-parallel must be positive.")
    if args.startup_timeout_secs <= 0:
        raise ValueError("--startup-timeout-secs must be positive.")
    if args.cooldown_secs < 0:
        raise ValueError("--cooldown-secs must be >= 0.")
    if args.restart_mcp_settle_secs < 0:
        raise ValueError("--restart-mcp-settle-secs must be >= 0.")
    if args.health_probe_interval_secs < 0:
        raise ValueError("--health-probe-interval-secs must be >= 0.")
    if args.health_probe_timeout_secs <= 0:
        raise ValueError("--health-probe-timeout-secs must be positive.")
    if args.restart_health_timeout_secs <= 0:
        raise ValueError("--restart-health-timeout-secs must be positive.")
    if args.mcp_port <= 0:
        raise ValueError("--mcp-port must be positive.")
    if args.quality_max_failed_probes < 0:
        raise ValueError("--quality-max-failed-probes must be >= 0.")
    if args.quality_max_hot_p95_ms <= 0:
        raise ValueError("--quality-max-hot-p95-ms must be positive.")
    if args.quality_max_cold_p95_ms <= 0:
        raise ValueError("--quality-max-cold-p95-ms must be positive.")
    if args.quality_min_health_samples < 0:
        raise ValueError("--quality-min-health-samples must be >= 0.")
    if args.quality_max_health_failure_rate < 0:
        raise ValueError("--quality-max-health-failure-rate must be >= 0.")
    if args.quality_max_health_p95_ms <= 0:
        raise ValueError("--quality-max-health-p95-ms must be positive.")
    if args.quality_max_hot_p95_regression_ratio < 0:
        raise ValueError("--quality-max-hot-p95-regression-ratio must be >= 0.")
    if args.quality_max_cold_p95_regression_ratio < 0:
        raise ValueError("--quality-max-cold-p95-regression-ratio must be >= 0.")

    project_root = resolve_path(args.project_root, Path.cwd())
    mcp_config = resolve_path(args.mcp_config, project_root)
    if not mcp_config.exists():
        raise ValueError(f"mcp config not found: {mcp_config}")

    script_dir = Path(__file__).resolve().parent
    stress_script = script_dir / "test_omni_agent_mcp_startup_stress.py"
    restart_script = script_dir / "restart-omni-mcp.sh"
    if not stress_script.exists():
        raise ValueError(f"stress runner not found: {stress_script}")
    if not restart_script.exists():
        raise ValueError(f"restart script not found: {restart_script}")

    health_url = args.health_url.strip() or f"http://{args.mcp_host}:{args.mcp_port}/health"
    strict_health_check = True
    if args.no_strict_health_check:
        strict_health_check = False
    if args.strict_health_check:
        strict_health_check = True

    restart_mcp_cmd = args.restart_mcp_cmd.strip() or None
    allow_mcp_restart = bool(args.allow_mcp_restart or restart_mcp_cmd is not None)
    skip_hot = bool(args.skip_hot)
    skip_cold = bool(args.skip_cold)
    if skip_hot and not skip_cold and not allow_mcp_restart:
        raise ValueError(
            "cold-only startup suite requires MCP restart permission. "
            "Use --allow-mcp-restart or --restart-mcp-cmd."
        )
    if not skip_cold and not allow_mcp_restart:
        print(
            "[mcp-startup-suite] cold mode auto-skipped (restart not allowed). "
            "Use --allow-mcp-restart to enable cold restart checks.",
            file=sys.stderr,
        )
        skip_cold = True
    if skip_hot and skip_cold:
        raise ValueError("At least one mode must run (do not set both --skip-hot and --skip-cold).")

    quality_baseline_json = args.quality_baseline_json.strip()
    baseline_path = (
        resolve_path(quality_baseline_json, project_root) if quality_baseline_json else None
    )
    if baseline_path is not None and not baseline_path.exists():
        raise ValueError(f"quality baseline report not found: {baseline_path}")

    return SuiteConfig(
        hot_rounds=int(args.hot_rounds),
        hot_parallel=int(args.hot_parallel),
        cold_rounds=int(args.cold_rounds),
        cold_parallel=int(args.cold_parallel),
        startup_timeout_secs=int(args.startup_timeout_secs),
        cooldown_secs=float(args.cooldown_secs),
        mcp_host=args.mcp_host.strip(),
        mcp_port=int(args.mcp_port),
        mcp_config=mcp_config,
        health_url=health_url,
        strict_health_check=bool(strict_health_check),
        health_probe_interval_secs=float(args.health_probe_interval_secs),
        health_probe_timeout_secs=float(args.health_probe_timeout_secs),
        restart_mcp_cmd=restart_mcp_cmd,
        allow_mcp_restart=allow_mcp_restart,
        restart_mcp_settle_secs=float(args.restart_mcp_settle_secs),
        restart_health_timeout_secs=int(args.restart_health_timeout_secs),
        restart_no_embedding=bool(args.restart_no_embedding),
        skip_hot=skip_hot,
        skip_cold=skip_cold,
        quality_max_failed_probes=int(args.quality_max_failed_probes),
        quality_max_hot_p95_ms=float(args.quality_max_hot_p95_ms),
        quality_max_cold_p95_ms=float(args.quality_max_cold_p95_ms),
        quality_min_health_samples=int(args.quality_min_health_samples),
        quality_max_health_failure_rate=float(args.quality_max_health_failure_rate),
        quality_max_health_p95_ms=float(args.quality_max_health_p95_ms),
        quality_baseline_json=baseline_path,
        quality_max_hot_p95_regression_ratio=float(args.quality_max_hot_p95_regression_ratio),
        quality_max_cold_p95_regression_ratio=float(args.quality_max_cold_p95_regression_ratio),
        project_root=project_root,
        stress_script=stress_script,
        restart_script=restart_script,
        output_json=resolve_path(args.output_json, project_root),
        output_markdown=resolve_path(args.output_markdown, project_root),
    )


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def build_restart_command(cfg: SuiteConfig) -> str:
    if cfg.restart_mcp_cmd:
        return cfg.restart_mcp_cmd

    runtime_root = Path(os.environ.get("PRJ_RUNTIME_DIR", ".run"))
    if not runtime_root.is_absolute():
        runtime_root = cfg.project_root / runtime_root
    pid_file = runtime_root / f"omni-mcp-sse-{cfg.mcp_port}.pid"
    log_file = runtime_root / "logs" / f"omni-mcp-sse-{cfg.mcp_port}.log"
    cmd = [
        "bash",
        str(cfg.restart_script),
        "--host",
        cfg.mcp_host,
        "--port",
        str(cfg.mcp_port),
        "--pid-file",
        str(pid_file),
        "--log-file",
        str(log_file),
        "--health-timeout-secs",
        str(cfg.restart_health_timeout_secs),
    ]
    if cfg.restart_no_embedding:
        cmd.append("--no-embedding")
    return shell_join(cmd)


def build_mode_specs(cfg: SuiteConfig) -> tuple[ModeSpec, ...]:
    specs: list[ModeSpec] = []
    if not cfg.skip_hot:
        specs.append(
            ModeSpec(
                name="hot",
                rounds=cfg.hot_rounds,
                parallel=cfg.hot_parallel,
                restart_mcp_cmd=None,
            )
        )
    if not cfg.skip_cold:
        specs.append(
            ModeSpec(
                name="cold",
                rounds=cfg.cold_rounds,
                parallel=cfg.cold_parallel,
                restart_mcp_cmd=build_restart_command(cfg),
            )
        )
    return tuple(specs)


def mode_report_paths(cfg: SuiteConfig, mode: str) -> tuple[Path, Path]:
    json_path = cfg.output_json.with_name(f"{cfg.output_json.stem}-{mode}{cfg.output_json.suffix}")
    md_path = cfg.output_markdown.with_name(
        f"{cfg.output_markdown.stem}-{mode}{cfg.output_markdown.suffix}"
    )
    return json_path, md_path


def load_summary(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else None


def run_shell_command(command: str, cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    return completed.returncode, output.strip()


def run_mode(cfg: SuiteConfig, spec: ModeSpec) -> dict[str, object]:
    report_json, report_markdown = mode_report_paths(cfg, spec.name)
    pre_restart_output = ""
    if spec.restart_mcp_cmd:
        pre_restart_code, pre_restart_output = run_shell_command(
            spec.restart_mcp_cmd,
            cfg.project_root,
        )
        if pre_restart_code != 0:
            return {
                "mode": spec.name,
                "rounds": spec.rounds,
                "parallel": spec.parallel,
                "return_code": pre_restart_code,
                "duration_ms": 0,
                "passed": False,
                "summary": None,
                "json_report": str(report_json),
                "markdown_report": str(report_markdown),
                "stdout_tail": "",
                "stderr_tail": pre_restart_output[-1200:],
                "pre_restart_failed": True,
            }

    cmd = [
        sys.executable,
        str(cfg.stress_script),
        "--rounds",
        str(spec.rounds),
        "--parallel",
        str(spec.parallel),
        "--startup-timeout-secs",
        str(cfg.startup_timeout_secs),
        "--cooldown-secs",
        str(cfg.cooldown_secs),
        "--mcp-config",
        str(cfg.mcp_config),
        "--health-url",
        cfg.health_url,
        "--health-probe-interval-secs",
        str(cfg.health_probe_interval_secs),
        "--health-probe-timeout-secs",
        str(cfg.health_probe_timeout_secs),
        "--output-json",
        str(report_json),
        "--output-markdown",
        str(report_markdown),
    ]
    if cfg.strict_health_check:
        cmd.append("--strict-health-check")
    if spec.restart_mcp_cmd:
        cmd.extend(["--restart-mcp-cmd", spec.restart_mcp_cmd])
        cmd.extend(["--restart-mcp-settle-secs", str(cfg.restart_mcp_settle_secs)])

    started = time.monotonic()
    completed = subprocess.run(
        cmd,
        cwd=str(cfg.project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    summary = load_summary(report_json)
    summary_failed = int(summary.get("failed", 1)) if summary else 1
    passed = completed.returncode == 0 and summary_failed == 0

    print(
        f"[mode:{spec.name}] return_code={completed.returncode} "
        f"duration_ms={duration_ms} passed={passed}",
        flush=True,
    )

    return {
        "mode": spec.name,
        "rounds": spec.rounds,
        "parallel": spec.parallel,
        "return_code": completed.returncode,
        "duration_ms": duration_ms,
        "passed": passed,
        "summary": summary,
        "json_report": str(report_json),
        "markdown_report": str(report_markdown),
        "stdout_tail": "\n".join((completed.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((completed.stderr or "").splitlines()[-20:]),
        "pre_restart_output": pre_restart_output[-1200:],
    }


def _mode_p95(summary: dict[str, object]) -> float:
    return float(summary.get("success_p95_startup_ms", 0.0))


def _mode_failed(summary: dict[str, object]) -> int:
    return int(summary.get("failed", 0))


def _load_baseline_mode_p95s(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    modes = payload.get("modes")
    if not isinstance(modes, list):
        return {}
    result: dict[str, float] = {}
    for mode in modes:
        if not isinstance(mode, dict):
            continue
        mode_name = mode.get("mode")
        summary = mode.get("summary")
        if isinstance(mode_name, str) and isinstance(summary, dict):
            result[mode_name] = _mode_p95(summary)
    return result


def evaluate_quality_gates(cfg: SuiteConfig, modes: list[dict[str, object]]) -> dict[str, object]:
    violations: list[str] = []
    for mode in modes:
        summary = mode.get("summary")
        if not isinstance(summary, dict):
            violations.append(f"{mode['mode']}: missing mode summary")
            continue
        failed = _mode_failed(summary)
        if failed > cfg.quality_max_failed_probes:
            violations.append(
                f"{mode['mode']}: failed probes {failed} > allowed {cfg.quality_max_failed_probes}"
            )

        p95 = _mode_p95(summary)
        if mode["mode"] == "hot" and p95 > cfg.quality_max_hot_p95_ms:
            violations.append(
                f"hot: p95 {p95:.1f}ms > threshold {cfg.quality_max_hot_p95_ms:.1f}ms"
            )
        if mode["mode"] == "cold" and p95 > cfg.quality_max_cold_p95_ms:
            violations.append(
                f"cold: p95 {p95:.1f}ms > threshold {cfg.quality_max_cold_p95_ms:.1f}ms"
            )
        health_samples = int(summary.get("health_samples_total", 0))
        health_failure_rate = float(summary.get("health_failure_rate", 0.0))
        health_p95 = float(summary.get("health_p95_latency_ms", 0.0))
        if health_samples < cfg.quality_min_health_samples:
            violations.append(
                f"{mode['mode']}: health samples {health_samples} < required "
                f"{cfg.quality_min_health_samples}"
            )
        if health_failure_rate > cfg.quality_max_health_failure_rate:
            violations.append(
                f"{mode['mode']}: health failure rate {health_failure_rate:.2%} > threshold "
                f"{cfg.quality_max_health_failure_rate:.2%}"
            )
        if health_p95 > cfg.quality_max_health_p95_ms:
            violations.append(
                f"{mode['mode']}: health p95 {health_p95:.1f}ms > threshold "
                f"{cfg.quality_max_health_p95_ms:.1f}ms"
            )

    baseline_p95: dict[str, float] = {}
    if cfg.quality_baseline_json is not None:
        baseline_p95 = _load_baseline_mode_p95s(cfg.quality_baseline_json)
        for mode in modes:
            summary = mode.get("summary")
            if not isinstance(summary, dict):
                continue
            mode_name = str(mode.get("mode"))
            current_p95 = _mode_p95(summary)
            base_p95 = baseline_p95.get(mode_name)
            if base_p95 is None or base_p95 <= 0:
                continue
            ratio = (current_p95 - base_p95) / base_p95
            if mode_name == "hot" and ratio > cfg.quality_max_hot_p95_regression_ratio:
                violations.append(
                    f"hot: p95 regression {ratio:.2%} > allowed "
                    f"{cfg.quality_max_hot_p95_regression_ratio:.2%} "
                    f"(baseline={base_p95:.1f}ms current={current_p95:.1f}ms)"
                )
            if mode_name == "cold" and ratio > cfg.quality_max_cold_p95_regression_ratio:
                violations.append(
                    f"cold: p95 regression {ratio:.2%} > allowed "
                    f"{cfg.quality_max_cold_p95_regression_ratio:.2%} "
                    f"(baseline={base_p95:.1f}ms current={current_p95:.1f}ms)"
                )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "thresholds": {
            "max_failed_probes": cfg.quality_max_failed_probes,
            "max_hot_p95_ms": cfg.quality_max_hot_p95_ms,
            "max_cold_p95_ms": cfg.quality_max_cold_p95_ms,
            "min_health_samples": cfg.quality_min_health_samples,
            "max_health_failure_rate": cfg.quality_max_health_failure_rate,
            "max_health_p95_ms": cfg.quality_max_health_p95_ms,
            "max_hot_p95_regression_ratio": cfg.quality_max_hot_p95_regression_ratio,
            "max_cold_p95_regression_ratio": cfg.quality_max_cold_p95_regression_ratio,
        },
        "baseline_json": str(cfg.quality_baseline_json) if cfg.quality_baseline_json else None,
        "baseline_mode_p95_ms": baseline_p95,
    }


def render_markdown(report: dict[str, object]) -> str:
    quality = report.get("quality_gate")
    if not isinstance(quality, dict):
        quality = {"passed": True, "violations": [], "thresholds": {}}
    quality_thresholds = quality.get("thresholds") if isinstance(quality, dict) else {}
    if not isinstance(quality_thresholds, dict):
        quality_thresholds = {}
    quality_violations = quality.get("violations") if isinstance(quality, dict) else []
    if not isinstance(quality_violations, list):
        quality_violations = []

    lines = [
        "# MCP Startup Suite Report",
        "",
        "## Overview",
        f"- Started: `{report['started_at']}`",
        f"- Finished: `{report['finished_at']}`",
        f"- Duration: `{report['duration_ms']} ms`",
        f"- Overall passed: `{report['overall_passed']}`",
        f"- Passed modes: `{report['passed_modes']}`",
        f"- Failed modes: `{report['failed_modes']}`",
        f"- Quality gate passed: `{quality.get('passed', True)}`",
        "",
        "## Quality Gate",
        f"- max_failed_probes: `{quality_thresholds.get('max_failed_probes', 0)}`",
        f"- max_hot_p95_ms: `{float(quality_thresholds.get('max_hot_p95_ms', 0.0)):.1f}`",
        f"- max_cold_p95_ms: `{float(quality_thresholds.get('max_cold_p95_ms', 0.0)):.1f}`",
        f"- min_health_samples: `{int(quality_thresholds.get('min_health_samples', 0))}`",
        (
            "- max_health_failure_rate: "
            f"`{float(quality_thresholds.get('max_health_failure_rate', 0.0)):.2%}`"
        ),
        f"- max_health_p95_ms: `{float(quality_thresholds.get('max_health_p95_ms', 0.0)):.1f}`",
        (
            "- max_hot_p95_regression_ratio: "
            f"`{float(quality_thresholds.get('max_hot_p95_regression_ratio', 0.0)):.2%}`"
        ),
        (
            "- max_cold_p95_regression_ratio: "
            f"`{float(quality_thresholds.get('max_cold_p95_regression_ratio', 0.0)):.2%}`"
        ),
        "",
        "## Modes",
        (
            "| Mode | Result | Rounds | Parallel | Avg ms | P95 ms | Failed Probes | "
            "Health Fail Rate | Health P95 ms | Report |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for mode in report["modes"]:
        summary = mode.get("summary") or {}
        lines.append(
            (
                "| {mode_name} | {result} | {rounds} | {parallel} | {avg:.1f} | {p95:.1f} | "
                "{failed} | {health_fail_rate:.2%} | {health_p95:.1f} | `{report_json}` |"
            ).format(
                mode_name=mode["mode"],
                result="PASS" if mode["passed"] else "FAIL",
                rounds=mode["rounds"],
                parallel=mode["parallel"],
                avg=float(summary.get("success_avg_startup_ms", 0.0)),
                p95=float(summary.get("success_p95_startup_ms", 0.0)),
                failed=int(summary.get("failed", 0)),
                health_fail_rate=float(summary.get("health_failure_rate", 0.0)),
                health_p95=float(summary.get("health_p95_latency_ms", 0.0)),
                report_json=mode["json_report"],
            )
        )

    lines.extend(["", "## Quality Violations"])
    if not quality_violations:
        lines.append("- None")
    else:
        for violation in quality_violations:
            lines.append(f"- {violation}")

    failures = [mode for mode in report["modes"] if not mode["passed"]]
    lines.extend(["", "## Failure Tails"])
    if not failures:
        lines.append("- None")
    else:
        for mode in failures:
            lines.extend(
                [
                    f"### {mode['mode']}",
                    "```text",
                    mode.get("stdout_tail", "") or "(no stdout)",
                    mode.get("stderr_tail", "") or "(no stderr)",
                    "```",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def run_suite(cfg: SuiteConfig) -> dict[str, object]:
    started_dt = datetime.now(UTC)
    started = time.monotonic()
    results = [run_mode(cfg, spec) for spec in build_mode_specs(cfg)]
    passed_modes = sum(1 for mode in results if mode["passed"])
    failed_modes = len(results) - passed_modes
    quality_gate = evaluate_quality_gates(cfg, results)
    overall_passed = failed_modes == 0 and bool(quality_gate.get("passed", False))
    report = {
        "started_at": started_dt.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "config": {
            "hot_rounds": cfg.hot_rounds,
            "hot_parallel": cfg.hot_parallel,
            "cold_rounds": cfg.cold_rounds,
            "cold_parallel": cfg.cold_parallel,
            "startup_timeout_secs": cfg.startup_timeout_secs,
            "cooldown_secs": cfg.cooldown_secs,
            "mcp_host": cfg.mcp_host,
            "mcp_port": cfg.mcp_port,
            "mcp_config": str(cfg.mcp_config),
            "health_url": cfg.health_url,
            "strict_health_check": cfg.strict_health_check,
            "health_probe_interval_secs": cfg.health_probe_interval_secs,
            "health_probe_timeout_secs": cfg.health_probe_timeout_secs,
            "restart_mcp_settle_secs": cfg.restart_mcp_settle_secs,
            "restart_health_timeout_secs": cfg.restart_health_timeout_secs,
            "restart_no_embedding": cfg.restart_no_embedding,
            "skip_hot": cfg.skip_hot,
            "skip_cold": cfg.skip_cold,
            "quality_max_failed_probes": cfg.quality_max_failed_probes,
            "quality_max_hot_p95_ms": cfg.quality_max_hot_p95_ms,
            "quality_max_cold_p95_ms": cfg.quality_max_cold_p95_ms,
            "quality_min_health_samples": cfg.quality_min_health_samples,
            "quality_max_health_failure_rate": cfg.quality_max_health_failure_rate,
            "quality_max_health_p95_ms": cfg.quality_max_health_p95_ms,
            "quality_baseline_json": str(cfg.quality_baseline_json)
            if cfg.quality_baseline_json
            else None,
            "quality_max_hot_p95_regression_ratio": cfg.quality_max_hot_p95_regression_ratio,
            "quality_max_cold_p95_regression_ratio": cfg.quality_max_cold_p95_regression_ratio,
        },
        "overall_passed": overall_passed,
        "passed_modes": passed_modes,
        "failed_modes": failed_modes,
        "quality_gate": quality_gate,
        "modes": results,
    }
    return report


def write_report(report: dict[str, object], output_json: Path, output_markdown: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_markdown.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    try:
        cfg = build_config(parse_args())
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    report = run_suite(cfg)
    write_report(report, cfg.output_json, cfg.output_markdown)

    print("MCP startup suite completed.", flush=True)
    print(
        (
            f"  modes={len(report['modes'])} "
            f"passed={report['passed_modes']} failed={report['failed_modes']}"
        ),
        flush=True,
    )
    quality_gate = report.get("quality_gate", {})
    if isinstance(quality_gate, dict):
        print(f"  quality_gate_passed={quality_gate.get('passed', True)}", flush=True)
        violations = quality_gate.get("violations")
        if isinstance(violations, list) and violations:
            print("  quality_violations:", flush=True)
            for violation in violations:
                print(f"    - {violation}", flush=True)
    print(f"  json_report={cfg.output_json}", flush=True)
    print(f"  markdown_report={cfg.output_markdown}", flush=True)
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
