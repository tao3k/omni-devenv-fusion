#!/usr/bin/env python3
"""
Valkey live-test suite runner for omni-agent Telegram webhook tests.

This script centralizes the logic behind:
  - test-omni-agent-valkey-stress.sh
  - test-omni-agent-valkey-session-gate.sh
  - test-omni-agent-valkey-session-context.sh
  - test-omni-agent-valkey-multi-http.sh
  - test-omni-agent-valkey-multi-process.sh
  - test-omni-agent-valkey-full.sh
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

DEFAULT_VALKEY_URL = "redis://127.0.0.1:6379/0"


def default_valkey_prefix(suite: str) -> str:
    safe_suite = suite.strip().lower() or "suite"
    return f"omni-agent:session:valkey-suite:{safe_suite}:{os.getpid()}:{int(time.time() * 1000)}"


@dataclass(frozen=True)
class SuiteSpec:
    name: str
    title: str
    cargo_args: tuple[str, ...]


SPECS: dict[str, SuiteSpec] = {
    "stress": SuiteSpec(
        name="stress",
        title="Running live Valkey stress tests (ignored suite)...",
        cargo_args=(
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "channels_webhook_stress",
            "--",
            "--ignored",
            "--nocapture",
        ),
    ),
    "session-gate": SuiteSpec(
        name="session-gate",
        title="Running live Valkey distributed session gate tests (ignored suite)...",
        cargo_args=(
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "telegram_session_gate",
            "--",
            "--ignored",
            "--nocapture",
        ),
    ),
    "session-context": SuiteSpec(
        name="session-context",
        title="Running live Valkey cross-instance session-context restore test...",
        cargo_args=(
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "agent_session_context",
            "reset_resume_bounded_restores_across_agent_instances_with_valkey",
            "--",
            "--ignored",
            "--nocapture",
        ),
    ),
    "multi-http": SuiteSpec(
        name="multi-http",
        title="Running focused multi-http dedup test...",
        cargo_args=(
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "channels_webhook_stress",
            "webhook_live_valkey_duplicate_update_id_across_two_http_servers_enqueues_once",
            "--",
            "--ignored",
            "--nocapture",
        ),
    ),
    "multi-process": SuiteSpec(
        name="multi-process",
        title="Running focused multi-process dedup test...",
        cargo_args=(
            "cargo",
            "test",
            "-p",
            "omni-agent",
            "--test",
            "channels_webhook_process",
            "webhook_live_valkey_duplicate_update_id_across_two_processes_enqueues_once",
            "--",
            "--ignored",
            "--nocapture",
        ),
    ),
}

FULL_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("stress", "Running stress suite..."),
    ("session-gate", "Running distributed session gate focused check..."),
    ("session-context", "Running cross-instance session-context focused check..."),
    ("multi-http", "Running dual-HTTP focused check..."),
    ("multi-process", "Running dual-process focused check..."),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run omni-agent Valkey live-test suite(s).")
    parser.add_argument(
        "--suite",
        choices=(
            "stress",
            "session-gate",
            "session-context",
            "multi-http",
            "multi-process",
            "full",
        ),
        required=True,
        help="Suite to run.",
    )
    parser.add_argument(
        "valkey_url",
        nargs="?",
        default=DEFAULT_VALKEY_URL,
        help=f"Valkey URL (default: {DEFAULT_VALKEY_URL}).",
    )
    parser.add_argument(
        "--valkey-prefix",
        default="",
        help=(
            "Optional explicit Valkey key prefix for test isolation. "
            "Default: an auto-generated per-run prefix."
        ),
    )
    return parser.parse_args()


def ensure_valkey_cli() -> None:
    if shutil.which("valkey-cli") is None:
        raise RuntimeError("valkey-cli not found in PATH.")


def check_valkey_connectivity(valkey_url: str) -> None:
    print(f"Checking Valkey connectivity at {valkey_url}...", flush=True)
    subprocess.run(
        ["valkey-cli", "-u", valkey_url, "ping"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_suite(spec: SuiteSpec, valkey_url: str, valkey_prefix: str) -> None:
    print(spec.title, flush=True)
    env = os.environ.copy()
    env["VALKEY_URL"] = valkey_url
    env["OMNI_AGENT_SESSION_VALKEY_PREFIX"] = valkey_prefix
    env["OMNI_AGENT_MEMORY_VALKEY_KEY_PREFIX"] = f"{valkey_prefix}:memory"
    subprocess.run(spec.cargo_args, check=True, env=env)


def run_full(valkey_url: str, valkey_prefix: str) -> None:
    print("Running full Valkey webhook verification suite...", flush=True)
    print(f"Target Valkey: {valkey_url}", flush=True)
    print(f"Valkey isolation prefix: {valkey_prefix}", flush=True)
    print(flush=True)
    for idx, (key, description) in enumerate(FULL_SEQUENCE, start=1):
        print(f"[{idx}/{len(FULL_SEQUENCE)}] {description}", flush=True)
        run_suite(SPECS[key], valkey_url, valkey_prefix)
        print(flush=True)
    print("Full Valkey webhook verification suite passed.", flush=True)


def main() -> int:
    args = parse_args()
    valkey_prefix = args.valkey_prefix.strip() or default_valkey_prefix(args.suite)
    try:
        ensure_valkey_cli()
        check_valkey_connectivity(args.valkey_url)
        if args.suite == "full":
            run_full(args.valkey_url, valkey_prefix)
            return 0
        print(f"Valkey isolation prefix: {valkey_prefix}", flush=True)
        run_suite(SPECS[args.suite], args.valkey_url, valkey_prefix)
        return 0
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
