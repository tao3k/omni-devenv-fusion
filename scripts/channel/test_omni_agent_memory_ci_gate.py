#!/usr/bin/env python3
"""
CI gate runner for omni-agent memory/channel verification.

Profiles:
  - quick: command-path black-box checks + Rust memory regressions
  - nightly: full memory suite (includes evolution DAG) + session matrix + benchmark
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GateConfig:
    profile: str
    project_root: Path
    script_dir: Path
    agent_bin: Path | None
    webhook_port: int
    telegram_api_port: int
    valkey_port: int
    valkey_url: str
    valkey_prefix: str
    username: str
    webhook_secret: str
    chat_id: int
    chat_b: int
    chat_c: int
    user_id: int
    user_b: int
    user_c: int
    runtime_log_file: Path
    mock_log_file: Path
    runtime_startup_timeout_secs: int
    quick_max_wait: int
    quick_max_idle: int
    full_max_wait: int
    full_max_idle: int
    matrix_max_wait: int
    matrix_max_idle: int
    benchmark_iterations: int
    skip_matrix: bool
    skip_benchmark: bool
    skip_evolution: bool
    skip_rust_regressions: bool
    skip_discover_cache_gate: bool
    skip_reflection_quality_gate: bool
    skip_trace_reconstruction_gate: bool
    skip_cross_group_complex_gate: bool
    evolution_report_json: Path
    benchmark_report_json: Path
    session_matrix_report_json: Path
    session_matrix_report_markdown: Path
    trace_report_json: Path
    trace_report_markdown: Path
    cross_group_report_json: Path
    cross_group_report_markdown: Path
    cross_group_dataset: Path
    cross_group_scenario_id: str
    min_planned_hits: int
    min_successful_corrections: int
    min_recall_credit_events: int
    min_quality_score: float
    slow_response_min_duration_ms: int
    slow_response_long_step_ms: int
    slow_response_min_long_steps: int
    trace_min_quality_score: float
    trace_max_events: int
    min_session_steps: int
    require_cross_group_step: bool
    require_mixed_batch_steps: bool
    cross_group_max_wait: int
    cross_group_max_idle: int
    cross_group_max_parallel: int
    discover_cache_hit_p95_ms: float
    discover_cache_miss_p95_ms: float
    discover_cache_bench_iterations: int
    max_mcp_call_waiting_events: int
    max_mcp_connect_waiting_events: int
    max_mcp_waiting_events_total: int


def default_valkey_prefix(profile: str) -> str:
    safe_profile = profile.strip().lower() or "default"
    return f"omni-agent:session:ci:{safe_profile}:{os.getpid()}:{int(time.time() * 1000)}"


def valkey_reachable(url: str) -> bool:
    result = subprocess.run(
        ["valkey-cli", "-u", url, "ping"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    return result.returncode == 0


def can_bind_tcp(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def allocate_free_tcp_port(host: str, *, avoid: set[int] | None = None) -> int:
    blocked = avoid or set()
    for _ in range(32):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            candidate = int(sock.getsockname()[1])
        if candidate in blocked:
            continue
        if can_bind_tcp(host, candidate):
            return candidate
    raise RuntimeError(f"failed to allocate free TCP port on host={host}")


def resolve_runtime_ports(
    webhook_port: int,
    telegram_api_port: int,
    *,
    host: str = "127.0.0.1",
) -> tuple[int, int]:
    resolved_telegram_api_port = telegram_api_port
    if not can_bind_tcp(host, resolved_telegram_api_port):
        resolved_telegram_api_port = allocate_free_tcp_port(host)
        print(
            "Port occupied; reassigned --telegram-api-port "
            f"{telegram_api_port} -> {resolved_telegram_api_port}",
            file=sys.stderr,
            flush=True,
        )

    resolved_webhook_port = webhook_port
    webhook_blocked = resolved_webhook_port == resolved_telegram_api_port or not can_bind_tcp(
        host, resolved_webhook_port
    )
    if webhook_blocked:
        resolved_webhook_port = allocate_free_tcp_port(host, avoid={resolved_telegram_api_port})
        print(
            "Port occupied/conflict; reassigned --webhook-port "
            f"{webhook_port} -> {resolved_webhook_port}",
            file=sys.stderr,
            flush=True,
        )

    return resolved_webhook_port, resolved_telegram_api_port


def default_run_suffix() -> str:
    return f"{os.getpid()}-{int(time.time() * 1000)}"


def default_artifact_relpath(
    *,
    category: str,
    stem: str,
    profile: str,
    run_suffix: str,
    extension: str,
) -> str:
    return f".run/{category}/{stem}-{profile}-{run_suffix}.{extension}"


def parse_args(project_root: Path) -> GateConfig:
    parser = argparse.ArgumentParser(description="Run omni-agent memory CI gate.")
    parser.add_argument(
        "--profile",
        choices=("quick", "nightly"),
        default="quick",
        help="Gate profile (default: quick).",
    )
    parser.add_argument(
        "--agent-bin",
        default="",
        help=(
            "Optional path to prebuilt omni-agent binary. "
            "When set, startup uses '<agent-bin> channel ...' instead of 'cargo run -p omni-agent -- channel ...'."
        ),
    )
    parser.add_argument("--webhook-port", type=int, default=18081)
    parser.add_argument("--telegram-api-port", type=int, default=18080)
    parser.add_argument("--valkey-port", type=int, default=6379)
    parser.add_argument(
        "--valkey-url",
        default="",
        help="Optional explicit Valkey URL (default: redis://127.0.0.1:<valkey-port>/0).",
    )
    parser.add_argument(
        "--valkey-prefix",
        default="",
        help=(
            "Optional explicit Valkey key prefix for CI session/memory isolation. "
            "Default: an auto-generated per-run prefix."
        ),
    )
    parser.add_argument("--username", default=os.environ.get("OMNI_TEST_USERNAME", "ci-user"))
    parser.add_argument(
        "--webhook-secret",
        default=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
        help=(
            "Telegram webhook secret token. "
            "Defaults to $TELEGRAM_WEBHOOK_SECRET, otherwise an ephemeral token is generated."
        ),
    )
    parser.add_argument("--chat-id", type=int, default=1304799691)
    parser.add_argument(
        "--chat-b",
        type=int,
        default=int(os.environ["OMNI_TEST_CHAT_B"]) if "OMNI_TEST_CHAT_B" in os.environ else None,
    )
    parser.add_argument(
        "--chat-c",
        type=int,
        default=int(os.environ["OMNI_TEST_CHAT_C"]) if "OMNI_TEST_CHAT_C" in os.environ else None,
    )
    parser.add_argument("--user-id", type=int, default=1304799692)
    parser.add_argument(
        "--user-b",
        type=int,
        default=int(os.environ["OMNI_TEST_USER_B"]) if "OMNI_TEST_USER_B" in os.environ else None,
    )
    parser.add_argument(
        "--user-c",
        type=int,
        default=int(os.environ["OMNI_TEST_USER_C"]) if "OMNI_TEST_USER_C" in os.environ else None,
    )
    parser.add_argument("--runtime-startup-timeout-secs", type=int, default=90)
    parser.add_argument("--quick-max-wait", type=int, default=45)
    parser.add_argument("--quick-max-idle", type=int, default=25)
    parser.add_argument("--full-max-wait", type=int, default=90)
    parser.add_argument("--full-max-idle", type=int, default=40)
    parser.add_argument("--matrix-max-wait", type=int, default=45)
    parser.add_argument("--matrix-max-idle", type=int, default=30)
    parser.add_argument("--benchmark-iterations", type=int, default=3)
    parser.add_argument("--skip-matrix", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--skip-evolution", action="store_true")
    parser.add_argument("--skip-rust-regressions", action="store_true")
    parser.add_argument("--skip-discover-cache-gate", action="store_true")
    parser.add_argument("--skip-reflection-quality-gate", action="store_true")
    parser.add_argument("--skip-trace-reconstruction-gate", action="store_true")
    parser.add_argument("--skip-cross-group-complex-gate", action="store_true")
    parser.add_argument(
        "--runtime-log-file",
        default="",
        help=(
            "Optional runtime log file path. "
            "Default: .run/logs/omni-agent-webhook-ci-<profile>-<run-suffix>.log"
        ),
    )
    parser.add_argument(
        "--mock-log-file",
        default="",
        help=(
            "Optional mock Telegram log file path. "
            "Default: .run/logs/omni-agent-mock-telegram-<profile>-<run-suffix>.log"
        ),
    )
    parser.add_argument(
        "--evolution-report-json",
        default="",
        help=(
            "Optional evolution report path. "
            "Default: .run/reports/omni-agent-memory-evolution-<profile>-<run-suffix>.json"
        ),
    )
    parser.add_argument(
        "--benchmark-report-json",
        default="",
        help=(
            "Optional benchmark report path. "
            "Default: .run/reports/omni-agent-memory-benchmark-<profile>-<run-suffix>.json"
        ),
    )
    parser.add_argument(
        "--session-matrix-report-json",
        default="",
        help=(
            "Optional session matrix JSON path. "
            "Default: .run/reports/agent-channel-session-matrix-<profile>-<run-suffix>.json"
        ),
    )
    parser.add_argument(
        "--session-matrix-report-markdown",
        default="",
        help=(
            "Optional session matrix Markdown path. "
            "Default: .run/reports/agent-channel-session-matrix-<profile>-<run-suffix>.md"
        ),
    )
    parser.add_argument(
        "--trace-report-json",
        default="",
        help=(
            "Optional trace report JSON path. "
            "Default: .run/reports/omni-agent-trace-reconstruction-<profile>-<run-suffix>.json"
        ),
    )
    parser.add_argument(
        "--trace-report-markdown",
        default="",
        help=(
            "Optional trace report Markdown path. "
            "Default: .run/reports/omni-agent-trace-reconstruction-<profile>-<run-suffix>.md"
        ),
    )
    parser.add_argument(
        "--cross-group-report-json",
        default="",
        help=(
            "Optional cross-group mixed-concurrency report JSON path. "
            "Default: .run/reports/agent-channel-cross-group-complex-<profile>-<run-suffix>.json"
        ),
    )
    parser.add_argument(
        "--cross-group-report-markdown",
        default="",
        help=(
            "Optional cross-group mixed-concurrency report Markdown path. "
            "Default: .run/reports/agent-channel-cross-group-complex-<profile>-<run-suffix>.md"
        ),
    )
    parser.add_argument(
        "--cross-group-dataset",
        default=str(
            project_root / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
        ),
        help="Dataset path for the cross-group mixed-concurrency complex scenario.",
    )
    parser.add_argument(
        "--cross-group-scenario",
        default="cross_group_control_plane_stress",
        help="Scenario id for cross-group mixed-concurrency gate.",
    )
    parser.add_argument("--min-planned-hits", type=int, default=10)
    parser.add_argument("--min-successful-corrections", type=int, default=3)
    parser.add_argument("--min-recall-credit-events", type=int, default=1)
    parser.add_argument("--min-quality-score", type=float, default=90.0)
    parser.add_argument(
        "--slow-response-min-duration-ms",
        type=int,
        default=20000,
        help="Minimum accepted total duration for evolution scenario (milliseconds).",
    )
    parser.add_argument(
        "--slow-response-long-step-ms",
        type=int,
        default=1200,
        help="Threshold used to classify a step as slow-response (milliseconds).",
    )
    parser.add_argument(
        "--slow-response-min-long-steps",
        type=int,
        default=1,
        help="Minimum number of slow-response steps expected in evolution scenario.",
    )
    parser.add_argument("--trace-min-quality-score", type=float, default=90.0)
    parser.add_argument("--trace-max-events", type=int, default=2000)
    parser.add_argument("--min-session-steps", type=int, default=20)
    parser.set_defaults(require_cross_group_step=True, require_mixed_batch_steps=True)
    parser.add_argument(
        "--no-require-cross-group-step",
        action="store_false",
        dest="require_cross_group_step",
    )
    parser.add_argument(
        "--no-require-mixed-batch-steps",
        action="store_false",
        dest="require_mixed_batch_steps",
    )
    parser.add_argument(
        "--cross-group-max-wait",
        type=int,
        default=90,
        help="Cross-group complex scenario per-step max wait (seconds).",
    )
    parser.add_argument(
        "--cross-group-max-idle",
        type=int,
        default=80,
        help="Cross-group complex scenario max idle wait (seconds).",
    )
    parser.add_argument(
        "--cross-group-max-parallel",
        type=int,
        default=3,
        help="Cross-group complex scenario max parallel probes per wave.",
    )
    parser.add_argument("--discover-cache-hit-p95-ms", type=float, default=15.0)
    parser.add_argument("--discover-cache-miss-p95-ms", type=float, default=80.0)
    parser.add_argument("--discover-cache-bench-iterations", type=int, default=12)
    parser.add_argument("--max-mcp-call-waiting-events", type=int, default=0)
    parser.add_argument("--max-mcp-connect-waiting-events", type=int, default=0)
    parser.add_argument("--max-mcp-waiting-events-total", type=int, default=0)
    args = parser.parse_args()

    if args.valkey_port <= 0 or args.valkey_port > 65535:
        raise ValueError("--valkey-port must be in range 1..65535")
    if args.webhook_port <= 0 or args.webhook_port > 65535:
        raise ValueError("--webhook-port must be in range 1..65535")
    if args.telegram_api_port <= 0 or args.telegram_api_port > 65535:
        raise ValueError("--telegram-api-port must be in range 1..65535")
    if args.min_session_steps <= 0:
        raise ValueError("--min-session-steps must be a positive integer.")
    if args.cross_group_max_wait <= 0:
        raise ValueError("--cross-group-max-wait must be a positive integer.")
    if args.cross_group_max_idle <= 0:
        raise ValueError("--cross-group-max-idle must be a positive integer.")
    if args.cross_group_max_parallel <= 0:
        raise ValueError("--cross-group-max-parallel must be a positive integer.")
    if args.slow_response_min_duration_ms <= 0:
        raise ValueError("--slow-response-min-duration-ms must be a positive integer.")
    if args.slow_response_long_step_ms <= 0:
        raise ValueError("--slow-response-long-step-ms must be a positive integer.")
    if args.slow_response_min_long_steps <= 0:
        raise ValueError("--slow-response-min-long-steps must be a positive integer.")
    if args.discover_cache_hit_p95_ms <= 0:
        raise ValueError("--discover-cache-hit-p95-ms must be positive.")
    if args.discover_cache_miss_p95_ms <= 0:
        raise ValueError("--discover-cache-miss-p95-ms must be positive.")
    if args.discover_cache_bench_iterations <= 0:
        raise ValueError("--discover-cache-bench-iterations must be a positive integer.")
    if args.max_mcp_call_waiting_events < 0:
        raise ValueError("--max-mcp-call-waiting-events must be >= 0.")
    if args.max_mcp_connect_waiting_events < 0:
        raise ValueError("--max-mcp-connect-waiting-events must be >= 0.")
    if args.max_mcp_waiting_events_total < 0:
        raise ValueError("--max-mcp-waiting-events-total must be >= 0.")
    if args.trace_min_quality_score <= 0:
        raise ValueError("--trace-min-quality-score must be positive.")
    if args.trace_max_events <= 0:
        raise ValueError("--trace-max-events must be a positive integer.")
    if not args.cross_group_scenario.strip():
        raise ValueError("--cross-group-scenario must not be empty.")
    agent_bin = Path(args.agent_bin).expanduser().resolve() if args.agent_bin.strip() else None
    if agent_bin is not None:
        if not agent_bin.exists():
            raise ValueError(f"--agent-bin not found: {agent_bin}")
        if not agent_bin.is_file():
            raise ValueError(f"--agent-bin must point to a file: {agent_bin}")

    resolved_webhook_port, resolved_telegram_api_port = resolve_runtime_ports(
        int(args.webhook_port),
        int(args.telegram_api_port),
    )
    run_suffix = default_run_suffix()

    runtime_log_file = args.runtime_log_file.strip() or default_artifact_relpath(
        category="logs",
        stem="omni-agent-webhook-ci",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="log",
    )
    mock_log_file = args.mock_log_file.strip() or default_artifact_relpath(
        category="logs",
        stem="omni-agent-mock-telegram",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="log",
    )
    evolution_report_json = args.evolution_report_json.strip() or default_artifact_relpath(
        category="reports",
        stem="omni-agent-memory-evolution",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="json",
    )
    benchmark_report_json = args.benchmark_report_json.strip() or default_artifact_relpath(
        category="reports",
        stem="omni-agent-memory-benchmark",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="json",
    )
    session_matrix_report_json = (
        args.session_matrix_report_json.strip()
        or default_artifact_relpath(
            category="reports",
            stem="agent-channel-session-matrix",
            profile=args.profile,
            run_suffix=run_suffix,
            extension="json",
        )
    )
    session_matrix_report_markdown = (
        args.session_matrix_report_markdown.strip()
        or default_artifact_relpath(
            category="reports",
            stem="agent-channel-session-matrix",
            profile=args.profile,
            run_suffix=run_suffix,
            extension="md",
        )
    )
    trace_report_json = args.trace_report_json.strip() or default_artifact_relpath(
        category="reports",
        stem="omni-agent-trace-reconstruction",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="json",
    )
    trace_report_markdown = args.trace_report_markdown.strip() or default_artifact_relpath(
        category="reports",
        stem="omni-agent-trace-reconstruction",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="md",
    )
    cross_group_report_json = args.cross_group_report_json.strip() or default_artifact_relpath(
        category="reports",
        stem="agent-channel-cross-group-complex",
        profile=args.profile,
        run_suffix=run_suffix,
        extension="json",
    )
    cross_group_report_markdown = (
        args.cross_group_report_markdown.strip()
        or default_artifact_relpath(
            category="reports",
            stem="agent-channel-cross-group-complex",
            profile=args.profile,
            run_suffix=run_suffix,
            extension="md",
        )
    )

    valkey_url = args.valkey_url.strip() or f"redis://127.0.0.1:{args.valkey_port}/0"
    valkey_prefix = args.valkey_prefix.strip() or default_valkey_prefix(args.profile)
    webhook_secret = args.webhook_secret.strip() or secrets.token_urlsafe(24)
    chat_id = int(args.chat_id)
    user_id = int(args.user_id)
    chat_b = int(args.chat_b) if args.chat_b is not None else chat_id + 1
    chat_c = int(args.chat_c) if args.chat_c is not None else chat_id + 2
    user_b = int(args.user_b) if args.user_b is not None else user_id + 1
    user_c = int(args.user_c) if args.user_c is not None else user_id + 2

    return GateConfig(
        profile=args.profile,
        project_root=project_root,
        script_dir=project_root / "scripts" / "channel",
        agent_bin=agent_bin,
        webhook_port=resolved_webhook_port,
        telegram_api_port=resolved_telegram_api_port,
        valkey_port=args.valkey_port,
        valkey_url=valkey_url,
        valkey_prefix=valkey_prefix,
        username=args.username.strip(),
        webhook_secret=webhook_secret,
        chat_id=chat_id,
        chat_b=chat_b,
        chat_c=chat_c,
        user_id=user_id,
        user_b=user_b,
        user_c=user_c,
        runtime_log_file=(project_root / runtime_log_file).resolve(),
        mock_log_file=(project_root / mock_log_file).resolve(),
        runtime_startup_timeout_secs=int(args.runtime_startup_timeout_secs),
        quick_max_wait=int(args.quick_max_wait),
        quick_max_idle=int(args.quick_max_idle),
        full_max_wait=int(args.full_max_wait),
        full_max_idle=int(args.full_max_idle),
        matrix_max_wait=int(args.matrix_max_wait),
        matrix_max_idle=int(args.matrix_max_idle),
        benchmark_iterations=int(args.benchmark_iterations),
        skip_matrix=bool(args.skip_matrix),
        skip_benchmark=bool(args.skip_benchmark),
        skip_evolution=bool(args.skip_evolution),
        skip_rust_regressions=bool(args.skip_rust_regressions),
        skip_discover_cache_gate=bool(args.skip_discover_cache_gate),
        skip_reflection_quality_gate=bool(args.skip_reflection_quality_gate),
        skip_trace_reconstruction_gate=bool(args.skip_trace_reconstruction_gate),
        skip_cross_group_complex_gate=bool(args.skip_cross_group_complex_gate),
        evolution_report_json=(project_root / evolution_report_json).resolve(),
        benchmark_report_json=(project_root / benchmark_report_json).resolve(),
        session_matrix_report_json=(project_root / session_matrix_report_json).resolve(),
        session_matrix_report_markdown=(project_root / session_matrix_report_markdown).resolve(),
        trace_report_json=(project_root / trace_report_json).resolve(),
        trace_report_markdown=(project_root / trace_report_markdown).resolve(),
        cross_group_report_json=(project_root / cross_group_report_json).resolve(),
        cross_group_report_markdown=(project_root / cross_group_report_markdown).resolve(),
        cross_group_dataset=Path(args.cross_group_dataset).expanduser().resolve(),
        cross_group_scenario_id=args.cross_group_scenario.strip(),
        min_planned_hits=int(args.min_planned_hits),
        min_successful_corrections=int(args.min_successful_corrections),
        min_recall_credit_events=int(args.min_recall_credit_events),
        min_quality_score=float(args.min_quality_score),
        slow_response_min_duration_ms=int(args.slow_response_min_duration_ms),
        slow_response_long_step_ms=int(args.slow_response_long_step_ms),
        slow_response_min_long_steps=int(args.slow_response_min_long_steps),
        trace_min_quality_score=float(args.trace_min_quality_score),
        trace_max_events=int(args.trace_max_events),
        min_session_steps=int(args.min_session_steps),
        require_cross_group_step=bool(args.require_cross_group_step),
        require_mixed_batch_steps=bool(args.require_mixed_batch_steps),
        cross_group_max_wait=int(args.cross_group_max_wait),
        cross_group_max_idle=int(args.cross_group_max_idle),
        cross_group_max_parallel=int(args.cross_group_max_parallel),
        discover_cache_hit_p95_ms=float(args.discover_cache_hit_p95_ms),
        discover_cache_miss_p95_ms=float(args.discover_cache_miss_p95_ms),
        discover_cache_bench_iterations=int(args.discover_cache_bench_iterations),
        max_mcp_call_waiting_events=int(args.max_mcp_call_waiting_events),
        max_mcp_connect_waiting_events=int(args.max_mcp_connect_waiting_events),
        max_mcp_waiting_events_total=int(args.max_mcp_waiting_events_total),
    )


def run_command(
    cmd: list[str],
    *,
    title: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    print()
    print(f">>> {title}", flush=True)
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(cwd), env=env)


def read_tail(path: Path, max_lines: int = 80) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def count_log_event(path: Path, event_name: str) -> int:
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(rf'event="?{re.escape(event_name)}"?')
    return len(pattern.findall(content))


def wait_for_log_regex(
    path: Path,
    pattern: str,
    *,
    timeout_secs: int,
    process: subprocess.Popen[str] | None = None,
) -> None:
    regex = re.compile(pattern)
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            tail = read_tail(path)
            raise RuntimeError(
                f"runtime process exited before readiness check passed.\ntail:\n{tail}"
            )
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore")
            if regex.search(content):
                return
        time.sleep(1.0)
    tail = read_tail(path)
    raise RuntimeError(
        f"timed out waiting for log pattern: {pattern}\nlog_file={path}\ntail:\n{tail}"
    )


def wait_for_mock_health(host: str, port: int, timeout_secs: int = 20) -> None:
    url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"mock Telegram API health endpoint not ready: {url}")


def terminate_process(process: subprocess.Popen[str] | None, *, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    print(f"{name} stopped (exit={process.returncode})", flush=True)


def ensure_parent_dirs(*paths: Path) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def start_background_process(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_file: Path,
    title: str,
) -> tuple[subprocess.Popen[str], object]:
    ensure_parent_dirs(log_file)
    handle = log_file.open("w", encoding="utf-8")
    print()
    print(f">>> {title}", flush=True)
    print("+ " + " ".join(cmd), flush=True)
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=None,
    )
    return process, handle


def assert_evolution_quality(cfg: GateConfig) -> None:
    if not cfg.evolution_report_json.exists():
        raise RuntimeError(f"missing evolution report: {cfg.evolution_report_json}")
    report = json.loads(cfg.evolution_report_json.read_text(encoding="utf-8"))
    if not bool(report.get("overall_passed", False)):
        raise RuntimeError("evolution report indicates overall failure")
    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise RuntimeError("evolution report has no scenarios")
    scenario = scenarios[0]
    quality = scenario.get("quality", {})
    planned_hits = int(quality.get("planned_hits", 0))
    successful_corrections = int(quality.get("successful_corrections", 0))
    recall_credit_events = int(quality.get("recall_credit_events", 0))
    quality_score = float(quality.get("quality_score", 0.0))

    failures: list[str] = []
    if planned_hits < cfg.min_planned_hits:
        failures.append(f"planned_hits={planned_hits} < {cfg.min_planned_hits}")
    if successful_corrections < cfg.min_successful_corrections:
        failures.append(
            f"successful_corrections={successful_corrections} < {cfg.min_successful_corrections}"
        )
    if recall_credit_events < cfg.min_recall_credit_events:
        failures.append(
            f"recall_credit_events={recall_credit_events} < {cfg.min_recall_credit_events}"
        )
    if quality_score < cfg.min_quality_score:
        failures.append(f"quality_score={quality_score:.2f} < {cfg.min_quality_score:.2f}")

    if failures:
        raise RuntimeError("evolution quality gates failed: " + "; ".join(failures))

    print(
        "Evolution quality gates passed: "
        f"planned_hits={planned_hits}, "
        f"successful_corrections={successful_corrections}, "
        f"recall_credit_events={recall_credit_events}, "
        f"quality_score={quality_score:.2f}",
        flush=True,
    )


def assert_benchmark_quality(cfg: GateConfig) -> None:
    if not cfg.benchmark_report_json.exists():
        raise RuntimeError(f"missing benchmark report: {cfg.benchmark_report_json}")
    report = json.loads(cfg.benchmark_report_json.read_text(encoding="utf-8"))
    mode_summaries = report.get("mode_summaries")
    if not isinstance(mode_summaries, dict) or not mode_summaries:
        raise RuntimeError("benchmark report missing mode_summaries")

    failures: list[str] = []
    for mode in ("baseline", "adaptive"):
        summary = mode_summaries.get(mode)
        if not isinstance(summary, dict):
            failures.append(f"missing mode summary: {mode}")
            continue
        query_turns = int(summary.get("query_turns", 0))
        mcp_error_turns = int(summary.get("mcp_error_turns", 0))
        if query_turns <= 0:
            failures.append(f"{mode}.query_turns={query_turns} <= 0")
        if mcp_error_turns > 0:
            failures.append(f"{mode}.mcp_error_turns={mcp_error_turns} > 0")

    if failures:
        raise RuntimeError("benchmark quality gates failed: " + "; ".join(failures))

    print("Benchmark quality gates passed (query_turns > 0 and mcp_error_turns == 0).", flush=True)


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise RuntimeError(f"missing report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid report payload (expected object): {path}")
    return payload


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def assert_evolution_slow_response_quality(cfg: GateConfig) -> None:
    report = load_json(cfg.evolution_report_json)
    scenarios_obj = report.get("scenarios")
    scenarios = scenarios_obj if isinstance(scenarios_obj, list) else []
    if not scenarios:
        raise RuntimeError("evolution report has no scenarios for slow-response gate")

    scenario = scenarios[0] if isinstance(scenarios[0], dict) else {}
    duration_ms = _safe_int(scenario.get("duration_ms"), default=0)
    steps_obj = scenario.get("steps")
    steps = steps_obj if isinstance(steps_obj, list) else []
    long_steps = sum(
        1
        for step in steps
        if isinstance(step, dict)
        and _safe_int(step.get("duration_ms"), default=0) >= cfg.slow_response_long_step_ms
    )

    failures: list[str] = []
    if duration_ms < cfg.slow_response_min_duration_ms:
        failures.append(
            "evolution.duration_ms="
            f"{duration_ms} < slow_response_min_duration_ms={cfg.slow_response_min_duration_ms}"
        )
    if long_steps < cfg.slow_response_min_long_steps:
        failures.append(
            "evolution.long_steps="
            f"{long_steps} < slow_response_min_long_steps={cfg.slow_response_min_long_steps} "
            f"(threshold={cfg.slow_response_long_step_ms}ms)"
        )
    if failures:
        raise RuntimeError("slow-response resilience gate failed: " + "; ".join(failures))

    print(
        "Slow-response resilience gate passed: "
        f"duration_ms={duration_ms}, "
        f"long_steps={long_steps}, "
        f"long_step_threshold_ms={cfg.slow_response_long_step_ms}",
        flush=True,
    )


def assert_session_matrix_quality(cfg: GateConfig) -> None:
    report = load_json(cfg.session_matrix_report_json)
    if not bool(report.get("overall_passed", False)):
        raise RuntimeError("session matrix report indicates overall failure")

    summary_obj = report.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    steps_total = int(summary.get("total", 0))
    steps_failed = int(summary.get("failed", 0))

    steps_obj = report.get("steps")
    steps = steps_obj if isinstance(steps_obj, list) else []
    steps_by_name: dict[str, dict[str, object]] = {}
    for item in steps:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        steps_by_name[name] = item

    # In `chat` partition mode, cross-group concurrency is validated by
    # `concurrent_baseline_cross_chat` and the dedicated `concurrent_cross_group`
    # step is intentionally skipped, so nightly step totals are one lower.
    expected_min_session_steps = cfg.min_session_steps
    if (
        "concurrent_baseline_cross_chat" in steps_by_name
        and "concurrent_cross_group" not in steps_by_name
    ):
        expected_min_session_steps = max(1, cfg.min_session_steps - 1)

    if steps_total < expected_min_session_steps:
        raise RuntimeError(
            "session matrix steps below threshold: "
            f"total={steps_total} < min_session_steps={expected_min_session_steps}"
        )
    if steps_failed > 0:
        raise RuntimeError(f"session matrix has failed steps: failed={steps_failed}")

    config_obj = report.get("config")
    config = config_obj if isinstance(config_obj, dict) else {}
    chat_ids = (
        int(config.get("chat_id", cfg.chat_id)),
        int(config.get("chat_b", cfg.chat_b)),
        int(config.get("chat_c", cfg.chat_c)),
    )
    if len(set(chat_ids)) < 3:
        raise RuntimeError(
            f"session matrix did not run with three distinct groups: chat_ids={chat_ids}"
        )

    if cfg.require_cross_group_step:
        cross_group = steps_by_name.get("concurrent_cross_group")
        cross_chat_baseline = steps_by_name.get("concurrent_baseline_cross_chat")
        if not isinstance(cross_group, dict) and not isinstance(cross_chat_baseline, dict):
            raise RuntimeError("session matrix missing required step: concurrent_cross_group")
        if isinstance(cross_group, dict) and not bool(cross_group.get("passed", False)):
            raise RuntimeError("session matrix cross-group step failed")
        if isinstance(cross_chat_baseline, dict) and not bool(
            cross_chat_baseline.get("passed", False)
        ):
            raise RuntimeError("session matrix cross-group baseline step failed")

    if cfg.require_mixed_batch_steps:
        required_mixed = (
            "mixed_reset_session_a",
            "mixed_resume_status_session_b",
            "mixed_plain_session_c",
        )
        missing = [name for name in required_mixed if name not in steps_by_name]
        if missing:
            raise RuntimeError(f"session matrix missing mixed batch steps: {missing}")
        failed = [
            name for name in required_mixed if not bool(steps_by_name[name].get("passed", False))
        ]
        if failed:
            raise RuntimeError(f"session matrix mixed batch steps failed: {failed}")

    print(
        "Session matrix quality gates passed: "
        f"steps_total={steps_total}, cross_group={'on' if cfg.require_cross_group_step else 'off'}, "
        f"mixed_batch={'on' if cfg.require_mixed_batch_steps else 'off'}",
        flush=True,
    )


def assert_cross_group_complex_quality(cfg: GateConfig) -> None:
    report = load_json(cfg.cross_group_report_json)
    if not bool(report.get("overall_passed", False)):
        raise RuntimeError("cross-group complex report indicates overall failure")

    scenarios_obj = report.get("scenarios")
    scenarios = scenarios_obj if isinstance(scenarios_obj, list) else []
    scenario_payload: dict[str, object] | None = None
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        if str(item.get("scenario_id", "")).strip() == cfg.cross_group_scenario_id:
            scenario_payload = item
            break
    if scenario_payload is None:
        raise RuntimeError(
            f"cross-group complex report missing scenario: {cfg.cross_group_scenario_id}"
        )
    if not bool(scenario_payload.get("passed", False)):
        raise RuntimeError("cross-group complex scenario failed")

    steps_obj = scenario_payload.get("steps")
    steps = steps_obj if isinstance(steps_obj, list) else []
    if not steps:
        raise RuntimeError("cross-group complex scenario has no steps")

    aliases = {
        str(step.get("session_alias", "")).strip()
        for step in steps
        if isinstance(step, dict) and str(step.get("session_alias", "")).strip()
    }
    missing_aliases = [alias for alias in ("a", "b", "c") if alias not in aliases]
    if missing_aliases:
        raise RuntimeError(
            f"cross-group complex scenario missing session aliases: {missing_aliases}"
        )

    session_keys = {
        str(step.get("session_key", "")).strip()
        for step in steps
        if isinstance(step, dict) and str(step.get("session_key", "")).strip()
    }
    if len(session_keys) < 3:
        raise RuntimeError(
            "cross-group complex scenario did not produce three distinct session keys: "
            f"session_keys={sorted(session_keys)}"
        )

    wave_counts: dict[int, int] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        wave_index = _safe_int(step.get("wave_index"), default=-1)
        wave_counts[wave_index] = wave_counts.get(wave_index, 0) + 1
    max_wave_width = max(wave_counts.values(), default=0)
    if max_wave_width < 2:
        raise RuntimeError("cross-group complex scenario did not exercise mixed concurrency waves")

    waiting_steps = sum(
        1 for step in steps if isinstance(step, dict) and bool(step.get("mcp_waiting_seen", False))
    )
    if waiting_steps > 0:
        raise RuntimeError(
            "cross-group complex scenario observed mcp waiting steps: "
            f"waiting_steps={waiting_steps}"
        )

    print(
        "Cross-group mixed-concurrency gate passed: "
        f"scenario_id={cfg.cross_group_scenario_id}, "
        f"steps={len(steps)}, "
        f"session_keys={len(session_keys)}, "
        f"max_wave_width={max_wave_width}",
        flush=True,
    )


def assert_trace_reconstruction_quality(cfg: GateConfig) -> None:
    report = load_json(cfg.trace_report_json)
    summary_obj = report.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    errors_obj = report.get("errors")
    errors = errors_obj if isinstance(errors_obj, list) else []

    events_total = int(summary.get("events_total", 0))
    quality_score = float(summary.get("quality_score", 0.0))
    stage_flags_obj = summary.get("stage_flags")
    stage_flags = stage_flags_obj if isinstance(stage_flags_obj, dict) else {}
    required_flags = (
        ("has_route", "has_injection", "has_reflection", "has_memory")
        if cfg.profile == "nightly"
        else ("has_memory",)
    )
    required_hits = sum(1 for flag in required_flags if bool(stage_flags.get(flag, False)))
    required_quality_score = (
        (float(required_hits) / float(len(required_flags))) * 100.0 if required_flags else 100.0
    )

    failures: list[str] = []
    if events_total <= 0:
        failures.append("events_total must be > 0")
    if errors:
        failures.append(f"errors present: {errors}")
    if required_quality_score < cfg.trace_min_quality_score:
        failures.append(
            "required_quality_score="
            f"{required_quality_score:.2f} < trace_min_quality_score={cfg.trace_min_quality_score:.2f}"
        )
    for required_flag in required_flags:
        if not bool(stage_flags.get(required_flag, False)):
            failures.append(f"stage flag missing: {required_flag}")

    if failures:
        raise RuntimeError("trace reconstruction quality gates failed: " + "; ".join(failures))

    print(
        "Trace reconstruction gate passed: "
        f"events_total={events_total}, quality_score={quality_score:.2f}, "
        f"required_quality_score={required_quality_score:.2f}",
        flush=True,
    )


def assert_mcp_waiting_warning_budget(cfg: GateConfig) -> None:
    if not cfg.runtime_log_file.exists():
        raise RuntimeError(f"missing runtime log file: {cfg.runtime_log_file}")

    call_waiting = count_log_event(cfg.runtime_log_file, "mcp.pool.call.waiting")
    connect_waiting = count_log_event(cfg.runtime_log_file, "mcp.pool.connect.waiting")
    waiting_total = call_waiting + connect_waiting

    failures: list[str] = []
    if call_waiting > cfg.max_mcp_call_waiting_events:
        failures.append(f"mcp.pool.call.waiting={call_waiting} > {cfg.max_mcp_call_waiting_events}")
    if connect_waiting > cfg.max_mcp_connect_waiting_events:
        failures.append(
            f"mcp.pool.connect.waiting={connect_waiting} > {cfg.max_mcp_connect_waiting_events}"
        )
    if waiting_total > cfg.max_mcp_waiting_events_total:
        failures.append(
            f"mcp_waiting_events_total={waiting_total} > {cfg.max_mcp_waiting_events_total}"
        )

    if failures:
        raise RuntimeError("mcp waiting warning budget exceeded: " + "; ".join(failures))

    print(
        "MCP waiting warning budget passed: "
        f"call_waiting={call_waiting}, "
        f"connect_waiting={connect_waiting}, "
        f"total={waiting_total}",
        flush=True,
    )


def run_reflection_quality_gate(cfg: GateConfig, *, cwd: Path, env: dict[str, str]) -> None:
    if cfg.skip_reflection_quality_gate:
        print("Skipping reflection quality gate (--skip-reflection-quality-gate).", flush=True)
        return
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--lib",
            "reflective_runtime_long_horizon_quality_thresholds",
        ],
        title="Reflection quality gate: long-horizon policy hint thresholds",
        cwd=cwd,
        env=env,
    )


def run_discover_cache_gate(cfg: GateConfig, *, cwd: Path, env: dict[str, str]) -> None:
    if cfg.skip_discover_cache_gate:
        print("Skipping discover cache gate (--skip-discover-cache-gate).", flush=True)
        return
    gate_env = env.copy()
    gate_env["OMNI_AGENT_DISCOVER_CACHE_HIT_P95_MS"] = f"{cfg.discover_cache_hit_p95_ms}"
    gate_env["OMNI_AGENT_DISCOVER_CACHE_MISS_P95_MS"] = f"{cfg.discover_cache_miss_p95_ms}"
    gate_env["OMNI_AGENT_DISCOVER_CACHE_BENCH_ITERATIONS"] = str(
        cfg.discover_cache_bench_iterations
    )
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "mcp_discover_cache",
            "discover_calls_use_valkey_read_through_cache_when_configured",
            "--",
            "--ignored",
            "--exact",
        ],
        title="Discover cache latency gate (A3)",
        cwd=cwd,
        env=gate_env,
    )


def run_trace_reconstruction_gate(cfg: GateConfig, *, cwd: Path, env: dict[str, str]) -> None:
    if cfg.skip_trace_reconstruction_gate:
        print("Skipping trace reconstruction gate (--skip-trace-reconstruction-gate).", flush=True)
        return

    script = cfg.script_dir / "reconstruct_omni_agent_trace.py"
    if not script.exists():
        raise FileNotFoundError(f"missing trace reconstruction script: {script}")

    required_stages = (
        ("route", "injection", "reflection", "memory") if cfg.profile == "nightly" else ("memory",)
    )

    run_command(
        [
            sys.executable,
            str(script),
            str(cfg.runtime_log_file),
            "--session-id",
            f"telegram:{cfg.chat_id}",
            "--max-events",
            str(cfg.trace_max_events),
            *[item for stage in required_stages for item in ("--required-stage", stage)],
            "--json-out",
            str(cfg.trace_report_json),
            "--markdown-out",
            str(cfg.trace_report_markdown),
        ],
        title="Trace reconstruction gate (S-01)",
        cwd=cwd,
        env=env,
    )
    assert_trace_reconstruction_quality(cfg)


def run_cross_group_complex_gate(cfg: GateConfig, *, cwd: Path, env: dict[str, str]) -> None:
    if cfg.skip_cross_group_complex_gate:
        print("Skipping cross-group complex gate (--skip-cross-group-complex-gate).", flush=True)
        return
    if not cfg.cross_group_dataset.exists():
        raise FileNotFoundError(f"cross-group dataset not found: {cfg.cross_group_dataset}")

    script = cfg.script_dir / "test_omni_agent_complex_scenarios.py"
    if not script.exists():
        raise FileNotFoundError(f"missing complex scenario script: {script}")

    # Use isolated chat IDs for this gate so prior suite traffic does not skew
    # per-step latency or session state for the concurrency stress scenario.
    cross_group_chat_a = max(cfg.chat_id, cfg.chat_b, cfg.chat_c) + 1000
    cross_group_chat_b = cross_group_chat_a + 1
    cross_group_chat_c = cross_group_chat_a + 2

    cmd = [
        sys.executable,
        str(script),
        "--dataset",
        str(cfg.cross_group_dataset),
        "--scenario",
        cfg.cross_group_scenario_id,
        "--max-wait",
        str(cfg.cross_group_max_wait),
        "--max-idle-secs",
        str(cfg.cross_group_max_idle),
        "--max-parallel",
        str(cfg.cross_group_max_parallel),
        "--execute-wave-parallel",
        "--chat-a",
        str(cross_group_chat_a),
        "--chat-b",
        str(cross_group_chat_b),
        "--chat-c",
        str(cross_group_chat_c),
        "--user-a",
        str(cfg.user_id),
        "--user-b",
        str(cfg.user_b),
        "--user-c",
        str(cfg.user_c),
        "--min-error-signals",
        "0",
        "--min-negative-feedback-events",
        "0",
        "--min-correction-checks",
        "0",
        "--min-successful-corrections",
        "0",
        "--min-planned-hits",
        "0",
        "--min-natural-language-steps",
        "0",
        "--min-recall-credit-events",
        "0",
        "--min-decay-events",
        "0",
        "--output-json",
        str(cfg.cross_group_report_json),
        "--output-markdown",
        str(cfg.cross_group_report_markdown),
    ]
    if cfg.username.strip():
        cmd.extend(["--username", cfg.username.strip()])

    run_command(
        cmd,
        title="Nightly gate: cross-group mixed-concurrency stress scenario (A4)",
        cwd=cwd,
        env=env,
    )
    assert_cross_group_complex_quality(cfg)


def run_gate(cfg: GateConfig) -> None:
    ensure_parent_dirs(cfg.runtime_log_file, cfg.mock_log_file, cfg.evolution_report_json)
    ensure_parent_dirs(
        cfg.benchmark_report_json,
        cfg.session_matrix_report_json,
        cfg.session_matrix_report_markdown,
        cfg.trace_report_json,
        cfg.trace_report_markdown,
        cfg.cross_group_report_json,
        cfg.cross_group_report_markdown,
    )

    valkey_start = cfg.script_dir / "valkey-start.sh"
    valkey_stop = cfg.script_dir / "valkey-stop.sh"
    mock_server = cfg.script_dir / "mock_telegram_api.py"
    memory_suite = cfg.script_dir / "test_omni_agent_memory_suite.py"
    session_matrix = cfg.script_dir / "test_omni_agent_session_matrix.py"
    memory_benchmark = cfg.script_dir / "test_omni_agent_memory_benchmark.py"

    if not mock_server.exists():
        raise FileNotFoundError(f"missing mock server script: {mock_server}")

    env = os.environ.copy()
    env["VALKEY_URL"] = cfg.valkey_url
    env["OMNI_AGENT_SESSION_VALKEY_PREFIX"] = cfg.valkey_prefix
    env["OMNI_AGENT_MEMORY_VALKEY_KEY_PREFIX"] = f"{cfg.valkey_prefix}:memory"
    env["TELEGRAM_BOT_TOKEN"] = env.get("TELEGRAM_BOT_TOKEN", "ci-telegram-token")
    env["TELEGRAM_WEBHOOK_SECRET"] = cfg.webhook_secret
    env["OMNI_AGENT_TELEGRAM_API_BASE_URL"] = f"http://127.0.0.1:{cfg.telegram_api_port}"
    env["OMNI_WEBHOOK_URL"] = f"http://127.0.0.1:{cfg.webhook_port}/telegram/webhook"
    env["OMNI_CHANNEL_LOG_FILE"] = str(cfg.runtime_log_file)
    env["OMNI_TEST_CHAT_ID"] = str(cfg.chat_id)
    env["OMNI_TEST_CHAT_B"] = str(cfg.chat_b)
    env["OMNI_TEST_CHAT_C"] = str(cfg.chat_c)
    env["OMNI_TEST_USER_ID"] = str(cfg.user_id)
    env["OMNI_TEST_USER_B"] = str(cfg.user_b)
    env["OMNI_TEST_USER_C"] = str(cfg.user_c)
    env["OMNI_TEST_USERNAME"] = cfg.username
    env["RUST_LOG"] = env.get("RUST_LOG", "omni_agent=debug")
    env["RUST_BACKTRACE"] = env.get("RUST_BACKTRACE", "1")

    mock_process: subprocess.Popen[str] | None = None
    mock_handle: object | None = None
    agent_process: subprocess.Popen[str] | None = None
    agent_handle: object | None = None
    valkey_preexisting = valkey_reachable(cfg.valkey_url)

    try:
        print(
            "CI gate Valkey isolation: "
            f"url={cfg.valkey_url} prefix={cfg.valkey_prefix} preexisting={valkey_preexisting}",
            flush=True,
        )
        run_command(
            ["bash", str(valkey_start), str(cfg.valkey_port)],
            title="Start Valkey",
            cwd=cfg.project_root,
            env=env,
        )

        mock_process, mock_handle = start_background_process(
            [
                sys.executable,
                str(mock_server),
                "--host",
                "127.0.0.1",
                "--port",
                str(cfg.telegram_api_port),
            ],
            cwd=cfg.project_root,
            env=env,
            log_file=cfg.mock_log_file,
            title="Start mock Telegram API",
        )
        wait_for_mock_health("127.0.0.1", cfg.telegram_api_port)

        if cfg.agent_bin is not None:
            agent_cmd = [
                str(cfg.agent_bin),
                "channel",
                "--provider",
                "telegram",
                "--mode",
                "webhook",
                "--webhook-bind",
                f"127.0.0.1:{cfg.webhook_port}",
                "--webhook-secret-token",
                cfg.webhook_secret,
                "--allowed-users",
                f"{cfg.user_id},{cfg.user_b},{cfg.user_c}",
                "--allowed-groups",
                "*",
                "--verbose",
            ]
        else:
            agent_cmd = [
                "cargo",
                "run",
                "-p",
                "omni-agent",
                "--",
                "channel",
                "--provider",
                "telegram",
                "--mode",
                "webhook",
                "--webhook-bind",
                f"127.0.0.1:{cfg.webhook_port}",
                "--webhook-secret-token",
                cfg.webhook_secret,
                "--allowed-users",
                f"{cfg.user_id},{cfg.user_b},{cfg.user_c}",
                "--allowed-groups",
                "*",
                "--verbose",
            ]

        agent_process, agent_handle = start_background_process(
            agent_cmd,
            cwd=cfg.project_root,
            env=env,
            log_file=cfg.runtime_log_file,
            title="Start omni-agent webhook runtime (CI gate)",
        )
        wait_for_log_regex(
            cfg.runtime_log_file,
            r"Telegram webhook listening on",
            timeout_secs=cfg.runtime_startup_timeout_secs,
            process=agent_process,
        )

        if cfg.profile == "quick":
            quick_suite_cmd = [
                sys.executable,
                str(memory_suite),
                "--suite",
                "full",
                "--skip-evolution",
                "--max-wait",
                str(cfg.quick_max_wait),
                "--max-idle-secs",
                str(cfg.quick_max_idle),
                "--username",
                cfg.username,
            ]
            if cfg.skip_rust_regressions:
                quick_suite_cmd.append("--skip-rust")
            run_command(
                quick_suite_cmd,
                title="Quick gate: memory suite (black-box + Rust regressions, evolution skipped)",
                cwd=cfg.project_root,
                env=env,
            )
            run_reflection_quality_gate(cfg, cwd=cfg.project_root, env=env)
            run_discover_cache_gate(cfg, cwd=cfg.project_root, env=env)
            run_trace_reconstruction_gate(cfg, cwd=cfg.project_root, env=env)
            assert_mcp_waiting_warning_budget(cfg)
            return

        # Complex evolution DAG steps can produce long, but still healthy, think/IO gaps.
        # Keep benchmark/session thresholds strict; only raise idle tolerance for this suite.
        nightly_suite_idle = max(cfg.full_max_idle, 80)
        nightly_suite_cmd = [
            sys.executable,
            str(memory_suite),
            "--suite",
            "full",
            "--max-wait",
            str(cfg.full_max_wait),
            "--max-idle-secs",
            str(nightly_suite_idle),
            "--username",
            cfg.username,
            "--evolution-output-json",
            str(cfg.evolution_report_json),
        ]
        if cfg.skip_evolution:
            nightly_suite_cmd.append("--skip-evolution")
        if cfg.skip_rust_regressions:
            nightly_suite_cmd.append("--skip-rust")
        run_command(
            nightly_suite_cmd,
            title="Nightly gate: full memory suite (includes evolution DAG + Rust regressions)",
            cwd=cfg.project_root,
            env=env,
        )
        if not cfg.skip_evolution:
            assert_evolution_quality(cfg)
            assert_evolution_slow_response_quality(cfg)
        else:
            print(
                "Skipping slow-response resilience gate because evolution is skipped.", flush=True
            )

        if not cfg.skip_matrix:
            run_command(
                [
                    sys.executable,
                    str(session_matrix),
                    "--max-wait",
                    str(cfg.matrix_max_wait),
                    "--max-idle-secs",
                    str(cfg.matrix_max_idle),
                    "--username",
                    cfg.username,
                    "--chat-id",
                    str(cfg.chat_id),
                    "--chat-b",
                    str(cfg.chat_b),
                    "--chat-c",
                    str(cfg.chat_c),
                    "--user-a",
                    str(cfg.user_id),
                    "--user-b",
                    str(cfg.user_b),
                    "--user-c",
                    str(cfg.user_c),
                    "--output-json",
                    str(cfg.session_matrix_report_json),
                    "--output-markdown",
                    str(cfg.session_matrix_report_markdown),
                    "--mixed-plain-prompt",
                    "/session json",
                ],
                title="Nightly gate: session matrix",
                cwd=cfg.project_root,
                env=env,
            )
            assert_session_matrix_quality(cfg)

        run_cross_group_complex_gate(cfg, cwd=cfg.project_root, env=env)

        if not cfg.skip_benchmark:
            run_command(
                [
                    sys.executable,
                    str(memory_benchmark),
                    "--username",
                    cfg.username,
                    "--chat-id",
                    str(cfg.chat_id),
                    "--user-id",
                    # Benchmark exercises control commands (/reset, /session feedback),
                    # so use the same known-admin test identity as the rest of nightly gate.
                    str(cfg.user_id),
                    "--iterations",
                    str(cfg.benchmark_iterations),
                    "--max-wait",
                    str(cfg.full_max_wait),
                    "--max-idle-secs",
                    str(cfg.full_max_idle),
                    "--output-json",
                    str(cfg.benchmark_report_json),
                ],
                title="Nightly gate: memory A/B benchmark",
                cwd=cfg.project_root,
                env=env,
            )
            assert_benchmark_quality(cfg)

        run_reflection_quality_gate(cfg, cwd=cfg.project_root, env=env)
        run_discover_cache_gate(cfg, cwd=cfg.project_root, env=env)
        run_trace_reconstruction_gate(cfg, cwd=cfg.project_root, env=env)
        assert_mcp_waiting_warning_budget(cfg)
    finally:
        terminate_process(agent_process, name="omni-agent runtime")
        terminate_process(mock_process, name="mock Telegram API")
        if agent_handle is not None:
            agent_handle.close()
        if mock_handle is not None:
            mock_handle.close()
        if not valkey_preexisting:
            subprocess.run(
                ["bash", str(valkey_stop), str(cfg.valkey_port)],
                cwd=str(cfg.project_root),
                env=env,
                check=False,
            )
        else:
            print(
                "Skip valkey-stop: existing Valkey instance was already running before CI gate.",
                flush=True,
            )


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    try:
        cfg = parse_args(project_root)
        run_gate(cfg)
        print()
        print(f"Memory CI gate passed (profile={cfg.profile}).", flush=True)
        return 0
    except (ValueError, RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
