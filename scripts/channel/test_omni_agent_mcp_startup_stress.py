#!/usr/bin/env python3
"""
MCP startup stress probe for omni-agent.

This probe repeatedly starts `omni-agent gateway` processes and verifies MCP
handshake robustness under reconnect pressure.

Outputs:
  - JSON report (machine-readable)
  - Markdown report (human-readable)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import select
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class StressConfig:
    rounds: int
    parallel: int
    startup_timeout_secs: int
    cooldown_secs: float
    executable: Path
    mcp_config: Path
    project_root: Path
    bind_addr: str
    rust_log: str
    output_json: Path
    output_markdown: Path
    restart_mcp_cmd: str | None
    restart_mcp_settle_secs: float
    health_url: str | None
    strict_health_check: bool
    health_probe_interval_secs: float
    health_probe_timeout_secs: float


@dataclass(frozen=True)
class ProbeResult:
    round_index: int
    worker_index: int
    success: bool
    reason: str
    startup_duration_ms: int
    return_code: int | None
    mcp_connect_succeeded: int
    mcp_connect_failed: int
    handshake_timeout_seen: bool
    connect_failed_seen: bool
    ready_seen: bool
    tail: str


@dataclass(frozen=True)
class HealthSample:
    ok: bool
    latency_ms: float
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stress MCP startup by repeatedly spawning omni-agent gateway and "
            "checking handshake logs."
        )
    )
    parser.add_argument("--rounds", type=int, default=6, help="Number of rounds (default: 6).")
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="Concurrent startups per round (default: 3).",
    )
    parser.add_argument(
        "--startup-timeout-secs",
        type=int,
        default=45,
        help="Max seconds waiting for gateway ready marker (default: 45).",
    )
    parser.add_argument(
        "--cooldown-secs",
        type=float,
        default=0.2,
        help="Delay between rounds (default: 0.2).",
    )
    parser.add_argument(
        "--executable",
        default="target/debug/omni-agent",
        help="Path to omni-agent executable (default: target/debug/omni-agent).",
    )
    parser.add_argument(
        "--mcp-config",
        default=".mcp.json",
        help="Path to MCP config file (default: .mcp.json).",
    )
    parser.add_argument(
        "--project-root",
        default=str(project_root_from(Path.cwd())),
        help="Project root for process cwd (default: auto-detect from .git).",
    )
    parser.add_argument(
        "--bind-addr",
        default="127.0.0.1:0",
        help="Gateway bind address (default: 127.0.0.1:0).",
    )
    parser.add_argument(
        "--rust-log",
        default=(
            "omni_agent::gateway::http=info,"
            "omni_agent::mcp_pool=debug,"
            "omni_agent::main_agent_builder=info"
        ),
        help="RUST_LOG used by spawned probe process.",
    )
    parser.add_argument(
        "--restart-mcp-cmd",
        default="",
        help="Optional shell command to restart MCP server between rounds.",
    )
    parser.add_argument(
        "--restart-mcp-settle-secs",
        type=float,
        default=2.0,
        help="Sleep after restart command before next round (default: 2.0).",
    )
    parser.add_argument(
        "--health-url",
        default="http://127.0.0.1:3002/health",
        help="MCP health endpoint checked before stress (empty to disable).",
    )
    parser.add_argument(
        "--strict-health-check",
        action="store_true",
        help="Fail immediately if health check is unavailable.",
    )
    parser.add_argument(
        "--health-probe-interval-secs",
        type=float,
        default=0.2,
        help="Background /health sampling interval during stress (default: 0.2, 0 disables).",
    )
    parser.add_argument(
        "--health-probe-timeout-secs",
        type=float,
        default=1.0,
        help="Timeout for each background /health probe (default: 1.0).",
    )
    parser.add_argument(
        "--output-json",
        default=str(default_report_path("omni-agent-mcp-startup-stress.json")),
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--output-markdown",
        default=str(default_report_path("omni-agent-mcp-startup-stress.md")),
        help="Output Markdown report path.",
    )
    return parser.parse_args()


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


def build_config(args: argparse.Namespace) -> StressConfig:
    if args.rounds <= 0:
        raise ValueError("--rounds must be positive.")
    if args.parallel <= 0:
        raise ValueError("--parallel must be positive.")
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

    project_root = resolve_path(args.project_root, Path.cwd())
    executable = resolve_path(args.executable, project_root)
    if not executable.exists():
        raise ValueError(
            f"executable not found: {executable}. Build first: cargo build -p omni-agent"
        )
    mcp_config = resolve_path(args.mcp_config, project_root)
    if not mcp_config.exists():
        raise ValueError(f"mcp config not found: {mcp_config}")

    restart_cmd = args.restart_mcp_cmd.strip() or None
    health_url = args.health_url.strip() or None

    return StressConfig(
        rounds=int(args.rounds),
        parallel=int(args.parallel),
        startup_timeout_secs=int(args.startup_timeout_secs),
        cooldown_secs=float(args.cooldown_secs),
        executable=executable,
        mcp_config=mcp_config,
        project_root=project_root,
        bind_addr=args.bind_addr.strip(),
        rust_log=args.rust_log.strip(),
        output_json=resolve_path(args.output_json, project_root),
        output_markdown=resolve_path(args.output_markdown, project_root),
        restart_mcp_cmd=restart_cmd,
        restart_mcp_settle_secs=float(args.restart_mcp_settle_secs),
        health_url=health_url,
        strict_health_check=bool(args.strict_health_check),
        health_probe_interval_secs=float(args.health_probe_interval_secs),
        health_probe_timeout_secs=float(args.health_probe_timeout_secs),
    )


def check_health(url: str, timeout_secs: float = 2.0) -> tuple[bool, str]:
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_secs) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, f"status={response.status} body={body[:180]}"
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return False, f"http_error={error.code} body={body[:180]}"
    except Exception as error:
        return False, f"error={error}"


def run_restart_command(command: str, cwd: Path) -> tuple[int, str]:
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


def classify_reason(
    *,
    ready_seen: bool,
    handshake_timeout_seen: bool,
    connect_failed_seen: bool,
    process_exited: bool,
    timed_out: bool,
) -> str:
    if ready_seen:
        return "ok"
    if handshake_timeout_seen:
        return "handshake_timeout"
    if connect_failed_seen:
        return "connect_failed"
    if timed_out:
        return "startup_timeout"
    if process_exited:
        return "process_exited_before_ready"
    return "unknown"


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    sorted_values = sorted(values)
    index = int(0.95 * (len(sorted_values) - 1))
    return float(sorted_values[index])


def summarize_health_samples(samples: Iterable[HealthSample]) -> dict[str, object]:
    rows = list(samples)
    total = len(rows)
    ok = sum(1 for row in rows if row.ok)
    failed = total - ok
    latencies = [row.latency_ms for row in rows if row.ok]
    error_counts: dict[str, int] = {}
    for row in rows:
        if row.ok:
            continue
        key = row.detail[:120]
        error_counts[key] = error_counts.get(key, 0) + 1
    top_errors = sorted(error_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    return {
        "health_samples_total": total,
        "health_samples_ok": ok,
        "health_samples_failed": failed,
        "health_failure_rate": (failed / total) if total else 0.0,
        "health_avg_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "health_p95_latency_ms": p95(latencies),
        "health_max_latency_ms": max(latencies) if latencies else 0.0,
        "health_error_top": [
            {"detail": detail, "count": count} for detail, count in top_errors if detail.strip()
        ],
    }


def _collect_health_sample(url: str, timeout_secs: float) -> HealthSample:
    started = time.monotonic()
    ok, detail = check_health(url, timeout_secs=timeout_secs)
    latency_ms = (time.monotonic() - started) * 1000.0
    return HealthSample(ok=ok, latency_ms=latency_ms, detail=detail)


def run_single_probe(cfg: StressConfig, round_index: int, worker_index: int) -> ProbeResult:
    env = os.environ.copy()
    env["RUST_LOG"] = cfg.rust_log
    cmd = [
        str(cfg.executable),
        "gateway",
        "--bind",
        cfg.bind_addr,
        "--mcp-config",
        str(cfg.mcp_config),
    ]

    started = time.monotonic()
    process = subprocess.Popen(
        cmd,
        cwd=str(cfg.project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    lines: list[str] = []
    ready_seen = False
    handshake_timeout_seen = False
    connect_failed_seen = False
    timed_out = False
    return_code: int | None = None
    mcp_connect_succeeded = 0
    mcp_connect_failed = 0
    deadline = time.monotonic() + cfg.startup_timeout_secs

    try:
        assert process.stdout is not None
        while True:
            if time.monotonic() > deadline:
                timed_out = True
                break

            if process.poll() is not None:
                return_code = process.returncode
                break

            ready, _, _ = select.select([process.stdout], [], [], 0.2)
            if not ready:
                continue
            raw_line = process.stdout.readline()
            if raw_line == "":
                if process.poll() is not None:
                    return_code = process.returncode
                    break
                continue

            line = raw_line.rstrip("\n")
            lines.append(line)

            if 'event="mcp.pool.connect.succeeded"' in line:
                mcp_connect_succeeded += 1
            if 'event="mcp.pool.connect.failed"' in line:
                mcp_connect_failed += 1

            if "MCP handshake timeout" in line:
                handshake_timeout_seen = True
            if "MCP connect failed after" in line:
                connect_failed_seen = True
            if "gateway listening on" in line:
                ready_seen = True
                break
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if return_code is None:
            return_code = process.returncode
        tail_extra = ""
        if process.stdout is not None:
            try:
                tail_extra = process.stdout.read()
            except Exception:
                tail_extra = ""
        if tail_extra:
            lines.extend(tail_extra.splitlines())

    duration_ms = int((time.monotonic() - started) * 1000)
    reason = classify_reason(
        ready_seen=ready_seen,
        handshake_timeout_seen=handshake_timeout_seen,
        connect_failed_seen=connect_failed_seen,
        process_exited=return_code is not None,
        timed_out=timed_out,
    )
    success = reason == "ok"

    return ProbeResult(
        round_index=round_index,
        worker_index=worker_index,
        success=success,
        reason=reason,
        startup_duration_ms=duration_ms,
        return_code=return_code,
        mcp_connect_succeeded=mcp_connect_succeeded,
        mcp_connect_failed=mcp_connect_failed,
        handshake_timeout_seen=handshake_timeout_seen,
        connect_failed_seen=connect_failed_seen,
        ready_seen=ready_seen,
        tail="\n".join(lines[-40:]),
    )


def summarize(
    results: Iterable[ProbeResult],
    health_samples: Iterable[HealthSample],
) -> dict[str, object]:
    rows = list(results)
    total = len(rows)
    passed = sum(1 for row in rows if row.success)
    failed = total - passed
    reasons: dict[str, int] = {}
    for row in rows:
        reasons[row.reason] = reasons.get(row.reason, 0) + 1

    success_durations = [row.startup_duration_ms for row in rows if row.success]
    failure_durations = [row.startup_duration_ms for row in rows if not row.success]

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / total) if total else 0.0,
        "reason_counts": reasons,
        "success_avg_startup_ms": statistics.fmean(success_durations) if success_durations else 0.0,
        "success_p95_startup_ms": p95(success_durations),
        "failure_avg_startup_ms": statistics.fmean(failure_durations) if failure_durations else 0.0,
    }
    summary.update(summarize_health_samples(health_samples))
    return summary


def render_markdown(report: dict[str, object]) -> str:
    summary = report["summary"]
    results = report["results"]
    lines = [
        "# MCP Startup Stress Report",
        "",
        "## Overview",
        f"- Started: `{report['started_at']}`",
        f"- Finished: `{report['finished_at']}`",
        f"- Duration: `{report['duration_ms']} ms`",
        f"- Total probes: `{summary['total']}`",
        f"- Passed: `{summary['passed']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Pass rate: `{summary['pass_rate']:.2%}`",
        f"- Success avg startup: `{summary['success_avg_startup_ms']:.1f} ms`",
        f"- Success p95 startup: `{summary['success_p95_startup_ms']:.1f} ms`",
        "",
        "## Health Monitor",
        f"- Samples: `{summary['health_samples_total']}`",
        f"- Failed probes: `{summary['health_samples_failed']}`",
        f"- Failure rate: `{summary['health_failure_rate']:.2%}`",
        f"- Avg latency: `{summary['health_avg_latency_ms']:.1f} ms`",
        f"- P95 latency: `{summary['health_p95_latency_ms']:.1f} ms`",
        f"- Max latency: `{summary['health_max_latency_ms']:.1f} ms`",
        "",
        "## Failure Reasons",
    ]
    health_errors = summary.get("health_error_top", [])
    if isinstance(health_errors, list):
        lines.append("### Health Error Top")
        if health_errors:
            for item in health_errors:
                if not isinstance(item, dict):
                    continue
                detail = str(item.get("detail", "")).strip()
                count = int(item.get("count", 0))
                if detail:
                    lines.append(f"- `{count}` x `{detail}`")
        else:
            lines.append("- None")
        lines.append("")

    reason_counts = summary["reason_counts"]
    if reason_counts:
        for reason, count in sorted(reason_counts.items(), key=lambda item: item[0]):
            lines.append(f"- `{reason}`: `{count}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Probe Rows",
            (
                "| Round | Worker | Result | Reason | Startup ms | "
                "mcp.connect.succeeded | mcp.connect.failed |"
            ),
            "|---:|---:|---|---|---:|---:|---:|",
        ]
    )
    for row in results:
        lines.append(
            "| {round} | {worker} | {result} | {reason} | {startup} | {ok} | {failed} |".format(
                round=row["round_index"],
                worker=row["worker_index"],
                result="PASS" if row["success"] else "FAIL",
                reason=row["reason"],
                startup=row["startup_duration_ms"],
                ok=row["mcp_connect_succeeded"],
                failed=row["mcp_connect_failed"],
            )
        )

    failures = [row for row in results if not row["success"]]
    lines.extend(["", "## Failure Tails"])
    if not failures:
        lines.append("- None")
    else:
        for row in failures:
            lines.extend(
                [
                    (
                        f"### round={row['round_index']} worker={row['worker_index']} "
                        f"reason={row['reason']}"
                    ),
                    "```text",
                    row["tail"] or "(no logs)",
                    "```",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def run_stress(cfg: StressConfig) -> dict[str, object]:
    started_dt = datetime.now(UTC)
    started = time.monotonic()
    health_preflight = None

    if cfg.health_url:
        ok, detail = check_health(cfg.health_url)
        health_preflight = {"url": cfg.health_url, "ok": ok, "detail": detail}
        if cfg.strict_health_check and not ok:
            raise RuntimeError(f"health check failed before stress: {detail}")

    results: list[ProbeResult] = []
    health_samples: list[HealthSample] = []
    health_samples_lock = threading.Lock()
    health_stop = threading.Event()
    restart_events: list[dict[str, object]] = []

    health_thread: threading.Thread | None = None
    if cfg.health_url and cfg.health_probe_interval_secs > 0:
        health_url = cfg.health_url

        def _health_loop() -> None:
            assert health_url is not None
            while not health_stop.is_set():
                sample = _collect_health_sample(health_url, cfg.health_probe_timeout_secs)
                with health_samples_lock:
                    health_samples.append(sample)
                if cfg.health_probe_interval_secs <= 0:
                    return
                health_stop.wait(cfg.health_probe_interval_secs)

        health_thread = threading.Thread(target=_health_loop, daemon=True)
        health_thread.start()

    try:
        for round_index in range(1, cfg.rounds + 1):
            if round_index > 1 and cfg.restart_mcp_cmd:
                code, output = run_restart_command(cfg.restart_mcp_cmd, cfg.project_root)
                restart_events.append(
                    {"round": round_index, "return_code": code, "output_tail": output[-400:]}
                )
                if code != 0:
                    raise RuntimeError(
                        f"restart command failed at round {round_index} (code={code}): "
                        f"{output[-400:]}"
                    )
                if cfg.restart_mcp_settle_secs > 0:
                    time.sleep(cfg.restart_mcp_settle_secs)

            round_started = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.parallel) as executor:
                futures = [
                    executor.submit(run_single_probe, cfg, round_index, worker_index)
                    for worker_index in range(1, cfg.parallel + 1)
                ]
                for future in concurrent.futures.as_completed(futures):
                    results.append(future.result())

            if cfg.cooldown_secs > 0 and round_index < cfg.rounds:
                elapsed = time.monotonic() - round_started
                if elapsed < cfg.cooldown_secs:
                    time.sleep(cfg.cooldown_secs - elapsed)
    finally:
        health_stop.set()
        if health_thread is not None:
            health_thread.join(timeout=max(1.0, cfg.health_probe_timeout_secs + 1.0))

    finished_dt = datetime.now(UTC)
    with health_samples_lock:
        health_rows = list(health_samples)
    summary = summarize(results, health_rows)
    report = {
        "started_at": started_dt.isoformat(),
        "finished_at": finished_dt.isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "config": {
            "rounds": cfg.rounds,
            "parallel": cfg.parallel,
            "startup_timeout_secs": cfg.startup_timeout_secs,
            "cooldown_secs": cfg.cooldown_secs,
            "executable": str(cfg.executable),
            "mcp_config": str(cfg.mcp_config),
            "bind_addr": cfg.bind_addr,
            "rust_log": cfg.rust_log,
            "health_url": cfg.health_url,
            "health_probe_interval_secs": cfg.health_probe_interval_secs,
            "health_probe_timeout_secs": cfg.health_probe_timeout_secs,
            "restart_mcp_cmd": cfg.restart_mcp_cmd,
            "restart_mcp_settle_secs": cfg.restart_mcp_settle_secs,
        },
        "health_preflight": health_preflight,
        "restart_events": restart_events,
        "summary": summary,
        "results": [asdict(row) for row in results],
        "health_samples": [asdict(row) for row in health_rows[-200:]],
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

    try:
        report = run_stress(cfg)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    write_report(report, cfg.output_json, cfg.output_markdown)
    summary = report["summary"]
    print("MCP startup stress completed.")
    print(
        "  probes={total} passed={passed} failed={failed}".format(
            total=summary["total"], passed=summary["passed"], failed=summary["failed"]
        )
    )
    print(
        "  success_avg_startup_ms={:.1f} success_p95_startup_ms={:.1f}".format(
            summary["success_avg_startup_ms"], summary["success_p95_startup_ms"]
        )
    )
    print(
        "  health_failure_rate={:.2%} health_p95_latency_ms={:.1f}".format(
            summary["health_failure_rate"],
            summary["health_p95_latency_ms"],
        )
    )
    print(f"  json_report={cfg.output_json}")
    print(f"  markdown_report={cfg.output_markdown}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
