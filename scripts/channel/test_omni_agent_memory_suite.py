#!/usr/bin/env python3
"""
Memory-focused validation suite for omni-agent Telegram channel/runtime.

This script combines:
  1) command-level black-box checks (webhook/runtime path)
  2) targeted Rust regression checks for memory behaviors
  3) optional Valkey cross-instance memory continuity check
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from test_config_resolver import (
        normalize_telegram_session_partition_mode,
        session_partition_mode_from_runtime_log,
        telegram_session_partition_mode,
    )
except ModuleNotFoundError as import_err:
    _resolver_path = Path(__file__).resolve().with_name("test_config_resolver.py")
    _resolver_spec = importlib.util.spec_from_file_location("test_config_resolver", _resolver_path)
    if _resolver_spec is None or _resolver_spec.loader is None:
        raise RuntimeError(f"failed to load resolver module from {_resolver_path}") from import_err
    _resolver_module = importlib.util.module_from_spec(_resolver_spec)
    sys.modules.setdefault(_resolver_spec.name, _resolver_module)
    _resolver_spec.loader.exec_module(_resolver_module)
    normalize_telegram_session_partition_mode = (
        _resolver_module.normalize_telegram_session_partition_mode
    )
    session_partition_mode_from_runtime_log = (
        _resolver_module.session_partition_mode_from_runtime_log
    )
    telegram_session_partition_mode = _resolver_module.telegram_session_partition_mode

DEFAULT_MAX_WAIT = int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "25"))
DEFAULT_MAX_IDLE_SECS = int(os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "25"))
DEFAULT_VALKEY_URL = os.environ.get("VALKEY_URL", "redis://127.0.0.1:6379/0")
FORBIDDEN_LOG_PATTERN = "tools/call: Mcp error"
DEFAULT_EVOLUTION_SCENARIO_ID = "memory_self_correction_high_complexity_dag"


def default_valkey_prefix(tag: str) -> str:
    safe_tag = tag.strip().lower() or "memory-suite"
    return f"omni-agent:session:{safe_tag}:{os.getpid()}:{int(time.time() * 1000)}"


def default_report_path(filename: str) -> Path:
    runtime_root = Path(os.environ.get("PRJ_RUNTIME_DIR", ".run"))
    if not runtime_root.is_absolute():
        project_root = Path(os.environ.get("PRJ_ROOT", Path.cwd()))
        runtime_root = project_root / runtime_root
    return runtime_root / "reports" / filename


def runtime_log_file() -> Path:
    return Path(os.environ.get("OMNI_CHANNEL_LOG_FILE", ".run/logs/omni-agent-webhook.log"))


def resolve_runtime_partition_mode() -> str | None:
    override = os.environ.get("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "").strip()
    normalized_override = normalize_telegram_session_partition_mode(override)
    if normalized_override:
        return normalized_override

    mode_from_log = session_partition_mode_from_runtime_log(runtime_log_file())
    if mode_from_log:
        return mode_from_log

    return telegram_session_partition_mode()


@dataclass(frozen=True)
class BlackboxCase:
    prompt: str
    expected_event: str
    extra_args: tuple[str, ...] = ()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run memory-focused omni-agent Telegram black-box + regression suite."
    )
    parser.add_argument(
        "--suite",
        choices=("quick", "full"),
        default="quick",
        help="Suite mode: quick (black-box only) or full (black-box + cargo regressions).",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=DEFAULT_MAX_WAIT,
        help=f"Per black-box probe max wait in seconds (default: {DEFAULT_MAX_WAIT}).",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=DEFAULT_MAX_IDLE_SECS,
        help=f"Per black-box probe max idle seconds (default: {DEFAULT_MAX_IDLE_SECS}).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME", ""),
        help="Synthetic Telegram username for allowlist checks.",
    )
    parser.add_argument(
        "--require-live-turn",
        action="store_true",
        help=(
            "Also probe a normal non-command turn and require memory recall observability "
            "events in logs."
        ),
    )
    parser.add_argument(
        "--skip-blackbox",
        action="store_true",
        help="Skip webhook black-box checks (useful when local webhook runtime is not running).",
    )
    parser.add_argument(
        "--skip-rust",
        action="store_true",
        help="Skip Rust regression checks.",
    )
    parser.add_argument(
        "--skip-evolution",
        action="store_true",
        help=(
            "Skip memory self-evolution DAG black-box scenario in full suite. "
            "By default, full suite includes this scenario."
        ),
    )
    parser.add_argument(
        "--evolution-dataset",
        default=str(
            Path(__file__).resolve().parent / "fixtures" / "memory_evolution_complex_scenarios.json"
        ),
        help="Path to memory self-evolution complex scenario dataset JSON.",
    )
    parser.add_argument(
        "--evolution-scenario",
        default=DEFAULT_EVOLUTION_SCENARIO_ID,
        help=(
            "Scenario id to run from the evolution dataset "
            f"(default: {DEFAULT_EVOLUTION_SCENARIO_ID})."
        ),
    )
    parser.add_argument(
        "--evolution-max-parallel",
        type=int,
        default=1,
        help="Max parallel probes per wave for evolution scenario (default: 1).",
    )
    parser.add_argument(
        "--evolution-output-json",
        default=str(default_report_path("omni-agent-memory-evolution.json")),
        help="Output JSON report path for evolution scenario.",
    )
    parser.add_argument(
        "--evolution-output-markdown",
        default=str(default_report_path("omni-agent-memory-evolution.md")),
        help="Output Markdown report path for evolution scenario.",
    )
    parser.add_argument(
        "--with-valkey",
        action="store_true",
        help="Run optional Valkey cross-instance memory snapshot continuity check.",
    )
    parser.add_argument(
        "--valkey-url",
        default=DEFAULT_VALKEY_URL,
        help=f"Valkey URL for optional --with-valkey checks (default: {DEFAULT_VALKEY_URL}).",
    )
    parser.add_argument(
        "--valkey-prefix",
        default="",
        help=(
            "Optional explicit Valkey key prefix for optional --with-valkey isolation. "
            "Default: an auto-generated per-run prefix."
        ),
    )
    return parser.parse_args()


def run_command(
    cmd: list[str],
    *,
    title: str,
    env: dict[str, str] | None = None,
) -> None:
    print()
    print(f">>> {title}", flush=True)
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def blackbox_cases(require_live_turn: bool) -> tuple[BlackboxCase, ...]:
    base = (
        BlackboxCase(
            prompt="/session memory json",
            expected_event="telegram.command.session_memory_json.replied",
            extra_args=("--expect-reply-json-field", "json_kind=session_memory"),
        ),
        BlackboxCase(
            prompt="/session feedback up json",
            expected_event="telegram.command.session_feedback_json.replied",
            extra_args=("--expect-reply-json-field", "json_kind=session_feedback"),
        ),
        BlackboxCase(
            prompt="/session feedback down json",
            expected_event="telegram.command.session_feedback_json.replied",
            extra_args=("--expect-reply-json-field", "json_kind=session_feedback"),
        ),
    )
    if not require_live_turn:
        return base
    return (
        *base,
        BlackboxCase(
            prompt="Please reply in one short sentence for memory probe.",
            expected_event="agent.memory.recall.planned",
            extra_args=(
                "--expect-log-regex",
                r"agent\.memory\.recall\.(planned|injected|skipped)",
            ),
        ),
    )


def run_blackbox_suite(
    script_dir: Path,
    *,
    max_wait: int,
    max_idle_secs: int,
    username: str,
    require_live_turn: bool,
) -> None:
    blackbox_script = script_dir / "agent_channel_blackbox.py"
    if not blackbox_script.exists():
        raise FileNotFoundError(f"black-box script not found: {blackbox_script}")
    runtime_partition_mode = resolve_runtime_partition_mode()
    if runtime_partition_mode:
        print(
            f"Resolved runtime session partition mode for black-box probes: {runtime_partition_mode}",
            flush=True,
        )
    allow_chat_ids = [
        token.strip()
        for token in os.environ.get("OMNI_BLACKBOX_ALLOWED_CHAT_IDS", "").split(",")
        if token.strip()
    ]
    if not allow_chat_ids:
        single_chat = os.environ.get("OMNI_TEST_CHAT_ID", "").strip()
        if single_chat:
            allow_chat_ids = [single_chat]

    for case in blackbox_cases(require_live_turn):
        cmd = [
            sys.executable,
            str(blackbox_script),
            "--prompt",
            case.prompt,
            "--expect-event",
            case.expected_event,
            "--forbid-log-regex",
            FORBIDDEN_LOG_PATTERN,
            "--max-wait",
            str(max_wait),
            "--max-idle-secs",
            str(max_idle_secs),
        ]
        for allowed_chat_id in allow_chat_ids:
            cmd.extend(["--allow-chat-id", allowed_chat_id])
        if username.strip():
            cmd.extend(["--username", username.strip()])
        if runtime_partition_mode:
            cmd.extend(["--session-partition", runtime_partition_mode])
        cmd.extend(case.extra_args)
        run_command(cmd, title=f"Black-box probe: {case.prompt}")


def run_memory_evolution_scenario(
    script_dir: Path,
    *,
    max_wait: int,
    max_idle_secs: int,
    username: str,
    dataset_path: Path,
    scenario_id: str,
    max_parallel: int,
    output_json: Path,
    output_markdown: Path,
) -> None:
    scenario_runner = script_dir / "test_omni_agent_complex_scenarios.py"
    if not scenario_runner.exists():
        raise FileNotFoundError(f"complex scenario runner not found: {scenario_runner}")
    if not dataset_path.exists():
        raise FileNotFoundError(f"evolution dataset not found: {dataset_path}")
    if max_parallel <= 0:
        raise ValueError("--evolution-max-parallel must be a positive integer.")

    cmd = [
        sys.executable,
        str(scenario_runner),
        "--dataset",
        str(dataset_path),
        "--scenario",
        scenario_id,
        "--max-wait",
        str(max_wait),
        "--max-idle-secs",
        str(max_idle_secs),
        "--max-parallel",
        str(max_parallel),
        "--output-json",
        str(output_json),
        "--output-markdown",
        str(output_markdown),
    ]
    if username.strip():
        cmd.extend(["--username", username.strip()])

    run_command(
        cmd,
        title=(
            "Black-box evolution: memory self-correction + feedback adaptation + "
            "cross-session isolation DAG"
        ),
    )


def run_rust_memory_regressions() -> None:
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "agent_memory_persistence_backend",
            "memory_turn_store_succeeds_when_embedding_endpoint_is_unavailable",
            "-q",
        ],
        title="Regression: embedding endpoint down fallback (3302 unavailable)",
    )
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--lib",
            "runtime_handle_inbound_session_memory_reports_latest_snapshot_json",
            "-q",
        ],
        title="Regression: /session memory json payload fields",
    )
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--lib",
            "runtime_handle_inbound_session_feedback_json",
            "-q",
        ],
        title="Regression: /session feedback json payload fields",
    )
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--lib",
            "agent::embedding_dimension::tests",
            "-q",
        ],
        title="Regression: embedding dimension auto-repair behavior",
    )
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--lib",
            "inspect_memory_recall_snapshot_keeps_embedding_repaired_source",
            "-q",
        ],
        title="Regression: session memory snapshot keeps embedding_repaired source",
    )


def ensure_valkey_cli() -> None:
    if shutil.which("valkey-cli") is None:
        raise RuntimeError("valkey-cli not found in PATH")


def check_valkey_connectivity(valkey_url: str) -> None:
    print(f"Checking Valkey connectivity at {valkey_url}...", flush=True)
    subprocess.run(
        ["valkey-cli", "-u", valkey_url, "ping"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_valkey_cross_instance_regression(valkey_url: str, valkey_prefix: str) -> None:
    ensure_valkey_cli()
    check_valkey_connectivity(valkey_url)
    env = os.environ.copy()
    env["VALKEY_URL"] = valkey_url
    env["OMNI_AGENT_SESSION_VALKEY_PREFIX"] = valkey_prefix
    env["OMNI_AGENT_MEMORY_VALKEY_KEY_PREFIX"] = f"{valkey_prefix}:memory"
    print(f"Valkey isolation prefix: {valkey_prefix}", flush=True)
    run_command(
        [
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "memory_recall_snapshot_is_shared_across_agent_instances_with_valkey",
            "--",
            "--ignored",
            "--nocapture",
        ],
        title="Regression: cross-instance /session memory snapshot continuity with Valkey",
        env=env,
    )


def main() -> int:
    args = parse_args()
    if args.max_wait <= 0:
        print("Error: --max-wait must be a positive integer.", file=sys.stderr)
        return 2
    if args.max_idle_secs <= 0:
        print("Error: --max-idle-secs must be a positive integer.", file=sys.stderr)
        return 2
    if args.evolution_max_parallel <= 0:
        print("Error: --evolution-max-parallel must be a positive integer.", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent
    try:
        if not args.skip_blackbox:
            print("Running memory black-box probes...", flush=True)
            run_blackbox_suite(
                script_dir=script_dir,
                max_wait=args.max_wait,
                max_idle_secs=args.max_idle_secs,
                username=args.username,
                require_live_turn=args.require_live_turn,
            )
            if args.suite == "full" and not args.skip_evolution:
                print()
                print("Running memory self-evolution DAG scenario...", flush=True)
                run_memory_evolution_scenario(
                    script_dir=script_dir,
                    max_wait=args.max_wait,
                    max_idle_secs=args.max_idle_secs,
                    username=args.username,
                    dataset_path=Path(args.evolution_dataset).expanduser().resolve(),
                    scenario_id=args.evolution_scenario.strip(),
                    max_parallel=args.evolution_max_parallel,
                    output_json=Path(args.evolution_output_json).expanduser().resolve(),
                    output_markdown=Path(args.evolution_output_markdown).expanduser().resolve(),
                )
        if args.suite == "full" and not args.skip_rust:
            print()
            print("Running memory Rust regressions...", flush=True)
            run_rust_memory_regressions()
        if args.with_valkey:
            print()
            print("Running optional Valkey memory continuity regression...", flush=True)
            valkey_prefix = args.valkey_prefix.strip() or default_valkey_prefix("memory-suite")
            run_valkey_cross_instance_regression(args.valkey_url, valkey_prefix)
        print()
        print("Memory suite passed.", flush=True)
        return 0
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
